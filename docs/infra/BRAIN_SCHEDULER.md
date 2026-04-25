---
owner: infra-ops
last_reviewed: 2026-04-25
doc_kind: runbook
domain: infra
status: active
---

# Brain APScheduler — SQLAlchemy job store and n8n shadow mirrors

> Reference + ops: Brain uses **SQLAlchemyJobStore** on Postgres so scheduled jobs survive process restarts. Optional **n8n shadow mirrors** (`SCHEDULER_N8N_MIRROR_ENABLED`) post only to **`#engineering-cron-shadow`** until T2.4 cutover.

[Brain](https://github.com/paperwork-labs/paperwork/tree/main/apis/brain) runs in-process [APScheduler](https://apscheduler.readthedocs.io/) jobs (PR sweep, proactive cadence, optional n8n shadow mirrors). The scheduler uses **SQLAlchemyJobStore** against the same PostgreSQL instance as the app ORM, so **process restarts do not clear** registered job definitions (unlike the default in-memory job store). Job rows live in table **`apscheduler_jobs`**; APScheduler creates it on first use (no separate Alembic migration).

**Default-off mirror:** `SCHEDULER_N8N_MIRROR_ENABLED` defaults to `false` — there is no behavioral change in production until you set it. Shadow jobs, when enabled, only post to **`#engineering-cron-shadow`** (operator canary), not to user- or product-facing channels.

**Timezone caveat (TODO T2.4):** n8n exports for some data workflows set **`settings.timezone: America/Los_Angeles`**, while Brain registers mirror crons in **UTC** using the same 5-field expression. Until cutover, wall-clock times may not match n8n for those workflows. Treat shadow runs as “expression parity,” not guaranteed LA-time parity, unless you add explicit timezone in APScheduler to match the workflow.

## When this fires

Use this runbook when:

- You are **enabling or debugging** shadow mirrors or SQLAlchemy persistence for Brain’s scheduler.
- **After a deploy**, you need to confirm jobs rehydrate from Postgres (`apscheduler_jobs`) instead of disappearing.
- Operators report **missing or duplicate cadence** relative to n8n during the T1/T2.4 migration window.

_n/a for pure application incidents — use product runbooks unless the failure is scheduler- or job-store-specific._

## Triage (≤5 min)

1. Confirm `BRAIN_SCHEDULER_ENABLED` is `true` on the `brain-api` service and the process started without scheduler import errors in logs.
2. If mirror issues: confirm `SCHEDULER_N8N_MIRROR_ENABLED` and that `DATABASE_URL` reaches Postgres (job store is sync `postgresql://`, no `+asyncpg`).
3. Run the SQL in [Verification](#verification) to list stored job ids and next run times.

## Mirrored n8n schedule-trigger workflows (from `infra/hetzner/workflows/`, `archive/` excluded)

Source JSON uses `n8n-nodes-base.scheduleTrigger` with a cron expression or (Infra Health) a minutes interval. Brain mirrors the **same expression** (or 30-minute interval) as listed.

| n8n workflow name | Schedule (5-field or interval) | Status in Brain |
| --- | --- | --- |
| Brain Daily Trigger | `0 7 * * *` | shadow |
| Brain Weekly Trigger | `0 18 * * 0` | shadow |
| Sprint Kickoff | `0 7 * * 1` | shadow |
| Sprint Close | `0 21 * * 5` | shadow |
| Weekly Strategy Check-in | `0 9 * * 1` | shadow |
| Infra Heartbeat | `0 8 * * *` | shadow |
| Data Source Monitor (P2.8) | `0 6 * * 1` (see LA caveat above) | shadow |
| Data Deep Validator (P2.9) | `0 3 1 * *` (see LA caveat) | shadow |
| Annual Data Update Trigger (P2.10) | `0 9 1 10 *` (see LA caveat) | shadow |
| Infra Health Check | every **30** minutes (not cron) | shadow |
| Credential Expiry Check | `0 8 * * *` | shadow |

**What the n8n flows do (reference):** daily/weekly/sprint kickoff → HTTP Brain `process`; sprint close and data validators → GitHub / HTTP and Slack; strategy → OpenAI + Slack; infra flows → n8n API and Slack; credential expiry → vault + conditional Slack. Shadow handlers do not duplicate this logic; they only log to `#engineering-cron-shadow`.

**Registry in code:** `apis/brain/app/schedulers/n8n_mirror.py` (`N8N_MIRROR_SPECS`).

## Environment variables (Brain / Render `brain-api`)

| Variable | Default | Effect |
| --- | --- | --- |
| `SCHEDULER_N8N_MIRROR_ENABLED` | `false` | When `true`, register shadow mirror jobs (requires the rest of the scheduler: `BRAIN_SCHEDULER_ENABLED=true`). |
| `BRAIN_SCHEDULER_ENABLED` | `true` | Master switch for starting APScheduler (including job store and mirrors). |
| `DATABASE_URL` | (dev default) | Must be reachably Postgres. Async URL uses `+asyncpg`; the job store uses a sync `postgresql://` form (no `+asyncpg`). |

## Cutover playbook (shadow → active)

1. **Verify shadow** — Enable `SCHEDULER_N8N_MIRROR_ENABLED=true` in staging or a canary, confirm messages appear in `#engineering-cron-shadow` on the expected cadence, and `SELECT * FROM apscheduler_jobs;` shows job rows. Fix timezone alignment for LA workflows if needed before prod cutover.
2. **Switch handler** — In a follow-up (e.g. T2.4), replace each shadow `async def _run_shadow_*` body in `n8n_mirror.py` (or a successor module) with the real work (or delegate to a service), still keeping side-effects off until you disable n8n.
3. **Disable n8n cron** — In n8n, turn off the schedule trigger (or pause the workflow) for that workflow *after* Brain active path is proven. Do not leave duplicate schedules firing without intent.
4. **Naming** — Keep job ids stable (`n8n_shadow_*` → rename in the same PR as behavior switch if you want cleaner ops names).

## Verification

**Database — confirm jobs are persisted:**

```sql
SELECT id, next_run_time, job_state
FROM apscheduler_jobs
ORDER BY id;
```

(Column names can vary slightly by APScheduler version; you should see one row per registered job when the process has started at least once with the job store.)

**Application logs** — On startup, Brain logs APScheduler start and, when the mirror is enabled, how many n8n shadow jobs were registered.

**No duplicate Slack to product channels in shadow mode** — Only `#engineering-cron-shadow` is used. If a token is missing, `slack_outbound` skips posting and logs; no user-channel blast.

## Rollback

- **Shadow off:** set `SCHEDULER_N8N_MIRROR_ENABLED` back to `false` and redeploy; re-enable the n8n schedule if you had disabled it. Job rows may remain in `apscheduler_jobs` but unused rows are harmless.
- **Scheduler off:** set `BRAIN_SCHEDULER_ENABLED=false` (stops all in-process schedules, including mirrors) — use only for maintenance; n8n crons remain until you change n8n separately.
- **Job store issues:** revert to a deploy without `SQLAlchemyJobStore` only in an emergency branch (not recommended long term); prefer fixing `DATABASE_URL` / network.

## Escalation

- **Channel:** `#engineering` for scheduling or cutover questions; **`#incidents`** if production user-facing behavior regressed because a real handler was wired incorrectly after T2.4.
- **Owner:** infra-ops + engineering (Brain). For n8n-side changes, whoever administers the Hetzner n8n instance.

## Post-incident

- Log durable decisions in [Company Knowledge](../KNOWLEDGE.md) and update this runbook if job ids, env vars, or timezone strategy change.
- Link the sprint tracker [Streamline + SSO + Real DAGs](../sprints/STREAMLINE_SSO_DAGS_2026Q2.md) when T2.4 closes the n8n cron side.

## Related

- Decision log: [Company Knowledge](../KNOWLEDGE.md) (2026-04-25 — Brain owns schedules; SQLAlchemy job store).
- Sprint: [Streamline + SSO + Real DAGs](../sprints/STREAMLINE_SSO_DAGS_2026Q2.md) (T1 orchestration / shadow period).
- Code: `apis/brain/app/schedulers/pr_sweep.py`, `apis/brain/app/schedulers/apscheduler_db.py`, `apis/brain/app/schedulers/n8n_mirror.py`.

---

**Tests:** `apis/brain/tests/test_schedulers/test_n8n_mirror.py`.
