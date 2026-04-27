---
owner: engineering
last_reviewed: 2026-04-24
doc_kind: plan
domain: data
status: active
---
# Medallion Audit — 2026 Q2

> **Status**: Phase 0.D complete — medallion import gate is strict; remaining cross-layer edges use inline `# medallion: allow` with tracked rationales.
> **Generated**: 2026-04-23 by `scripts/medallion/tag_files.py`
> **Next review**: After next major `app/services/` layout change

This document classifies every `.py` file under `app/services/` into a medallion layer and records the target move path + risk + blockers. It's the **input contract for Phase 0.C** — the migration script `scripts/medallion_migrate.py` consumes this mapping.

Reference: `docs/archive/2026-04-22-medallion-wave-0-stage-setting.md` (archived; decisions extracted into this doc + `PLATFORM_REVIEW_2026Q2.md`.)

---

## Summary

Total classified: **268 files** across 37 top-level directories.

| Layer | Files | % | Status |
|---|---|---|---|
| bronze | 23 | 9% | Partially native (`bronze/` = 6 files). Brokers in `portfolio/` not yet moved. |
| silver | 87 | 32% | 0% native. All grandfathered in `market/`, `portfolio/`, `tax/`, `corporate_actions/`, `symbols/`, `intelligence/`, `data_quality/`. |
| gold | 57 | 21% | Partially native (`gold/` = 8 files). Stragglers in `strategy/`, `picks/`, `backtest/`, `ml/`, `narrative/`, `signals/`, `risk/`. |
| execution | 20 | 7% | All native in `execution/`. Phase 0.C = "tag only, don't move" (fourth layer per §6.6). |
| ops | 81 | 30% | Cross-cutting infra; not part of medallion data flow. Stay put. |

---

## Directory → Layer mapping (authoritative)

### bronze — raw ingestion, broker I/O, external API

| Dir | Files | Native? | Target in Phase 0.C |
|---|---|---|---|
| `bronze/` | 6 | ✅ native | stay |
| `aggregator/` | 1 | ❌ | move to `bronze/aggregator/` |
| `portfolio/ibkr/` | 4 | ❌ | move to `bronze/ibkr/` — **DANGER ZONE, pre-approval required** |
| `portfolio/schwab_sync_service.py` | 1 | ❌ | move to `bronze/schwab/sync_service.py` |
| `portfolio/tastytrade_sync_service.py` | 1 | ❌ | move to `bronze/tastytrade/sync_service.py` |
| `portfolio/broker_sync_service.py` | 1 | ❌ | move to `bronze/broker_sync_service.py` |
| Other `portfolio/*` (broker-specific files) | ~10 | ❌ | per-file classification required — see "Blockers" below |

### silver — enrichment, analytics, indicators, cross-broker reconciliation

| Dir | Files | Target |
|---|---|---|
| `market/` | 43 | `silver/` (subdivided: `silver/indicators/`, `silver/regime/`, `silver/math/`) — **Pass 2 of 0.C** |
| `portfolio/portfolio_analytics_service.py` | 1 | `silver/portfolio_analytics.py` |
| `portfolio/closing_lot_matcher.py` | 1 | `silver/closing_lot_matcher.py` |
| `portfolio/tax_lot_service.py`, `activity_aggregator.py`, etc. | ~10 | `silver/portfolio/` (subfolder) |
| `tax/` | 4 | `silver/tax/` |
| `corporate_actions/` | 4 | `silver/corporate_actions/` |
| `data_quality/` | 3 | `silver/data_quality/` |
| `intelligence/` | 2 | `silver/intelligence/` |
| `symbols/` | 2 | `silver/symbols/` |

### gold — strategy outputs, picks, scoring, backtests, narratives

| Dir | Files | Target |
|---|---|---|
| `gold/` | 8 | ✅ stay (already native) |
| `strategy/` | 11 | `gold/strategy/` — **Pass 4 of 0.C** |
| `picks/` | 10 | `gold/picks/` — **Pass 4 of 0.C** |
| `backtest/` | 5 | `gold/backtest/` |
| `ml/` | 1 | `gold/ml/` |
| `narrative/` | 6 | `gold/narrative/` |
| `signals/` | 1 | `gold/signals/` |
| `risk/` | 4 | **SPLIT**: some files → `gold/risk/`, some → `execution/risk/`. Manual review required before 0.C Pass 4. |

