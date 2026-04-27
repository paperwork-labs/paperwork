---
owner: agent-ops
last_reviewed: 2026-04-26
doc_kind: runbook
domain: infra
status: active
---

# Cheap-agent sprint planning (Brain)

Brain generates **discrete, copy-pasteable task specs** from open work and packs them into **~1-day sprints** (multiple sprints per calendar day are expected when the scheduler ticks several times). This is **rule-based v1** — no LLM inside the generator.

## Loop

1. **Sources** — Open GitHub PRs (health bucket), issues labeled `ready` (with `bug`), optional `docs/infra/FOUNDER_ACTIONS.md` (lines without URLs are agent-eligible; URL-only lines are skipped), and open items from `apps/studio/src/data/tracker-index.json`.
2. **Generate** — `app.services.agent_task_generator.generate()` returns `AgentTaskSpec` rows (stable `task_id`, title ≤ 80 chars, scope, estimate, agent type, model hint, `depends_on`, `touches_paths`, `source`).
3. **Collision edges** — `app.services.sprint_planner.add_path_collision_dependencies` adds `depends_on` when `touches_paths` overlap (prefix rules).
4. **Bucket** — `select_sprint_bucket` picks up to `BRAIN_AGENT_SPRINT_MAX_TASKS` tasks within `BRAIN_AGENT_SPRINT_DAY_CAP_MINUTES`, respecting dependencies and preferring disjoint paths.
5. **Persist** — `apis/brain/data/agent_sprints_store.json` (canonical). Optional mirror digest on `cheap_agent_sprints` in `tracker-index.json` when `BRAIN_AGENT_SPRINT_WRITE_TRACKER=true` and the file is writable under `REPO_ROOT`.
6. **Learn** — Memory episode `source=agent_sprint:generated` with `skip_embedding=True` (lightweight signal for retrieval).
7. **Review** — Studio **`/admin/agent-sprints`** lists the last 24h. **Dispatch is manual** in this version (button stub).

## Scheduler

- **Job id:** `brain_agent_sprint_planner`
- **Trigger:** cron `0 */4 * * *` with `ZoneInfo("America/Los_Angeles")` (six wall-clock ticks per day in PT; adjust in `agent_sprint_scheduler.py` if you want exactly three ticks).
- **Enable:** `BRAIN_OWNS_AGENT_SPRINT_SCHEDULER=true` (requires `BRAIN_SCHEDULER_ENABLED=true`).

## HTTP (founder / automation)

| Method | Path | Auth |
| --- | --- | --- |
| GET | `/internal/agent-sprints/today` | `X-Brain-Secret` = `BRAIN_API_SECRET` |
| POST | `/internal/agent-sprints/regenerate` | same |

Studio proxies via **`/api/admin/agent-sprints/today`** and **`/api/admin/agent-sprints/regenerate`**.

## PR buckets (heuristic)

| Bucket | Typical task |
| --- | --- |
| DIRTY / behind base | `rebase + push` (15 min, `shell`) |
| RED, single lint failure | `fix lint` (5 min, `shell`) |
| RED, other failures | `fix failing CI` (60 min, `generalPurpose`) |
| UNSTABLE (pending, no failures yet) | unblock / watch checks (15 min, `shell`) |
| MERGEABLE / clean | no automatic cheap task (review/merge is founder or existing automation) |

## Tuning

- Raise **`BRAIN_AGENT_SPRINT_MAX_TASKS`** for wider buckets; lower for tighter review batches.
- Raise **`BRAIN_AGENT_SPRINT_DAY_CAP_MINUTES`** if you schedule longer cheap-agent sessions.
- Turn on **`BRAIN_AGENT_SPRINT_WRITE_TRACKER`** only on machines with a git checkout (digest updates will dirty `tracker-index.json`).

## Relation to PR #240

PR #240 may introduce additional `sprint_planner` logic. This work **extends** `app/services/sprint_planner.py` with shared collision and bucketing helpers; rebase after #240 if both touch that module.

## Related code

- `apis/brain/app/services/agent_task_generator.py`
- `apis/brain/app/services/sprint_planner.py`
- `apis/brain/app/schedulers/agent_sprint_scheduler.py`
- `apis/brain/app/api/agent_sprints.py`
- `apps/studio/src/app/admin/agent-sprints/`
