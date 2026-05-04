# Wave 1 audit: Daily + weekly briefings

## TL;DR

Briefing cadence jobs **are implemented and registered** on the Brain APScheduler singleton (`brain_daily_briefing`, `brain_weekly_briefing`), but filenames and schedules follow **legacy n8n UTC expressions** (`0 7 * * *` and `0 18 * * 0` with `timezone=UTC`), **not** the Pacific-local times stated in `.cursor/rules/ea.mdc` (7am PT / Sun 6pm PT). Outputs are **`Brain agent.process` LLM drafts** persisted as Conversations via `create_conversation` (filesystem JSON store), **not** a structured assembler of the eight EA checklist sections — quality is model- and tooling-dependent. **Google Drive write-through described in ea.mdc is not implemented** in `apis/brain`. On failure, `run_with_scheduler_record` logs and writes **`agent_scheduler_runs`** rows but **does not** open Conversations tagged `alert` or route to infra-ops. Prod last-run timestamps and live briefing bodies were **not verified** in this audit (no DB/API access from the audit environment).

## Findings

### 1. APScheduler job registration

| Question | Status | Evidence |
| --- | --- | --- |
| `daily_briefing.py` / `weekly_plan.py` exist by those names | **✗ broken naming expectation** — use `brain_daily_briefing.py` and `brain_weekly_briefing.py` instead | `apis/brain/app/schedulers/brain_daily_briefing.py`, `brain_weekly_briefing.py` |
| Both call `scheduler.add_job(...)` in `install()` | **✓ works** | `brain_daily_briefing.py` L78–89; `brain_weekly_briefing.py` L78–89 |
| Cron matches ea.mdc (7am PT daily, Sun 6pm PT weekly); timezones explicit | **⚠ partial** — cron matches **retired n8n** UTC expressions with **`timezone=UTC`**, **not** `America/Los_Angeles`; **misaligned with ea.mdc PT wording** | `brain_daily_briefing.py` L81–82 `CronTrigger.from_crontab("0 7 * * *", timezone=UTC)`; `brain_weekly_briefing.py` L81–82 `CronTrigger.from_crontab("0 18 * * *", timezone=UTC)`; `.cursor/rules/ea.mdc` (cadence bullets); `docs/infra/BRAIN_SCHEDULER.md` L38–41 documents same expressions as former n8n |
| `install()` called from bootstrap | **✓ works** via `pr_sweep.start_scheduler()` (not directly from `schedulers/__init__.py` sequential block; that file calls `pr_sweep.start_scheduler()` first, which registers briefings among other jobs) | `apis/brain/app/schedulers/pr_sweep.py` L227–239; `apis/brain/app/schedulers/__init__.py` imports `start_scheduler` from `pr_sweep`; `apis/brain/app/main.py` L124 `start_scheduler()` |

**Gate:** **`BRAIN_SCHEDULER_ENABLED`** must be `true` — otherwise no scheduler (`pr_sweep.py` L101–104).

---

### 2. Job execution

| Question | Status | Evidence |
| --- | --- | --- |
| Job body collects the eight EA §1 bullet sections programmatically | **✗ not in code** — a **single generic user message** is sent to `brain_agent.process`; sections exist only if the **EA persona + tools** produce them | `brain_daily_briefing.py` L35, L44–52 (`_DAILY_MESSAGE = "Generate daily briefing for the founder."`); similarly `brain_weekly_briefing.py` L35, L43–52 |
| Calls `POST /admin/conversations` | **⚠ partial** — uses **`conv_svc.create_conversation(ConversationCreate(...))`** synchronously (~same persistence path as admin create, **not** HTTP self-call) | `brain_daily_briefing.py` L23–25, L57–65; router delegates to service in `apis/brain/app/routers/conversations.py` |
| Tags `daily-briefing` / `weekly-plan` | **✓ works** | `brain_daily_briefing.py` L61; `brain_weekly_briefing.py` L61 |
| `persona="ea"` on created Conversation | **✓ works** | `brain_daily_briefing.py` L63; `brain_weekly_briefing.py` L63 |
| Router uses EA for LLM turn | **✓ likely** — message contains “daily”/“briefing”/“weekly” (`ea` keywords in `routing.py`); **`persona_pin` is not passed** | `apis/brain/app/personas/routing.py` L62, L149–157; scheduler passes `channel="conversations"` (not a Slack id), so channel map does not boost |

---

### 3. Last-run history

| Question | Status | Evidence |
| --- | --- | --- |
| `JobRun`-style row populated | **✓ works** — table **`agent_scheduler_runs`** via `SchedulerRun` model | `apis/brain/app/schedulers/_history.py` L29–64; `apis/brain/app/models/scheduler_run.py` L15–26 |
| Who writes rows | **`run_with_scheduler_record`** inserts on success/error/skip paths | `_history.py` L49–62 |
| Public admin listing for these job_ids | **? unknown / likely partial** — `admin.py` only shows a **`workstream_progress_writeback`**-specific `SchedulerRun` query in sampled grep | `apis/brain/app/routers/admin.py` L325–330 (grep hit only that job_id) |
| Prod last successful run timestamps | **? unknown** — not queried (requires prod SQL against `agent_scheduler_runs` where `job_id` in (`brain_daily_briefing`,`brain_weekly_briefing`) and `status='success'`) | — |

