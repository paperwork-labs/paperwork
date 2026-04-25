---
owner: infra-ops
last_reviewed: 2026-04-23
doc_kind: architecture
domain: infra
status: active
---
# Paperwork Labs — Infra Architecture

**Status**: Adopted 2026-04-23. Supersedes per-product dev compose files.

Companion docs: `docs/INFRA_PHILOSOPHY.md` (Tier-1 vs Tier-2, Render vs
Hetzner), `docs/ORCHESTRATION_PHILOSOPHY.md` (Celery vs Airflow/Dagster),
`docs/DATA_PHILOSOPHY.md` (medallion + five iron laws).

---

## TL;DR — the rules

1. **One dev stack.** A single `docker compose -f infra/compose.dev.yaml up`
   boots every product — postgres, redis, all backends, all frontends. No
   per-product dev compose.
2. **One postgres, one redis.** Each product gets its own logical database
   (`axiomfolio_dev`, `brain_dev`, `filefree_dev`, `launchfree_dev`) on a
   single `postgres:17-alpine` instance. Each product gets its own redis
   logical DB index (`/0..3`).
3. **Opt-in extras are profiles.** Interactive Brokers gateway, Cloudflare
   tunnel, Celery Flower — all live behind `docker compose --profile`
   flags and in `infra/<product>/compose.profiles.yaml` overlays.
4. **Per-product infra lives under `infra/<product>/`.** Observability
   configs, env templates, profile overlays — everything that is
   product-specific but dev-infra-shaped.
5. **Render deploys are per-product `render.yaml`.** Each backend sets
   `rootDir: apis/<product>`; each frontend sets `rootDir: apps/<product>`.
   Dev compose and prod Render are independent orchestrations of the
   same monorepo.

---

## Directory layout

```
infra/
├── compose.dev.yaml             # THE unified dev compose
├── env.dev.defaults             # shared non-secret dev env (vault-free)
├── init-test-db.sh              # creates *_dev and *_test DBs on postgres boot
├── axiomfolio/
│   ├── README.md                # product-scoped notes
│   ├── compose.profiles.yaml    # ib-gateway, cloudflared, flower (opt-in)
│   └── env.examples/            # env.dev.example, env.prod.example, env.test.example
├── gcp/                         # cross-product: GCP service account keys, runbooks
├── hetzner/                     # cross-product: Hetzner host configs
└── git-hooks/                   # cross-product: shared git hooks
```

Each product that needs dev-only integrations (brokers, tunnels, external
APIs) gets its own `infra/<product>/` folder following the same pattern.

---

## The single dev compose (`infra/compose.dev.yaml`)

### Shared services (always up)

| Service    | Port host:container | Purpose                                    |
| ---------- | ------------------- | ------------------------------------------ |
| `portal`   | 3000:80             | dev portal — <http://localhost:3000>        |
| `postgres` | 5433:5432           | postgres 17-alpine, all product DBs        |
| `redis`    | 6380:6379           | redis 7-alpine, logical DBs `/0..3`        |

The **portal** is a static landing page (`infra/portal/index.html`,
served by `nginx:alpine`) that links to every frontend, API `/docs`,
ops tool, and philosophy doc. It's the "where is everything?" map —
open <http://localhost:3000> any time the stack is up. Edits to the
HTML hot-reload (no rebuild needed); structural changes go via
`docker compose restart portal`.

**Databases (auto-created by `init-test-db.sh`):**

| DB                 | Owner       | Purpose                    |
| ------------------ | ----------- | -------------------------- |
| `filefree_dev`     | `paperwork` | FileFree backend           |
| `filefree_test`    | `paperwork` | FileFree pytest            |
| `launchfree_dev`   | `paperwork` | LaunchFree backend         |
| `launchfree_test`  | `paperwork` | LaunchFree pytest          |
| `brain_dev`        | `paperwork` | Brain backend              |
| `brain_test`       | `paperwork` | Brain pytest               |
| `axiomfolio_dev`   | `paperwork` | AxiomFolio backend         |
| `axiomfolio_test`  | `paperwork` | AxiomFolio pytest          |

All products share the `paperwork` postgres role (owner of all DBs).
This is dev-only; production Render deploys provision per-service
managed databases with scoped roles. The role was renamed from
`filefree` to `paperwork` on 2026-04-24 — if you have a pre-existing
`pgdata` volume, wipe it (see "Upgrading an existing dev environment"
below; the same `down -v` resets both the pg17 bump and the role).

