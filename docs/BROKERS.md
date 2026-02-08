# Brokers and Data Services

Broker Integrations
===================

Implemented
-----------
- IBKR
  - History (system of record): FlexQuery (trades, tax lots, cash transactions incl. dividends/fees/taxes, account balances, margin interest, transfers, options + exercises)
  - Live overlay: TWS/Gateway (intraday prices/positions, account summary, discovery)
- TastyTrade
  - SDK with username/password (accounts, positions, trades, transactions, dividends, balances)

Broker sync flow
----------------
![Broker sync flow](assets/brokers_sync_flow.png)

Planned
-------
- Schwab: OAuth app required. Env: SCHWAB_CLIENT_ID, SCHWAB_CLIENT_SECRET, SCHWAB_REDIRECT_URI, ENCRYPTION_KEY. Live trading: Yes after app approval (feature-flagged).
- Fidelity: no broad public trading API. Possible via partner/experimental; likely read-only first.
- Robinhood: private/undocumented API; trading possible but stability/ToS concerns. Prefer read-only.

Approach to add a broker
------------------------
1) Client in backend/services/clients/<broker>_client.py (env-only creds)
2) Normalize to canonical fields (market_value, asset_category, account_id FK)
3) Add sync service under backend/services/portfolio/
4) Expose account add/list/sync routes under /api/v1/accounts
5) Seeding: env-driven; never hardcode account numbers; optional discovery

Schwab Direct OAuth (Internal Aggregator)
-----------------------------------------
- Backend routes:
  - POST `/api/v1/aggregator/brokers` → returns available brokers
  - POST `/api/v1/aggregator/schwab/link` → returns authorization URL (requires JWT; body: `{ account_id, trading }`)
  - GET `/api/v1/aggregator/schwab/callback` → handles `code` + `state`, persists encrypted tokens to `AccountCredentials`, marks `BrokerAccount` connected
- Storage:
  - Credentials encrypted at rest via `CredentialVault` (Fernet). Configure `ENCRYPTION_KEY` or fallback derives from `SECRET_KEY` (dev only).
- Sync:
  - `SchwabSyncService` ingests equities + options (basic), with corporate action (split) adjustments.
  - Orchestrated via `BrokerSyncService`; existing `/api/v1/accounts/{id}/sync` kicks off a Celery task.
- Frontend:
  - Settings page lists accounts, adds Schwab accounts, opens the link URL in a new tab to complete OAuth, and triggers sync.

## Index Constituents Service
- File: `backend/services/market/index_constituents_service.py`
- Purpose: Fetch and cache constituents for SP500, NASDAQ100, DOW30 (FMP primary, Polygon optional, Wikipedia fallback)
- Used to build ATR universe and market scanners
- Cached 24h in Redis to minimize API calls

