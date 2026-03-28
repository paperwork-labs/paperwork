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
| 1.5.4 | Silent error audit | DONE | Zero `except Exception: pass` in indicator_engine.py and `backend/tasks/market/` task modules |
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

## Phase 3: Frontend [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 3.1 | Bloomberg-style Market Dashboard | DONE | 5 views: Overview, Top-Down, Bottom-Up, Sector, Heatmap |
| 3.2 | Education page rewrite | MOVED | Moved to Phase 7.1 |
| 3.3 | Intelligence Brief system | DONE | Daily/weekly/monthly briefs, Celery tasks, in-app viewing with polling + error handling |
| 3.4 | Admin reimagine (SystemStatus) | DONE | Single SystemStatus page replaces Dashboard/Jobs/Schedules/Coverage. Composite health, dimension cards, auto-ops activity, collapsible Advanced with OperatorActions |
| 3.5 | TanStack Query v5 migration | DONE | Migrated from react-query v3 to @tanstack/react-query v5. isLoading→isPending, import renames |
| 3.6 | Console cleanup | DONE | All console.log/error/warn removed from committed frontend code (dev-gated logging allowed) |

## Phase 3.5: Greenfield DB Rebuild [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 3.5.1 | Clean Alembic baseline | DONE | 33 migrations deleted, single 0001_baseline.py using Base.metadata.create_all() |
| 3.5.2 | Google OAuth + email verification | DONE | /auth/google/login + callback, find-or-create user, verification email via Resend |
| 3.5.3 | Refresh token flow | DONE | 15-min access JWT + 7-day httpOnly refresh cookie + /auth/refresh + token family rotation |
| 3.5.4 | Frontend auth updates | DONE | Google button on Login, AuthCallback page, 401 refresh interceptor in api.ts |
| 3.5.5 | BrokerAdapter interface | DONE | ABC in broker_adapter.py, AlpacaAdapter stub |
| 3.5.6 | Multi-tenant enforcement | DONE | user_id scoping on OrderManager, portfolio, dashboard, options routes. IDOR fixes |
| 3.5.7 | Silent exception cleanup | DONE | 34 except-pass blocks replaced with logger.warning in market_data_service + tasks |
| 3.5.8 | MAX_SINGLE_POSITION_PCT | DONE | Wired from settings (default 15%) into RiskGate |
| 3.5.9 | Agent cold-start | DONE | Empty DB triggers 5-year `backend.tasks.market.backfill.full_historical`; migration logging with exc_info=True |

## Phase 4: Deploy Greenfield + Stabilize [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 4.1 | Merge PR #225 (greenfield rebuild) | DONE | PR reviewed, CI green, squash-merged to main |
| 4.2 | Reset Render Postgres + deploy | DONE | Delete Render DB, redeploy backend, `alembic upgrade head` creates all tables |
| 4.3 | Add prod env vars for new features | DONE | Google OAuth, Resend, OpenAI keys configured in Render |
| 4.4 | Verify prod cold-start backfill | DONE | Data populated via nightly pipeline |
| 4.5 | Verify Google OAuth end-to-end | DONE | Login via Google works on prod |
| 4.6 | Education page rewrite | MOVED | Moved to Phase 7.1 |

## Phase 4.5: PR #225 Follow-up [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 4.5.1 | Fix Celery task routing bugs | DONE | 4 critical mismatches fixed (job_catalog, tools.py, admin.py) |
| 4.5.2 | Extract task helpers to task_utils.py | DONE | setup_event_loop, resolve_history_days, etc. moved for modular reuse |
| 4.5.3 | AdminUsers page cleanup | DONE | Google OAuth users show name+email, not @username |
| 4.5.4 | Dependency mega-upgrade | DONE | Postgres 18, Python 3.13, Vite 6, Dependabot PRs merged |
| 4.5.5 | Add dep-freshness cursor rule | DONE | `.cursor/rules/dep-freshness.mdc` with quarterly audit checklist |
| 4.5.6 | Document D29+D30 in KNOWLEDGE.md | DONE | Naming convention and dependency freshness decisions logged |
| 4.5.7 | Retire market_data_tasks.py | DONE | Market tasks live in `backend/tasks/market/`; Celery paths are `backend.tasks.market.<module>.<function>` (see `job_catalog.py`) |
| 4.5.8 | Agent inline tools + hardening | DONE | INLINE_ONLY_AGENT_TOOLS for read_file/list_files, path traversal protection, RegimeBanner fix |

