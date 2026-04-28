---
owner: infra-ops
last_reviewed: 2026-04-26
doc_kind: runbook
domain: infra
status: active
severity_default: yellow
related_runbooks: []
---

# Tonight: Brain ambient learning env vars on `brain-api` (J1)

**Time budget:** ~5 minutes dashboard + ~3 minutes deploy.

Use this runbook when **`RENDER_API_KEY` is not available** for automation, or as a manual duplicate of the API flow.

## Service

- **Name:** `brain-api`
- **Dashboard:** open [Render Dashboard](https://dashboard.render.com) → search **`brain-api`** → **Environment** (or **Env Vars**).

## `GITHUB_TOKEN` (do not overwrite if present)

1. In **Environment**, locate **`GITHUB_TOKEN`**.
2. If it already has a value → **leave it** (fine-grained PAT with repo contents/metadata as required by Brain).
3. If **missing** → create a GitHub PAT (classic or fine-grained per org policy), paste into **`GITHUB_TOKEN`**, save.

## Set / update these variables (exact values)

Ambient-learning schedulers (**sprint auto-logger**, **merged PRs**, **decisions**, **postmortems**) register whenever **`BRAIN_SCHEDULER_ENABLED=true`** — the retired `BRAIN_OWNS_SPRINT_AUTO_LOGGER` / `BRAIN_OWNS_*_INGEST*` / `BRAIN_OWNS_*_INGESTER` env keys are **ignored** if still present in the dashboard (remove them to avoid confusion).

Add or edit so the **value** matches exactly:

| Key | Value |
| --- | --- |
| `REPO_ROOT` | `/opt/render/project/src` |

**`REPO_ROOT` note:** [`render.yaml`](../../render.yaml) builds `brain-api` with Docker (`dockerContext: .`). At runtime the container filesystem is the image (see [`apis/brain/Dockerfile`](../../apis/brain/Dockerfile)); `/opt/render/project/src` is the common path for **non-Docker** Render runtimes. If file-based ingesters (`docs/decisions`, sprint postmortems under `docs/`) scan zero files after deploy, open **Render Shell** (if enabled) or check logs — you may need a follow-up to align `REPO_ROOT` with where the monorepo tree is visible, or expand the image. Setting the variable as above matches ops intent and [`docs/sprints/BRAIN_CONTINUOUS_LEARNING_2026Q3.md`](../sprints/BRAIN_CONTINUOUS_LEARNING_2026Q3.md).

## Deploy

- **Save** env vars. Render usually triggers a **new deploy**; if not, **Manual Deploy** → **Clear build cache** only if instructed — otherwise deploy latest commit.

## Verify (after deploy live)

**Health (no secret):**

```bash
curl -sS https://brain-api-zo5t.onrender.com/health
# or custom domain:
curl -sS https://brain.paperworklabs.com/health
```

**Logs (dashboard → `brain-api` → Logs):** confirm lines such as:

- `merged_prs_ingest installed`
- `ingest_decisions_cadence installed`
- `ingest_postmortems_cadence installed`
- `sprint_auto_logger installed`

**Database (optional, requires read access to Brain `DATABASE_URL`):** recent scheduler rows:

```sql
SELECT job_id, status, started_at
FROM agent_scheduler_runs
ORDER BY started_at DESC
LIMIT 30;
```

Look for `job_id` in `merged_prs_ingest`, `ingest_decisions_daily`, `ingest_postmortems_daily`, `sprint_auto_logger`.

**Episodes (optional):** merged PR / decision / postmortem ingesters write memory with sources `merged_pr`, `decision`, `postmortem` — inspect via your usual Brain admin or SQL on `episodes` if needed.

## API automation (when `RENDER_API_KEY` is in your shell)

1. `GET https://api.render.com/v1/services?name=brain-api&limit=10` — note `service.id`.
2. `GET https://api.render.com/v1/services/<svc-id>/env-vars` — snapshot existing.
3. `PUT https://api.render.com/v1/services/<svc-id>/env-vars` with a **full** JSON array = existing vars **plus** the keys above (PUT replaces the entire list).
4. `POST https://api.render.com/v1/services/<svc-id>/deploys` with body `{"clearCache":"do_not_clear"}`.

## Reference

- Blueprint: [`render.yaml`](../../render.yaml) (`brain-api`)
- Brain schedulers: [`apis/brain/app/schedulers/pr_sweep.py`](../../apis/brain/app/schedulers/pr_sweep.py)
