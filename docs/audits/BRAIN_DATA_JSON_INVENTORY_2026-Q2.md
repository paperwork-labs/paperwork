# Brain `apis/brain/data/*.json` inventory (T3.0a)

**Date:** 2026-05-04  
**Scope:** All committed `*.json` under `apis/brain/data/` (27 files; no nested JSON subfolders in this tree).  
**Method:** Grep of `apis/brain/app/` and `apis/brain/` for `.json` path strings, loader modules, and schema docstrings. **Read-only** — no runtime or schema changes.  
**Primary consumer** = first production code path (not test-only), using `app/...` module style for brevity.

---

## Summary table

| Path | Primary consumer(s) | Mutation frequency (guess) | Risk if lost | Suggested canonical home (long-term) |
|------|---------------------|----------------------------|--------------|--------------------------------------|
| `agent_dispatch_log.json` | `app/routers/admin.py`, `app/routers/stats.py`, `app/schedulers/pr_outcome_recorder.py`, `app/services/auto_distillation.py`, `app/services/operating_score_collectors/autonomy.py`, `app/services/kg_validation.py` | **Runtime** — appends/updates on dispatch + merge; also `agent_dispatch_log.jsonl` in autopilot | **High** — breaks dispatch analytics, admin views, backfill source for `agent_dispatches` | **Postgres** — continue `agent_dispatches` as SoT; treat JSON as legacy/compat until removed |
| `anomaly_alerts.json` | `app/services/anomaly_detection.py` | **Runtime** — scheduler / detector rewrites | **Med** — lose anomaly history; detection can regen from `operating_score` + `pr_outcomes` with gaps | **Postgres** (time-series or event table) |
| `app_registry.json` | `app/services/app_registry.py` (used by cost/ops surfaces) | **Infrequent** — human or script edits under lock | **Med** — wrong cost attribution / missing apps in registry | **Stay in git** or **Postgres** if multi-tenant edit UI; not `packages/data` (Brain/ops specific) |
| `audit_registry.json` | `app/services/audits.py` (seed + updates) | **Low** — seeded; occasional founder edits | **Med** — audit definitions missing until re-seed | **Postgres** if Studio needs CRUD; else **stay git** with file lock |
| `axe_runs.json` | `app/services/operating_score_collectors/a11y_design_system.py` | **CI / scheduled** — new runs overwrite/extend | **Low–med** — POS pillar weak / missing | **Object store or Postgres JSON** for CI artifacts; avoid giant git blobs long-term |
| `bills.json` | `app/services/bills.py` | **Runtime** — API/file-locked updates | **Med–high** — vendor billing tracking gaps | **Postgres** (finance ops) |
| `cost_ledger.json` | `app/services/cost_monitor.py`, `app/audits/cost_monitor.py` | **Mixed** — manual ETL + edits | **Med** — burn metrics wrong | **Postgres** ledger table |
| `decommissions.json` | `app/services/decommissions.py` | **Low** — curated registry | **Low** — ops clarity only | **Stay git** or **Postgres** row per service |
| `expense_routing_rules.json` | `app/services/expenses.py`, `app/services/expense_rules.py` | **Low** — human-edited policy | **Med** — wrong routing for expense workflow | **Postgres** with admin UI (per expense tags in master plan) |
| `expenses.json` | `app/services/expenses.py` | **Runtime** — file-locked append/update | **High** — PII/financial rows (treat as sensitive) | **Postgres** (already directionally “Company OS”) |
| `goals.json` | `app/routers/admin.py` (read/write goals helpers) | **Medium** — admin/API writes | **Med** — Studio `/admin/goals` wrong until DB unified | **Postgres** via **T2.0 /admin/goals** — **same entity family as T2.10 Studio snapshot kill** |
| `incidents.json` | `app/services/procedural_memory.py`, `app/services/coach_preflight.py`, `app/services/self_improvement.py`, `app/services/auto_revert.py`, `app/services/operating_score_collectors/reliability_security.py` | **Runtime + edits** — incidents appended/updated | **High** — procedural memory + revert context degraded | **Postgres** incident/event store |
| `infra_registry.json` | `app/services/infra_registry.py` | **Low** — mirrors render.yaml / docs drift sweeps | **Med** — infra probes / registry stale | **Stay git** as canonical ops inventory **or** generated artifact checked in (tie to REGISTRY.md workflows) |
| `kg_validation.json` | `app/services/kg_validation.py` | **Scheduled** — validator overwrites structured report | **Med** — integrity signals missing (**related: T2.15** KG checks, not T2.10 table) | **Postgres** run records + optional blob for full report |
| `lighthouse_ci_runs.json` | `app/services/operating_score_collectors/web_perf_ux.py` | **CI / scheduled ingest** | **Low–med** — web perf pillar degrades | **Object storage / DB**, not durable git growth |
| `long_tail.json` | `app/audits/cross_app_ui_redundancy.py` | **Rare** — audit proposes entries | **Low** — backlog proposals lost | **Postgres** optional backlog table **or** stay git |
| `merge_queue.json` | `app/services/system_health.py`, `app/services/blitz_progress_poster.py` | **Runtime** — orchestrator updates queue | **Med** — merge-queue UX + health wrong | **Postgres** queue **or** Redis for ephemeral queue state |
| `operating_score.json` | `app/services/operating_score.py`, collectors, `app/services/anomaly_detection.py`, `app/services/kg_validation.py` | **Scheduled** — frequent rewrite / history growth | **High** — POS / dashboards / gates | **Postgres** time-series + latest snapshot row |
| `paperwork_links.json` | `app/services/paperwork_links.py` | **Low** | **Low** | **Postgres** small table **or** stay git |
| `pr_outcomes.json` | `app/services/pr_outcomes.py`, `app/schedulers/pr_outcome_recorder.py`, `app/services/sprint_velocity.py`, `app/services/self_improvement.py`, `app/services/auto_revert.py`, `app/services/auto_distillation.py`, collectors | **Runtime** — append on merge + horizon updates | **High** — WS-62 loop, labels backfill inputs (**T2.17**) | **Postgres** (`pr_outcomes` / facts table); JSON retention optional |
| `probe_results.json` | `app/schedulers/ux_probe_runner.py`, `app/schedulers/probe_failure_dispatcher.py`, `app/api/probe_results.py` | **Runtime** — rolling ~1000 rows | **Med** — probe UX + dispatch degraded | **Postgres** or **time-limited store** |
| `self_merge_promotions.json` | `app/services/self_merge_gate.py`, `app/services/self_improvement.py` | **Runtime** — updates on merge milestones | **Med** — self-merge promotion ladder wrong | **Postgres** small config/state |
| `sprint_velocity.json` | `app/services/sprint_velocity.py` | **Scheduled** — weekly compute writes | **Med** — velocity metrics stale | **Postgres** computed rollup **or** derived-only (no file) |
| `vendors.json` | `app/services/vendors.py` | **Low** — curated vendor catalog | **Med** — vendor intelligence gaps | **Stay git** (ops catalog) **or** Postgres if edited in UI often |
| `web_push_subscriptions.json` | `app/services/web_push.py` | **Runtime** — subscribe/unsubscribe | **Med** — push fanout breaks until clients re-register | **Postgres** (standard for push endpoints) |
| `weekly_retros.json` | `app/services/self_improvement.py` | **Scheduled / weekly** | **Med** — retros missing | **Postgres** or append to **episodes** / doc store |
| `workstream_candidates.json` | `app/services/self_prioritization.py`, `app/services/self_improvement.py` | **Runtime / brain jobs** | **Med** — prioritization inputs missing | **Postgres** candidate queue |

