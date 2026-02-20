# Portfolio Section

Overview of the Portfolio frontend and data flow.

## Routes

| Route | Page | Description |
|-------|------|-------------|
| `/portfolio` | Portfolio Overview | KPIs, allocation donut, performance chart, stage distribution, top movers, account cards |
| `/portfolio/holdings` | Holdings | Enriched SortableTable (stage, RS%, sector), filter presets, heatmap toggle, SymbolLink |
| `/portfolio/options` | Options | Summary KPIs, positions grouped by underlying, account filter |
| `/portfolio/transactions` | Transactions | Unified activity feed; date range, category, side, symbol filters |
| `/portfolio/categories` | Categories | Category cards, target/actual allocation, CRUD, position assignment |
| `/portfolio/workspace` | Workspace | Per-symbol deep dive (chart, tax lots) |

## Data flow

1. **Brokerage sync** (Settings → Brokerages): IBKR FlexQuery and/or Tastytrade sync populate `positions`, `trades`, `tax_lots`, `transactions`, `dividends`, `options`, `account_balances`, `portfolio_snapshots`.
2. **Sync lifecycle**: POST /accounts/sync-all is async (returns task_ids for polling). After POST /accounts/add, a Celery sync task is auto-enqueued; response includes sync_task_id. Frontend can trigger sync on login when accounts are NEVER_SYNCED.
3. **Backend APIs**: Portfolio routes under `/api/v1/portfolio` serve dashboard, stocks (with optional market data enrichment), performance history, categories CRUD, activity, options.
4. **Market–portfolio bridge**: `GET /portfolio/stocks?include_market_data=true` LEFT JOINs latest `MarketSnapshot` per symbol so positions include `stage_label`, `rs_mansfield_pct`, `perf_1d`/`perf_5d`/`perf_20d`, `rsi`, `atr_14`. Portfolio symbols are part of the tracked universe; no separate sync.
5. **Frontend**: React Query hooks (`usePositions`, `usePortfolioOverview`, `useOptions`, `useActivity`, etc.) consume APIs; shared components (StatCard, StageBar, StageBadge, PnlText, SymbolLink) and `AccountFilterWrapper` provide consistent UI. Account selection is global (AccountContext) so Overview, Holdings, Options, Transactions share the same selection.

## Smart categories (planned)

- **CategoryRule** model and **CategoryEngine** service: auto_categorize (presets: market cap, sector, Weinstein stage, account type), compute_drift, generate_rebalance_orders. Hooked into post-sync when user has rules.
- **Strategy bridge**: Category allocation drift can feed into strategy signals (REBALANCE) for rebalance automation.

## Key files

- **Types**: `frontend/src/types/portfolio.ts`
- **Hooks**: `frontend/src/hooks/usePortfolio.ts`
- **Shared components**: `frontend/src/components/shared/` (StatCard, StageBar, StageBadge, PnlText)
- **Pages**: `frontend/src/pages/portfolio/` (PortfolioOverview, PortfolioHoldings, PortfolioOptions, PortfolioTransactions, PortfolioCategories)
- **Backend**: `backend/api/routes/portfolio_*.py`, `backend/api/routes/portfolio_categories.py`