## Phase 5: Quant Platform Core [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 5.1 | Strategy templates update | DONE | Regime-aware entries (R1-R3 for longs), 3 short templates, 2 TTM squeeze templates in templates.py |
| 5.2 | TTM Squeeze indicator | DONE | Bollinger + Keltner squeeze detection in indicator_engine.py, ttm_squeeze_on/ttm_momentum columns |
| 5.3 | Multi-timeframe confirmation | DONE | MultiTimeframeEngine in backend/services/market/multi_timeframe.py with 1H/4H/1D/1W support |
| 5.4 | Trailing stop optimization | DONE | Adaptive trailing stop logic in exit_cascade._tier2_trailing_stop, ATR-based with regime adjustment |
| 5.5 | Position reconciliation service | DONE | ReconciliationService in backend/services/portfolio/reconciliation.py with discrepancy detection |
| 5.6 | Drawdown alerts + PortfolioHistory | DONE | PortfolioHistory model, DrawdownService in backend/services/portfolio/drawdown.py |
| 5.7 | Execution analytics | DONE | CircuitBreaker + PreTradeValidator in backend/services/risk/ |
| 5.8 | Real-time regime monitoring | DONE | SignalEngine + PriceFeedService with Redis Streams event-driven architecture |

## Phase 5.5: AdminAgent Redesign [MERGED INTO PHASE 7]

See Phase 7 Gold Standard for AI strategy and agent improvements.

## Phase 6: Pipeline [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 6.1 | Nightly pipeline (full sequence) | DONE | PipelineOrchestrator in backend/tasks/pipeline/orchestrator.py with 10-step sequence, per-step tracking |
| 6.2 | New data feeds | DONE | VIX/VIX3M/VVIX, NH-NL, breadth in backend/services/market/regime_inputs.py |

## Phase 7: Gold Standard Rebuild [DONE]

Clean-slate rebuild into a trading platform better than LEAN/QuantConnect.

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 7.0 | Token efficiency setup | DONE | Headroom, RTK, MemStack installed for AI coding efficiency |
| 7.1 | Day 0: Cleanup sprint | DONE | Dead code removed, broker sync consolidated, schema FKs added |
| 7.2 | Day 1: Safety foundation | DONE | CircuitBreaker (tiered 2/3/5%), PreTradeValidator, wired into OrderManager |
| 7.3 | Day 2: Real-time execution | DONE | PriceFeedService (WebSocket), SignalEngine (Redis Streams), TradingView webhook |
| 7.4 | Day 3: Intelligence layer | DONE | MultiTimeframeEngine, TaxLossHarvester, auto-backtest pipeline |
| 7.5 | Day 4: AI + Validation | DONE | AIStrategyBuilder, WalkForwardAnalyzer, Pine Script indicators, UI components |
| 7.6 | Code quality guardian | DONE | .cursor/rules/code-quality-guardian.mdc for continuous quality checks |

## Phase 8: Brain Integration [DONE]

Prepare AxiomFolio as tool provider for Paperwork Brain.

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 8.1 | API key authentication | DONE | X-Brain-Api-Key header validation in dependencies.py |
| 8.2 | Tool endpoints | DONE | /tools/portfolio, /tools/stage/{symbol}, /tools/regime, /tools/scan, /tools/risk |
| 8.3 | Trade endpoints | DONE | /tools/preview-trade, /tools/execute-trade, /tools/approve-trade, /tools/reject-trade |
| 8.4 | Tool manifest | DONE | docs/brain/axiomfolio_tools.yaml for Brain registration |
| 8.5 | Webhooks to Brain | DONE | BrainWebhookClient for trade_executed, approval_required, etc. |
| 8.6 | Notifications cleanup | DONE | Discord removed, unified notifications via Brain webhook |
| 8.7 | Analyst role | DONE | UserRole: owner/analyst/viewer with require_role dependency |
| 8.8 | Approval workflow | DONE | ApprovalService for Tier 3 trades, PENDING_APPROVAL status |