Dev connection string (inside a container):

```
postgresql://paperwork:paperwork_dev@postgres:5432/<product>_dev
```

**Redis logical DBs:**

| Index | Product    |
| ----- | ---------- |
| `/0`  | filefree   |
| `/1`  | launchfree |
| `/2`  | brain      |
| `/3`  | axiomfolio |

### Always-up backends

| Service         | Port | Product     | Entry                                 |
| --------------- | ---- | ----------- | ------------------------------------- |
| `api-filefree`  | 8001 | filefree    | `uvicorn app.main:app`                |
| `api-launchfree`| 8002 | launchfree  | `uvicorn app.main:app`                |
| `api-brain`     | 8003 | brain       | `uvicorn app.main:app`                |
| `api-axiomfolio`| 8004 | axiomfolio  | `uvicorn app.api.main:app`            |

### Axiomfolio worker stack (always up when axiomfolio backend is up)

Dev compose mirrors Render exactly: same services, same queue routing,
same concurrency. Only instance sizes differ (dev shares your laptop;
Render pins Standard 2 GiB per worker).

| Service                          | Queues                             | Concurrency | Matches Render service       |
| -------------------------------- | ---------------------------------- | ----------- | ---------------------------- |
| `celery-axiomfolio-worker`       | `celery`, `account_sync`, `orders` | 2           | `axiomfolio-worker`          |
| `celery-axiomfolio-worker-heavy` | `heavy`                            | 1           | `axiomfolio-worker-heavy`    |
| `celery-axiomfolio-beat`         | n/a (scheduler)                    | n/a         | (runs inside fast worker in prod via `--beat`; split for dev) |

Other products (filefree, brain, launchfree) can add their own celery
workers when they need them; today only axiomfolio has scheduled tasks.

### Always-up frontends

| Service       | Port | Product    |
| ------------- | ---- | ---------- |
| `web-filefree`| 3001 | filefree   |
| `web-launchfree`| 3002 | launchfree |
| `web-trinkets`| 3003 | trinkets   |
| `web-studio`  | 3004 | studio     |
| `web-distill` | 3005 | distill    |
| `web-axiomfolio`| 3006 | axiomfolio | **(phase 2 — Vite Dockerfile.dev pending; run `pnpm dev:axiomfolio` host-side today)** |

---

## Opt-in profiles (`infra/<product>/compose.profiles.yaml`)

Profile overlays are mounted via `-f`:

```bash
# Default stack (no brokers, no tunnel, no flower):
docker compose -f infra/compose.dev.yaml up

# With Interactive Brokers gateway:
docker compose \
  -f infra/compose.dev.yaml \
  -f infra/axiomfolio/compose.profiles.yaml \
  --profile ibkr up

# With Cloudflare tunnel (for OAuth testing against dev):
docker compose \
  -f infra/compose.dev.yaml \
  -f infra/axiomfolio/compose.profiles.yaml \
  --profile tunnel up

# With Celery Flower UI:
docker compose \
  -f infra/compose.dev.yaml \
  -f infra/axiomfolio/compose.profiles.yaml \
  --profile ops up
```

Profiles documented per product:

### Axiomfolio profiles (`infra/axiomfolio/compose.profiles.yaml`)

| Profile  | Service       | Purpose                                  |
| -------- | ------------- | ---------------------------------------- |
| `ibkr`   | `ib-gateway`  | Interactive Brokers gateway (live/paper) |
| `tunnel` | `cloudflared` | Cloudflare tunnel for OAuth dev testing  |
| `ops`    | `flower`      | Celery Flower UI (task monitor)          |

---

## Env management

### Precedence
1. `infra/env.dev.defaults` — tracked, non-secret, shared across products
2. `.env.secrets` — repo-root, gitignored, synced from Studio Vault via
   `./scripts/sync-secrets.sh`
3. Per-service `environment:` block in compose — product-specific overrides

### Product env templates

Each product documents its required env vars via templates in
`infra/<product>/env.examples/`. These are **documentation only** — the
compose file is the executable source of truth. Templates exist so a
new contributor can see "what env vars does this product need?" at a
glance.

---

## Postgres version alignment (pg17)

Root postgres was `15-alpine`. Bumped to `17-alpine` to get closer to
AxiomFolio's production Render DB (pg18, 7.3 GB of live data). FileFree
/ LaunchFree / Brain have no version-specific features and work
unchanged on pg17.

