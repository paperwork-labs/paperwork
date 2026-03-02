# Roadmap

Execution is split into sections. Complete Section 1, merge, then Section 2, then Section 3.

## Section 1 -- Foundation (PR 1) [DONE]

**Backend**

- Remove dead portfolio endpoints; fix N+1 in statements, live, options; async sync-all; auto-sync on account add; re-enable strategies route.

**Frontend**

- Shared portfolio utils (buildAccountsFromBroker, toStartEnd, timeAgo, etc.); type safety (API response types, typed hooks, AccountContext); useDebounce; account filter consistency (AccountContext); mutation toasts; skeletons (TableSkeleton, StatCardSkeleton in Holdings, Options, Transactions); SortableTable Chakra + filter debounce; accessibility (PnlText aria-label, StageBar role=img + aria-label, table overflowX); Pagination on Transactions.

**Docs**

- ARCHITECTURE, ROADMAP, PORTFOLIO, FRONTEND_UI, MODELS updated with mermaid and current patterns.

## Section 1.5 -- Brokerage Infra + Per-User Credentials (PR 191) [DONE]

**Backend**

- TastyTrade migrated to OAuth (SDK v12+); per-user encrypted credentials via AccountCredentials + CredentialVault (Fernet); Redis-backed ConnectJobStore for multi-worker connect flows; sync history recording (AccountSync model); API-level sync rejection tracking; Celery task time limits.

**Frontend**

- Connect wizard for TT (OAuth) and IBKR (FlexQuery); credential edit modal; sync history table with error tooltips; useConnectJobPoll hook with exponential backoff; modal centering fix (Chakra v3 DialogPositioner).

**Infra**

- Dev/prod parity: Celery restart policies, healthchecks, depends_on conditions; removed New Relic wrapper from dev backend; fixed celery beat volume-as-directory crash.

## Section 1.75 -- Market Data DB-First + Portfolio Intelligence [DONE]

**Backend**

- Refactor `get_historical_data()` to check `PriceData` table before calling external APIs. Current flow: Redis -> FMP/yfinance. Target flow: Redis (L1) -> PriceData table (L2) -> External API (L3, backfills DB on fetch).
- Write-through already implemented: every chart load that hits an external API now persists bars to `PriceData` via `persist_price_bars()`.
- Portfolio analytics now uses `MarketSnapshot.beta` for weighted portfolio beta (replaces hardcoded 1.0) and `MarketSnapshot.sector` as fallback for sector attribution.
- Unified indicator engine: single `compute_full_indicator_series()` replacing 4 scattered compute paths. Adds ADX, Bollinger, StochRSI, 52w H/L, volume avg, TD Sequential per-bar to both `MarketSnapshot` and `MarketSnapshotHistory`.
- Indicator series endpoint: `GET /market-data/prices/{symbol}/indicators` reads from `MarketSnapshotHistory` (SQL read, not on-the-fly computation). Gap detection triggers `backfill_snapshot_history_for_symbol()` for missing history.

**Frontend**

- Workspace now shows MarketSnapshot fundamentals (Stage, RSI, ATR%, P/E, Div Yield, Beta, RS Mansfield, Earnings date) in a context strip.
- Support/Resistance horizontal price levels from clustered pivot highs/lows.
- Persistent colored circle markers on chart event days (buy/sell/dividend) visible without hovering.
- Settings > Brokerages renamed to Settings > Connections -- unified hub for brokers, IB Gateway, TradingView preferences, future data providers.
- TradingView external link removed; all charting stays in-app. Default studies/interval synced to server preferences.

**Benefits**: Offline chart rendering, no wasted API credits, instant loads for known symbols, richer portfolio intelligence from existing BRAIN data. "Fetch once, ready forever" for both OHLCV and indicator history.

| Status | Item |
|--------|------|
| DONE | Write-through to PriceData on API fetch |
| DONE | MarketSnapshot LEFT JOIN for portfolio enrichment |
| DONE | Workspace context strip with fundamentals |
| DONE | DB-first read path (L1 Redis -> L2 PriceData -> L3 API) |
| DONE | Unified indicator engine rewrite |
| DONE | SettingsBrokerages -> SettingsConnections rename |
| DONE | Indicator series endpoint from MarketSnapshotHistory |
| DONE | 5-year snapshot history backfill (36,806 rows) |
| PLANNED | Frontend indicator migration (Track 1: scalar from DB, Track 2: geometric overlays stay on frontend) |

