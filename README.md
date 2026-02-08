AxiomFolio
==========

Monorepo for the AxiomFolio trading platform.

- Backend: FastAPI + SQLAlchemy + Alembic (Docker)
- Frontend: React + Vite + Chakra UI (Docker)
- DB: Postgres + Redis

Quick Start
-----------
- Preferred local entrypoint:
  - `make up`
  - `make ps`
- Backend: http://localhost:8000/docs
- Frontend: http://localhost:3000

Onboarding
----------
- Start here: `docs/ONBOARDING.md`

Environment Files
-----------------
- Dev stack uses `infra/env.dev` (copy from `infra/env.dev.example`).
- Test stack uses `infra/env.test` (copy from `infra/env.test.example`) and is physically isolated via the `postgres_test` service.
- Your legacy `.env` remains local-only; Docker orchestration is standardized on `infra/env.*`.

Tests (Isolated DB)
-------------------
- Backend (isolated DB): `make test`
- Frontend (unit): `make test-frontend`
- Both: `make test-all`

PR Automation
-------------
- Dependabot PRs can auto-merge after CI passes.
- Preferred flow for agent/human changes:
  - `scripts/open_pr.sh <type> "short description"` (creates `agent/**` branch, commits, pushes, opens draft PR)
  - Do **not** run `gh pr create` manually; `agent-auto-pr.yml` opens the bot PR on push.
- Full details in `docs/PR_AUTOMATION.md`.

Migrations
----------
- docker-compose exec backend alembic revision -m "message" --autogenerate
- docker-compose exec backend alembic upgrade head

Docs
----
- Canonical docs live under `docs/`:
  - Architecture: `docs/ARCHITECTURE.md`
  - Models: `docs/MODELS.md`
  - Market Data: `docs/MARKET_DATA.md`
  - Rebrand runbook: `docs/REBRAND.md`
  - Tests: `docs/TESTS.md`, `docs/TEST_PLAN.md`
  - Roadmap/Status: `docs/ROADMAP.md`, `docs/STATUS.md`
  - Brokers: `docs/BROKERS.md`
  - TODOs: `docs/TODO.md`

API Map (v1)
------------
- Portfolio:
  - Live: `/api/v1/portfolio/live`
  - Stocks: `/api/v1/portfolio/stocks`, `/api/v1/portfolio/stocks/{position_id}/tax-lots`
  - Options: `/api/v1/portfolio/options/accounts`, `/api/v1/portfolio/options/unified/portfolio`, `/api/v1/portfolio/options/unified/summary`
  - Statements: `/api/v1/portfolio/statements`
  - Dividends: `/api/v1/portfolio/dividends`
- Market Data:
  - Refresh prices: `POST /api/v1/market-data/prices/refresh`
  - Technicals: `GET /api/v1/market-data/technical/moving-averages/{symbol}`
  - MA bucket: `GET /api/v1/market-data/technical/ma-bucket/{symbol}`
  - Stage (Weinstein): `GET /api/v1/market-data/technical/stage/{symbol}`

Market Data (dev vs prod)
-------------------------
- Dev: Docker Compose stack with optional Celery Beat/RedBeat; trigger tasks with `make task-run`.
- Prod: Provider cron (Render/Fly) enqueues tasks via `backend/scripts/run_task.py`; workers consume from Redis.
- Diagrams + flow details: `docs/MARKET_DATA.md`.

Naming
------
- Position = equities (stocks/ETFs)
- Option = option contracts (per-contract state)
- Avoid “holdings” in routes and UI; use “stocks” and “options” consistently

Task Flow (Celery)
------------------
- See `backend/tasks/README.md` for full task descriptions and schedules.
- Daily pipeline (high level):
  - Portfolio backfill (delta-only, ~270 bars) → `price_data`
  - Indicator refresh (portfolio + indices) → `market_analysis_cache`
  - Daily history snapshots → `market_analysis_history`
  - Optional Pine metrics enrichment → latest cache row
- Operations:
  - Flower: http://localhost:5555 (Workers → current worker → Tasks)
  - Provider policy: paid month prioritizes FMP; free mode prioritizes Finnhub → Twelve Data → yfinance; indicators computed locally from stored OHLCV

