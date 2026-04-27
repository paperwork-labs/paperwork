---
owner: infra-ops
last_reviewed: 2026-04-26
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
2. If mirror issues: confirm `SCHEDULER_N8N_MIRROR_ENABLED` or any `SCHEDULER_N8N_MIRROR_<ID>` you set, and that `DATABASE_URL` reaches Postgres (job store is sync `postgresql://`, no `+asyncpg`).
3. Run the SQL in [Verification](#verification) to list stored job ids and next run times.

## Mirrored n8n schedule-trigger workflows (from `infra/hetzner/workflows/`, `archive/` excluded)

Source JSON uses `n8n-nodes-base.scheduleTrigger` with a cron expression or (Infra Health) a minutes interval. Brain mirrors the **same expression** (or 30-minute interval) as listed.

| n8n workflow name | Schedule (5-field or interval) | Status in Brain |
| --- | --- | --- |
| Brain Daily Trigger | `0 7 * * *` | **Cutover (T1.2):** real job `brain_daily_briefing` when `BRAIN_OWNS_DAILY_BRIEFING=true`; otherwise optional n8n shadow `n8n_shadow_brain_daily` |
| Brain Weekly Trigger | `0 18 * * 0` | **Cutover (T1.5 — Brain Weekly):** real job `brain_weekly_briefing` when `BRAIN_OWNS_BRAIN_WEEKLY=true`; otherwise optional n8n shadow `n8n_shadow_brain_weekly` |
| Sprint Kickoff | `0 7 * * 1` | **Cutover (Track K):** real job `brain_sprint_kickoff` when `BRAIN_OWNS_SPRINT_KICKOFF=true`; otherwise optional n8n shadow `n8n_shadow_sprint_kickoff` |
| Sprint Close | `0 21 * * 5` | **Cutover (Track K):** real job `brain_sprint_close` when `BRAIN_OWNS_SPRINT_CLOSE=true`; otherwise optional n8n shadow `n8n_shadow_sprint_close` |
| Weekly Strategy Check-in | `0 9 * * 1` | **Cutover (T1.6):** real job `brain_weekly_strategy` when `BRAIN_OWNS_WEEKLY_STRATEGY=true`; otherwise optional n8n shadow `n8n_shadow_weekly_strategy` |
| Infra Heartbeat | `0 8 * * *` | shadow — or first-party `brain_infra_heartbeat` when `BRAIN_OWNS_INFRA_HEARTBEAT=true` (T1.3) |
| Data Source Monitor (P2.8) | `0 6 * * 1` (see LA caveat above) | **Cutover (Track K):** real job `brain_data_source_monitor` when `BRAIN_OWNS_DATA_SOURCE_MONITOR=true`; otherwise optional n8n shadow `n8n_shadow_data_source_monitor` |
| Data Deep Validator (P2.9) | `0 3 1 * *` (see LA caveat) | shadow |
| Annual Data Update Trigger (P2.10) | `0 9 1 10 *` (see LA caveat) | shadow |
| Infra Health Check | every **30** minutes (``IntervalTrigger``) | **Cutover (T1, interval):** first-party `brain_infra_health` when `BRAIN_OWNS_INFRA_HEALTH=true`; otherwise optional n8n shadow `n8n_shadow_infra_health` |
| Credential Expiry Check | `0 8 * * *` | shadow — or first-party `brain_credential_expiry` when `BRAIN_OWNS_CREDENTIAL_EXPIRY=true` (T1.4) |

**What the n8n flows do (reference):** daily/weekly/sprint kickoff → HTTP Brain `process`; sprint close and data validators → GitHub / HTTP and Slack; **Weekly Strategy Check-in** (legacy) → OpenAI in n8n + Slack `#all-paperwork-labs` — replaced in-process by `brain_weekly_strategy` (Brain `process` with `strategy` persona) when `BRAIN_OWNS_WEEKLY_STRATEGY=true`; infra flows → n8n API and Slack; credential expiry → vault + conditional Slack. Shadow handlers do not duplicate this logic; they only log to `#engineering-cron-shadow`.

**Registry in code:** `apis/brain/app/schedulers/n8n_mirror.py` (`N8N_MIRROR_SPECS`).

## Environment variables (Brain / Render `brain-api`)

| Variable | Default | Effect |
| --- | --- | --- |
| `SCHEDULER_N8N_MIRROR_ENABLED` | `false` | When `true`, register **all** n8n shadow mirror jobs (subject to per-job overrides below). Requires the rest of the scheduler: `BRAIN_SCHEDULER_ENABLED=true`. |
| `SCHEDULER_N8N_MIRROR_<ID>` | _(unset)_ | **Per-mirror opt-in (or opt-out).** When set, that job uses this boolean instead of the global. `<ID>` is the mirror **job_id** in uppercase with underscores, e.g. `SCHEDULER_N8N_MIRROR_N8N_SHADOW_BRAIN_DAILY=true`. If unset, the job follows `SCHEDULER_N8N_MIRROR_ENABLED`. |
| `BRAIN_SCHEDULER_ENABLED` | `true` | Master switch for starting APScheduler (including job store and mirrors). |
| `DATABASE_URL` | (dev default) | Must be reachably Postgres. Async URL uses `+asyncpg`; the job store uses a sync `postgresql://` form (no `+asyncpg`). |

Per-job ``BRAIN_OWNS_*`` flags are read with ``os.getenv`` in each scheduler (and in ``n8n_mirror.py`` for shadow suppression); they are documented below by class, not duplicated as a flat env table.

### Cutover gates (flip in Render after n8n / shadow verified)

First-party Brain jobs that replace exported n8n crons. Each has a row in ``N8N_MIRROR_SPECS`` (see ``infra/hetzner/workflows/`` / ``retired/``). Default **off** until cutover.

| Scheduler / `job_id` | Schedule (UTC) | Render env flag | Shadow suppressed when on |
| --- | --- | --- | --- |
| `brain_daily_briefing` | `0 7 * * *` | `BRAIN_OWNS_DAILY_BRIEFING` | `n8n_shadow_brain_daily` |
| `brain_weekly_briefing` | `0 18 * * 0` | `BRAIN_OWNS_BRAIN_WEEKLY` | `n8n_shadow_brain_weekly` |
| `brain_weekly_strategy` | `0 9 * * 1` | `BRAIN_OWNS_WEEKLY_STRATEGY` | `n8n_shadow_weekly_strategy` |
| `brain_sprint_kickoff` | `0 7 * * 1` | `BRAIN_OWNS_SPRINT_KICKOFF` | `n8n_shadow_sprint_kickoff` |
| `brain_sprint_close` | `0 21 * * 5` | `BRAIN_OWNS_SPRINT_CLOSE` | `n8n_shadow_sprint_close` |
| `brain_infra_heartbeat` | `0 8 * * *` | `BRAIN_OWNS_INFRA_HEARTBEAT` | `n8n_shadow_infra_heartbeat` |
| `brain_credential_expiry` | `0 8 * * *` | `BRAIN_OWNS_CREDENTIAL_EXPIRY` | `n8n_shadow_credential_expiry` |
| `brain_infra_health` | every **30** min (`IntervalTrigger`) | `BRAIN_OWNS_INFRA_HEALTH` | `n8n_shadow_infra_health` |
| `brain_data_source_monitor` | `0 6 * * 1` | `BRAIN_OWNS_DATA_SOURCE_MONITOR` | `n8n_shadow_data_source_monitor` |

**Infra Health Check (`brain_infra_health`) — dedup and reminders:** The exported n8n flow (`retired/infra-health-check.json`) posts to Slack only when the **fingerprint** of the n8n liveness + workflow count changes, or on transition from unhealthy → healthy. The Brain port matches that (Redis keys under `brain:infra_health:*` when Redis is available; otherwise in-process state for the lifetime of the process). If the system stays **unhealthy** with an unchanged fingerprint, Brain re-alerts after **`INFRA_HEALTH_REMINDER_HOURS`** (default **4**), so sustained incidents are not silent forever.

Data monitors and annual update remain **shadow-only** in ``n8n_mirror.py`` until their cutover PRs land (separate from this doc section).

### Operational gates (intentionally default off)

| Scheduler / `job_id` | Schedule (UTC) | Render env flag | Why gated |
| --- | --- | --- | --- |
| `sprint_auto_logger` | `*/15 * * * *` | `BRAIN_OWNS_SPRINT_AUTO_LOGGER` | Opens **batched bot PRs** that edit `docs/sprints/*.md`; no n8n shadow. Flip after validating GitHub token scopes and a canary tick. Manual backfill: `cd apis/brain && python -m app.cli.sprint_auto_logger_cli --since YYYY-MM-DD`. |

### Net-new (no `BRAIN_OWNS_*` / on when `BRAIN_SCHEDULER_ENABLED`)

| `job_id` | Schedule (UTC) | Notes |
| --- | --- | --- |
| `pr_sweep` | interval (``SCHEDULER_PR_SWEEP_MINUTES``, default 30) | Brain PR review + merge sweep |
| `proactive_cadence` | hourly | Persona Slack briefs (LLM) |
| `cfo_cost_dashboard` | daily 15:30 | Read Redis → Slack |
| `qa_weekly_report` | Sun 17:00 | Registry digest → Slack |
| `cfo_friday_digest` | Fri 18:00 | Tracker + CFO persona → Slack |
| `sprint_lessons_ingest` | interval (default 6h) | Sprint markdown → memory |
| `merged_prs_ingest` | interval (default 6h) | Merged PRs → memory |
| `ingest_decisions_daily` | daily 03:00 | ADR docs → memory |
| `ingest_postmortems_daily` | daily 03:30 | Postmortems / incidents → memory |

### Read-only mirror status

- **Path:** `GET /api/v1/admin/scheduler/n8n-mirror/status`
- **Auth:** same as other admin routes (`X-Brain-Secret` = `BRAIN_API_SECRET`).

**Example (replace the secret and host):**

```bash
curl -sS -H "X-Brain-Secret: $BRAIN_API_SECRET" \
  "https://brain.paperworklabs.com/api/v1/admin/scheduler/n8n-mirror/status"
```

Response `data` includes `global_enabled` and `per_job` (each entry: `key`, `enabled`, `last_run`, `last_status`, `success_count_24h`, `error_count_24h`).

### Studio Admin (Paperwork Studio)

Operators can use the **n8n cron mirror** page in [Paperwork Studio](https://github.com/paperwork-labs/paperwork/tree/main/apps/studio) — **`/admin/n8n-mirror`** (Clerk or Basic Auth on `/admin` as for other command-center pages). The page calls the same endpoint via a server route using `BRAIN_API_URL` and `BRAIN_API_SECRET` (`X-Brain-Secret`), and shows a table of every mirror job id with shadow on/off, last run status, and 24h success/error counts. A summary strip highlights how many job rows have the n8n shadow registered versus heuristic “Brain path” (cutover) for the daily and infra **T1.2** / **T1.3** job ids. The UI auto-refreshes about every 30 seconds.

### Cutover order (T1.1)

Prefer **one mirror at a time** with per-job env vars, watch a few green shadow runs, then widen — instead of a single big-bang global toggle for every workflow. **Lower risk first:** start with internal / operational mirrors (e.g. `n8n_shadow_infra_heartbeat`, `n8n_shadow_infra_health`) before flows that post toward **user-facing** or high-visibility product channels. The Brain in-process `pr_sweep` job is separate from n8n; cut that over on its own cadence. Document which `n8n_shadow_*` job id is live in each phase.

## Cutover playbook (single-cron, env-flag ownership)

This is the supported path to move one exported n8n schedule to Brain without double-firing Slack or the Brain pipeline.

1. **Pick the owner flag** — Each strangled cron gets an explicit `BRAIN_OWNS_*` environment variable. **`BRAIN_OWNS_DAILY_BRIEFING=true` is the first** production flip: it enables `apis/brain/app/schedulers/brain_daily_briefing.py` and automatically **skips** registering `n8n_shadow_brain_daily` so the n8n mirror and the real job never run together.
2. **Deploy + verify** — With `BRAIN_SCHEDULER_ENABLED=true`, confirm `apscheduler_jobs` contains the new job id (e.g. `brain_daily_briefing`), `agent_scheduler_runs` shows `success` rows for that `job_id`, and the product channel (`#daily-briefing` for the daily workflow) looks correct. Watch logs for `brain_daily_briefing` on the 07:00 UTC tick.
3. **Monitor** — `GET /api/v1/admin/scheduler/n8n-mirror/status` still reports n8n **shadow** jobs (per-job `enabled`, last run, 24h success/error counts). The daily row’s `enabled` becomes `false` for `n8n_shadow_brain_daily` while Brain owns the cron; use `SELECT job_id, status, finished_at, error_text FROM agent_scheduler_runs WHERE job_id IN ('n8n_shadow_brain_daily', 'brain_daily_briefing') ORDER BY finished_at DESC LIMIT 20;` to compare during migration windows.
4. **Disable n8n on Hetzner** — After **24h of clean runs**, disable or pause the **Brain Daily Trigger** workflow on the Hetzner n8n instance (workflow inventory: [`infra/hetzner/workflows/README.md`](../../infra/hetzner/workflows/README.md)) so n8n no longer POSTs the same work. Until then, leaving n8n enabled duplicates the user-visible briefing — avoid that in production.
5. **Rollback** — Set `BRAIN_OWNS_DAILY_BRIEFING=false` (or remove it), redeploy, re-enable the n8n schedule on Hetzner, and (if you use mirrors) turn `SCHEDULER_N8N_MIRROR_N8N_SHADOW_BRAIN_DAILY` back on for shadow coverage until the next attempt.

## Cutover playbook (shadow → active, historical)

1. **Verify shadow** — In staging or a canary, enable a **single** mirror with `SCHEDULER_N8N_MIRROR_<ID>=true` (or set the global to `true` for all). Confirm messages in `#engineering-cron-shadow`, `SELECT * FROM apscheduler_jobs;` shows the expected job row(s), the status endpoint shows `enabled` and rising `success_count_24h`, and `SELECT * FROM agent_scheduler_runs ORDER BY finished_at DESC LIMIT 20;` looks sane. Fix timezone alignment for LA workflows if needed before prod cutover.
2. **Switch handler** — In a follow-up (e.g. T2.4), replace each shadow handler in `n8n_mirror.py` (or a successor module) with the real work (or delegate to a service), still keeping side-effects off until you disable n8n.
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

- **Shadow off:** set `SCHEDULER_N8N_MIRROR_ENABLED` back to `false`, clear per-job `SCHEDULER_N8N_MIRROR_*` you set, and redeploy; re-enable the n8n schedule if you had disabled it. Job rows may remain in `apscheduler_jobs` but unused rows are harmless.
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
- Code: `apis/brain/app/schedulers/pr_sweep.py`, `apis/brain/app/schedulers/apscheduler_db.py`, `apis/brain/app/schedulers/n8n_mirror.py`, `apis/brain/app/schedulers/brain_daily_briefing.py`, `apis/brain/app/schedulers/brain_weekly_briefing.py`, `apis/brain/app/schedulers/weekly_strategy.py`, `apis/brain/app/schedulers/sprint_kickoff.py`, `apis/brain/app/schedulers/sprint_close.py`, `apis/brain/app/schedulers/data_source_monitor.py`, `apis/brain/app/schedulers/infra_heartbeat.py`, `apis/brain/app/schedulers/infra_health.py`, `apis/brain/app/schedulers/credential_expiry.py`.

---

**Tests:** `apis/brain/tests/test_schedulers/test_n8n_mirror.py`, `apis/brain/tests/test_schedulers/test_n8n_mirror_perjob.py`, `apis/brain/tests/test_schedulers/test_brain_daily_briefing.py`, `apis/brain/tests/test_schedulers/test_brain_weekly.py`, `apis/brain/tests/test_schedulers/test_weekly_strategy.py`, `apis/brain/tests/test_schedulers/test_sprint_kickoff.py`, `apis/brain/tests/test_schedulers/test_sprint_close.py`, `apis/brain/tests/test_schedulers/test_data_source_monitor.py`, `apis/brain/tests/test_schedulers/test_infra_heartbeat.py`, `apis/brain/tests/test_schedulers/test_infra_health.py`, `apis/brain/tests/test_schedulers/test_credential_expiry.py`.
