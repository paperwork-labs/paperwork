---
owner: infra-ops
last_reviewed: 2026-04-25
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
| `axiomfolio-frontend` | static | `srv-d7lg0dv7f7vs73b2k1u0` | **`paperwork-labs/axiomfolio` ⚠️** | — | `cd frontend && npm ci && npm run build` | starter | running |

Data stores:

| Name | Type | ID | Plan | Status |
|---|---|---|---|---|
| `axiomfolio-db` | postgres 18 | `dpg-d7lg0e77f7vs73b2k220-a` | basic_1gb (15 GiB) | available |
| `axiomfolio-redis` | keyvalue (Redis 8.1.4) | `red-d7lg0dv7f7vs73b2k1t0` | starter | available |

## Critical findings

### F-1 — Four `axiomfolio-*` services still point to the old standalone repo ⚠️

All four axiomfolio services (`axiomfolio-api`, `axiomfolio-worker`, `axiomfolio-worker-heavy`, `axiomfolio-frontend`) have their `repo` field set to **`https://github.com/paperwork-labs/axiomfolio`**, not the monorepo. This means:

- Code changes to `apis/axiomfolio/` in the monorepo **do not deploy** to these services.
- They're deploying off a repo that should be archived.
- Their Dockerfile path is `./Dockerfile.backend` (the old standalone layout) — the monorepo has `apis/axiomfolio/Dockerfile` instead.
- The frontend service build command is `cd frontend && npm ci && npm run build` — but the monorepo expects `pnpm --filter=@paperwork-labs/axiomfolio build` with `rootDir: apps/axiomfolio`.

**The root `apis/axiomfolio/render.yaml` blueprint is correct.** It's just not applied. The services were created against the old repo and never repointed.

**Fix**: repoint each of the 4 services at `paperwork-labs/paperwork` via the Render dashboard, then re-sync from `apis/axiomfolio/render.yaml` as a Blueprint. See [RENDER_REPOINT.md](RENDER_REPOINT.md).

### F-2 — `launchfree-api` is defined in `render.yaml` but not deployed

The root [`render.yaml`](../../render.yaml) declares a `launchfree-api`
service backed by `apis/launchfree/` (FastAPI app, Alembic migrations,
state-filing code), but no service by that name is currently running
on Render — the Blueprint has never been synced for it.

**Decision (2026-04-25)**: keep the entry in `render.yaml`. LaunchFree
is a real product (frontend at `launchfree.ai`, backend code at
`apis/launchfree/`); the blueprint is the canonical "this is the
service we want when we run sync." A briefly-attempted PR #143 cleanup
removed the entry on the assumption that it was a stub — that was
incorrect, the entry is restored. F-2 closes when the operator either
(a) provisions the service via the Path B Blueprint Sync, or
(b) explicitly retires the LaunchFree backend product, in which case
this block can be dropped from `render.yaml`.

### F-3 — Env var naming drift: `VERCEL_API_TOKEN` vs `VERCEL_TOKEN`

- Root `render.yaml` brain-api block uses `VERCEL_TOKEN`.
- Studio reads `VERCEL_API_TOKEN` (`apps/studio/src/lib/command-center.ts`).
- These need to match or the Studio infra probe can't authenticate. Pick one; rename everywhere.

**Proposed canonical**: `VERCEL_API_TOKEN` (Studio already uses this; it's what the Vercel CLI and most examples use).

### F-4 — Blueprint contents disagree with live services

The root `render.yaml` declares `brain-api` at `plan: starter` with
`numInstances: 1`, `runtime: docker` — matches live.

The four `axiomfolio-*` blueprint entries lived at
`apis/axiomfolio/render.yaml`, which Render's "New Blueprint" preview
won't show alongside the root file. Resolved on 2026-04-25 by
**consolidating** the AxiomFolio blocks into the root `render.yaml`
([commit](../../render.yaml)) and reducing
`apis/axiomfolio/render.yaml` to a stub pointer comment.

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
- [ ] F-2: `launchfree-api` decision — entry restored to `render.yaml` (2026-04-25); closes when operator either provisions via Path B Blueprint Sync or formally retires the backend product.
- [ ] F-3: env var naming reconciled to `VERCEL_API_TOKEN`.
- [x] F-4: single `render.yaml` is the source of truth; `apis/axiomfolio/render.yaml` reduced to a stub pointer.
- [ ] F-5: `GITHUB_WEBHOOK_SECRET` added to `brain-api` env (declared in blueprint with `sync: false`; operator must paste actual value).
- [x] F-6: `brain-api` Docker Build Context Directory cleared; latest `main` SHA `f0255542` is live (deploy `dep-d7m63jeffeas73bmkeeg`).
- [ ] Studio `/admin/infrastructure` shows all six services green (currently only probes a subset).

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
