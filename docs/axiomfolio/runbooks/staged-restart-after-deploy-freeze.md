---
owner: infra-ops
last_reviewed: 2026-04-24
doc_kind: runbook
domain: infra
status: active
severity_default: yellow
---
# Runbook: Staged Restart After Deploy Freeze

> Render deploys are frozen or unreliable; restart services in dependency order without introducing stale queue state. Order: `web` → `worker` → `beat`, with health gates between steps.

## When this fires

- A deploy freeze or unreliable Render deploys make a normal single-step redeploy unsafe.
- You need a **staged restart** (health gates between `web`, `worker`, and `beat`) instead of a blind restart.
- _TODO: alert names / Studio tiles / log lines that should trigger this runbook._

## Triage (≤5 min)

### Preconditions (confirm before you start)

- Confirm no emergency incident is in progress.
- Confirm DB migrations are already applied (`alembic current` on target revision).
- Confirm you have access to Render logs for all three services.

### Classify

```bash
# _TODO: base URL for the Render-backed API — set before running
# export AXIOMFOLIO_BASE_URL="https://<service>.onrender.com"
# curl -fsS "${AXIOMFOLIO_BASE_URL}/health" && curl -fsS "${AXIOMFOLIO_BASE_URL}/health/full"
```

If preconditions fail → do not start the staged sequence until resolved. If healthy but restarts are required → follow **Procedure** below.

### Procedure (staged restart)

1. Restart `web` first.
2. Wait for `web` to become live, then go to **Verification** for `web` checks.
3. Restart primary `worker`.
4. Wait for `worker` live status, then go to **Verification** for `worker` checks.
5. Restart `beat` last.
6. Wait for `beat` live status, then go to **Verification** for `beat` checks.
7. Monitor all logs for 5 minutes after the final restart.

**Notes**

- Do not restart `beat` before workers are healthy.
- Do not run manual queue drains unless explicitly approved by the founder or on-call lead.

## Verification

### After `web` restart

- `GET /health` returns `200`.
- `GET /health/full` returns `200`.

```bash
# After setting AXIOMFOLIO_BASE_URL
curl -fsS -o /dev/null -w "%{http_code}\n" "${AXIOMFOLIO_BASE_URL}/health"
curl -fsS -o /dev/null -w "%{http_code}\n" "${AXIOMFOLIO_BASE_URL}/health/full"
```

### After `worker` restart

- Celery heartbeat appears in logs.
- No immediate `task_time_limit` or DB connection errors.

### After `beat` restart

- Beat emits schedule ticks.
- New scheduled tasks are enqueued and picked up by workers.

## Rollback

Rollback immediately if any of these occur:

- `/health/full` fails after `web` restart.
- Worker cannot connect to broker/DB for more than 2 minutes.
- `beat` starts enqueueing tasks but the worker does not consume them.

**Actions**

- _TODO: e.g. redeploy previous revision from Render → Service → Deploys, or follow vendor rollback for the last good deploy._
- Stop the staged sequence at the first failed gate; return to a known-good deploy before retrying.

## Escalation

- If gates fail repeatedly: escalate to the founder or on-call lead (same approver as manual queue drains in **Triage** notes).
- _TODO: primary Slack channel (e.g. `#ops`) and on-call rotation._

## Post-incident

- Add a row to `docs/KNOWLEDGE.md` under "Recent incidents" with the pattern and the runbook section that handled it.
- If a new guardrail emerged, file a `.cursor/rules/*.mdc` update PR.
- If this runbook was wrong or stale, update it before closing the ticket. Bump `last_reviewed`.