### execution — fourth medallion layer (§6.6), reads gold + writes orders

| Dir | Files | Target |
|---|---|---|
| `execution/` | 20 | ✅ stay (fourth layer — declared per §6.6 decision) |

### ops — cross-cutting infra (not part of medallion)

These stay in place. They get the `medallion: ops` docstring tag but are **not subject to bronze/silver/gold import rules** (the Phase 0.B lint rule treats `ops/*` as a "may import from anywhere" escape hatch where necessary).

| Dir | Files | Purpose |
|---|---|---|
| `agent/` | 17 | Brain's AI agent tooling (client-side) |
| `billing/` | 7 | Stripe, subscription mgmt |
| `brain/` | 1 | Brain integration shim |
| `clients/` | 5 | External HTTP clients |
| `connections/` | 1 | OAuth/API connection mgmt |
| `core/` | 1 | App-wide utilities |
| `deploys/` | 3 | Render deploy helpers |
| `engine/` | 1 | Legacy engine entry |
| `gdpr/` | 2 | Data export/delete |
| `multitenant/` | 3 | Org/workspace mgmt |
| `notifications/` | 3 | Email, Discord |
| `oauth/` | 6 | OAuth flow handlers |
| `observability/` | 2 | Metrics, logging |
| `ops/` | 1 | Admin ops |
| `pipeline/` | 2 | Pipeline orchestrator |
| `security/` | 4 | Credential encryption, PKCE |
| `share/` | 2 | Public share links |
| `__init__.py`, `cache.py` | 2 | Services package-level |

---

## Known blockers (resolve before Phase 0.C)

### B1 — DANGER ZONE files require pre-approval

Per `.cursor/rules/protected-regions.mdc`, these files cannot move without founder sign-off:

- `app/services/market/indicator_engine.py` → `silver/indicators/indicator_engine.py`
- `app/services/market/stage_classifier.py` → `silver/regime/stage_classifier.py`
- `app/services/market/regime_engine.py` → `silver/regime/regime_engine.py`
- `app/services/portfolio/ibkr/*` (4 files) → `bronze/ibkr/*`

**Mitigation**: diff proves zero-content change (path-only), run `git diff --stat` showing only file rename + import rewrites.

### B2 — `portfolio/` requires per-file classification ✅ RESOLVED 2026-04-23

Resolution in `scripts/medallion/generate_move_map.py`:

- `portfolio/ibkr/*` (4 files) → `bronze/ibkr/*` (bronze — broker SDK calls).
- `portfolio/{schwab,tastytrade,ibkr,broker}_sync_service.py` → `bronze/<broker>/sync_service.py` (bronze — broker I/O).
- `portfolio/plaid/*` → `bronze/plaid/*` (bronze — external API).
- `portfolio/adapters/*` → `bronze/adapters/*` (bronze — broker adapter layer).
- `portfolio/portfolio_analytics_service.py`, `closing_lot_matcher.py`, `tax_lot_service.py`, `tax_loss_harvester.py`, `day_pnl_service.py`, `discipline_trajectory_service.py`, `drawdown.py`, `reconciliation.py`, `broker_catalog.py`, `monitoring.py`, `activity_aggregator.py` → `silver/portfolio/*` (silver — cross-broker analytics).
- `portfolio/account_config_service.py`, `account_credentials_service.py`, `account_type_resolver.py` → **stay** (ops — cross-cutting infra for account management).

Full listing: `medallion_move_map.yaml` — pass `pass2_silver_portfolio`, `pass3_bronze_core`, `ops_stays_portfolio_helpers`.

### B3 — Celery `task_path` coverage ✅ RESOLVED 2026-04-23

Full scan of `backend/` (non-test) for string literals matching `"backend\.services\.*"`:

