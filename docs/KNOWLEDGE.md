# Knowledge — Decision Log

Numbered decisions with date, rationale, alternatives considered, and reversibility. Newest decisions at the top of each section.

## Front and Center — Must Act On

- ~~**D5**: Celery global time_limit=360s silently kills long tasks.~~ **RESOLVED** — Global defaults raised to 3500s/3600s; short-lived tasks have explicit per-task limits.
- ~~**D6**: Dual order paths (OrderManager vs OrderService) will drift.~~ **RESOLVED** — OrderService now delegates risk checking to canonical RiskGate; duplicate RiskViolation class removed.
- ~~**D7**: `get_portfolio_user` falls back to `User.first()` — tenant-unsafe.~~ **RESOLVED** — Now delegates to `get_current_user` (JWT required).
- ~~**D8**: RSI uses SMA, not Wilder smoothing.~~ **RESOLVED** — Code already uses Wilder's method (see D8 below).

## Should Track

- **D12**: React Query v3 is legacy. Plan migration to @tanstack/react-query v5.
- **D14**: Schwab `TRADE → BUY` transaction mapping loses sell-side distinction.
- **D15**: TastyTrade tax lots are synthetic (CALCULATED) — not suitable for tax reporting.
- ~~**D19**: MarketDashboard.tsx is 1400+ lines — needs decomposition.~~ **RESOLVED** — Decomposed into 5-tab container (Overview, Top-Down, Bottom-Up, Sectors, Heatmap) with lazy-loaded views.

---

## Decisions

### D30 — 2026-03-25 — Dependency freshness policy

**Decision**: Establish quarterly dependency audit process with specific upgrade procedures for Postgres, Python, and Vite major versions. Created `.cursor/rules/dep-freshness.mdc` with checklist.

**Rationale**: Dependencies drift quickly; security vulnerabilities accumulate. Postgres 16→18, Python 3.11→3.13, and Vite 5→6 were all available but not applied. Dependabot handles minor/patch but not major versions.

**Alternatives**: Ad-hoc upgrades when breakages occur — rejected (reactive not proactive).

**Reversible**: Yes — the rule is guidance, not enforcement.

### D29 — 2026-03-25 — Celery task routing must match registered name= exactly

**Decision**: All task references (job_catalog.py, TOOL_TO_CELERY_TASK, auto_ops REMEDIATION_MAP, beat_schedule, send_task() calls) must match the `name=` parameter from `@shared_task(name="...")` exactly. There is no automatic derivation from Python module paths.

**Current naming patterns** (legacy, not a convention to follow for new tasks):
- `backend.tasks.market_data_tasks.*` — monolith tasks
- `backend.tasks.intelligence_tasks.*` — intelligence briefs
- `backend.tasks.auto_ops_tasks.*` — auto-ops
- `backend.tasks.account_sync.*` — portfolio sync
- `backend.tasks.portfolio.orders.*` — order execution (new modular style)
- `backend.tasks.market.{module}.*` — new modular market tasks

**Rationale**: Audit found 4 critical routing mismatches where `send_task()` dispatched to non-existent or wrong task names:
1. `backend.tasks.order_tasks.*` (wrong) vs `backend.tasks.portfolio.orders.*` (real)
2. `refresh_index_constituents_task` (trailing `_task`) vs `refresh_index_constituents`
3. `backend.tasks.intelligence.tasks.*` vs `backend.tasks.intelligence_tasks.*`
4. `recover_stale_job_runs_impl` (helper function) vs `recover_stale_job_runs` (actual task)

**Alternatives**: Enforce a strict naming convention — rejected (too disruptive for existing tasks).

**Reversible**: Yes, with coordinated multi-file update.

### D24 — 2026-03-24 — Scan overlay field-name bugs found and fixed

