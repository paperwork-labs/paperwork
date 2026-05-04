---
owner: infra-ops
last_reviewed: 2026-04-27
doc_kind: runbook
domain: infra
status: active
---

# Brain APScheduler — SQLAlchemy job store

> Reference + ops: Brain uses **SQLAlchemyJobStore** on Postgres so scheduled jobs survive process restarts. **Track K is complete:** first-party jobs that replaced n8n schedule-trigger workflows register whenever `BRAIN_SCHEDULER_ENABLED=true`. Transitional `BRAIN_OWNS_*` env flags for those crons and the **n8n shadow mirror** module were **retired** in `chore/brain-delete-legacy-owns-flags` (no more `n8n_shadow_*` APScheduler rows).

[Brain](https://github.com/paperwork-labs/paperwork/tree/main/apis/brain) runs in-process [APScheduler](https://apscheduler.readthedocs.io/) jobs (PR sweep, proactive cadence, ex-n8n crons, etc.). The scheduler uses **SQLAlchemyJobStore** against the same PostgreSQL instance as the app ORM, so **process restarts do not clear** registered job definitions (unlike the default in-memory job store). Job rows live in table **`apscheduler_jobs`**; APScheduler creates it on first use (no separate Alembic migration).

**Legacy env (harmless):** `SCHEDULER_N8N_MIRROR_ENABLED` and `SCHEDULER_N8N_MIRROR_*` remain in settings for backward compatibility with old deploy env blocks; the mirror installer was removed.

**Timezone:** First-party data jobs (P2.8–P2.10) use **`America/Los_Angeles`** where noted in code. Canonical policy: [TIMEZONE_STANDARDS.md](./TIMEZONE_STANDARDS.md).

## When this fires

Use this runbook when:

- **After a deploy**, you need to confirm jobs rehydrate from Postgres (`apscheduler_jobs`) instead of disappearing.
- Operators report **missing or duplicate cadence** for a Brain-owned job.

_n/a for pure application incidents — use product runbooks unless the failure is scheduler- or job-store-specific._

## Triage (≤5 min)

1. Confirm `BRAIN_SCHEDULER_ENABLED` is `true` on the `brain-api` service and the process started without scheduler import errors in logs.
2. Confirm `DATABASE_URL` reaches Postgres (job store is sync `postgresql://`, no `+asyncpg`).
3. Run the SQL in [Verification](#verification) to list stored job ids and next run times.

## Former n8n schedule-trigger workflows (now Brain-first)

Source JSON used `n8n-nodes-base.scheduleTrigger` with a cron expression or (Infra Health) a minutes interval. Brain registers the **same expression** (or 30-minute interval) as listed.

| n8n workflow name | Schedule (5-field or interval) | Status in Brain |
| --- | --- | --- |
| Brain Daily Trigger | `0 7 * * *` | First-party `brain_daily_briefing` when `BRAIN_SCHEDULER_ENABLED=true` |
| Brain Weekly Trigger | `0 18 * * 0` | First-party `brain_weekly_briefing` |
| Sprint Kickoff | `0 7 * * 1` | First-party `brain_sprint_kickoff` |
| Sprint Close | `0 21 * * 5` | First-party `brain_sprint_close` |
| Weekly Strategy Check-in | `0 9 * * 1` | First-party `brain_weekly_strategy` |
| Infra Heartbeat | `0 8 * * *` | First-party `brain_infra_heartbeat` |
| Data Source Monitor (P2.8) | `0 6 * * 1` — Mon **06:00 PT (DST-aware)** (`America/Los_Angeles`) | First-party `brain_data_source_monitor` |
| Data Deep Validator (P2.9) | `0 3 1 * *` — 1st of month **03:00 PT (DST-aware)** | First-party `brain_data_deep_validator` |
| Annual Data Update Trigger (P2.10) | `0 9 1 10 *` — 1 Oct **09:00 PT (DST-aware)** | First-party `brain_data_annual_update` |
| Infra Health Check | every **30** minutes (`IntervalTrigger`) | First-party `brain_infra_health` |
| Credential Expiry Check | `0 8 * * *` | First-party `brain_credential_expiry` |

**What the n8n flows did (reference):** daily/weekly/sprint kickoff → HTTP Brain `process`; sprint close and data validators → GitHub / HTTP and Slack; weekly strategy → Brain `process` with `strategy` persona + Slack; infra flows → n8n API and Slack; credential expiry → vault + conditional Slack.

## Environment variables (Brain / Render `brain-api`)

| Variable | Default | Effect |
| --- | --- | --- |
| `SCHEDULER_N8N_MIRROR_ENABLED` | `false` | **Legacy — unused** (mirror module removed). |
| `SCHEDULER_N8N_MIRROR_<ID>` | _(unset)_ | **Legacy — unused.** |
| `BRAIN_SCHEDULER_ENABLED` | `true` | Master switch for starting APScheduler (including job store). |
| `BRAIN_LEARNING_DASHBOARD_ENABLED` | `true` | J2/J3: When `true`, `GET /api/v1/admin/brain/*` (episodes, decisions, learning-summary) are enabled for Studio `/admin/brain-learning`. Set `false` to hard-disable those read-only routes without changing scheduler code. |
| `BRAIN_OWNS_AGENT_SPRINT_SCHEDULER` | `false` | When `true`, registers `brain_agent_sprint_planner` (cheap-agent sprint buckets, LA cron). See [AGENT_SPRINT_PLANNING.md](./AGENT_SPRINT_PLANNING.md). |
| `BRAIN_AGENT_SPRINT_MAX_TASKS` | `8` | Max tasks per generated sprint. |
| `BRAIN_AGENT_SPRINT_DAY_CAP_MINUTES` | `480` | Estimated minutes ceiling per sprint. |
| `BRAIN_AGENT_SPRINT_WRITE_TRACKER` | `false` | When `true`, appends sprint digest to `tracker-index.json` (`cheap_agent_sprints`) if `REPO_ROOT` is writable. |
| `DATABASE_URL` | (dev default) | Must be reachably Postgres. Async URL uses `+asyncpg`; the job store uses a sync `postgresql://` form (no `+asyncpg`). |

### Operational gates (intentionally default off)

| Scheduler / `job_id` | Schedule (UTC) | Render env flag | Why gated |
| --- | --- | --- | --- |
| `brain_agent_sprint_planner` | `0 */4 * * *` (tz `America/Los_Angeles`) | `BRAIN_OWNS_AGENT_SPRINT_SCHEDULER` | Heuristic cheap-agent tasks → 1-day buckets; persists under `apis/brain/data/`. HTTP: `/internal/agent-sprints/today`, `/internal/agent-sprints/regenerate`. See [AGENT_SPRINT_PLANNING.md](./AGENT_SPRINT_PLANNING.md). |

### Net-new (on when `BRAIN_SCHEDULER_ENABLED`)

| `job_id` | Schedule (UTC) | Notes |
| --- | --- | --- |
| `pr_sweep` | interval (`SCHEDULER_PR_SWEEP_MINUTES`, default 30) | Brain PR review + merge sweep |
| `proactive_cadence` | hourly | Persona Slack briefs (LLM) |
| `cfo_cost_dashboard` | daily 15:30 | Read Redis → Slack |
| `qa_weekly_report` | Sun 17:00 | Registry digest → Slack |
| `cfo_friday_digest` | Fri 18:00 | Tracker + CFO persona → Slack |
| `sprint_lessons_ingest` | interval (default 6h) | Sprint markdown → memory |
| `sprint_auto_logger` | `*/15 * * * *` | Batched bot PRs editing `docs/sprints/*.md`; validate `GITHUB_TOKEN`. Manual backfill: `cd apis/brain && python -m app.cli.sprint_auto_logger_cli --since YYYY-MM-DD`. |
| `merged_prs_ingest` | interval (default 6h) | Merged PRs → memory |
| `ingest_decisions_daily` | daily 03:00 | ADR docs → memory |
| `ingest_postmortems_daily` | daily 03:30 | Postmortems / incidents → memory |
| `secrets_drift_audit` | daily **03:00** `America/Los_Angeles` | Vault vs Vercel/Render fingerprint audit → episodes + optional agent tasks; `BRAIN_OWNS_SECRETS_DRIFT_AUDIT` (default on) |
| `secrets_rotation_monitor` | daily **09:00** `America/Los_Angeles` | Rotations due within 7d → episodes + optional agent tasks; `BRAIN_OWNS_SECRETS_ROTATION_MONITOR` |
| `secrets_health_probe` | hourly (UTC) | For `criticality=critical` rows, sample health URLs; `BRAIN_OWNS_SECRETS_HEALTH_PROBE` |

Plus all **ex-n8n** first-party jobs in the table above (no separate `BRAIN_OWNS_*` flags).

See [BRAIN_SECRETS_INTELLIGENCE.md](./BRAIN_SECRETS_INTELLIGENCE.md) for schema, webhooks, and runbook.

**Job list (process):** `GET /internal/schedulers` returns the current APScheduler registry (`id`, `next_run`, `trigger`, `classification`: `net-new` / `cutover` / `operational`). Unauthenticated — use for deploy verification or behind an edge allowlist.

### Mirror status endpoint (legacy)

- **Path:** `GET /api/v1/admin/scheduler/n8n-mirror/status`
- **Auth:** same as other admin routes (`X-Brain-Secret` = `BRAIN_API_SECRET`).

Returns `retired: true`, a short `message`, `global_enabled: false`, and `per_job: []`. Studio `/admin/n8n-mirror` still works and shows the retirement notice.

**Infra Health Check (`brain_infra_health`) — dedup and reminders:** The Brain port matches the old n8n flow: posts to Slack when the **fingerprint** of n8n liveness + workflow count changes, or on transition from unhealthy → healthy (Redis keys under `brain:infra_health:*` when Redis is available; otherwise in-process state). If the system stays **unhealthy** with an unchanged fingerprint, Brain re-alerts after **`INFRA_HEALTH_REMINDER_HOURS`** (default **4**).

## Verification

**Database — confirm jobs are persisted:**

```sql
SELECT id, next_run_time, job_state
FROM apscheduler_jobs
ORDER BY id;
```

(Column names can vary slightly by APScheduler version; you should see one row per registered job when the process has started at least once with the job store.)

**Application logs** — On startup, Brain logs APScheduler start and registered jobs.

## Rollback

- **Scheduler off:** set `BRAIN_SCHEDULER_ENABLED=false` (stops all in-process schedules) — use only for maintenance; re-enable when ready.
- **Job store issues:** revert to a deploy without `SQLAlchemyJobStore` only in an emergency branch (not recommended long term); prefer fixing `DATABASE_URL` / network.

## Escalation

- **Channel:** `#engineering` for scheduling questions; **`#incidents`** if production user-facing behavior regressed.
- **Owner:** infra-ops + engineering (Brain).

## Post-incident

- Log durable decisions in [Company Knowledge](../KNOWLEDGE.md) and update this runbook if job ids, env vars, or timezone strategy change.
- Link the sprint tracker [Streamline + SSO + Real DAGs](../sprints/STREAMLINE_SSO_DAGS_2026Q2.md).

## Post-deploy smoke (T3.7)

Automated verification lives at `apis/brain/scripts/post_deploy_smoke.py`. It exercises **`GET /health`** (required), **`GET /health/deep`** (optional — 404 logs `skipped — route absent` and continues), **`GET /internal/schedulers`** (optional — missing `brain_autopilot_dispatcher` logs an informational warning only), and a **database probe** (`SELECT 1 FROM agent_dispatches LIMIT 1`, required).

### Running locally

From repo root (with Brain API up and `DATABASE_URL` set so SQLAlchemy can reach the same Postgres as production):

```bash
cd apis/brain
export BRAIN_API_URL=http://localhost:8000   # optional; defaults to this without --ci
python scripts/post_deploy_smoke.py
```

CI / production-style run (URL mandatory):

```bash
export BRAIN_API_URL=https://<brain-host>
python apis/brain/scripts/post_deploy_smoke.py --ci
```

On failure, **`--report-conversation`** posts a Brain Conversation via **`POST /api/v1/admin/conversations`** using **`BRAIN_ADMIN_TOKEN`** as **`X-Brain-Secret`** (same value as Brain `BRAIN_API_SECRET` on Render — see [pre-deploy guard](./pre-deploy-guard.md)).

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | All required checks passed; optional checks passed or were skipped as documented |
| `1` | At least one **required** check failed (`/health` or DB) |
| `2` | Required checks passed but an **optional** HTTP probe failed (e.g. `/health/deep` or `/internal/schedulers` non-success) |

Structured stdout: one JSON object per line per check (no PII).

### Automation

GitHub Actions workflow **`.github/workflows/brain-post-deploy-smoke.yml`** runs on `repository_dispatch` type **`brain-deploy-completed`** (wire Render → GitHub separately) and on **`workflow_dispatch`**. It does **not** run on pull requests and does not gate merges.

## Related

- Decision log: [Company Knowledge](../KNOWLEDGE.md).
- Sprint: [Streamline + SSO + Real DAGs](../sprints/STREAMLINE_SSO_DAGS_2026Q2.md).
- Code: `apis/brain/app/schedulers/pr_sweep.py`, `apis/brain/app/schedulers/apscheduler_db.py`, `apis/brain/app/schedulers/brain_daily_briefing.py`, `apis/brain/app/schedulers/brain_weekly_briefing.py`, `apis/brain/app/schedulers/weekly_strategy.py`, `apis/brain/app/schedulers/sprint_kickoff.py`, `apis/brain/app/schedulers/sprint_planner.py`, `apis/brain/app/schedulers/sprint_close.py`, `apis/brain/app/schedulers/data_source_monitor.py`, `apis/brain/app/schedulers/data_deep_validator.py`, `apis/brain/app/schedulers/data_annual_update.py`, `apis/brain/app/schedulers/infra_heartbeat.py`, `apis/brain/app/schedulers/infra_health.py`, `apis/brain/app/schedulers/credential_expiry.py`.

---

**Tests:** `apis/brain/tests/test_schedulers/test_brain_daily_briefing.py`, `apis/brain/tests/test_schedulers/test_brain_weekly.py`, `apis/brain/tests/test_schedulers/test_weekly_strategy.py`, `apis/brain/tests/test_schedulers/test_sprint_kickoff.py`, `apis/brain/tests/test_schedulers/test_sprint_planner.py`, `apis/brain/tests/test_schedulers/test_sprint_close.py`, `apis/brain/tests/test_schedulers/test_data_source_monitor.py`, `apis/brain/tests/test_schedulers/test_data_deep_validator.py`, `apis/brain/tests/test_schedulers/test_data_annual_update.py`, `apis/brain/tests/test_schedulers/test_infra_heartbeat.py`, `apis/brain/tests/test_schedulers/test_infra_health.py`, `apis/brain/tests/test_schedulers/test_credential_expiry.py`.
