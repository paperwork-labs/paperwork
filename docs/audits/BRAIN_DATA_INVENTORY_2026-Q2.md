# Brain Data Inventory — Q2 2026

**Status**: PROPOSED  
**Date**: 2026-05-04  
**Authored by**: T3.0a cheap-agent (composer-1.5)  
**Feeds**: T3.0 stack audit, T2.10 snapshot kill scope  

## Summary

- **33** files in `apis/brain/data/` (extensions: `.json`, `.yaml`, `.yml`, `.jsonl`, `.flag`, `.lock` — no `.lock` present in tree).
- **A** reference/seed: **6**
- **B** ops state (migrate to Postgres): **14**
- **C** snapshot (kill per T2.10): **7**
- **D** learning data (move to `brain_episodes` / `agent_dispatches` or adjacent tables): **4**
- **NEEDS_HUMAN**: **2**

Counts sum to **33**.

## Inventory table

| File | Size (lines) | Classification | Last commit¹ | Notes |
|------|--------------|----------------|--------------|-------|
| `agent_dispatch_log.json` | 29 | D | 2026-04-29 | Schema + `dispatches[]`; cheap-agent fleet dispatch log |
| `anomaly_alerts.json` | 5 | C | 2026-04-28 | Z-score alerts; empty shell — recomputable from metrics pipeline |
| `app_registry.json` | 600 | C | 2026-05-04 | Repo-wide app conformance / LOC signals — regenerate via stack audit / scanner |
| `audit_registry.json` | 105 | A | 2026-04-30 | Catalog of Brain audits (`runner_module`, cadence) — PR-reviewed seed |
| `axe_runs.json` | 5 | C | 2026-04-28 | axe-core run history placeholder — CI / collector is source of truth |
| `bills.json` | 1 | B | 2026-04-30 | Empty `[]` — intended vendor bill ledger (T2.x expense family) |
| `brain_paused.flag` | 0 | B | 2026-04-28 | Runtime pause sentinel — belongs with scheduler / feature-flag store |
| `cost_ledger.json` | 33 | B | 2026-04-30 | Spend entries + `monthly_budgets` — CFO / cost ops (T2.x) |
| `decommissions.json` | 19 | B | 2026-04-28 | Lifecycle records (`status`, `decommissioned_at`) — ops, not static seed |
| `expense_routing_rules.json` | 11 | A | 2026-04-29 | Auto-approve thresholds, categories, flag rules — policy seed |
| `expenses.json` | 1 | B | 2026-04-29 | Empty `[]` — expense rows (T2.x) |
| `goals.json` | 90 | B | 2026-05-01 | Quarterly objectives / KRs — founder & Brain progress state (T2.0 overlay) |
| `incidents.json` | 5 | B | 2026-04-28 | Incident list schema — operational record (Pydantic: `schemas/incidents.py`) |
| `infra_registry.json` | 226 | A | 2026-04-30 | Curated deploy surfaces + vendor-linked inventory — canonical reference (may overlap generated docs) |
| `kg_validation.json` | 5 | C | 2026-04-28 | KG self-validate `current` + `history` — re-run `kg_self_validate` audit |
| `lighthouse_ci_runs.json` | 5 | C | 2026-04-28 | Lighthouse-CI history shell — CI artifacts regenerate |
| `long_tail.json` | 19 | B | 2026-04-28 | Deferred scope overflow queue — planning / ops backlog |
| `merge_queue.json` | 24 | B | 2026-04-28 | Cheap-agent merge queue state — transient orchestration (T2.10 / Redis candidate) |
| `operating_score.json` | 344 | C | 2026-04-30 | POS composite + pillar notes — derived from collectors + registries |
| `operating_score_spec.yaml` | 74 | A | 2026-04-29 | POS weights, gates, pillar definitions — scoring policy seed |
| `paperwork_links.json` | 10 | B | 2026-04-30 | Clerk user ↔ org linkage — tenant ops state |
| `pr_outcomes.json` | 5 | D | 2026-04-28 | PR outcome horizons (`schemas/pr_outcomes.py`) — WS-62 learning corpus |
| `probe_results.json` | 5 | B | 2026-04-30 | Rolling UX probe results (scheduler + API) — operational buffer / alerting |
| `procedural_memory.yaml` | 219 | NEEDS_HUMAN | 2026-05-03 | See NEEDS_HUMAN — mixes human PR-reviewed rules and machine append |
| `required_env_vars.yaml` | 38 | A | 2026-04-28 | Vercel project → required env manifest (`check_pre_deploy.py`) |
| `self_merge_promotions.json` | 15 | D | 2026-04-28 | Tier graduation + merge/revert log — fleet learning (rule #7 companion) |
| `slack_routing.yaml` | 44 | NEEDS_HUMAN | 2026-04-28 | See NEEDS_HUMAN — Slack decommission vs adapter remnants |
| `social_posts.jsonl` | 0 | B | 2026-04-30 | Social post log (append-only) — growth / ops pipeline |
| `sprint_velocity.json` | 22 | C | 2026-04-28 | Weekly velocity snapshot — recompute from `gh` + workstreams (schema notes bootstrap) |
| `vendors.json` | 105 | A | 2026-04-30 | Vendor catalog (`brain_vendors/v1`) — reference seed |
| `web_push_subscriptions.json` | 1 | B | 2026-04-29 | Empty `[]` — PWA push endpoints — user/device ops |
| `weekly_retros.json` | 6 | D | 2026-04-28 | Weekly retro entries — Phase G2 self-improvement → episodic store |
| `workstream_candidates.json` | 8 | B | 2026-04-28 | Proposed workstreams before promotion to Studio `workstreams.json` |

¹ **Last commit**: `git log -1 --format=%cs -- <path>` on branch `feat/t3.0a-brain-data-inventory` at inventory time.

### Drift note (not a data file)

`operating_score_spec.yaml` references `audit_runs.json` as a measurement source for pillar `audit_freshness`; that path **does not** exist under `apis/brain/data/` in this snapshot — track under T3.0 / doc-code alignment, not this file count.

## Per-category detail

### A. Reference / seed data (keep version-controlled)

| File | Rationale |
|------|-----------|
| `audit_registry.json` | Defines which audits exist and how they run — stable product config. |
| `expense_routing_rules.json` | Expense approval policy — EA / CFO canon; small, reviewable JSON. |
| `infra_registry.json` | Curated inventory of URLs and services for probes and ops; treat as reference unless automation fully replaces it. |
| `operating_score_spec.yaml` | POS pillar weights and industry references — policy, not computed totals. |
| `required_env_vars.yaml` | Pre-deploy env manifest per Vercel project — engineering guardrail seed. |
| `vendors.json` | Canonical vendor list for renewals and cost modeling — reference data. |

### B. Ops state (migrate to Postgres)

| File | Rationale | Owner (if known) |
|------|-----------|------------------|
| `bills.json` | Bill records — empty placeholder for vendor spend. | T2.x expense / EA family |
| `brain_paused.flag` | Scheduler / automation pause bit. | T2.10 + Brain scheduler |
| `cost_ledger.json` | Ledger lines + budgets — live CFO data. | T2.x / WS-69 expense cadence |
| `decommissions.json` | Decommission workflow state (`proposed`, timestamps). | Infra / ops |
| `expenses.json` | Line-item expenses — empty today. | T2.x |
| `goals.json` | OKR-style objectives — mutable progress. | T2.0 goals (OBJECTIVES overlay) |
| `incidents.json` | Incident log — SRE-style rows. | Ops / incidents service |
| `long_tail.json` | Deferred workstream overflow — active queue. | Phase H / planner |
| `merge_queue.json` | PR merge serialization state. | Cheap-agent fleet / T2.10 |
| `paperwork_links.json` | Clerk bindings for founder/org. | Auth / tenant data |
| `probe_results.json` | Rolling synthetic UX probe results (API + dispatchers). | UX probe runner — durable buffer until DB |
| `social_posts.jsonl` | Published / queued social lines — growth ops. | Social pipeline |
| `web_push_subscriptions.json` | Browser push subscriptions. | Notifications / PWA |
| `workstream_candidates.json` | Brain proposals before Studio promotion. | WS / strategic planner |

### C. Snapshot (kill per T2.10)

| File | What regenerates it |
|------|----------------------|
| `anomaly_alerts.json` | Cost / usage anomaly job recomputing baselines. |
| `app_registry.json` | Stack modernity / repo scanner (conformance, LOC). |
| `axe_runs.json` | axe-core CI workflow + collector writing latest runs. |
| `kg_validation.json` | `kg_self_validate` audit + KG validators. |
| `lighthouse_ci_runs.json` | Lighthouse-CI workflow on `main` / labeled PRs. |
| `operating_score.json` | `operating_score` collectors reading sources listed in `operating_score_spec.yaml`. |
| `sprint_velocity.json` | GitHub PR merge stats + workstream completion job (`schemas/sprint_velocity.py`). |

### D. Learning data (move to `brain_episodes` / `agent_dispatches` or adjacent tables)

| File | Suggested destination |
|------|------------------------|
| `agent_dispatch_log.json` | `agent_dispatches` (or equivalent) — one row per dispatch with model, workstream, preflight flag, outcomes. |
| `pr_outcomes.json` | `pr_outcomes` / merge metrics table — horizons h1/h24/d7… per merged PR. |
| `self_merge_promotions.json` | Promotion / graduation table — tier, merge counts, reverts. |
| `weekly_retros.json` | `brain_episodes` (type=`weekly_retro`) or dedicated `weekly_retros` table keyed by week. |

### NEEDS_HUMAN

| File | Question |
|------|----------|
| `procedural_memory.yaml` | Rules are **appendable at runtime** (`procedural_memory` service) but also **PR-reviewed doctrine**. Should T2.10 migrate **all** rules to Postgres with optional YAML export for review, keep YAML as SOT with DB mirror, or split **bootstrap seed (A)** vs **machine-learned rows (D)**? |
| `slack_routing.yaml` | EA persona says Slack is decommissioned in favor of Brain Conversations; **no `slack_routing` loader** appears under `apis/brain/app/` in this tree. Should this file be **deleted/archived**, **migrated** if any Slack adapter remains, or kept as dormant reference until adapter code is removed? |

## Stale files (>60 days untouched)

**None** by `git log -1` date: every file’s last touching commit is **on or after 2026-04-28**, which is **within 60 days** of the inventory date **2026-05-04** (threshold **before 2026-03-05**).

---

## Acceptance checklist (T3.0a)

- [x] `docs/audits/BRAIN_DATA_INVENTORY_2026-Q2.md` exists.
- [x] Every file under `apis/brain/data/` with the scoped extensions is classified (33/33).
- [x] Summary counts sum to total file count (6 + 14 + 7 + 4 + 2 = 33).
- [x] NEEDS_HUMAN entries name concrete founder/architecture questions.
