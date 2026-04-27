---
owner: infra-ops
last_reviewed: 2026-04-26
doc_kind: runbook
domain: infra
status: active
severity_default: yellow
related_runbooks:
  - RENDER_REPOINT.md
---

# Tonight: Repoint AxiomFolio Render services to the monorepo (I1)

**Time budget:** ~10 minutes in the dashboard, plus 5–10 minutes for builds.

**Goal:** Move the **four** backend/data AxiomFolio resources that still sync from `paperwork-labs/axiomfolio` so they track **`paperwork-labs/paperwork`** via the root Blueprint ([Path B in `RENDER_REPOINT.md`](RENDER_REPOINT.md)).

## Services in scope (exactly these four)

| Render name        | Type     | Why |
| ------------------ | -------- | --- |
| `axiomfolio-api`   | Web      | API Docker service |
| `axiomfolio-worker` | Worker  | Celery + Beat |
| `axiomfolio-worker-heavy` | Worker | Heavy queue |
| `axiomfolio-db`    | Postgres | Managed DB attached to the Blueprint |

**Not in this repoint list**

- **`axiomfolio-frontend`** — Track G4 will remove this Render static site after `apps/axiomfolio-next` + Vite retirement; do not block on repointing it here.
- **`axiomfolio-redis`** — Still associates when you apply the monorepo Blueprint; treat it as part of the same wizard if Render lists it (expected).

## One-time Blueprint flow (copy path)

1. Open **New Blueprint:** [https://dashboard.render.com/blueprints/new](https://dashboard.render.com/blueprints/new)
2. **Connect repository:** `paperwork-labs/paperwork`
3. **Branch:** `main`
4. **Blueprint path:** `render.yaml` (default at repo root)
5. Click **Apply** / continue until the **preview** lists services to create or **associate**.
6. For every row that matches an **existing** service (names above, plus `filefree-api`, `brain-api`, `axiomfolio-redis` if shown), choose **Associate existing services** — **not** “create all new”.
7. When Render asks whether to **associate** existing services with this Blueprint, confirm **Associate**.
8. Wait for the first **sync** to finish; open **Logs** on `axiomfolio-api` and confirm paths mention the monorepo (e.g. `apis/axiomfolio`, `rootDir`, or root `render.yaml` context — **not** the old standalone repo layout).

## Verify (copy-paste)

Set your API key in the shell (from the Render Dashboard → Account → API keys — **do not commit it**):

```bash
export RENDER_API_KEY='***'   # paste from Render Dashboard
```

**Per-service repo pointer** (repeat for each service id from the dashboard URL `.../srv-XXXX/settings` or from [RENDER_REPOINT.md appendix](RENDER_REPOINT.md#appendix)):

```bash
SVC_ID='srv-REPLACE_ME'
curl -sS -H "Authorization: Bearer $RENDER_API_KEY" \
  "https://api.render.com/v1/services/$SVC_ID" | jq '.service.repo'
```

**Pass:** value contains `paperwork-labs/paperwork`. **Fail:** `paperwork-labs/axiomfolio`.

Quick health (after deploys go green):

```bash
curl -sS https://axiomfolio-api-02ei.onrender.com/health
```

## Rollback

- Re-run **Blueprint sync** from the **previous** Blueprint tied to `paperwork-labs/axiomfolio`, or use **Manual Deploy → last green** on each service. Per [`RENDER_REPOINT.md`](RENDER_REPOINT.md), the old association remains usable for roughly **7 days** after repoint — keep the old Blueprint until you are sure.

## After 24 h green

Archive the standalone repo (irreversible read-only):

```bash
gh repo archive paperwork-labs/axiomfolio --yes
```

## Reference

- Full narrative: [`docs/infra/RENDER_REPOINT.md`](RENDER_REPOINT.md)
- Inventory: [`docs/infra/RENDER_INVENTORY.md`](RENDER_INVENTORY.md) (F-1)
