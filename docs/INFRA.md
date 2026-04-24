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
   single `postgres:18-alpine` instance. Each product gets its own redis
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
│   ├── env.examples/            # env.dev.example, env.prod.example, env.test.example
│   └── observability/
│       └── newrelic.ini         # NewRelic app config for axiomfolio containers
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
| `postgres` | 5433:5432           | postgres 18-alpine, all product DBs        |
| `redis`    | 6380:6379           | redis 7-alpine, logical DBs `/0..3`        |

**Databases (auto-created by `init-test-db.sh`):**

| DB                 | Owner      | Purpose                    |
| ------------------ | ---------- | -------------------------- |
| `filefree_dev`     | `filefree` | FileFree backend           |
| `filefree_test`    | `filefree` | FileFree pytest            |
| `launchfree_dev`   | `filefree` | LaunchFree backend         |
| `launchfree_test`  | `filefree` | LaunchFree pytest          |
| `brain_dev`        | `filefree` | Brain backend              |
| `brain_test`       | `filefree` | Brain pytest               |
| `axiomfolio_dev`   | `filefree` | AxiomFolio backend         |
| `axiomfolio_test`  | `filefree` | AxiomFolio pytest          |

All products share the `filefree` postgres role (owner of all DBs). This
is dev-only; production Render deploys provision per-service managed
databases with scoped roles.

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

| Service                    | Purpose                                         |
| -------------------------- | ----------------------------------------------- |
| `celery-axiomfolio-worker` | celery worker (queues: celery, account_sync, orders) |
| `celery-axiomfolio-beat`   | celery beat scheduler                           |

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

## Postgres version alignment (pg18)

Root postgres was `15-alpine`. Bumped to `18-alpine` to align with
AxiomFolio's production Render DB (which has 7.3 GB of live data on
pg18). FileFree / LaunchFree / Brain have no pg15-specific features and
work unchanged on pg18.

Local dev DBs are re-init-able (`docker compose down -v && docker compose up`);
no prod risk. Production Render databases are managed per-service and
unaffected by this bump.

---

## Migration sequence (2026-04-23)

Performed as part of PR #80 (AxiomFolio monorepo absorption):

1. **Shared stack bumped to pg18.** Existing dev DBs re-initialized.
2. **AxiomFolio services added to root compose.** `api-axiomfolio`,
   `celery-axiomfolio-worker`, `celery-axiomfolio-beat` now live in
   `infra/compose.dev.yaml`.
3. **Axiomfolio-specific compose files deleted.**
   `apis/axiomfolio/infra/compose.dev.yaml` and `compose.test.yaml` are
   gone — superseded by the root compose.
4. **Axiomfolio profile overlay added.** `infra/axiomfolio/compose.profiles.yaml`
   holds ib-gateway, cloudflared, flower.
5. **Observability stays product-scoped.** `infra/axiomfolio/observability/newrelic.ini`
   is mounted into the axiomfolio containers at `/opt/observability/` and
   referenced via `NEW_RELIC_CONFIG_FILE=/opt/observability/newrelic.ini`.
6. **Axiomfolio Makefile slimmed.** Targets that wrapped Docker Compose
   now call the root compose via relative paths; frontend-*, ladle-*,
   and db-* targets delegate to `pnpm` workspace commands.

### Deferred to phase 2

- **`web-axiomfolio` in root compose.** Axiomfolio frontend is Vite + React 19,
  not Next.js. Needs an `apps/axiomfolio/Dockerfile.dev` designed for Vite's
  dev server + HMR. For now, run `pnpm dev:axiomfolio` directly from host.
- **Unified test compose.** AxiomFolio tests historically ran in a dedicated
  `compose.test.yaml` container. Migrating to `pytest` against shared
  postgres/redis with `axiomfolio_test` DB requires a conftest audit.
  Non-blocking for dev work.
- **Per-product celery workers for brain/filefree/launchfree.** Only
  axiomfolio has scheduled tasks today. Other products add workers on
  demand.

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
  NewRelic app config, Flower — these are axiomfolio-specific and don't
  belong in the shared compose.
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
