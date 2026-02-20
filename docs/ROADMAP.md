Roadmap
=======

Execution is split into three PRs (sections). Complete Section 1, merge, then Section 2, then Section 3.

Section 1 (PR 1) – Foundation
------------------------------
- Backend: Remove dead portfolio endpoints; fix N+1 in statements, live, options; async sync-all; auto-sync on account add; re-enable strategies route.
- Frontend: Shared portfolio utils (buildAccountsFromPositions, toStartEnd, timeAgo, etc.); type safety (API response interfaces, typed hooks, AccountContext); useDebounce; account filter consistency (AccountContext); mutation toasts and skeletons; SortableTable Chakra + keyboard nav + aria-sort; accessibility (StatCard, PnlText, StageBar, StageBadge).
- Docs: Delete TODO.md, STATUS.md; merge TEST_PLAN into TESTS.md; update ARCHITECTURE, ROADMAP, PORTFOLIO, MODELS, frontend-ui.

Section 2 (PR 2) – Smart Categories + Strategy Engine
-----------------------------------------------------
- Backend: CategoryRule model + CategoryEngine (presets, drift, rebalance); Strategy enums (PAPER_TRADING, BACKTESTING; TRIM, REBALANCE, ROTATE); RuleEvaluator; Order model + OrderEngine, RiskGate, PaperExecutor, Reconciler; wire Strategy → Signal → Order pipeline.
- Frontend: Categories redesign (concentric rings, auto-organize, drift alerts, rebalance preview); StrategyList, StrategyBuilder; Overview redesign; invisible sync UX.

Section 3 (PR 3) – Live Execution + Polish
-------------------------------------------
- Broker order APIs (IBKR, TastyTrade, Schwab OAuth); circuit breakers and kill switch; StrategyDetail, StrategyBacktest; paper-to-live toggle; mobile polish.

Milestones (legacy)
-------------------
1) Data sync (IBKR + TastyTrade) – done
2) Portfolio UI – done (Overview, Holdings, Options, Transactions, Categories)
3) Section 1 Foundation – in progress
4) Section 2 Categories + Strategy – planned
5) Section 3 Live + Polish – planned

Operational
-----------
- CI runs tests, lints, alembic upgrade head
- CHANGELOG from conventional commits
- For run commands and migration workflow see ONBOARDING.md

