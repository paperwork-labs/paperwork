# Roadmap

Execution is split into three sections (PRs). Complete Section 1, merge, then Section 2, then Section 3.

## Section 1 — Foundation (PR 1)

**Backend** (done)

- Remove dead portfolio endpoints; fix N+1 in statements, live, options; async sync-all; auto-sync on account add; re-enable strategies route.

**Frontend** (done)

- Shared portfolio utils (buildAccountsFromBroker, toStartEnd, timeAgo, etc.); type safety (API response types, typed hooks, AccountContext); useDebounce; account filter consistency (AccountContext); mutation toasts; skeletons (TableSkeleton, StatCardSkeleton in Holdings, Options, Transactions); SortableTable Chakra + filter debounce; accessibility (PnlText aria-label, StageBar role=img + aria-label, table overflowX); Pagination on Transactions.

**Docs** (done)

- ARCHITECTURE, ROADMAP, PORTFOLIO, frontend-ui, MODELS updated with mermaid and current patterns.

## Section 2 — Smart Categories + Strategy Engine (PR 2)

**Planned**

- Backend: CategoryRule model + CategoryEngine (presets, drift, rebalance); Strategy enums (PAPER_TRADING, BACKTESTING; TRIM, REBALANCE, ROTATE); RuleEvaluator; Order model + OrderEngine, RiskGate, PaperExecutor, Reconciler; wire Strategy → Signal → Order pipeline.
- Frontend: Categories redesign (concentric rings, auto-organize, drift alerts, rebalance preview); StrategyList, StrategyBuilder; Overview redesign; invisible sync UX.

## Section 3 — Live Execution + Polish (PR 3)

**Planned**

- Broker order APIs (IBKR, TastyTrade, Schwab OAuth); circuit breakers and kill switch; StrategyDetail, StrategyBacktest; paper-to-live toggle; mobile polish.

## Operational

- CI runs tests, lints, alembic upgrade head.
- CHANGELOG from conventional commits.
- Run commands and migration workflow: see ONBOARDING.md.