**Decision**: Fixed 3 wrong field names in `market_data_tasks.py` scan overlay wiring (`atre_pctile` → cross-sectional percentile of `atrx_sma_150`, `range_position_52w` → `range_pos_52w`, `atr_pct_14` → `atrp_14`), plus 2 in exit cascade wiring (`atr_pct_14` → `atrp_14`, `prior_stage` → `previous_stage_label`). Also replaced silent `except Exception: continue` with logged warnings.

**Rationale**: These mismatches caused every stock's scan tier to evaluate with `None` values, meaning Set 1 never matched and tiering was degraded. The silent exception swallowing hid the `AttributeError` from wrong column names.

**Alternatives**: N/A — these were bugs.

**Reversible**: N/A.

### D23 — 2026-03-24 — TopDown dashboard is dual-mode (universe vs portfolio)

**Decision**: The Top-Down view will support two lenses: (1) Universe Top-Down (~2,500 tracked tickers) for regime, breadth, indices, sector ETFs, volatility — the macro view; (2) Portfolio Top-Down for aggregated accounts, exposure, long/short/net, and positions with sizing, ATR, P/L, impact. Matches the user's Bloomberg workflow with the `TopD` sheet in the trading spreadsheet.

**Rationale**: A quant flips between universe-level market context and book-level portfolio detail constantly. Both views answer different questions and must coexist.

**Alternatives**: Single Top-Down view (rejected — loses either market context or portfolio detail).

**Reversible**: Yes.

### D22 — 2026-03-24 — Intelligence brief has Universe + Book sections

**Decision**: The infographic executive brief has two sections: (A) "The Market" — regime, breadth, vol structure, sector rotation, stage distribution, top scan picks (universe view); (B) "Your Book" — portfolio P/L, exposure by stage/sector, exit alerts, sizing headroom (portfolio view).

**Rationale**: These sections answer different questions. Universe = "Where are the opportunities?" Book = "How is my portfolio positioned?"

**Alternatives**: Single combined brief (rejected — mixes macro with portfolio detail).

**Reversible**: Yes.

### D21 — 2026-03-24 — AxiomFolio is a Paperwork Brain skill

**Decision**: AxiomFolio is a skill/capability within the Paperwork Brain platform. It exposes a clean API surface (`regime_check`, `scan_universe`, `portfolio_status`, `generate_brief`, `place_order`, `backtest`) callable by the Brain agent loop.

**Rationale**: Per `BRAIN_ARCHITECTURE.md`: "axiomfolio ('manage your portfolio') is a skill/capability within it. Products are the hands, Brain is the mind."

**Alternatives**: Standalone product (rejected — Brain integration enables voice/chat control, cross-product orchestration).

**Reversible**: Yes — API surface can be consumed independently.

### D1 — 2026-03-23 — SMA150 replaces 30-week SMA as primary stage anchor

**Decision**: Migrate from Weinstein's 30-week SMA (computed on weekly bars) to Oliver Kell's SMA150 (computed on daily bars) as the primary stage classification anchor.

**Rationale**: The Stage Analysis specification (`Stage_Analysis_v4.docx`) specifies SMA150. User's live Bloomberg workflow already uses Ext150% and ATRv150. The backend must match the live methodology.

**Alternatives**: Keep 30-week SMA (rejected — diverges from the spec and live workflow).

**Reversible**: Yes, but requires full MarketSnapshotHistory backfill.

### D2 — 2026-03-23 — Market Regime Engine is a mandatory hard gate

**Decision**: The Regime Engine (6 daily inputs → composite score → R1–R5) is the outermost gate for all downstream modules. All position sizing, scan access, entry timing, and exit acceleration inherit the current Regime state.

**Rationale**: Spec Section 10 explicitly states "no longer advisory — mandatory daily calculation that gates all downstream system behavior."

**Alternatives**: Keep regime as advisory overlay (rejected — spec mandates hard gate).

**Reversible**: No — this is a fundamental architecture change.

### D3 — 2026-03-23 — 10 sub-stages replace simplified stage labels

