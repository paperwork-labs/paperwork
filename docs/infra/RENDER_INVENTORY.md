---
owner: infra-ops
last_reviewed: 2026-04-26
doc_kind: reference
domain: infra
status: active
---
# Render inventory — 2026-04-25

**Owner**: `infra-ops` persona (Track A).
**Source of truth**: Render MCP (`list_services`, `list_postgres_instances`, `list_key_value`) against workspace `tea-d6uflspj16oc73ft6gj0` (Paperwork team, `billing@paperworklabs.com`).

This supersedes [docs/axiomfolio/RENDER_INVENTORY.md](../axiomfolio/RENDER_INVENTORY.md), which was authored before the monorepo consolidation and is now stale.

## Account consolidation status

- **Accounts found**: 1 (`Paperwork` team at `tea-d6uflspj16oc73ft6gj0`). ✅
- **Suspended services**: 0. ✅
- **Old `sankalp404` account**: archived; no live services migrated. ✅

The old account migration is effectively done. What remains is **repo-pointer drift** — see the critical finding below.

## Live services

| Service | Type | ID | Repo pointer | Root dir | Dockerfile / runtime | Plan | Status |
|---|---|---|---|---|---|---|---|
| `brain-api` | web | `srv-d74f3cmuk2gs73a4013g` | `paperwork-labs/paperwork` ✅ | — | `apis/brain/Dockerfile` (docker) | starter | running |
| `filefree-api` | web | `srv-d70o3jvkijhs73a0ee7g` | `paperwork-labs/paperwork` ✅ | — | python (`cd apis/filefree && …`) | starter | running |
| `axiomfolio-api` | web | `srv-d7lg0o77f7vs73b2k7m0` | **`paperwork-labs/axiomfolio` ⚠️** | — | `./Dockerfile.backend` (docker) | standard | running |
| `axiomfolio-worker` | worker | `srv-d7lg0o77f7vs73b2k7lg` | **`paperwork-labs/axiomfolio` ⚠️** | — | `./Dockerfile.backend` (docker) | standard | running |
| `axiomfolio-worker-heavy` | worker | `srv-d7lg0o77f7vs73b2k7kg` | **`paperwork-labs/axiomfolio` ⚠️** | — | `./Dockerfile.backend` (docker) | standard | running |
| ~~`axiomfolio-frontend`~~ | — | `srv-d7lg0dv7f7vs73b2k1u0` | **`paperwork-labs/axiomfolio` ⚠️** | — | *AxiomFolio frontend served from Vercel (`apps/axiomfolio`); see [PORT_INVENTORY_2026Q2.md](../axiomfolio/plans/PORT_INVENTORY_2026Q2.md) for migration* | — | **delete stale service in dashboard** |

Data stores:

| Name | Type | ID | Plan | Status |
|---|---|---|---|---|
| `axiomfolio-db` | postgres 18 | `dpg-d7lg0e77f7vs73b2k220-a` | basic_1gb (15 GiB) | available |
| `axiomfolio-redis` | keyvalue (Redis 8.1.4) | `red-d7lg0dv7f7vs73b2k1t0` | starter | available |

## Critical findings

### F-1 — Three `axiomfolio-*` API/worker services still point to the old standalone repo ⚠️

The three backend services (`axiomfolio-api`, `axiomfolio-worker`, `axiomfolio-worker-heavy`) still have their `repo` field set to **`https://github.com/paperwork-labs/axiomfolio`**, not the monorepo. (**Update 2026-04-27:** `axiomfolio-frontend` was retired from the root blueprint; customer UI is Next.js on Vercel.)

This means:

- Code changes to `apis/axiomfolio/` in the monorepo **do not deploy** to these services.
- They're deploying off a repo that should be archived.
- Their Dockerfile path is `./Dockerfile.backend` (the old standalone layout) — the monorepo has `apis/axiomfolio/Dockerfile` instead.

**The root [`render.yaml`](../../render.yaml) blueprint is correct.** It's just not applied. The services were created against the old repo and never repointed.

**Fix**: repoint each of the **three** remaining services at `paperwork-labs/paperwork` via the Render dashboard, then re-sync from the root blueprint. See [RENDER_REPOINT.md](RENDER_REPOINT.md). If `axiomfolio-frontend` still appears in the dashboard, delete it (stale).