## Phase 9: Paper Trading & Validation [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 9.1 | Paper trading mode | DONE | PaperExecutor in backend/services/execution/paper_executor.py with virtual fills |
| 9.2 | Strategy paper validation | DONE | PaperValidator service with min_trades, min_win_rate, max_drawdown thresholds |
| 9.3 | Circuit breaker verification | DONE | Comprehensive test suite in test_circuit_breaker_simulation.py |
| 9.4 | Slippage tracking | DONE | SlippageTracker service + decision_price/slippage_pct on Order model |

## Phase 10: Education & Content [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 10.1 | Education page rewrite | DONE | MarketEducation.tsx with Stage Analysis content, deep-dives, glossary |
| 10.2 | Interactive stage examples | DONE | StageChartExample + InteractiveStageExplorer components |

## Phase 11: Slippage Prediction ML [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 11.1 | SlippagePredictor service | DONE | GradientBoostingRegressor model in backend/services/ml/slippage_predictor.py |
| 11.2 | Feature engineering | DONE | Order size, time of day, spread, ATR, volume ratio features |
| 11.3 | Model persistence | DONE | Pickle save/load with model versioning |

## Phase 12: Sentiment Integration [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 12.1 | SentimentService | DONE | backend/services/market/sentiment_service.py with StockTwits + Finnhub |
| 12.2 | Batch sentiment | DONE | get_batch_sentiment for multiple symbols |
| 12.3 | Alert detection | DONE | detect_alerts for extreme sentiment levels |

## Phase 13: Memory Agent [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 13.1 | AgentMemory model | DONE | SQLAlchemy model with embedding support |
| 13.2 | MemoryService | DONE | store, search (semantic + keyword), find_similar_situations |
| 13.3 | Alembic migration | DONE | 0010_add_agent_memories.py creates table with indexes |

## Phase 14: Alpha Factor Engine [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| 14.1 | AlphaEngine | DONE | backend/services/strategy/alpha_engine.py with 8 factors |
| 14.2 | Factor categories | DONE | Momentum, Value, Quality, Volatility, Technical |
| 14.3 | Regime-weighted scoring | DONE | Factor weights adjust by market regime |
| 14.4 | Top picks generation | DONE | get_top_picks with composite scores |

---

## Cleanup & Quality [DONE]

| ID | Task | Status | Acceptance Criteria |
|----|------|--------|---------------------|
| C.1 | Chakra UI removal | DONE | All Chakra imports removed, CircuitBreakerBanner migrated to shadcn |
| C.2 | alpha_engine field names | DONE | Correct MarketSnapshot field names (sma_150, vol_ratio, etc.) |
| C.3 | paper_validator P&L | DONE | Uses realized_pnl instead of slippage for validation metrics |
| C.4 | Order model additions | DONE | realized_pnl + cost_basis columns (migration 0011) |
| C.5 | PaperValidator tests | DONE | test_paper_validator.py with 33 test cases |

---

## Next Sprint Backlog

| ID | Task | Status | Notes |
|----|------|--------|-------|
| N.1 | Alpaca broker adapter | DONE | AlpacaExecutor in backend/services/execution/alpaca_executor.py |
| N.2 | Apple Sign-In | DONE | /auth/apple/login + callback |
| N.3 | User onboarding flow | DONE | Onboarding.tsx with 5-step flow |
| N.4 | Bloomberg terminal dashboard | DONE | Terminal.tsx at /terminal with 4-pane layout |

---

## Future Phases (Post-Stabilization)

| Phase | Focus | Status |
|-------|-------|--------|
| 15 | Live Trading Integration | PLANNED |
| 16 | Portfolio Optimization | PLANNED |
| 17 | Risk Analytics Dashboard | PLANNED |
| 18 | Mobile App | PLANNED |