**Why not pg18?** We tried. `postgres:18-alpine` (released Oct 2025)
silently exited(1) on GitHub Actions runners — the container reported
"Started" but crashed before healthcheck passed, breaking CI across the
monorepo. pg17-alpine is what Render, Supabase, Neon, and every managed
provider ship today; revisit pg18 once the alpine image has baked.

Local dev DBs are re-init-able (`docker compose down -v && docker compose up`);
no prod risk. Production Render databases are managed per-service and
unaffected by this bump.

### Upgrading an existing dev environment

If you have an existing `pgdata` volume from before this change, the pg17
container will refuse to start ("incompatible data directory version").
Wipe the volume to re-initialize:

```bash
docker compose -f infra/compose.dev.yaml down -v
docker compose -f infra/compose.dev.yaml up -d postgres
# init-test-db.sh creates all *_dev and *_test DBs on first boot.
```

This destroys local dev data only; production Render DBs are untouched.
Re-run migrations per product (`make migrate-up` from each `apis/*/`).

---

## Migration sequence (2026-04-23)

Performed as part of PR #80 (AxiomFolio monorepo absorption):

1. **Shared stack bumped to pg17.** Existing dev DBs re-initialized.
2. **AxiomFolio services added to root compose.** `api-axiomfolio`,
   `celery-axiomfolio-worker`, `celery-axiomfolio-beat` now live in
   `infra/compose.dev.yaml`.
3. **Axiomfolio-specific compose files deleted.**
   `apis/axiomfolio/infra/compose.dev.yaml` and `compose.test.yaml` are
   gone — superseded by the root compose.
4. **Axiomfolio profile overlay added.** `infra/axiomfolio/compose.profiles.yaml`
   holds ib-gateway, cloudflared, flower.
5. **Observability is in-app (OpenTelemetry).** Axiomfolio uses OTel
   via `app/observability/tracing.py` — FastAPI, SQLAlchemy, Celery,
   httpx, and Redis auto-instrumentation. Vendor-neutral: set
   `OTEL_EXPORTER_OTLP_ENDPOINT` to ship spans to Grafana Tempo /
   Honeycomb / Jaeger. Unset = no-op (dev default). New Relic was
   previously bundled but never activated; removed 2026-04-24.
6. **Axiomfolio Makefile slimmed.** Targets that wrapped Docker Compose
   now call the root compose via relative paths; frontend-*, ladle-*,
   and db-* targets delegate to `pnpm` workspace commands.

### Deferred to phase 2

- **`web-axiomfolio` in root compose.** Axiomfolio frontend is Vite + React 19,
  not Next.js. Needs an `apps/axiomfolio/Dockerfile.dev` designed for Vite's
  dev server + HMR. For now, run `pnpm dev:axiomfolio` directly from host —
  which is also how studio, distill, filefree, launchfree, and trinkets
  run day-to-day, so it's not an outlier pattern.
- **Unified test compose.** AxiomFolio tests historically ran in a dedicated
  `compose.test.yaml` container. Migrating to `pytest` against shared
  postgres/redis with `axiomfolio_test` DB requires a conftest audit.
  Non-blocking for dev work.
- **Per-product celery workers for brain/filefree/launchfree.** Only
  axiomfolio has scheduled tasks today. Other products add workers on
  demand.

---

## Strategic roadmap (not this PR)

### Axiomfolio frontend → Next.js

Every other paperwork app (studio, distill, filefree, launchfree,
trinkets) is Next.js. Axiomfolio is the lone Vite + React 19 holdout,
carried over from its pre-monorepo life. Next.js brings:

- **SSR / RSC** for data-heavy authenticated dashboards (fetch holdings
  server-side, stream to client).
- **Shared auth middleware** with the rest of paperwork (no per-app
  token handling).
- **Shared UI patterns** (Radix UI + Tailwind + shadcn/ui is already the
  house kit; axiomfolio uses the same; the diff is routing + data
  fetching, not components).
- **SEO-friendly public surface** (landing, pricing, docs) without a
  separate marketing site.

**Cost**: 1–2 weeks of focused frontend work to port routing, data
fetching, proxy config, and the Vite-specific env vars. Zero user-
visible value in the short term.

**When**: After (a) axiomfolio is stable on monorepo Render, and (b)
Medallion Phase 0.C is shipped. Target: Q3. Tracked in `docs/axiomfolio/`
as a separate plan.

Until then, the Vite dev server runs host-side (`pnpm dev:axiomfolio`);
the static build is deployed to Render via `apis/axiomfolio/render.yaml`
→ `axiomfolio-frontend` service.

