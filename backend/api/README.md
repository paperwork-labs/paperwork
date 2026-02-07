AxiomFolio V1 API
==================

Overview
--------
FastAPI application exposing clean, broker‑agnostic portfolio APIs. The backend does the heavy lifting (sync, P&L, analytics); the frontend consumes read‑only endpoints and only uses live connections to execute trades.

Route Organization
------------------
- Prefix: `/api/v1`
- Tags in Swagger (/docs):
  - Authentication
  - Accounts
  - Portfolio (includes stocks and options)
  - Market Data & Technicals

Modules and Prefixes
--------------------
- `auth` → included at `/api/v1/auth` (tag: Authentication)
  - POST `/register`, POST `/login`, GET `/me`, etc.

- `account_management` → `/api/v1/accounts` (tag: Accounts)
  - POST `/add`, GET `` (list), POST `/{account_id}/sync`, POST `/sync-all`, DELETE `/{account_id}`

- Portfolio (tag: Portfolio) – all under `/api/v1/portfolio`
  - `portfolio_live.py`
    - GET `/live` – aggregated accounts map and summary for dashboard
  - `portfolio_stocks.py`
    - GET `/stocks` – equity positions (server-side filtering: `user_id`, `account_id`)
    - GET `/stocks/{position_id}/tax-lots`
  - `portfolio_options.py` (nested under `/portfolio/options`)
    - GET `/options/accounts`
    - GET `/options/unified/portfolio`
    - GET `/options/unified/summary`
  - `portfolio_statements.py`
    - GET `/statements` – unified transactions (optional `user_id`, `account_id`, `days`)
  - `portfolio_dividends.py`
    - GET `/dividends` – dividends (optional `user_id`, `account_id`, `days`)
  - `portfolio.py`
    - GET `/summary`, `/positions`, `/performance` (auth placeholder via `get_current_user`)

- `market_data.py` → `/api/v1/market-data` (tag: Market Data & Technicals)
  - POST `/prices/refresh` – refreshes P&L for positions and tax lots
  - GET `/technical/snapshot/{symbol}` – latest technical snapshot from `market_analysis_cache`
  - POST `/technical/snapshot/{symbol}/refresh` – recompute + persist snapshot
  - GET `/technical/stage/{symbol}` – Weinstein stage; prefers cached snapshot, falls back to on-demand
  - Admin: POST `/admin/backfill/index` – backfill OHLCV for an index
  - Admin: POST `/admin/indicators/refresh-index` – refresh indicators (MarketAnalysisCache) for index constituents
  - Admin: POST `/admin/history/record` – record daily snapshot history

 

Naming Standards
----------------
- Position: equities only (stocks/ETFs)
- Option: options contract/position (singular model; table `options`)
- Stocks vs Options: avoid “holdings”; use stocks and options across API and UI

Auth & Dependencies
-------------------
- `backend/api/dependencies.py` provides `get_current_user` (placeholder) and `get_admin_user`
- `auth` routes include JWT scaffolding; main app includes `auth` at `/api/v1/auth` with tag “Authentication”

Examples
--------
Fetch live portfolio (all accounts):
```
GET /api/v1/portfolio/live
```

Fetch stocks for an account:
```
GET /api/v1/portfolio/stocks?account_id={ACCOUNT_NUMBER}
```

Unified options portfolio (account filter):
```
GET /api/v1/portfolio/options/unified/portfolio?account_id={ACCOUNT_NUMBER}
```

Refresh prices for current positions:
```
POST /api/v1/market-data/prices/refresh
```

Conventions & Notes
-------------------
- All server-side filtering via query params for consistent SSR on the frontend
- No hardcoded accounts; read from DB and environment seeding on startup
- Options grouped under Portfolio in Swagger for a single consolidated section

Where to add new endpoints
--------------------------
- Portfolio stocks: `backend/api/routes/portfolio_stocks.py`
- Portfolio options: `backend/api/routes/portfolio_options.py`
- Portfolio statements/dividends/live: respective `portfolio_*.py` files
- Technicals/market data: `backend/api/routes/market_data.py`