**Unreferenced in `apis/brain/app/` by filename grep:** **None** of the 27 committed JSON files — each has at least one loader or path constructor under `app/`. (If a path were missed, treat as **unreferenced (verify)** and re-grep after refactors.)

**Related paths not in this glob:** `dispatch_queue.json` is referenced in schedulers but **not** present as a committed file under `data/` (likely runtime-created or optional). `vercel_billing.json`, `dora_metrics.json`, `pending_audit_conversations.json` are mentioned in code comments — **not** in the 27-file inventory (absent or non-JSON naming).

---

## Classification: snapshot vs registry vs append-only / log

| Kind | Files | Notes |
|------|-------|------|
| **Registry / catalog** (curated lists, replace wholesale on edit) | `app_registry.json`, `audit_registry.json`, `decommissions.json`, `infra_registry.json`, `vendors.json`, `expense_routing_rules.json` | Human-maintained or seeded; schema/version headers common |
| **Append-only / log / rolling history** | `agent_dispatch_log.json` (`dispatches` array), `pr_outcomes.json` (`outcomes`), `probe_results.json` (rolling cap), `weekly_retros.json`, `web_push_subscriptions.json` (subscription rows), `expenses.json`, `bills.json`, `incidents.json` | Frequent appends; conflict-prone under git without locks |
| **Snapshot / computed artifact** (point-in-time or overwritten rollup) | `kg_validation.json`, `lighthouse_ci_runs.json`, `axe_runs.json`, `sprint_velocity.json`, `operating_score.json`, `merge_queue.json`, `anomaly_alerts.json`, `long_tail.json` | Often regenerated by jobs; git tracks template + last run for dev convenience |
| **Hybrid** | `goals.json`, `self_merge_promotions.json`, `workstream_candidates.json` | Mix of stable structure + changing content |