### Python tooling consolidation → ruff

The monorepo root `pyproject.toml` defines a full ruff + mypy + pytest
config. AxiomFolio still carries its own `pyproject.toml` (black + isort)
and `.flake8`. These should be deleted and axiomfolio should inherit
root ruff.

**Blocker**: format drift. Axiomfolio has ~500+ Python files formatted
with black (line-length=88); root ruff targets line-length=100. A
forced ruff pass would produce a massive diff that drowns review
signal. Solution: one dedicated PR that runs `ruff format .` on
axiomfolio, merges with a "format-only" commit trailer, and drops the
axiomfolio pyproject + .flake8 in the same PR.

**When**: Any calm week. Non-urgent.

### Medallion tooling → cross-product

`apis/axiomfolio/scripts/medallion/` (check_imports, check_sql,
tag_files, etc.) is axiomfolio-specific today but the *architecture*
is meant to apply to brain, filefree, launchfree as well. When the
second product starts using medallion layers, lift the scripts to
`scripts/medallion/` at repo root and make them parametric over
`--app-dir`.

**When**: When the second product adopts medallion (probably brain
after Wave 0 ships on axiomfolio).

### Secrets namespacing convention

`.env.secrets` at repo root is shared across all products. Axiomfolio
loads `IBKR_USERNAME`, `TASTYTRADE_CLIENT_ID`, etc. without product
prefixes. This is fine operationally (each container only reads what
it uses) but makes the file hard to audit.

**Proposed convention**: `AXIOMFOLIO_*` prefix for axiomfolio-only
secrets; unprefixed for cross-product (e.g. `OPENAI_API_KEY` if
multiple products use it).

**When**: When a secret collision happens, or when we onboard a
second developer who needs to reason about the vault.

### Hetzner tier-2 for axiomfolio heavy batch jobs

Per `docs/INFRA_PHILOSOPHY.md`, nightly historical backtests and
market-data warming (2am–5am, failure-tolerant, compute-heavy) are a
better fit for Hetzner than paying Render Pro. The dev compose already
supports this pattern via queue routing — `heavy` queue can be pinned
to a Hetzner-hosted celery worker by changing `CELERY_BROKER_URL` to
the Hetzner redis.

**When**: When axiomfolio's Render costs start biting (currently ~$108/mo
on Standard plans; Hetzner worker would be ~$15/mo for equivalent CPU).

---

## FAQ

### Why one postgres instead of per-product postgres containers?

- **Disk.** One postgres instance uses one shared `pgdata` volume. Per-product
  instances multiply the overhead by N products.
- **Memory.** Postgres idle memory is ~200 MB per instance. Running four
  postgres instances on a dev laptop is ~800 MB wasted.
- **Operational simplicity.** One connection string pattern, one backup/restore
  flow, one upgrade path.
- **Isolation is still perfect.** Separate DBs with separate owners is the
  standard postgres multi-tenancy pattern. Prod Render is per-service
  managed DBs, independent of dev.

### Why keep `infra/axiomfolio/` at all if there's one shared compose?

- **Product-specific integrations exist.** IB Gateway, Cloudflare tunnel,
  Flower — these are axiomfolio-specific and don't belong in the shared
  compose.
- **Env templates need scoping.** `infra/env.dev.defaults` covers the shared
  stack; `infra/axiomfolio/env.examples/env.dev.example` documents
  axiomfolio-specific required vars (broker OAuth, flex tokens, etc.)
  without cluttering the shared defaults.
- **Pattern extends cleanly.** When Brain grows its own optional services
  (e.g., a dedicated MCP server container), they live at
  `infra/brain/compose.profiles.yaml` following the same pattern.

### Why not keep axiomfolio's compose.dev.yaml and just point the Makefile at the new location?

That was the original path of least resistance, but it leaves two dev
stacks (one for axiomfolio, one for everything else), two postgres
instances, two redis instances, and every contributor has to remember
which compose to run. The whole point of a monorepo is one dev
experience. One stack, boot it, go.

### What about `compose.test.yaml`?

AxiomFolio's test compose spun up a parallel postgres/redis for pytest
isolation. In the new architecture, tests run against the same postgres
using the `*_test` database (already the pattern for filefree/brain).
The test compose file is retained in git history (reachable via `git log
-- infra/axiomfolio/compose.test.yaml`) for reference, but is not used
by the new `make test` path.