**Decision**: Expand stage labels from {1, 2A, 2B, 2C, 3, 4} to {1A, 1B, 2A, 2B, 2C, 3A, 3B, 4A, 4B, 4C}.

**Rationale**: The specification requires granular sub-stages for position sizing caps, exit cascade behavior, and scan overlay gating. 1B is the critical watchlist stage; 3A vs 3B determines reduce vs exit; 4A/4B/4C differentiate decline phases.

**Alternatives**: Map 1A/1B to "1" in display only (rejected — loses decision-relevant information).

**Reversible**: Yes, can collapse back to simplified labels in UI.

### D4 — 2026-03-23 — Persona-based cursor rules for AI development

**Decision**: Create 7 context-specific cursor rules (engineering, quant-analyst, portfolio-manager, ux-lead, ops-engineer, git-workflow, token-management) activated by file glob patterns.

**Rationale**: Inspired by Paperwork Labs' 16-persona system. Domain-specific context improves code quality and reduces hallucination. The quant-analyst persona prevents approximate financial math.

**Alternatives**: Single monolithic .cursorrules file (rejected — too large, always-on context is expensive).

**Reversible**: Yes, can consolidate or remove rules at any time.

### D5 — 2026-03-23 — Celery time limits must be per-task

**Decision**: Add explicit `time_limit` and `soft_time_limit` decorators to every Celery task, matching `job_catalog.py` `timeout_s` values.

**Rationale**: Global default is 360s (6 minutes). IBKR FlexQuery poll loop alone can take 8+ minutes. Coverage pipelines and backfills need 3600s. Tasks silently die at 360s with no error logged.

**Alternatives**: Raise global default to 3600s (rejected — too permissive for short tasks).

**Reversible**: Yes.

### D6 — 2026-03-23 — Consolidate OrderService into OrderManager

**Decision**: Merge `OrderService` (order_service.py) into `OrderManager` (execution/order_manager.py). Delete duplicate `RiskViolation` class.

**Rationale**: Two parallel paths for order preview/submit with duplicated risk gates and a duplicated exception class. They will diverge over time.

**Alternatives**: Keep both with shared base class (rejected — unnecessary complexity for single-operator system).

**Reversible**: Yes, but migration of callers required.

### D7 — 2026-03-23 — Remove get_portfolio_user first-user fallback

**Decision**: Remove `db.query(User).first()` fallback from `get_portfolio_user` in `dependencies.py`.

**Rationale**: Any route using this dependency is effectively unauthenticated. In a multi-user future, this would be a security hole. Even for single-user, it masks auth failures.

**Alternatives**: Keep as dev convenience (rejected — too risky if any route accidentally uses it in production).

**Reversible**: Yes.

### D8 — 2026-03-23 — RSI uses Wilder smoothing (confirmed)

**Decision**: CONFIRMED — `calculate_rsi_series` already implements Wilder's exponential smoothing. The seed period uses a simple mean, then applies the recursive formula `avg = (prev_avg * (period-1) + current_value) / period`, which is exactly Wilder's method (EWM with alpha=1/period). This matches Bloomberg and industry standard.

**Rationale**: Initial audit incorrectly flagged the implementation as "SMA-based." Upon closer inspection, the code seeds with SMA for the first period (standard Wilder practice) then switches to Wilder's recursive exponential. No change needed. No backfill required.

**Alternatives**: N/A — already correct.

**Reversible**: N/A.

### D9 — 2026-03-23 — Stage Analysis spec is the canonical reference

**Decision**: `Stage_Analysis_v4.docx` at repo root is the single source of truth for all stage classification, regime, scan, exit, and sizing logic.

**Rationale**: The document is comprehensive (15 sections, 10 sub-stages, regime engine, scan overlay, exit cascade, position sizing, sector matrix). All implementation must match it exactly.

**Alternatives**: None — this is the specification.

**Reversible**: N/A.

### D10 — 2026-03-23 — SMA150 slope uses 20-day lookback

