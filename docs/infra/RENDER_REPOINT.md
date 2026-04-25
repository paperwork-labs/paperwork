---
owner: infra-ops
last_reviewed: 2026-04-24
doc_kind: runbook
domain: infra
status: active
severity_default: yellow
related_runbooks: []
---
# Runbook: Render Repoint to Monorepo

> Four axiomfolio Render services still point at the old standalone repo; repoint them to `paperwork-labs/paperwork` so deploys use live code. Operator-driven (~15 min); Brain cannot reassign repository via API.

## When this fires

- [RENDER_INVENTORY.md](RENDER_INVENTORY.md) Finding **F-1** is open, or a migration plan schedules cutover of `axiomfolio-api`, `axiomfolio-worker`, `axiomfolio-worker-heavy`, and `axiomfolio-frontend` to the monorepo.
- Deliberate change window (not a surprise outage) — you are switching **Repository** / **Root Directory** / **Blueprint** in Render, not hot-fixing a crash loop.

| Level | Trigger | Action |
| --- | --- | --- |
| YELLOW | Planned repoint, CI green, no user-visible outage yet | Run this runbook, coordinate in `#deployment`, no merge halt required unless you widen scope. |
| RED | Repoint caused failed deploys, health red, or customer impact | Rollback first (see [Rollback](#rollback)), then [Escalation](#escalation). |

**Prereqs (blockers if missing):** Read [RENDER_INVENTORY.md](RENDER_INVENTORY.md) (F-1). Render dashboard: [dashboard.render.com](https://dashboard.render.com). `gh` CLI for archive step. _TODO: add any org-specific sign-off if required._

## Triage (≤5 min)

```bash
# Monorepo main is healthy
gh run list --branch main --limit 5
# Optional: open PRs you care about
gh pr list --state open
```

```bash
# Brain reachable (baseline for post-repoint health checks)
curl -sS https://brain-api-zo5t.onrender.com/health
```

If `main` is red → **stop**; fix CI before repointing. If Brain health fails → treat as separate incident, then return here.

## Path: Monorepo repoint (dashboard)

For **each** of the four services, in Render: **Settings** → **Build & Deploy**.

**Service links (direct):**

- [`axiomfolio-api`](https://dashboard.render.com/web/srv-d7lg0o77f7vs73b2k7m0)
- [`axiomfolio-worker`](https://dashboard.render.com/worker/srv-d7lg0o77f7vs73b2k7lg)
- [`axiomfolio-worker-heavy`](https://dashboard.render.com/worker/srv-d7lg0o77f7vs73b2k7kg)
- [`axiomfolio-frontend`](https://dashboard.render.com/static/srv-d7lg0dv7f7vs73b2k1u0)

1. Under **Repository**: **Disconnect** the old connection → confirm.
2. **Connect a repository** → `paperwork-labs/paperwork` → `main`.
3. **Root Directory**:
   - Three backend services → `apis/axiomfolio`
   - `axiomfolio-frontend` → `apps/axiomfolio`
4. **Dockerfile Path** (backend only): `./Dockerfile` (not `./Dockerfile.backend`).
5. `axiomfolio-frontend` (static): **Build Command**:

   ```bash
   cd ../.. && corepack enable && corepack prepare pnpm@10.32.1 --activate && pnpm install --frozen-lockfile --filter=@paperwork-labs/axiomfolio... && pnpm --filter=@paperwork-labs/axiomfolio build
   ```

   **Publish Path:** `dist`
6. Save. Render starts a build from the monorepo.
7. **Blueprint (optional but recommended):** same page → set **Blueprint file path** to `apis/axiomfolio/render.yaml` so future changes propagate on push to `main`.

_Why not API/MCP only:_ Render’s API supports create/update and env, but not repository reassignment on an existing service on the surface we use — one-shot human clicks. After repoint, Brain can drive more via MCP. _TODO: re-check if Render API adds repo switch; update runbook if automated._

## Verification

After each service’s build finishes (about 2–5 min):

```bash
# Expect 200 + useful payload
curl -sS https://axiomfolio-api-02ei.onrender.com/health
curl -sS https://axiomfolio-frontend-ia2b.onrender.com/
```

Workers: no HTTP — confirm recent **Deploys** in the dashboard or via Brain, e.g. in Cursor: `@brain render: show me recent deploys for axiomfolio-worker`.

- All four **Deploy** tabs show success for monorepo `main` within the last deploy.
- _TODO: add any org smoke test (auth, key flows) if required beyond `/health`._

## Rollback

If the monorepo Dockerfile or build is wrong, prefer rollback over editing env in panic:

1. **Settings** → **Build & Deploy** → **Repository**: reconnect `paperwork-labs/axiomfolio` (or last known good remote).
2. **Dockerfile Path** (backend): `./Dockerfile.backend`.
3. **Manual Deploy** → last known-green commit (not delete/recreate the service — preserves `srv-d7…` IDs and hostnames).

Do **not** delete a service; recreating breaks hardcoded `srv-…` or hostname assumptions.

## Escalation

- **`#deployment`:** `@paperwork status axiomfolio` if services go red; don’t “fix” by random env changes mid-flight.
- **Pager / owner:** _TODO: PagerDuty or primary on-call for infra-ops if RED customer impact after rollback attempt._
- **Vendor:** [Render support](https://render.com) if dashboard/API blocks you — link the ticket in `#deployment`.

`RENDER_API_KEY` and other tokens stay where you already store them; this runbook does not require pasting new secrets. _TODO: link to internal secret location if not standard._

## Post-incident

- Tick **F-1** in [RENDER_INVENTORY.md](RENDER_INVENTORY.md) when four services are on the monorepo and verified.
- After all four are green on the monorepo for **≥ 24h**, archive the old repo (read-only history):

  ```bash
  gh repo archive paperwork-labs/axiomfolio --yes
  ```

- Add a line under **Recent incidents** or sprint notes in `docs/KNOWLEDGE.md` if your process requires it. _TODO: link sprint doc if applicable._
- Bump `last_reviewed` on this file when the migration is done.

## Appendix

### Axiomfolio on Render (repoint targets)

- API: <https://dashboard.render.com/web/srv-d7lg0o77f7vs73b2k7m0>
- Worker: <https://dashboard.render.com/worker/srv-d7lg0o77f7vs73b2k7lg>
- Worker heavy: <https://dashboard.render.com/worker/srv-d7lg0o77f7vs73b2k7kg>
- Frontend: <https://dashboard.render.com/static/srv-d7lg0dv7f7vs73b2k1u0>
- Blueprint source: `apis/axiomfolio/render.yaml` (monorepo)

### Related

- [RENDER_INVENTORY.md](RENDER_INVENTORY.md) — F-1, DoD checkboxes
- [dashboard.render.com](https://dashboard.render.com)
