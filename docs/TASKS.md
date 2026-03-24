# Tasks — Sprint Plan

Current execution plan organized by phase. One task per PR where possible.

## Status Legend

- DONE — Merged to main
- IN PROGRESS — Active development
- NEXT — Ready to start
- PLANNED — Scoped but not started
- BLOCKED — Waiting on dependency

---

## Phase 1: AI Development Infrastructure [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 1.1 | Create 7 persona-based cursor rules | DONE | Rules in `.cursor/rules/`: engineering, quant-analyst, portfolio-manager, ux-lead, ops-engineer, git-workflow, token-management |
| 1.2 | Create KNOWLEDGE.md with seeded decisions | DONE | `docs/KNOWLEDGE.md` with D1–D20, front-and-center section |
| 1.3 | Create TASKS.md (this file) | DONE | Sprint plan with acceptance criteria |
| 1.4 | Create PRD.md | DONE | Product requirements document in `docs/PRD.md` |
| 1.5 | Create AGENTS.md | DONE | AI agent entry point at repo root |

## Phase 1.5: Critical Fixes [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 1.5.1 | Fix Celery time limits | DONE | Every task has explicit `time_limit`/`soft_time_limit` matching `job_catalog.py` |
| 1.5.2 | Consolidate order paths | DONE | `OrderService` delegates to `OrderManager`, duplicate `RiskViolation` deleted |
| 1.5.3 | Remove auth first-user fallback | DONE | `get_portfolio_user` requires JWT, no `User.first()` fallback |
| 1.5.4 | Silent error audit | DONE | Zero `except Exception: pass` in indicator_engine.py and market_data_tasks.py |
| 1.5.5 | RSI implementation decision | DONE | Wilder smoothing confirmed correct (D8), no change needed |

## Phase 2: Stage Analysis engine [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 2.1 | Add extended stage fields to models | DONE | Migration `1e0612af8a13`: ext_pct, sma150_slope, sma50_slope, ema10_dist_n, vol_ratio, scan_tier, action_label, regime_state on both snapshot tables. MarketRegime table. |
| 2.2 | Rewrite stage classifier | DONE | SMA150 anchor, 10 sub-stages, priority classification, ATRE override, RS modifier, breakout rule (1B→2A) |
| 2.3 | Build Market Regime Engine | DONE | 6 inputs, scoring 1–5, composite → R1–R5, MarketRegime model, persist/get functions |
| 2.4 | Build Scan Overlay Engine | DONE | 4 long + 2 short tiers, 6-filter gate, regime-gated access, action label derivation |
| 2.5 | Build Exit Cascade Engine | DONE | 9 long tiers (5 base + 4 regime) + 4 short exits, independently firing |
| 2.6 | ATR-based position sizing | DONE | ATR-based formula with Regime Multiplier × Stage Cap, wired into RiskGate.check |

## Phase 3: Frontend [IN PROGRESS]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 3.1 | Bloomberg-style Market Dashboard | DONE | 5 views: Overview, Top-Down, Bottom-Up, Sector, Heatmap |
| 3.2 | Education page rewrite | PLANNED | Stage Analysis content: 10 sub-stages, regime engine, scan overlay, exit cascade |
| 3.3 | Intelligence Brief system | DONE | Daily/weekly/monthly briefs, Celery tasks, in-app viewing with polling + error handling |
| 3.4 | Admin simplification | PLANNED | Auto-monitoring via Celery, System Health summary |

## Phase 4: Strategy Alignment [PLANNED]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 4.1 | Update strategy templates | PLANNED | Regime-aware entries, short templates, new extended stage fields in rule evaluator |

## Phase 5: Pipeline [PLANNED]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 5.1 | Nightly pipeline (full sequence) | PLANNED | 10-step sequence per spec Section 14.1 |
| 5.2 | New data feeds | PLANNED | VIX/VIX3M/VVIX, NH-NL, breadth (%above200D, %above50D) |