| File | Count | Targets `services/` subtree | Phase 0.C action |
|---|---|---|---|
| `app/services/execution/__init__.py` | 5 | `execution.*` | **no-op** — `execution/` stays in place |
| `app/services/execution/shadow_mark_to_market.py` | 1 | `execution.*` | **no-op** — stays |
| `app/tasks/job_catalog.py` | 1 | `execution.shadow_mark_to_market.run` | **no-op** — stays |
| `app/tasks/celery_app.py` | 1 | `execution.shadow_mark_to_market` | **no-op** — stays |
| `app/models/strategy.py` | 2 | `atr_options_strategy`, `dca_strategy` | ⚠ **dead refs** — modules don't exist; flag for cleanup pre-0.C |

Also: all `task="app.tasks.*"` entries in `job_catalog.py` point at `app/tasks/`, which is **not touched by 0.C** (services-only scope).

Alembic migrations, frontend code, and YAML configs contain **zero** `app.services.*` string literals (verified).

**Attack surface**: 2 string refs to clean up (both dead refs in `models/strategy.py`, lines 518 + 532). The migration script's string-rewriting pass can be a simple pattern-replace; no preservation-of-behavior concerns.

### B4 — `risk/` splits across gold and execution ✅ RESOLVED 2026-04-23

Four files in `services/risk/`, classified after reading imports + callers:

| File | Layer | Target | Rationale |
|---|---|---|---|
| `risk/pre_trade_validator.py` | execution | `execution/risk/pre_trade_validator.py` | Called by broker executors on live order path — execution-tier |
| `risk/circuit_breaker.py` | gold | `gold/risk/circuit_breaker.py` | Portfolio-level halting signal, not order-level |
| `risk/firm_caps.py` | gold | `gold/risk/firm_caps.py` | Policy/config data model |
| `risk/account_risk_profile.py` | gold | `gold/risk/account_risk_profile.py` | Portfolio-level risk aggregation |

Recorded in `medallion_move_map.yaml` under pass `pass4_risk_split`.

### B5 — `agent/` vs `brain/` overlap

`services/agent/` (17 files) is Brain's client-side tooling. `services/brain/` (1 file) is the integration shim. These could merge. Not a Phase 0 concern — park as tech-debt for Wave 1.

---

## Import rule matrix (for Phase 0.B CI lint)

```
bronze/    → may import from: (core stdlib + clients/ + ops/security/ + ops/observability/)
silver/    → may import from: bronze/ + core stdlib + clients/ + ops/
gold/      → may import from: silver/ + bronze/ + core stdlib + ops/
execution/ → may import from: gold/ + silver/ + core stdlib + ops/
ops/       → may import from: anywhere (escape hatch, but use sparingly)
```

**Banned cross-layer imports** (these should fail CI):
- `bronze/` importing from `silver/`, `gold/`, `execution/` (upward dependency)
- `silver/` importing from `gold/`, `execution/`
- `gold/` importing from `execution/`

**Exceptions** must use a magic comment: `# medallion: allow <target-layer> for <reason>`

---

## Phase 0.C execution order (dependency-safe)

Full per-file move map lives at `medallion_move_map.yaml` (generated by `scripts/medallion/generate_move_map.py`). Summary:

| Pass | Description | File count |
|---|---|---|
| 1 | Leaf utilities (`market/dataframe_utils.py`, `atr_series.py`, `coverage_utils.py`, `stage_utils.py`, `backfill_params.py`, `constants.py`, `rate_limiter.py`) → `silver/math/` | 7 |
| 2 | Silver core (`market/` indicators + regime, `tax/`, `corporate_actions/`, `data_quality/`, `intelligence/`, `symbols/`) → `silver/` | 54 |
| 2 | Silver portfolio (`portfolio/portfolio_analytics_service.py`, `closing_lot_matcher.py`, analytics files) → `silver/portfolio/` | 12 |
| 3 | Bronze core (`portfolio/ibkr/*`, `portfolio/{schwab,tastytrade,broker}_sync_service.py`, `plaid/*`, `adapters/*`) → `bronze/<broker>/` | 19 |
| 3 | Bronze market providers (`market/providers/*`) → `bronze/market/providers/` | 4 |
| 3 | Bronze aggregator (`aggregator/*`) → `bronze/aggregator/` | 1 |
| 4 | Gold stragglers (`strategy/`, `picks/`, `backtest/`, `ml/`, `narrative/`, `signals/`) → `gold/*` | 43 |
| 4 | Risk split (4 files — see B4) | 4 + 1 |
| 5 | `execution/*` — stays put (fourth medallion layer) | 20 stays |
|   | **Total moves** | **145** |
|   | **Total stays** (native + ops + execution + services root) | **124** |