## Section 2 -- Options, Categories, IB Gateway [DONE]

### WS-1: IB Gateway Connection [P0]

- Validate credentials and Docker container config.
- `make ib-verify` target for end-to-end connection check.
- Exponential backoff in `connect_with_retry` (1s, 2s, 4s, 8s, 16s). No Celery auto-reconnect (anti-pattern for stateful IBKR connections).
- Manual reconnect button wired to `POST /portfolio/options/gateway-connect`.
- GatewayStatusBadge promoted to portfolio nav shell (visible on all portfolio pages).
- IB Gateway card in Settings > Connections.

### WS-2: Options Page Overhaul

**P0: Table + Decomposition**

- Migrate P/L table from raw Chakra `<TableRoot>` to `SortableTable` with sorting, filtering, presets (Winners, Losers, High Delta).
- Decompose 1263-line `PortfolioOptions.tsx` monolith into 7 focused components: shell, PositionsTab, OptionChainTab, PnlTab, StrategyCard, PositionRow, utils/optionStrategies.

**P1: Strategy Detection**

- Enhance from 4 patterns to full coverage: Covered Call, Cash-Secured Put, Calendar, Diagonal, Butterfly.
- Add credit/debit classification, max P/L, breakeven computation.
- Strategy card UX: net credit/debit, breakeven distance, "% of max profit" progress bar, combined Greeks row.

**P2: Advanced Analytics (Deferred)**

- Payoff diagrams, theta calendar, Greeks dashboard, chain heatmap, IV skew, P/L treemap.

### WS-3: Categories Redesign

**P0: Visibility + Presets**

