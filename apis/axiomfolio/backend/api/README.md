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
  - GET `/admin/backfill/5m/toggle` – get 5m backfill toggle (admin)
  - GET `/admin/coverage/sanity` – admin sanity coverage (DB only) (admin)
  - GET `/admin/db/history` – DB history (price_data) (admin)
  - GET `/admin/jobs` – admin jobs (admin)
  - GET `/admin/tasks` – admin tasks (admin)
  - GET `/admin/tasks/status` – admin tasks status (admin)
  - GET `/coverage` – coverage summary
  - GET `/coverage/{symbol}` – symbol coverage
  - GET `/indices/constituents` – index constituents
  - GET `/prices/{symbol}` – current price
  - GET `/prices/{symbol}/history` – price history
  - GET `/snapshots` – technical snapshots (tracked)
  - GET `/snapshots/{symbol}` – technical snapshot (symbol)
  - GET `/snapshots/{symbol}/history` – snapshot history (symbol)
  - GET `/universe/tracked` – tracked universe
  - POST `/admin/backfill/coverage` – guided full backfill (tracked) (admin)
  - POST `/admin/backfill/since-date` – guided full backfill since date (admin)
  - POST `/admin/backfill/daily` – backfill daily bars (rolling) (admin)
  - POST `/admin/backfill/daily/since-date` – backfill daily bars since date (admin)
  - POST `/admin/backfill/5m` – backfill 5m bars (admin)
  - POST `/admin/backfill/coverage/stale` – backfill stale daily bars (admin)
  - POST `/admin/backfill/snapshots/history` – backfill snapshot history (admin)
  - POST `/admin/snapshots/history/record` – record snapshot history (admin)
  - POST `/admin/indicators/recompute-universe` – recompute indicators (universe) (admin)
  - POST `/admin/backfill/coverage/refresh` – refresh coverage cache (admin)
  - POST `/admin/backfill/5m/toggle` – toggle 5m backfill (admin)
  - POST `/admin/retention/enforce` – enforce retention (admin)
  - POST `/admin/snapshots/discord-digest` – snapshot digest to Brain webhook (admin; path unchanged)
  - POST `/admin/tasks/run` – admin run task (admin)
  - POST `/indices/constituents/refresh` – refresh constituents (admin)
  - POST `/symbols/{symbol}/refresh` – refresh symbol (admin)
  - POST `/universe/tracked/refresh` – refresh tracked universe (admin)

 

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


