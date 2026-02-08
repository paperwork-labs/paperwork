Architecture Overview
=====================

RBAC (Role-Based Access Control)
--------------------------------
- JWT includes `sub` (username) and `role` claim.
- `/api/v1/auth/me` returns `{ id, username, email, role }`.
- Use `require_roles([UserRole.ADMIN])` to guard routes. Admin router is mounted at `/api/v1/admin`.
- Non-admins receive HTTP 403 on admin routes.

Auth & Security Module
----------------------
- JWT helpers live in `backend/api/security.py`:
  - `JWT_ALGORITHM = "HS256"`
  - `create_access_token(claims, expires)` and `decode_token(token)`
- All routes resolve the current user via `backend/api/dependencies.py` (`get_current_user`, `get_optional_user`, `require_roles`).
- Encoding and decoding share one algorithm/secret source to avoid divergence.

Admin Seeding Policy
--------------------
- Dev-only convenience: when `DEBUG=True` and `ADMIN_*` are set, an admin user is auto-seeded (verified and active).
- In non-dev environments, admin seeding is disabled by default.
- Configure in `.env`: `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `DEBUG`.

Components
----------
- Backend: FastAPI service exposing REST endpoints
- DB: Postgres (state) + Redis (cache/queue)
- Frontend: React SPA consuming backend APIs
- Brokers: IBKR (FlexQuery + TWS) and TastyTrade (SDK)

System overview
---------------
![System architecture](assets/architecture_overview.png)

Scheduling Architecture
-----------------------
- Celery provides the workers (execution) and Beat provides periodic scheduling.
- RedBeat is a Redis-backed scheduler for Celery Beat – it does not replace Celery. It replaces the static, code-defined Beat schedule with a dynamic schedule persisted in Redis.
- We keep a small bootstrap `beat_schedule` in code (defaults) so a new environment has a sensible starting schedule; on startup the system can seed RedBeat from a job catalog when the store is empty.
- Admin UI (Settings → Admin → Schedules) interacts with an admin API to list/create/delete schedules in RedBeat with timezone-aware cron strings.
- Execution path:
  1. A schedule entry (RedBeat) triggers a task at the specified cron time (in its timezone).
  2. Celery routes the task to the appropriate worker queue.
  3. Tasks write a `JobRun` row and Redis last-run status; failures/slow runs can notify Discord and surface in KPIs.
- Market data jobs are universal (update tracked, backfills, indicators, history); account jobs (IBKR/TastyTrade syncs) are separate. Code defaults are grouped for clarity and UI displays them by group.

Broker Data Strategy
--------------------
- IBKR FlexQuery (system of record): trades, cash transactions (dividends/fees/taxes), tax lots (cost basis), account balances, margin interest, transfers, options (open + historical exercises). Persist into `trades`, `transactions`, `dividends`, `tax_lots`, `account_balances`, `margin_interest`, `transfers`, `options`.
- Implementation status: FlexQuery single-report fetch with cached XML; tax lots, options (positions + exercises), trades are parsed and persisted. Cash transactions (incl. dividends), account balances, margin interest, and transfers are now implemented and persisted. Celery task `sync_all_ibkr_accounts` can enqueue comprehensive syncs for all enabled IBKR accounts. Configure long history via `IBKR_FLEX_LOOKBACK_YEARS` in `.env` and FlexQuery template.
- IBKR TWS/Gateway (live overlay): intraday prices/positions, managed accounts discovery, account summary. Do not overwrite official cost basis; only update live prices/market values.
- TastyTrade SDK: discovery + positions/trades/transactions/dividends/balances via credentials. No hardcoded account numbers; env/secure storage only.

Data Flow
---------
1) Startup: create tables; optional account seeding (env-driven only).
2) Sync: FlexQuery comprehensive sync writes authoritative rows; live overlay updates prices/positions only.
3) Market data: provider-prioritized OHLCV fetch (FMP→TwelveData→yfinance), Redis caching, local indicator compute (pandas/numpy), snapshot persistence, scheduled backfills and history.
4) API: backend serves portfolio endpoints; frontend is read-only except trade execution paths.

Security
--------
- Env-only secrets; JWT planned for user auth; scoped tokens for prod