- Show ticker chips on category cards (the core problem: can't see which tickers are where).
- Table view toggle with inline category dropdown for quick reassignment.
- Fix `Category.user_id` bug (column missing from model, filtered in routes).
- Auto-categorize presets: by Sector, Market Cap, Weinstein Stage, RS percentile.
- Preview modal before applying presets.

**P1: Drag-and-Drop + Allocation**

- `@dnd-kit` integration for dragging ticker chips between categories.
- Allocation ring chart (target vs actual as nested rings).
- Rebalance preview with before/after donut.

## Section 2.5 -- Backend-Served Indicator Series [DONE]

Architecture: `MarketSnapshotHistory` IS the indicator series. One row per (symbol, date) with all computed indicators. The endpoint is a SQL read, not on-the-fly computation.

```
Indicator Data Flow:
┌──────────┐     ┌──────────────────────────────┐     ┌──────────────────────┐
│ PriceData│ --> │ compute_full_indicator_series │ --> │ MarketSnapshotHistory│
│ (OHLCV)  │     │ (one unified function)        │     │ (immutable ledger)   │
└──────────┘     └──────────────────────────────┘     └──────────────────────┘
                                                              │
                                                    ┌────────┴─────────┐
                                                    │                  │
                                              .iloc[-1]          SQL read
                                                    │                  │
                                           ┌────────▼───┐    ┌────────▼────────┐
                                           │ MarketSnap- │    │ GET /indicators │
                                           │ shot(latest)│    │ (series endpoint)│
                                           └────────────┘    └─────────────────┘
```

**Two tracks for frontend migration:**

- **Track 1** (from MarketSnapshotHistory): EMA/SMA lines, RSI, MACD, Bollinger, ATR, stage coloring, TD Sequential labels, volume bars. Scalar-per-date values read from DB columns.
- **Track 2** (stays on frontend): Gap zones, trendline geometry, S/R level lists. Structured geometric objects computed from raw OHLCV.

## Section 2.6 -- Portfolio Finish Line [DONE]

**Sync Layer Refactor (Phase 0.5)**

- Split monolithic `ibkr_sync_service.py` (2092 lines) into `ibkr/` package: `pipeline.py`, `sync_positions.py`, `sync_transactions.py`, `sync_balances.py`, `sync_greeks.py`, `helpers.py`.
- Fixed silent `except: pass` blocks in TastyTrade sync; all errors now logged.
- Fixed `UniqueViolation` on transfers with empty `transaction_id`.
- Added `recover_stale_syncs` Celery task (every 5 min) for stuck accounts.
- Added `flexquery-diagnostic` endpoint for verifying FlexQuery config without persisting data.
- Schwab OAuth client scaffold and sync service implemented.

**Live Data + Monitoring**

- `GET /portfolio/live/summary` and `/live/positions` — real-time from IB Gateway with DB fallback.
- `GET /portfolio/dashboard/margin-health` — cushion, leverage, buying power, margin warnings.
- `GET /portfolio/dashboard/pnl-summary` — aggregated P&L, dividends, fees, total return.
- Frontend credential error surfacing ("Credentials invalid — please re-add this account").

**Frontend Fixes**

- `PortfolioTransactions.tsx`: Category filter aligned to backend categories, row count shows total, summary bar added.
- `PortfolioOverview.tsx`: API response shape handling, silent query failure fix.
- `PortfolioOptions.tsx`: Gateway offline state handling, type safety pass.

**Cron Alignment**

- IBKR Daily Sync: 01:00 UTC
- Daily Coverage Pipeline (OHLCV + indicators + history): 03:00 UTC
- Stale Sync Recovery: every 5 min

## Section 2.75 -- BRAIN + PORTFOLIO Integration

- "My Holdings" filter toggle in Market Tracked (highlight held symbols, show Qty/Cost/P&L columns).
- "Portfolio" badge on Market Dashboard setup table rows where symbol is held.
- Intelligence context strip in Workspace: Stage pill, RSI badge, ATR%, PE, Beta, RS Mansfield, earnings countdown, 52w range bar.
- Actionable insights: stage deterioration alerts, concentration warnings, sector drift, RS degradation, earnings proximity.
- Portfolio vs SPY benchmark comparison on Dashboard.

## Section 3 -- Live Execution + Polish (PR 3)

**Prerequisites**: IB Gateway connected and stable, Strategy models wired, order pipeline tested in paper mode.

- Broker order APIs (IBKR via ib_insync, TastyTrade SDK, Schwab OAuth).
- Strategy engine execution pipeline: Signal -> Order -> RiskGate -> Execution.
- Circuit breakers and kill switch (max daily loss, max position size, max orders/minute).
- StrategyDetail page, StrategyBacktest page (reads from MarketSnapshotHistory for historical indicator values).
- Paper-to-live toggle with confirmation gate.
- Watchlist management: `Watchlist` model, "Watch" toggle button, auto-add to tracked universe.
- Mobile polish: responsive layouts, touch-friendly drag-and-drop fallback.

## Section 3.5 -- Charts and TA Enhancement

- Upgrade `lightweight-charts` from v4.2.1 (CDN) to v5 (npm). Gain native `createPane()` for sub-charts.
- RSI/MACD/Bollinger sub-panes using backend indicator series.
- Stage background coloring (subtle tint by Weinstein stage).
- Earnings markers, comparison overlay (SPY/sector ETF), multi-timeframe toggle.
- Screenshot button via `chart.takeScreenshot()`.
- Do NOT build: drawing tools, volume profile, custom indicators, Elliott Wave, Fibonacci (use TradingView for these).

## Testing Requirements

- **Financial calculations**: Unit tests for every indicator in `compute_full_indicator_series()`. Parity tests comparing Python output vs TypeScript `utils/indicators/` output for same OHLCV input.
- **Strategy detection**: Unit tests for every pattern in `utils/optionStrategies.ts` with known position sets.
- **Integration**: DB-first read path (L1 miss -> L2 hit), indicator gap detection and backfill trigger, race condition handling (indicators requested before OHLCV fetched).
- **Backend**: Pytest for all new endpoints, Alembic migration up/down.
- **Frontend**: Vitest for utility functions and hooks.

## Operational

- CI runs tests, lints, alembic upgrade head.
- CHANGELOG from conventional commits.
- Run commands and migration workflow: see ONBOARDING.md.
