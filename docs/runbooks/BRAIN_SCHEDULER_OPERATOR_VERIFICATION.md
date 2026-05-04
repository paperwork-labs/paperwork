# Brain scheduler operator verification (`GET /internal/schedulers`)

Use this after deploy or when confirming **T1.2** autopilot wiring: the Brain API exposes an **unauthenticated**, read-only JSON list of in-process APScheduler jobs.

## Prerequisites

- **`BRAIN_SCHEDULER_ENABLED=true`** on the Brain API process. If the scheduler did not start, the endpoint still returns **`[]`** (empty list) — that is expected, not a transport failure.
- **Production base URL** is **not** committed in this repository. Substitute your real Brain API host (e.g. from Render, internal DNS, or your ops runbook). If you do not know it, treat the URL as **unknown** and resolve it from your hosting dashboard or team secret store.

## Copy-paste: development (local default)

Assumes Brain listens on `http://localhost:8000` (see `apis/brain` and local compose):

```bash
curl -sS "http://localhost:8000/internal/schedulers" | jq .
```

Filter for the autopilot job (constant `brain_autopilot_dispatcher` in `apis/brain/app/schedulers/autopilot_dispatcher.py`):

```bash
curl -sS "http://localhost:8000/internal/schedulers" | jq '.[] | select(.id == "brain_autopilot_dispatcher")'
```

## Copy-paste: production or staging

Replace **`<BRAIN_API_BASE_URL>`** with the real HTTPS origin (unknown in-repo — see above):

```bash
export BRAIN_API_BASE_URL='https://your-brain-api-host'   # example shape only
curl -sS "${BRAIN_API_BASE_URL}/internal/schedulers" | jq .
```

```bash
curl -sS "${BRAIN_API_BASE_URL}/internal/schedulers" | jq '.[] | select(.id == "brain_autopilot_dispatcher")'
```

**Auth:** this route is intentionally unauthenticated (read-only job metadata). Do not use admin or MCP tokens here.

## What “good” looks like

- HTTP **200** and a **JSON array** of objects with at least `id`, `next_run`, `trigger`, `enabled`, `classification`.
- When the scheduler is enabled and jobs are registered, the list should include **`brain_autopilot_dispatcher`** (T1.2 closure check).
- The probe-failure cadence job id is **`brain_probe_failure_dispatcher`** (see `apis/brain/app/schedulers/probe_failure_dispatcher.py`), not `probe_failure_dispatcher`.

## Automated check: `post_deploy_smoke.py`

Script: **`apis/brain/scripts/post_deploy_smoke.py`**.

- Calls **`GET /internal/schedulers`** and treats absence of `brain_autopilot_dispatcher` as a **non-fatal warning** (exit still success unless other required checks fail); see `probe_schedulers()` in that file.
- **Local / default base:** unset `BRAIN_API_URL` → defaults to `http://localhost:8000`.
- **CI / prod-like:** set **`BRAIN_API_URL`** to the non-empty production base URL and pass **`--ci`** (required — avoids silent localhost).

Example:

```bash
cd apis/brain
python scripts/post_deploy_smoke.py
```

```bash
export BRAIN_API_URL='https://your-brain-api-host'   # required for --ci; URL unknown in-repo
python scripts/post_deploy_smoke.py --ci
```

Optional failure alerting uses **`BRAIN_ADMIN_TOKEN`** as `X-Brain-Secret` for `/api/v1/admin/conversations` — token values are **not** in the repo.

## Further reading

- [docs/infra/BRAIN_SCHEDULER.md](../infra/BRAIN_SCHEDULER.md) — SQLAlchemy job store, `BRAIN_SCHEDULER_ENABLED`, triage.