### F-2 — `launchfree-api` deferred (entry commented out in `render.yaml`) ✅

**Status**: closed (deferred) — 2026-04-25 (PR #144).

The root [`render.yaml`](../../render.yaml) used to declare a
`launchfree-api` service backed by `apis/launchfree/` (FastAPI app,
Alembic migrations, state-filing code). After the consolidated-Blueprint
sync (F-1) made every `render.yaml` entry forced into provisioning on
the next sync, we faced a binary: pay $7/mo for a Render Starter that
serves zero traffic, or remove the entry.

The frontend at `apps/launchfree/src/lib/dashboard-formations.ts:118`
still has a `// TODO: session user id → GET /api/v1/formations` and
renders `MOCK_FORMATIONS`. So provisioning today gives an empty,
unused backend that costs money.

**Decision (PR #144)**: comment out (not delete) the `launchfree-api`
block in `render.yaml`, with the rationale and re-enable workflow
documented inline. The spec is preserved as a comment so re-enabling is
a 10-line revert PR plus one Sync Blueprint click. F-2 reopens if the
LaunchFree frontend is wired to a live API and the service still isn't
provisioned.

### F-3 — Env var naming: `VERCEL_API_TOKEN` (consolidated)

**Canonical name**: `VERCEL_API_TOKEN` everywhere — root `render.yaml` brain-api block, Studio (`apps/studio/src/lib/command-center.ts` and related), GitHub Actions (`vercel-promote-on-merge.yaml`), and Brain settings (`apis/brain/app/config.py` field `VERCEL_API_TOKEN`). Brain still accepts a legacy `VERCEL_TOKEN` env key via pydantic `AliasChoices` until the operator removes it from the Render dashboard after cutover.

### F-4 — Blueprint contents disagree with live services

The root `render.yaml` declares `brain-api` at `plan: starter` with
`numInstances: 1`, `runtime: docker` — matches live.

The four `axiomfolio-*` blueprint entries lived at
`apis/axiomfolio/render.yaml`, which Render's "New Blueprint" preview
won't show alongside the root file. Resolved on 2026-04-25 by
**consolidating** the AxiomFolio blocks into the root `render.yaml`
([commit](../../render.yaml)) and reducing
`apis/axiomfolio/render.yaml` to a stub pointer comment.

**Track F4 — `axiomfolio-frontend` decommission (complete 2026-04-27):**
the legacy Render static site block was **removed entirely** from root
`render.yaml`. Customer UI is Next.js on Vercel (`apps/axiomfolio`); see
[PORT_INVENTORY_2026Q2.md](../axiomfolio/plans/PORT_INVENTORY_2026Q2.md).
The live `axiomfolio-frontend` service (if still present) is stale — delete
it in the Render dashboard after [Track I1 / Blueprint repoint](RENDER_REPOINT.md)
when safe.

**Remaining action (Path B in [RENDER_REPOINT.md](RENDER_REPOINT.md)):**
the operator runs the Blueprint Sync once. After that, blueprint and
live config track each other automatically.

### F-5 — `brain-api` missing `GITHUB_WEBHOOK_SECRET`

Week 1 Track B wires a GitHub webhook to Brain. Neither `render.yaml` nor the live service declares `GITHUB_WEBHOOK_SECRET`. Add it (with `sync: false`) before Track B ships.

### F-6 — `brain-api` Docker Build Context Directory drifted from blueprint, every push to `main` failed ⚠️ (resolved 2026-04-25)

Live `brain-api` service config (Render API):

```json
"envSpecificDetails": {
  "dockerCommand": "",
  "dockerContext": "apis/brain",        // ← stale; blueprint says "."
  "dockerfilePath": "apis/brain/Dockerfile"
}
```

But [`apis/brain/Dockerfile`](../../apis/brain/Dockerfile) does:

```dockerfile
COPY apis/brain/requirements.txt .
COPY apis/brain/ /app/
COPY .cursor/rules/ /app/cursor-rules/   # ← monorepo-root path
```

With `dockerContext: apis/brain`, those paths resolved under
`apis/brain/apis/brain/...` (does not exist), so every build since
the monorepo cutover failed:

```
#16 ERROR: failed to compute cache key: "/apis/brain/requirements.txt": not found
#15 ERROR: "/apis/brain": not found
#14 ERROR: "/.cursor/rules": not found
```

PR #141's Render auto-deploy `dep-d7m4kgf41pts738qcpeg` failed at
2026-04-25T05:00Z. Brain kept serving the PR #140 image.

The blueprint was already correct (`render.yaml` declares
`dockerContext: .`); the live service was created before the
monorepo move and never resynced.

**Field-name correction (important for future runbooks):** Render's
Settings UI exposes **two** separate fields:

| Render field | Blueprint maps to | What it does |
| --- | --- | --- |
| **Root Directory** | `rootDir:` | Where commands run (e.g. `buildCommand`, `preDeployCommand`). |
| **Docker Build Context Directory** | `dockerContext:` | Path passed as `docker build <context>`. |

The drifted value lived in **Docker Build Context Directory**, not
Root Directory (Root Directory was already empty). Earlier drafts of
the runbook called out the wrong field; corrected on 2026-04-25.

**Why we can't COPY the .cursor/rules into apis/brain to dodge this:**
persona `.mdc` files live at `.cursor/rules/` at the monorepo root,
used by `app/services/agent.py` for cold-start persona instructions.
Pulling them in via `apis/brain/` is the wrong layering — agent
context belongs at repo root, not inside the API.

**Resolution:** operator cleared **Docker Build Context Directory**
on 2026-04-25; deploy `dep-d7m63jeffeas73bmkeeg` (PR #142 SHA
`f0255542`) went **live** at 06:49:55Z. Brain now serves the persona
platform + PR sweep + chain strategy code shipped in #141 + #142.

Runbook: [RENDER_REPOINT.md → Path A](RENDER_REPOINT.md#path-a-brain-api-docker-build-context-directory-fix-f-6).

## Definition of Done

- [x] Render MCP shows one account, zero suspended services.
- [x] Inventory (this doc) exists.
- [ ] F-1: AxiomFolio services repointed to monorepo via consolidated Blueprint Sync; old `paperwork-labs/axiomfolio` repo archived after 24h green.
- [x] F-2: `launchfree-api` decision — commented out in `render.yaml` (2026-04-25, PR #144); reopens if frontend wires to live API and service still isn't provisioned.
- [x] F-3: env var naming reconciled to `VERCEL_API_TOKEN` (code + blueprint; remove duplicate `VERCEL_TOKEN` in Render when safe).
- [x] F-4: single `render.yaml` is the source of truth; `apis/axiomfolio/render.yaml` reduced to a stub pointer; **`axiomfolio-frontend` removed from blueprint 2026-04-27 (Track F4)** — delete stale dashboard service post–I1.
- [ ] F-5: `GITHUB_WEBHOOK_SECRET` added to `brain-api` env (declared in blueprint with `sync: false`; operator must paste actual value).
- [x] F-6: `brain-api` Docker Build Context Directory cleared; latest `main` SHA `f0255542` is live (deploy `dep-d7m63jeffeas73bmkeeg`).
- [x] Studio `/admin/infrastructure` enumerates every Render service + Postgres + Key Value + every Vercel project from the APIs (live/build_failed/deploy state per row; no hardcoded service IDs). See `apps/studio/src/lib/infra-probes.ts` (Q2 Tech Debt Track I4).

## Verification commands

```bash
# From repo root:
# 1. Enumerate live services via Render MCP (agent: uses project-0-paperwork-render MCP)
# 2. Confirm every service's repo pointer:
curl -s -H "Authorization: Bearer $RENDER_API_KEY" "https://api.render.com/v1/services?limit=50" | \
  jq '.[] | {name: .service.name, repo: .service.repo}'

# 3. Health probes from outside Render (agent uses Brain):
for url in \
  https://brain-api-zo5t.onrender.com/health \
  https://filefree-api-5l6x.onrender.com/health \
  https://axiomfolio-api-02ei.onrender.com/health; do
  echo "=== $url ==="; curl -sS -m 10 "$url"; echo
done
```
