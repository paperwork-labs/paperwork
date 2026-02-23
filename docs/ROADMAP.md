# Roadmap

Execution is split into three sections (PRs). Complete Section 1, merge, then Section 2, then Section 3.

## Section 1 -- Foundation (PR 1) [DONE]

**Backend**

- Remove dead portfolio endpoints; fix N+1 in statements, live, options; async sync-all; auto-sync on account add; re-enable strategies route.

**Frontend**

- Shared portfolio utils (buildAccountsFromBroker, toStartEnd, timeAgo, etc.); type safety (API response types, typed hooks, AccountContext); useDebounce; account filter consistency (AccountContext); mutation toasts; skeletons (TableSkeleton, StatCardSkeleton in Holdings, Options, Transactions); SortableTable Chakra + filter debounce; accessibility (PnlText aria-label, StageBar role=img + aria-label, table overflowX); Pagination on Transactions.

**Docs**

- ARCHITECTURE, ROADMAP, PORTFOLIO, frontend-ui, MODELS updated with mermaid and current patterns.

## Section 1.5 -- Brokerage Infra + Per-User Credentials (PR 191) [DONE]

**Backend**

- TastyTrade migrated to OAuth (SDK v12+); per-user encrypted credentials via AccountCredentials + CredentialVault (Fernet); Redis-backed ConnectJobStore for multi-worker connect flows; sync history recording (AccountSync model); API-level sync rejection tracking; Celery task time limits.

**Frontend**

- Connect wizard for TT (OAuth) and IBKR (FlexQuery); credential edit modal; sync history table with error tooltips; useConnectJobPoll hook with exponential backoff; modal centering fix (Chakra v3 DialogPositioner).

**Infra**

- Dev/prod parity: Celery restart policies, healthchecks, depends_on conditions; removed New Relic wrapper from dev backend; fixed celery beat volume-as-directory crash.

## Section 1.75 -- Market Data DB-First + Portfolio Intelligence [NEXT]

**Backend**

- Refactor `get_historical_data()` to check `PriceData` table before calling external APIs. Current flow: Redis -> FMP/yfinance. Target flow: Redis (L1) -> PriceData table (L2) -> External API (L3, backfills DB on fetch).
- Write-through already implemented: every chart load that hits an external API now persists bars to `PriceData` via `persist_price_bars()`.
- Portfolio analytics now uses `MarketSnapshot.beta` for weighted portfolio beta (replaces hardcoded 1.0) and `MarketSnapshot.sector` as fallback for sector attribution.

**Frontend**

- Workspace now shows MarketSnapshot fundamentals (Stage, RSI, ATR%, P/E, Div Yield, Beta, RS Mansfield, Earnings date) in a context strip.
- Support/Resistance horizontal price levels from clustered pivot highs/lows.
- Persistent colored circle markers on chart event days (buy/sell/dividend) visible without hovering.

**Benefits**: Offline chart rendering, no wasted API credits, instant loads for known symbols, richer portfolio intelligence from existing BRAIN data.

## Section 2 -- Smart Categories + Strategy Engine (PR 2)

**Planned**

- Backend: CategoryRule model + CategoryEngine (presets, drift, rebalance); Strategy enums (PAPER_TRADING, BACKTESTING; TRIM, REBALANCE, ROTATE); RuleEvaluator; Order model + OrderEngine, RiskGate, PaperExecutor, Reconciler; wire Strategy -> Signal -> Order pipeline.
- Frontend: Categories redesign (concentric rings, auto-organize, drift alerts, rebalance preview); StrategyList, StrategyBuilder; Overview redesign; invisible sync UX.

## Section 3 -- Live Execution + Polish (PR 3)

**Planned**

- Broker order APIs (IBKR, TastyTrade, Schwab OAuth); circuit breakers and kill switch; StrategyDetail, StrategyBacktest; paper-to-live toggle; mobile polish.

## Section 2.5 -- Backend-Served Indicator Series

**Planned**

- New endpoint `GET /market-data/prices/{symbol}/indicators` returning full EMA series, trendline coordinates, gap zones, TD Sequential labels.
- Eliminates all frontend indicator computation -- frontend becomes a pure renderer.
- Server-side caching of computed indicator series.
- Prerequisite: DB-first OHLCV reads from Section 1.75.

## Section 2.75 -- BRAIN + PORTFOLIO Integration

**Planned**

- "My Holdings" filter toggle in Market Tracked page (highlight/filter to held symbols).
- Holdings badges in Market Dashboard (mark held symbols in setup tables, stage transitions, divergence alerts).
- Stage change alerts for portfolio positions (Alert model + AlertCondition exist, need routes + UI + Celery task).
- Portfolio vs SPY benchmark comparison on Dashboard.
- Watchlist management (track symbols beyond index constituents + portfolio holdings).
- Strategy engine execution (Strategy, Signal, Order models exist -- need pipeline: Signal -> Order -> RiskGate -> Execution).

## Operational

- CI runs tests, lints, alembic upgrade head.
- CHANGELOG from conventional commits.
- Run commands and migration workflow: see ONBOARDING.md.