Regenerate with:
```bash
python3 scripts/medallion/generate_move_map.py --stats   # summary
python3 scripts/medallion/generate_move_map.py > medallion_move_map.yaml
```

---

## Status tracker

| Phase | Target date | Status | Notes |
|---|---|---|---|
| 0.A — Tags + audit | 2026-04-23 | ✅ DONE | 268 files tagged, this doc produced |
| 0.A — DAG swimlanes | 2026-04-23 | ✅ DONE | `PipelineDAG.tsx` bands + legend shipped in PR #127 (bronze/silver/gold/ops colored bands behind node grid, inline legend). Also added a company-wide medallion DAG to `infra/portal/index.html`. |
| 0.A — Prose sweep | 2026-04-23 | ✅ DONE | `ARCHITECTURE.md` + `AGENTS.md` updated with 4-layer medallion + pillar cross-map. PRD.md unchanged (historically frozen; MASTER_PLAN is source of truth) |
| 0.B — Silver scaffold + CI rule | 2026-04-23 | ✅ DONE | `silver/__init__.py`, `scripts/medallion/check_imports.py`, `make medallion-check`, CI job added. 21 known-debt violations auto-captured as waivers. |
| 0.C prep — per-file move map + blocker resolution | 2026-04-23 | ✅ DONE | `medallion_move_map.yaml` generated (145 moves / 124 stays); B2/B3/B4 blockers resolved in-doc; `task_path` attack surface = 2 dead refs in `models/strategy.py`. |
| 0.C — File migrations | 2026-04-23 | ✅ DONE | PR [#116](https://github.com/paperwork-labs/paperwork/pull/116) merged (Medallion Wave 0.C). 145 files moved via `scripts/medallion_migrate.py`; 2085 backend tests passing; stale re-exports in `silver/market/__init__.py`, `silver/portfolio/__init__.py`, `gold/risk/__init__.py`, `gold/__init__.py` removed to break circular imports; 38 test-file string literals rewritten. |
| 0.D — Shim removal + strict CI | ~2026-05-07 | ✅ DONE | Account helpers retagged `ops` where appropriate; `gold/position_sizing` owns Stage Analysis sizing; bronze→silver edges use permanent `# medallion: allow` lines; `check_imports` invoked with `--strict` in CI; `app/services/__init__.py` verified free of D88 re-export shims. |

---

Closing this document at Phase 0.D: mark every row `Verified at target path: <path>`.

---

## Phase 0.D checklist

**Target**: ~2026-05-07 (2 weeks after 0.C landed).

1. Drain the 21 inherited-debt waivers captured by `scripts/medallion/check_imports.py` at 0.B. Each waiver must either:
   - Move the importer or importee to the correct layer, or
   - Add a permanent `# medallion: allow <layer> for <reason>` with a tracked reason.
2. Flip `check_imports.py` from warn-mode to strict — no new waivers accepted without PR-level approval.
3. Remove remaining D88-era shims in `app/services/__init__.py` (the silver/bronze re-export fallbacks left for Wave 0.C safety).
4. Sweep `from app.services.{market,portfolio,tax,risk,strategy,picks,backtest,ml,narrative,signals}` imports outside tests — each must either be rewritten to the canonical medallion path or declared ops.
5. Audit `mock.patch("app.services.*")` string literals one more time (see B3) now that 0.C has settled.
6. Update this doc's Status tracker: all rows → ✅ Verified.

Tracking: when 0.D opens, spin a single tracking issue on `paperwork-labs/paperwork` labelled `infrastructure`, `epic` referencing this checklist.

_Extracted from docs/archive/2026-04-22-medallion-wave-0-stage-setting.md._

## Wave 0 stage-setting decisions (handoff 2026-04-22)

### TL;DR (medallion + warehouse execution scope)

- **Meta finding**: we are ~30% aligned with the medallion / "three pillars decoupled" story we're publishing. Bronze exists as a folder (3/6 brokers in it). Silver does not exist as a folder at all (0 files, 0 imports). Gold exists with 7 native files but ~30 more gold-shaped files still live in `strategy/`, `picks/`, `execution/`. The system-status DAG happens to lay out as bronze→silver→gold but has zero medallion labels.
- **Proposed**: insert a **Wave 0 — Medallion stage-setting** before W1 (safety envelope) instead of running medallion as parallel W16 over 6 weeks. Compresses to **6–9 days focused work + 2-week passive shadow-import bake**.
- **Founder asked for the plan in detail with no implementation yet**. This handoff captures that plan plus the four pre-execution decisions still needed before any code lands.
- **Decision gates not yet answered (block execution)**:
  2. Single atomic migration PR, or split silver-first / bronze+gold-second (recommended split).
  3. Acknowledge `execution/` as a fourth medallion layer (recommended yes).
- **Do NOT touch any DANGER ZONE file** (per `.cursor/rules/protected-regions.mdc`) without explicit founder approval. Wave 0 moves three of them (`indicator_engine.py`, `stage_classifier.py`, `regime_engine.py`) — see §6.2.

The current Wave 16 in PLATFORM_REVIEW Ch 11 describes a **6-week parallel** medallion migration. **The Wave 0 proposal in this handoff supersedes that timeline if accepted by the founder.** If accepted, PLATFORM_REVIEW Ch 11 needs an amendment to renumber Wave 16 → Wave 0 and adjust the wave count from 16 back to 15 (or keep Wave 16 and call Wave 0 "pre-W1 prerequisite"). Editorial choice for next chat.

### §3 The receipts — what's actually true on disk (3.1–3.5)

#### 3.1 Bronze — 50% real

```bash
$ ls app/services/bronze/
__init__.py  coinbase/  etrade/  tradier/
```

The three NEW brokers are bronze-native ([D130](../KNOWLEDGE.md), [D132](../KNOWLEDGE.md), Coinbase). The three CORE brokers are still grandfathered:

```bash
$ ls app/services/portfolio/ | grep -E "ibkr|schwab|tastytrade"
ibkr/                              # subdir, ~6 files
schwab_sync_service.py             # 32.7K
tastytrade_sync_service.py         # 25.3K
```

None of the grandfathered files carry a `medallion: bronze` docstring tag. A reader landing in the repo cold cannot tell they are bronze.

#### 3.2 Silver — 0% real

```bash
$ ls app/services/silver/ 2>&1
ls: app/services/silver/: No such file or directory

$ rg "from app.services.silver" backend/
(no matches)
```

What we call "silver" lives in `app/services/market/`, `app/services/portfolio/portfolio_analytics_service.py`, `app/services/portfolio/closing_lot_matcher.py`, `app/services/tax/*`. Roughly 25 files, zero docstring tags, zero physical layout.

#### 3.3 Gold — 60% real

```bash
$ ls app/services/gold/
__init__.py  conviction_pick_generator.py  options_chain_surface.py
peak_signal_engine.py  pick_quality_scorer.py  pick_scorer_config.py
tax_aware_exit_calculator.py  trade_card_composer.py  winner_exit_advisor.py
```

7 native gold files. But the older gold-shaped code is in `app/services/strategy/` (rule evaluator, backtest, walk-forward, signal generator, AI strategy builder) and `app/services/picks/candidate_generator.py` plus `app/services/picks/generators/`.

#### 3.4 Execution — orthogonal to medallion (currently mis-classified)

```bash
$ ls app/services/execution/
approval_service.py  broker_adapter.py  broker_base.py  broker_router.py
exit_cascade.py  ibkr_executor.py  order_manager.py  paper_executor.py
risk_gate.py  runner_state_service.py  shadow_mark_to_market.py
shadow_order_recorder.py  slippage_tracker.py
```

These don't fit bronze/silver/gold cleanly. They read gold outputs and write orders to real money. **Recommendation in §6.6**: declare `execution/` a fourth layer. Cleaner story than forcing it into gold.

#### 3.5 The DAG accidentally already shows medallion

`frontend/src/components/pipeline/PipelineDAG.tsx` row layout (lines 33–88):

| Row | Stage IDs | In medallion terms |
|---|---|---|
| 0 | `constituents` → `tracked_cache` → `daily_bars` | bronze |
| 1 | `regime` · `indicators` · `exit_cascade` | silver (+ gold straggler) |
| 2 | `scan_overlay` · `strategy_eval` · `snapshot_history` | gold + silver ledger |
| 3–4 | `digest` · `health_check` · `mv_refresh` · `audit` · `warm_dashboard` | observability / ops |

Architecturally correct, rhetorically invisible: zero labels, zero color bands, no legend. Adding swimlane bands behind the existing node grid would make the DAG the **living org chart of the warehouse** with no data-model change. ~80 lines of JSX in Phase 0.A.

### §4 The Wave 0 proposal (4 phases, 6–9 days + 2-week bake)

> **Status**: founder reviewed the detail level and asked for it captured in a handoff doc on this PR. **No implementation has begun.** All file paths and counts below are accurate as of `ea99062e` on this branch.

#### Phase 0.A — Rhetorical honesty + mechanical tags (1 day)

1. Module-level docstring tag on every file under `app/services/<dir>/`: `"""medallion: bronze"""` / `silver` / `gold` / `execution` / `ops`. ~100 files. `sed`-able. Zero behavior change.
2. `PipelineDAG.tsx` gets four horizontal swimlane bands (bronze / silver / gold / ops) behind the existing node grid, with a legend. Design tokens from `frontend/src/constants/chart.ts`. ~80 lines JSX.
3. Prose sweep mapping pillars ↔ layers:
   - `docs/ARCHITECTURE.md` Three Pillars + Medallion Architecture sections.
   - `docs/axiomfolio/plans/PLATFORM_REVIEW_2026Q2.md` Ch 1.8.
   - `docs/PRD.md` system overview.
   - `AGENTS.md` Three Pillars table.
4. New doc `docs/axiomfolio/plans/MEDALLION_AUDIT_2026Q2.md`: one row per file, current path → target layer → move risk → blocker (e.g. "referenced in `job_catalog.py` task_path"). This is the input to Phase 0.C.
5. D127 + D145 entries amended with current-state numbers (3/6 brokers in bronze, 0 files in silver, 7 files in gold native + ~55 grandfathered).

**Reversibility**: trivial. Revert one PR. Docstrings + swimlanes vanish; nothing else changes.

#### Phase 0.B — Silver scaffold + CI gate (1–2 days)

1. `app/services/silver/__init__.py` created with module docstring defining the layer contract.
2. Custom lint rule (Ruff plugin if its plugin API supports import-graph rules; else pylint custom checker via astroid). Enforces:
   - `app/services/bronze/**` cannot import from `silver/`, `gold/`, `strategy/`, `picks/`, `execution/`.
   - `app/services/silver/**` cannot import from `gold/`, `strategy/`, `picks/`, `execution/`.
   - Anything outside `gold/` / `strategy/` / `picks/` cannot write to gold tables (data-layer rule, deferred to W3.5 — see §6.5).
3. Wired into `pre-commit` + GH Actions CI. `make lint` fails on violations.
4. Tested with 3–4 deliberate violations (one per kind), then removed.
5. Exception mechanism: `# medallion: allow cross-layer for <reason>` magic comment for the ≤5 known technical-debt imports the ARCHITECTURE.md already flags.

**Reversibility**: trivial. Revert one PR. Rule removed, silver folder empty and harmless.

#### Phase 0.C — Automated atomic migration (3–5 days)

The compression-pays-off phase. **Requires founder freeze window** (§6.1).

1. **Migration script** at `scripts/medallion_migrate.py`:
   - Input: `medallion_move_map.yaml` with `{old_path: new_path}` per file.
   - `git mv` in one pass.
   - Rewrites every `from app.services.X.Y import ...` and `import app.services.X.Y` across `backend/`, `tests/`, `alembic/`, `tasks/`.
   - Rewrites `task_path="app.tasks...."` and `"app.services...."` strings in `job_catalog.py`, Celery Beat schedules, `agent/tools.py` dotted-path lookups.
   - Updates relative imports.
   - Runs `ruff --fix`, `isort`, `black`.
   - `python -c "import app.api.main"` to catch import-time failures.
   - `pytest --collect-only` to catch test-import failures.
   - Exits non-zero on any failure.

2. **Move order** (dependency-safe):
   - **Pass 1** — leaf utilities: `market/dataframe_utils.py`, `market/atr_series.py`, `market/coverage_utils.py` → `silver/math/`.
   - **Pass 2** — silver core: `market/indicator_engine.py`, `stage_classifier.py`, `regime_engine.py`, `portfolio/portfolio_analytics_service.py`, `portfolio/closing_lot_matcher.py`, `tax/*` → `silver/`.
   - **Pass 3** — bronze core: `portfolio/ibkr/*`, `portfolio/schwab_sync_service.py`, `portfolio/tastytrade_sync_service.py`, `portfolio/broker_sync_service.py` → `bronze/<broker>/`.
   - **Pass 4** — gold stragglers: `strategy/` → `gold/strategy/`, `picks/` → `gold/picks/`.
   - **Pass 5** — `execution/` stays put; tagged as fourth layer (§6.6).

3. **Shadow re-exports** for the 2-week bake. Every old location keeps a minimal `__init__.py`:
   ```python
   """medallion: grandfathered shim; remove after 2026-05-13. See D145."""
   from app.services.silver.indicator_engine import *  # noqa: F401,F403
   import warnings
   warnings.warn(
       "app.services.market.indicator_engine is moving to app.services.silver; "
       "update imports by 2026-05-13 (D145).",
       DeprecationWarning, stacklevel=2,
   )
   ```
   External callers (Brain, future plugins) keep working through the bake. Internal callers all updated by the script in the same PR.

4. **PR strategy** — recommended split (decision §6.2):
   - **PR A**: Phase 0.C Pass 1 + Pass 2 (silver moves) + shims.
   - **PR B**: Phase 0.C Pass 3 + Pass 4 (bronze + gold moves) + shims.
   Each PR independently green on `make test-all`, `npm run type-check`, `docker compose up` smoke.

5. **Celery `task_path` registration**: deploy with both old + new paths registered for 1 week. Beat schedules updated to new paths. Old paths emit `warnings.warn` but still execute. Prevents in-flight scheduled tasks from 404'ing on first post-deploy Beat tick.

#### Phase 0.D — Shadow removal + final cleanup (1 day, 2 weeks after 0.C lands in prod)

1. Shadow `__init__.py` shims deleted.
2. Old `task_path` registrations removed.
3. CI rule upgrades from "warn + tagged exceptions" to "strict; no exceptions without an approved issue reference."
4. `docs/axiomfolio/plans/MEDALLION_AUDIT_2026Q2.md` closed out — every file verified at target path.
5. `PLATFORM_REVIEW_2026Q2.md` Ch 11 Wave 16 rewritten as Wave 0, completed.

### §5 Compressed timeline

| Day | Phase | What ships | Reversible |
|---|---|---|---|
| 1 | 0.A | Tags + DAG swimlanes + prose + MEDALLION_AUDIT.md + D127/D145 honesty update | Trivially |
| 2 | 0.B | `silver/` folder + CI lint rule + tests | Trivially |
| 3 | 0.C Pass 1 | Leaf utilities moved (~10 files) | Revert one PR |
| 4 | 0.C Pass 2 | Silver core moved (~25 files) + shadow shims | Revert one PR |
| 5 | 0.C Pass 3 | Bronze core moved (~15 files) + shadow shims + danger-zone approval | Revert one PR |
| 6 | 0.C Pass 4 | Gold stragglers moved + `strategy/` + `picks/` relocated | Revert one PR |
| 7 | 0.C verification | Full `make test-all`, prod deploy, Render watch for 24hrs | Roll back deploy |
| ~Day 21 | 0.D | Shadow shims removed, CI gate strict | Revert one PR |

**Real elapsed**: 7 focused days + 2-week passive bake before final cleanup.

### §6.2 – §6.7 — Risks and mitigations (medallion migration)

#### 6.2 Danger-zone approvals

`app/services/market/indicator_engine.py`, `stage_classifier.py`, `regime_engine.py` are **danger zones** per `.cursor/rules/protected-regions.mdc`. Moving them requires founder approval. The diff is zero-content (just a path change), but approval is still required.

**Mitigation**: pre-approval conversation before Phase 0.C Pass 2, with `git diff --stat` proof showing only path-header changes.

PR strategy choice (single atomic PR vs split — decision gate #2):
- **Single atomic PR**: one approval, one CI cycle, one revert button. Higher blast radius.
- **Split** (recommended): silver in PR A, bronze+gold in PR B. Two approvals, two CI cycles, half the blast radius. Adds ~1 day calendar.

#### 6.3 Celery `task_path` drift

If any string reference is missed, scheduled tasks silently stop running. Direct violation of `.cursor/rules/no-silent-fallback.mdc`.

**Mitigation**: migration script has explicit coverage for `task_path=` strings + post-migration check that runs `python -c "import app.tasks.<x>"` for every module listed in `job_catalog.py`. Also: 1-week dual-registration window for Celery tasks (both old and new paths registered).

#### 6.4 Shadow shims masking real regressions

During the 2-week bake, someone could add a new import to an old path and not get caught.

**Mitigation**: shims emit `DeprecationWarning` that CI treats as error in **new** code via `pytest -W error::DeprecationWarning` against a `tests/test_no_new_grandfathered_imports.py` file. Old code paths keep their warnings soft so existing tests stay green.

#### 6.5 Database `gold_plugin` partition doesn't exist yet

The plugin-write gold rule can't be enforced via Postgres grants today; we don't have a `gold_plugin` schema.

**Mitigation**: defer the data-layer gold-write rule to Wave 3.5 when the plugin SDK ([D110](../KNOWLEDGE.md)) lands. Phase 0.B ships **import-layer rules only**.

#### 6.6 `execution/` doesn't fit bronze/silver/gold

It reads gold outputs and writes orders to real money. Forcing it into gold collapses two very different danger profiles.

**Resolution**: officially declare `execution/` a **fourth layer** (not a sublayer of gold). Update D127 + D145 + ARCHITECTURE.md + PLATFORM_REVIEW Ch 1.8 to describe four layers: **bronze → silver → gold → execution**. Cleaner danger-zone story; honest about the safety envelope. **This is decision gate #3.**

#### 6.7 Two-week bake vs immediate cleanup

Could skip the bake and remove shims in the same PR as the moves. Cheaper, riskier for external callers (Brain, future plugins).

**Recommendation**: keep the bake. 2 weeks of passive waiting, not active engineering. Worst case we shorten to 1 week if bake is uneventful.

### §7 — Decision gates 2 and 3 (medallion execution)

| # | Question | Recommendation | Why it matters |
|---|---|---|---|
| 2 | Single atomic migration PR or split silver-first / bronze+gold-second? | **Split** | Half blast radius per PR for one extra calendar day |
| 3 | Acknowledge `execution/` as a fourth medallion layer? | **Yes** | Cleaner danger-zone story than forcing into gold |

Gates 1 and 4 (roadmap / coordination) are recorded under the same handoff section in `PLATFORM_REVIEW_2026Q2.md`.
