---
owner: infra-ops
last_reviewed: 2026-04-24
doc_kind: runbook
domain: infra
status: active
---
# Render repoint runbook — axiomfolio services

**Who runs this**: User (operator). Brain can't click dashboard buttons.
**Time**: ~15 minutes.
**Pre-req**: Read [RENDER_INVENTORY.md](RENDER_INVENTORY.md). Finding F-1 is the reason this doc exists.

## Context

Four Render services (`axiomfolio-api`, `axiomfolio-worker`, `axiomfolio-worker-heavy`, `axiomfolio-frontend`) still deploy from the **old standalone repo** `paperwork-labs/axiomfolio`. Since axiomfolio was merged into the monorepo `paperwork-labs/paperwork`, those four services have been deploying dead code. We need to repoint them at the monorepo, using `apis/axiomfolio/render.yaml` as the blueprint source.

## Before you start

1. Monorepo `main` is green (CI passing). Check: `gh pr list --state open` and `gh run list --branch main --limit 5`.
2. You have Render dashboard access at [dashboard.render.com](https://dashboard.render.com).
3. Brain is reachable at `https://brain-api-zo5t.onrender.com/health` (test: `curl -sS https://brain-api-zo5t.onrender.com/health`).

## Step 1 — Disconnect the old repo, connect the monorepo

For **each** of the four services, in the Render dashboard:

1. Open the service (direct links below):
   - [`axiomfolio-api`](https://dashboard.render.com/web/srv-d7lg0o77f7vs73b2k7m0)
   - [`axiomfolio-worker`](https://dashboard.render.com/worker/srv-d7lg0o77f7vs73b2k7lg)
   - [`axiomfolio-worker-heavy`](https://dashboard.render.com/worker/srv-d7lg0o77f7vs73b2k7kg)
   - [`axiomfolio-frontend`](https://dashboard.render.com/static/srv-d7lg0dv7f7vs73b2k1u0)
2. Click **Settings** → **Build & Deploy**.
3. Under **Repository**, click **Disconnect**. Confirm.
4. Click **Connect a repository** → choose `paperwork-labs/paperwork` → `main`.
5. Under **Root Directory**, set:
   - For the three backend services → `apis/axiomfolio`
   - For `axiomfolio-frontend` → `apps/axiomfolio`
6. Under **Dockerfile Path** (backend services only): set to `./Dockerfile` (NOT `./Dockerfile.backend`).
7. For `axiomfolio-frontend` (static site), set **Build Command** to:
   ```
   cd ../.. && corepack enable && corepack prepare pnpm@10.32.1 --activate && pnpm install --frozen-lockfile --filter=@paperwork-labs/axiomfolio... && pnpm --filter=@paperwork-labs/axiomfolio build
   ```
   and **Publish Path** to `dist`.
8. Save. Render will kick off a fresh build from the monorepo.

## Step 2 — Verify

After each service's build finishes (2–5 min), confirm green via Brain:

```bash
# Expect 200 + JSON payload on each:
curl -sS https://axiomfolio-api-02ei.onrender.com/health
curl -sS https://axiomfolio-frontend-ia2b.onrender.com/
# Workers don't expose HTTP — check recent deploys via MCP:
# (In Cursor chat) @brain render: show me recent deploys for axiomfolio-worker
```

If any service goes red, **stop and page Brain**: `@paperwork status axiomfolio` in `#deployment`. Don't try to fix by editing env vars mid-flight; roll back by flipping **Manual Deploy → Deploy latest commit** from the previous green deploy.

## Step 3 — Pin Blueprint file path

Render supports linking a service to a Blueprint `render.yaml` for future auto-updates. For each of the four services:

1. Settings → **Blueprint** (at the bottom of the Build & Deploy page).
2. Set **Blueprint file path** to `apis/axiomfolio/render.yaml`.
3. Save.

This makes future changes to `apis/axiomfolio/render.yaml` propagate on push to `main`.

## Step 4 — Archive the old repo

Once all four services are green on monorepo for ≥24h:

```bash
# Still need to do this from Cursor with gh CLI keyring auth (the workflow scope is there):
gh repo archive paperwork-labs/axiomfolio --yes
```

Leaves it read-only as a historical record; no pushes, no deploys.

## Step 5 — Close out the DoD

Tick the boxes in [RENDER_INVENTORY.md](RENDER_INVENTORY.md):

- [ ] F-1: four axiomfolio services repointed to monorepo; old repo archived.

…and commit this doc's updated status to `main`.

## Rollback

If the monorepo Dockerfile doesn't cleanly build for you, the safest rollback is:

1. In the service Settings, flip **Repository** back to `paperwork-labs/axiomfolio`.
2. Dockerfile path back to `./Dockerfile.backend`.
3. **Manual Deploy** → pick the last known-green commit.

Do NOT delete the service — recreating loses the `srv-d7…` ID and breaks anything that hardcodes the hostname. Repointing preserves IDs.

## Why Brain can't do this automatically

Render's API supports service creation and env var updates but not repository reassignment on an existing service (as of the MCP surface we have). This is a one-shot human click. After this is done, all future state changes can be driven by Brain via MCP.