**Verification hint (operator):**

```sql
SELECT job_id, status, finished_at
FROM agent_scheduler_runs
WHERE job_id IN ('brain_daily_briefing', 'brain_weekly_briefing')
ORDER BY finished_at DESC LIMIT 20;
```

---

### 4. Output quality (sample one recent briefing)

| Question | Status | Evidence |
| --- | --- | --- |
| Most recent Conversation body reviewed | **? unknown** — no prod `GET /api/v1/admin/conversations` or DB/export sample in audit scope | — |
| All eight EA Responsibilities §1 sections present | **⚠ partial by design** — **no code enforces** headings or section coverage | Same as §2 generic LLM prompt |
| Mobile-first ≤ ~2k chars | **? unknown** — no truncation in scheduler; depends on model | `brain_daily_briefing.py` L55 wraps empty as `"Brain returned no response."` only |
| Real data vs placeholder | **? unknown** — depends on **`process`** tool usage (e.g. `read_github_file` on `docs/TASKS.md`) session-to-session | `apis/brain/app/services/agent.py` system prompt suggests tools for tasks (L78–79) |

Local repo **`apis/brain/data/conversations/`** had **no `*.json` sample** at audit time — expected for CI machines without scheduled runs.

---

### 5. GDrive write-through

| Question | Status | Evidence |
| --- | --- | --- |
| Code writes briefings under `Paperwork Labs HQ/Operations/Daily Briefings/YYYY-MM-DD.md` | **✗ broken / not wired** — **no Google Drive integration** surfaced under `apis/brain` for these jobs (`rg` over `apis/brain` for drive/gdrive yielded no briefing writer) | Grep sweep; briefing modules only call `create_conversation` |

This is an **ea.mdc doctrine vs implementation gap** unless another service (outside Brain) performs the Drive sync.

---

### 6. Failure surfacing

| Question | Status | Evidence |
| --- | --- | --- |
| On job failure: Conversation tagged `alert` | **✗ broken** — failure path persists **`agent_scheduler_runs`** + **logs**; **`create_conversation` not invoked** when `brain_agent.process` throws before L55–65 | `_history.py` L44–48; briefing modules structure: conversation only after successful `process` |
| infra-ops / Engineering equivalent | **✗ broken** in sampled briefing paths — Slack removed per module docstrings (**WS-69 PR J**) | Headers in `brain_daily_briefing.py` L7–8; `brain_weekly_briefing.py` L7–8 |
| Silent failure | **⚠ partial** — **not silent in logs / DB observability**, but **silent to founder Conversations UX** unless someone monitors Postgres rows or log drains | `_history.py` L48 |

**Test hygiene note:** `tests/test_schedulers/test_brain_daily_briefing.py` and `test_brain_weekly.py` **monkeypatch `slack_outbound.post_message`** on modules that **do not define `slack_outbound`** — suggests tests are **stale vs PR J**; full pytest could not load in audit env due to unrelated `ModuleNotFoundError` (`app.utils.paths` from `conftest`/import chain).

## Gap list

```yaml
gaps:
  - id: brief-gap-1
    severity: medium
    surface: scheduler
    description: Daily/weekly briefing crons use UTC (legacy n8n parity) instead of Pacific-local triggers required by ea.mdc copy.
    evidence: "brain_daily_briefing.py:81-82; brain_weekly_briefing.py:81-82; .cursor/rules/ea.mdc (cadence)"
    fix_size: S

  - id: brief-gap-2
    severity: high
    surface: content
    description: Briefing bodies are unstructured LLM output with no programmatic guarantee of EA §1 sections (tasks, phase, overnight jobs, infra, filing engine, blockers, quick wins, partnerships).
    evidence: "brain_daily_briefing.py:35,44-52"
    fix_size: M

  - id: brief-gap-3
    severity: medium
    surface: persistence
    description: Conversations persist to filesystem JSON under apis/brain/data; durability on ephemeral Render disks not verified — risk of drift/loss alongside ea.mdc GDrive omission.
    evidence: "apis/brain/app/services/conversations.py:1-10,89-100"
    fix_size: M

  - id: brief-gap-4
    severity: high
    surface: output
    description: Google Drive write-through for Daily Briefings / Weekly Plans (ea.mdc) is not implemented in Brain briefing jobs.
    evidence: "brain_daily_briefing.py / brain_weekly_briefing.py (no Drive); .cursor/rules/ea.mdc Responsibilities §1 output bullets"
    fix_size: L

  - id: brief-gap-5
    severity: high
    surface: failure-handling
    description: Scheduler failures record agent_scheduler_runs + logs but do not create alert-tagged Conversations or route to infra-ops persona.
    evidence: "_history.py:44-62; briefing modules omit alert path"
    fix_size: S

  - id: brief-gap-6
    severity: low
    surface: persistence
    description: No first-party audited evidence of prod last-run or latest briefing quality; operators should query agent_scheduler_runs and admin conversations filtered by tags.
    evidence: "audit environment — prod not queried"
    fix_size: XS
```
