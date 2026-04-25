---
owner: infra-ops
last_reviewed: 2026-04-24
doc_kind: reference
domain: infra
status: active
---
# Render inventory — 2026-04-24

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

The root [`render.yaml`](../../render.yaml) defines a `launchfree-api` service (lines 41–66), but Render returns no service by that name. Either:
- The blueprint was never synced, or
- It was deleted in the dashboard and the yaml wasn't updated.

**Fix**: decide — either deploy (blueprint sync) or delete from `render.yaml` if launchfree's API isn't needed yet.

### F-3 — Env var naming drift: `VERCEL_API_TOKEN` vs `VERCEL_TOKEN`

- Root `render.yaml` brain-api block uses `VERCEL_TOKEN`.
- Studio reads `VERCEL_API_TOKEN` (`apps/studio/src/lib/command-center.ts`).
- These need to match or the Studio infra probe can't authenticate. Pick one; rename everywhere.

**Proposed canonical**: `VERCEL_API_TOKEN` (Studio already uses this; it's what the Vercel CLI and most examples use).

### F-4 — Blueprint contents disagree with live services

The root `render.yaml` declares `brain-api` at `plan: starter` with `numInstances: 1`, `runtime: docker` — which matches the live service. Good.

But the four `axiomfolio-*` blueprint entries at [apis/axiomfolio/render.yaml](../../apis/axiomfolio/render.yaml) are NOT what's live:
- Blueprint says `rootDir: apis/axiomfolio`, `dockerfilePath: ./Dockerfile`. Live says `rootDir: ""`, `dockerfilePath: ./Dockerfile.backend`.
- Blueprint declares `axiomfolio-redis` (keyvalue) and `axiomfolio-db` (postgres basic-1gb). Live has these but they were provisioned directly, not via Blueprint.

**Fix**: after F-1 repoints are done, sync the blueprint from the monorepo and let it take over.

### F-5 — `brain-api` missing `GITHUB_WEBHOOK_SECRET`

Week 1 Track B wires a GitHub webhook to Brain. Neither `render.yaml` nor the live service declares `GITHUB_WEBHOOK_SECRET`. Add it (with `sync: false`) before Track B ships.

## Definition of Done

- [x] Render MCP shows one account, zero suspended services.
- [x] Inventory (this doc) exists.
- [ ] F-1: four axiomfolio services repointed to monorepo; old `paperwork-labs/axiomfolio` repo archived.
- [ ] F-2: `launchfree-api` decision — deploy or remove.
- [ ] F-3: env var naming reconciled to `VERCEL_API_TOKEN`.
- [ ] F-4: both blueprints are what production actually uses.
- [ ] F-5: `GITHUB_WEBHOOK_SECRET` added to `brain-api`.
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