**Decision**: `SMA150_slope = (SMA150_today - SMA150_20d_ago) / SMA150_20d_ago * 100` with thresholds ±0.35%.

**Rationale**: Spec Section 4.5 specifies 20-day lookback for SMA150 slope. Current implementation uses 5-week lookback on weekly bars — must migrate.

**Alternatives**: None — the spec is clear.

**Reversible**: Yes.

### D11 — 2026-03-23 — EMA10 Distance normalized by ATR is primary scan input

**Decision**: `EMA10_Dist_N = EMA10_Dist% / ATR%14` replaces legacy EMA10 Distance % as the primary scan gate input.

**Rationale**: Spec Section 4.4 — the normalized form is regime-adaptive. A 3% gap in a low-vol name (ATR% 1%) = chase (Dist_N 3.0). Same gap in high-vol (ATR% 4%) = acceptable (Dist_N 0.75).

**Alternatives**: Keep legacy Dist% (rejected — not adaptive to volatility regime).

**Reversible**: Yes, compute and store both.

### D12 — 2026-03-23 — React Query v3 migration to TanStack Query v5

**Decision**: Plan migration from `react-query` v3 to `@tanstack/react-query` v5.

**Rationale**: v3 is legacy, different package name and API. v5 has better TypeScript support, automatic garbage collection, and structural sharing.

**Alternatives**: Stay on v3 (acceptable short-term, not long-term).

**Reversible**: Yes.

### D13 — 2026-03-23 — Bloomberg-style multi-view dashboard

**Decision**: Restructure Market Dashboard into 4 views: Top-Down (Regime/Macro), Bottom-Up (Stock Scanner), Sector Deep-Dives, Historical Heatmap.

**Rationale**: User's live Bloomberg workflow uses these exact views. The dashboard should mirror real trading workflow.

