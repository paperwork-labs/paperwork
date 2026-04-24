# Staged Restart After Deploy Freeze

Use this runbook when Render deploys are frozen/unreliable and you must restart safely without introducing stale queue state.

## Goal

Restart services in dependency order with health gates between each step:
1. `web`
2. `worker`
3. `beat`

## Preconditions

- Confirm no emergency incident is in progress.
- Confirm DB migrations are already applied (`alembic current` on target revision).
- Confirm you have access to Render logs for all three services.

## Procedure

1. Restart `web` service first.
2. Wait for `web` to become live, then verify:
   - `GET /health` returns `200`
   - `GET /health/full` returns `200`
3. Restart primary `worker`.
4. Wait for `worker` live status, then verify:
   - Celery heartbeat appears in logs
   - No immediate `task_time_limit` or DB connection errors
5. Restart `beat` last.
6. Wait for `beat` live status, then verify:
   - Beat emits schedule ticks
   - New scheduled tasks are enqueued and picked up by workers
7. Monitor all logs for 5 minutes after final restart.

## Rollback Trigger

Rollback immediately if any of these occur:
- `/health/full` fails after web restart
- worker cannot connect to broker/DB for >2 minutes
- beat starts enqueueing tasks but worker does not consume

## Notes

- Do not restart `beat` before workers are healthy.
- Do not run manual queue drains unless explicitly approved by the founder/on-call lead.
