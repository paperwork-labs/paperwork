# Medallion Audit — 2026 Q2

> **Status**: Phase 0.A output. Read before touching `backend/services/` during the Wave 0 migration.
> **Generated**: 2026-04-23 by `scripts/medallion/tag_files.py`
> **Next review**: After Phase 0.D closeout (~2026-05-13)

This document classifies every `.py` file under `backend/services/` into a medallion layer and records the target move path + risk + blockers. It's the **input contract for Phase 0.C** — the migration script `scripts/medallion_migrate.py` consumes this mapping.

Reference: `docs/handoffs/2026-04-22-medallion-wave-0-stage-setting.md`

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

- `backend/services/market/indicator_engine.py` → `silver/indicators/indicator_engine.py`
- `backend/services/market/stage_classifier.py` → `silver/regime/stage_classifier.py`
- `backend/services/market/regime_engine.py` → `silver/regime/regime_engine.py`
- `backend/services/portfolio/ibkr/*` (4 files) → `bronze/ibkr/*`

**Mitigation**: diff proves zero-content change (path-only), run `git diff --stat` showing only file rename + import rewrites.

### B2 — `portfolio/` requires per-file classification

`portfolio/` has 30 files; currently split between broker-facing (bronze) and analytics (silver). Before 0.C Pass 3:

- Walk each file; tag with `medallion: bronze` or `medallion: silver` based on imports (if it imports from `market/` or does cross-broker math → silver; if it calls a broker SDK → bronze).
- Extract the mapping into `medallion_move_map.yaml`.

### B3 — Celery `task_path` coverage

29 entries in `job_catalog.py`, 12 in `app/celery_beat_schedule.py`, unknown in `tasks/`. The migration script must rewrite every dotted-path string reference. Pre-check:

```bash
rg "backend\.services\.(market|portfolio|strategy|picks|tax|corporate_actions)\." \
   --type py -l
```

Expected: ~40-60 matches. Script must cover all.

### B4 — `risk/` splits across gold and execution

Four files in `services/risk/`:

- `position_risk_calculator.py` → likely gold (computes exposure from positions)
- `pre_trade_risk_gate.py` → likely execution (blocks live orders)
- `concentration_limits.py` → likely gold (portfolio-level analytics)
- `drawdown_monitor.py` → ops or gold (monitoring)

**Resolve before Pass 4**: read each file, decide, annotate in `medallion_move_map.yaml`.

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

Per handoff §4, Phase 0.C Pass order:

1. **Pass 1** — Leaf utilities: `market/dataframe_utils.py`, `market/atr_series.py`, `market/coverage_utils.py` → `silver/math/`. ~10 files.
2. **Pass 2** — Silver core: `market/indicator_engine.py`, `stage_classifier.py`, `regime_engine.py`, `portfolio/portfolio_analytics_service.py`, `portfolio/closing_lot_matcher.py`, `tax/*` → `silver/`. ~25 files.
3. **Pass 3** — Bronze core: `portfolio/ibkr/*`, `portfolio/schwab_sync_service.py`, `portfolio/tastytrade_sync_service.py`, `portfolio/broker_sync_service.py` → `bronze/<broker>/`. ~15 files.
4. **Pass 4** — Gold stragglers: `strategy/` → `gold/strategy/`, `picks/` → `gold/picks/`, `backtest/`, `narrative/`, etc. ~30 files.
5. **Pass 5** — `execution/` stays put; tagged as fourth layer.

---

## Status tracker

| Phase | Target date | Status | Notes |
|---|---|---|---|
| 0.A — Tags + audit | 2026-04-23 | ✅ DONE | 268 files tagged, this doc produced |
| 0.A — DAG swimlanes | 2026-04-24 | ⏳ pending | `PipelineDAG.tsx` bands + legend (frontend) |
| 0.A — Prose sweep | 2026-04-23 | ✅ DONE | `ARCHITECTURE.md` + `AGENTS.md` updated with 4-layer medallion + pillar cross-map. PRD.md unchanged (historically frozen; MASTER_PLAN is source of truth) |
| 0.B — Silver scaffold + CI rule | 2026-04-23 | ✅ DONE | `silver/__init__.py`, `scripts/medallion/check_imports.py`, `make medallion-check`, CI job added. 21 known-debt violations auto-captured as waivers. |
| 0.C — File migrations (split into 2 PRs) | 2026-04-26–28 | ⏳ pending | Founder freeze window no longer needed (no parallel agents writing PRs yet). |
| 0.D — Shim removal + strict CI | ~2026-05-13 | ⏳ pending | 2 weeks after 0.C lands |

---

Closing this document at Phase 0.D: mark every row `Verified at target path: <path>`.
