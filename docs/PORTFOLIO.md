# Portfolio Section

Overview of the Portfolio frontend and data flow.

## Routes

| Route | Page | Description |
|-------|------|-------------|
| `/portfolio` | PortfolioOverview | KPIs, allocation donut, performance chart, stage distribution, top movers, account cards |
| `/portfolio/holdings` | PortfolioHoldings | Enriched SortableTable (stage, RS%, sector), filter presets, heatmap toggle, SymbolLink |
| `/portfolio/options` | PortfolioOptions | Summary KPIs (StatCards), positions grouped by underlying, account filter |
| `/portfolio/transactions` | PortfolioTransactions | Unified activity feed with pagination; date range, category, side, symbol filters |
| `/portfolio/categories` | PortfolioCategories | Category cards, target/actual allocation, CRUD, position assignment |
| `/portfolio/workspace` | PortfolioWorkspace | Per-symbol deep dive (chart, tax lots) |

## Sync lifecycle

1. **Brokerage** (Settings → Brokerages): Add IBKR or TastyTrade account → POST /accounts/add.
2. **Backend**: Celery `sync_account_task` is enqueued; response includes `sync_task_id` for polling.
3. **Sync populates**: `positions`, `trades`, `tax_lots`, `transactions`, `dividends`, `options`, `account_balances`, `portfolio_snapshots`.
4. **Frontend**: POST /accounts/sync-all returns `{ status: "queued", task_ids }`; sync can be triggered on login when accounts are NEVER_SYNCED.

## Market data integration

- **Bridge**: `GET /portfolio/stocks?include_market_data=true` LEFT JOINs latest `MarketSnapshot` per symbol.
- **Enrichment**: Positions get `stage_label`, `rs_mansfield_pct`, `perf_1d`/`perf_5d`/`perf_20d`, `rsi`, `atr_14`. Portfolio symbols are in the tracked universe; no separate market sync.

## Smart categories (planned)

- **CategoryRule** model and **CategoryEngine**: auto_categorize (presets: market cap, sector, Weinstein stage, account type), compute_drift, generate_rebalance_orders. Hooked into post-sync when user has rules.
- **Strategy bridge**: Category allocation drift can feed into strategy signals (REBALANCE).

## Component architecture

- **Shared** (`frontend/src/components/shared/`): StatCard, StageBar, StageBadge, PnlText, Skeleton (StatCardSkeleton, TableSkeleton, ChartSkeleton).
- **UI** (`frontend/src/components/ui/`): AccountFilterWrapper (account selector + loading/skeleton slot), Pagination, SortableTable (with debounced filter inputs).
- **Hooks**: `usePortfolio.ts` — usePositions, usePortfolioOverview, useOptions, useActivity, usePortfolioAccounts, usePortfolioSync; `useAccountContext` for global account selection.
- **Types**: `frontend/src/types/portfolio.ts`.

## Key files

- **Types**: `frontend/src/types/portfolio.ts`
- **Hooks**: `frontend/src/hooks/usePortfolio.ts`
- **Pages**: `frontend/src/pages/portfolio/` (PortfolioOverview, PortfolioHoldings, PortfolioOptions, PortfolioTransactions, PortfolioCategories, PortfolioWorkspace)
- **Backend**: `backend/api/routes/portfolio*.py`, `backend/api/routes/activity.py`