**Alternatives**: Single flat dashboard (rejected — doesn't match professional workflow).

**Reversible**: Yes.

### D14 — 2026-03-23 — Schwab transaction type mapping needs fix

**Decision**: Audit and fix `SCHWAB_TYPE_MAP` in schwab_sync_service.py — `TRADE → BUY` loses sell-side distinction.

**Rationale**: All Schwab trades are currently categorized as BUY transactions regardless of side. This corrupts transaction analysis.

**Alternatives**: None — this is a bug.

**Reversible**: Yes, re-sync after fix.

### D15 — 2026-03-23 — TastyTrade tax lots are synthetic

**Decision**: Accept synthetic tax lots (one per position, marked CALCULATED) for TastyTrade. Flag clearly in UI. Never use for tax reporting.

**Rationale**: TastyTrade API doesn't provide lot-level detail. Synthetic lots give approximate position tracking but not real FIFO/LIFO.

**Alternatives**: Compute FIFO from trade history (possible future improvement).

**Reversible**: Yes.

### D16 — 2026-03-23 — Single order execution path

**Decision**: All order execution goes through OrderManager → RiskGate → BrokerRouter → Executor. No alternative paths.

**Rationale**: Multiple paths (OrderManager + OrderService) lead to divergence and duplicated risk checks.

**Alternatives**: Keep both (rejected per D6).

**Reversible**: Yes.

### D17 — 2026-03-23 — Intelligence Brief system for multi-cadence output

**Decision**: Build an intelligence brief system delivering daily digests (auto), weekly strategy briefs (Monday), and monthly reviews.

**Rationale**: Replace manual admin dashboard monitoring with proactive intelligence delivery via Discord + in-app.

**Alternatives**: Keep manual admin dashboard only (rejected — doesn't scale).

**Reversible**: Yes.

### D18 — 2026-03-23 — IBKR is primary execution broker

**Decision**: IBKR via ib_insync is the primary and currently only execution broker. Schwab and TastyTrade are read-only.

**Rationale**: IBKR Gateway provides whatIfOrder, paper mode, and full order lifecycle. TastyTrade SDK has place_order (future). Schwab has order endpoints (future).

**Alternatives**: None — reflects current capability.

**Reversible**: Expand to multi-broker execution as APIs are wired.

### D19 — 2026-03-23 — MarketDashboard.tsx decomposition needed

**Decision**: Break MarketDashboard.tsx (~1400 lines) into feature modules with dedicated hooks.

**Rationale**: Monolithic component is hard to test, review, and extend. Multiple data fetches on mount could be shared via React Query cache.

**Alternatives**: Keep monolith (rejected — unsustainable).

**Reversible**: Yes.

### D20 — 2026-03-23 — Silent error handling must be eliminated

**Decision**: Replace all `except Exception: pass` patterns in indicator_engine.py and market_data_tasks.py with proper logging.

**Rationale**: Silent failures in financial calculations are dangerous. ADX, performance windows, and enrichment errors are currently invisible.

**Alternatives**: None — this is a reliability requirement.

**Reversible**: N/A.

### D25 — 2026-03-24 — Auto-Ops Agent for self-remediating admin health

**Decision**: Created `backend/tasks/auto_ops_tasks.py` with `auto_remediate_health` Celery task. Runs every 15 min via Beat schedule (dev) and job catalog (prod/Render). Checks 5 health dimensions and dispatches appropriate remediation tasks.

**Rationale**: Manual admin dashboard monitoring is unsustainable. The 5 health dimensions (coverage, stage_quality, jobs, audit, regime) each have known remediation paths that can be automated.

**Alternatives**: External monitoring (Datadog/PagerDuty) — rejected for now (overkill for single-user platform). Discord bot — complementary, not replacement.

**Reversible**: Yes — disable beat schedule entry or remove from job catalog.

### D26 — 2026-03-24 — compute_daily_regime missing session.commit()

**Decision**: Added `session.commit()` after `persist_regime()` in `compute_daily_regime` task. The regime engine's `persist_regime()` only calls `flush()` per the convention that callers control commit scope.

**Rationale**: Without commit, the INSERT was rolled back on `session.close()`. Regime data was never persisted despite the task reporting success.

**Alternatives**: Have `persist_regime()` commit internally — rejected (violates DB session convention).

**Reversible**: N/A — bug fix.

### D27 — 2026-03-24 — Intelligence tasks must be registered in Celery include list

**Decision**: Added `backend.tasks.intelligence_tasks` and `backend.tasks.auto_ops_tasks` to `celery_app.py` `include` list.

**Rationale**: Celery worker rejected intelligence brief tasks as "unregistered" because the module was never imported at worker startup. Tasks defined with `@celery_app.task()` require explicit include.

**Alternatives**: Switch to `autodiscover_tasks()` — viable but would require restructuring task imports.

**Reversible**: Yes.

### D28 — 2026-03-24 — Greenfield DB Rebuild

**Decision**: Delete all 33 Alembic migrations and create a single `0001_baseline.py` that uses `Base.metadata.create_all()`. Reset production Postgres and redeploy. Bundled with: Google OAuth, email verification, refresh token flow, BrokerAdapter ABC, multi-tenant user_id enforcement, TanStack Query v5 migration, admin reimagine (SystemStatus), silent exception cleanup, MAX_SINGLE_POSITION_PCT enforcement, agent cold-start deep backfill.

**Rationale**: Production was broken (500 errors) due to a blocked Alembic migration chain — migration `0b618cd073a8` referenced `strategies` table that didn't exist in prod. 33 migrations with multiple FK ordering issues made patching impractical. Rebuilding from scratch on a fresh DB was the cleanest path, and the downtime window was acceptable for a pre-launch platform with a single user.

**Alternatives**: (1) Patch individual migrations — rejected, too fragile with 33-deep chain. (2) Data-aware migration with pg_dump + transform — rejected, no critical user data at risk.

**Reversible**: No — old migration history is deleted. Schema is identical to what ORM models define.