---

## Cross-reference: master plan **T2.10 snapshot kill** (`apps/studio/src/data/`)

**Important distinction:** [T2.10](../plans/PAPERWORK_LABS_2026Q2_MASTER_PLAN.md) names **13 JSON snapshots under `apps/studio/src/data/`** (e.g. `workstreams.json`, `goals.json`, `personas-snapshot.json`, …) to replace with Brain **`GET /admin/...`** endpoints and DB-backed data. **Those paths are not the same directory as `apis/brain/data/*.json`.** This inventory does **not** duplicate that file list one-for-one.

**Overlap / alignment**

| Inventory row | Relation to T2.10 |
|---------------|-------------------|
| **`goals.json`** (`apis/brain/data/`) | **Same domain** as Studio `goals.json` / `GET /admin/goals` — **clearly snapshot-class for migration**: JSON must converge on Postgres + API as **T2.0 goals unification** and **T2.10** complete. |
| **`kg_validation.json`** | Not in the T2.10 table (different from Studio `knowledge-graph.json`). Belongs to **T2.15** / integrity automation family — still **generated snapshot** to move off raw git over time. |
| **CI / metric dumps** (`lighthouse_ci_runs.json`, `axe_runs.json`, `sprint_velocity.json`) | Same **anti-pattern theme** as snapshots (static JSON holding live-changing observability) — migrate to DB/object storage; not listed as T2.10 rows because they are under Brain data, not Studio `src/data/`. |
| **All other rows** | **Out of scope** for the literal T2.10 file list; judge by **T3.0** ops-state vs reference-data doctrine (most belong **Postgres**, not `packages/data`). |

**Snapshot-class rows (for T2.10 *family* / kill-the-static-export pattern)** — clearest first: **`goals.json`**, then generated/metric artifacts **`kg_validation.json`**, **`lighthouse_ci_runs.json`**, **`axe_runs.json`**, **`sprint_velocity.json`**, **`operating_score.json`** (history + `current`), **`merge_queue.json`** (ephemeral queue serialized to disk).

---

## References

- Master plan T3.0a / T2.10 / T2.10a: [`docs/plans/PAPERWORK_LABS_2026Q2_MASTER_PLAN.md`](../plans/PAPERWORK_LABS_2026Q2_MASTER_PLAN.md)
- Cheap-agent merge queue rule: [`../../.cursor/rules/cheap-agent-fleet.mdc`](../../.cursor/rules/cheap-agent-fleet.mdc)
