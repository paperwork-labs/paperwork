# Medallion Audit — 2026 Q2

> **Status**: Phase 0.A output. Read before touching `app/services/` during the Wave 0 migration.
> **Generated**: 2026-04-23 by `scripts/medallion/tag_files.py`
> **Next review**: After Phase 0.D closeout (~2026-05-13)

This document classifies every `.py` file under `app/services/` into a medallion layer and records the target move path + risk + blockers. It's the **input contract for Phase 0.C** — the migration script `scripts/medallion_migrate.py` consumes this mapping.

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
| 0.D — Shim removal + strict CI | ~2026-05-07 | ⏳ pending | 2 weeks after 0.C landed (0.C merged 2026-04-23). Remove D88-era shims, flip `scripts/medallion/check_imports.py` from warn-mode to strict, drain 21 inherited-debt waivers. See §0.D Checklist below. |

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
