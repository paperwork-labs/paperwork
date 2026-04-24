AxiomFolio Backend
===================

Overview
--------
FastAPI + SQLAlchemy + Alembic backend that unifies multi-broker data (IBKR, TastyTrade), persists portfolio state (positions, options, trades, transactions, dividends, balances, tax lots), and serves read-only APIs for the frontend. Heavy lifting happens here; the frontend only reads and executes trades via live connections.

Runbook (Docker)
----------------
Run from `apis/axiomfolio/` via the Makefile (Docker Compose is driven
from the monorepo-root `infra/compose.dev.yaml`; see `docs/INFRA.md`):

- Start dev stack:            `make up`
- With IB Gateway:            `make up-ibkr`
- Logs:                       `make logs`
- Shell into backend:         `make backend-shell`
- Tests (axiomfolio_test DB): `make test`
- Migrations (dev DB):
  - Apply:                    `make migrate-up`
  - Autogenerate:             `make migrate-create MSG="message"`
  - Downgrade:                `make migrate-down REV=-1`

Dependencies: Pydantic vs pydantic-settings
-------------------------------------------
- `pydantic` (v2.x) is used by FastAPI models and our ORM DTOs.
- `pydantic-settings` is used for environment-driven settings loading; do not remove it.
- Alembic is required for database migrations (CLI available inside backend container after rebuild).

Key Services
------------
- services/portfolio/ibkr_sync_service.py: FlexQuery + live API fallback; syncs positions, trades, transactions; writes `TransactionSyncStatus`; snapshot serialization fixes.
- services/portfolio/tastytrade_sync_service.py: Connects via SDK, normalizes data, dedupes by execution/order/external ids; inserts option positions only when quantity != 0.
- services/market/market_data_service.py: Fetches prices from yfinance/FMP/Finnhub/TwelveData; endpoint `/api/v1/market-data/prices/refresh` updates `positions` and `tax_lots`.
- api/routes/*: Clean endpoints powering frontend pages (standardized naming):
  - Portfolio live: `/api/v1/portfolio/live`
  - Stocks: `/api/v1/portfolio/stocks`, `/api/v1/portfolio/stocks/{position_id}/tax-lots`
  - Options: `/api/v1/portfolio/options/accounts`, `/api/v1/portfolio/options/unified/portfolio`, `/api/v1/portfolio/options/unified/summary`
  - Statements: `/api/v1/portfolio/statements`
  - Dividends: `/api/v1/portfolio/dividends`

Database & Models
-----------------
- Core models in `app/models/` with broker-agnostic schema: `position.py`, `options.py`, `trade.py`, `transaction.py`, `tax_lot.py`, etc.
- Dedupe safety (unique constraints):
  - trades: (`account_id`, `execution_id`) and (`account_id`, `order_id`)
  - transactions: (`account_id`, `external_id`) and (`account_id`, `execution_id`)
- options: (`account_id`, `underlying_symbol`, `strike_price`, `expiry_date`, `option_type`)

Frontend Contract
-----------------
- All list pages accept `account_id` for server-side filtering.
- Market data refresh endpoint should be called on page load to populate P&L when missing.

Operational Notes
-----------------
- .env lives at repo root; never overwrite from code.
- When dependencies change, rebuild containers; do not pip install on host.
- If an IBKR account shows no data, verify FlexQuery report config and throttling.

Housekeeping
------------
- Prefer adding new endpoints under `api/routes/` with single-responsibility files.
- Keep scripts under `app/scripts/` or remove if obsolete. Avoid standalone root-level scripts unless required.
Docs
----
- API routes overview: `app/api/README.md`
- See ../../docs/ARCHITECTURE.md, ../../docs/ROADMAP.md, ../../docs/STATUS.md
- Models reference: ../../docs/MODELS.md
- Test plan: ../../docs/TEST_PLAN.md and ../../docs/TESTS.md

