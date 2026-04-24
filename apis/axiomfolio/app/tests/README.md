# AxiomFolio V1 - Test Suite
============================

Scope and Structure
-------------------
Tests are organized to validate core APIs, models, sync services, and analytics. Heavy external dependencies are mocked; local runs accept 200/404/422/500 for smoke tests when data isn’t seeded yet.

Layout (key files)
------------------
```
backend/tests/
├── test_api_smoke.py          # Minimal health + core endpoints
├── test_api_endpoints.py      # Portfolio + Market Data endpoint coverage
├── test_models_uniqueness.py  # DB uniqueness constraints (Trade, Transaction, Option)
├── test_models.py             # Model invariants/helpers
├── test_services.py           # Service-level pure logic
├── test_broker_sync_service.py# Broker sync orchestration (mocked)
├── test_atr_system_complete.py# ATR engine (if enabled)
└── conftest.py                # Pytest config/fixtures
```

What we assert now
------------------
- API availability and basic shapes for:
  - `/api/v1/portfolio/live`, `/portfolio/stocks`, `/portfolio/options/...`
  - `/api/v1/portfolio/statements`, `/portfolio/dividends`
  - `/api/v1/market-data/prices/refresh`, `/technical/*`
- Model dedupe constraints:
  - `Trade(account_id, execution_id)` and fallback `(account_id, order_id)`
  - `Transaction(account_id, external_id)` and fallback `(account_id, execution_id)`
  - `Option(account_id, underlying_symbol, strike_price, expiry_date, option_type)`

Conventions
-----------
- Keep tests systematic and concise; extend existing files instead of creating many variants.
- Mark true integration tests with `@pytest.mark.integration` and skip in default runs.
- Avoid hardcoding secrets or account numbers; derive from environment fixtures.

Running tests
-------------
Inside Docker:
```
docker-compose exec backend bash -lc "pytest -q"
```
Focused:
```
docker-compose exec backend bash -lc "pytest -q backend/tests/test_api_endpoints.py"
```

Next additions
--------------
- Options lifecycle mapping tests (buy/open, close/expire) from Trades → Options panel.
- Market technicals persistence tests (Weinstein weekly metrics).
- Portfolio API enrichment tests for stage/RS/MA bucket badges.
