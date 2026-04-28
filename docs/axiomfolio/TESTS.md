---
owner: qa
last_reviewed: 2026-04-24
doc_kind: reference
domain: automation
status: active
---
# Testing Strategy

**How to run:** See [How to run](#how-to-run) below. Never run tests against the dev database; see [ONBOARDING.md](ONBOARDING.md) (golden rules).

---

## Table of contents

- [Test Database Isolation](#test-database-isolation-backend)
- [Safe Patterns](#safe-patterns-enforced)
- [Env Guidance](#env-guidance)
- [Do/Don't](#dodont)
- [Goals](#goals)
- [How to run](#how-to-run)
- [Scopes](#scopes)
- [Conventions](#conventions)
- [Test Plan](#test-plan-from-test_planmd)

---

## Test Database Isolation (Backend)
- Tests run against a dedicated Postgres database in Docker (`postgres_test`).
- **Safety invariant:** in tests, `DATABASE_URL` **must equal** `TEST_DATABASE_URL` so any accidental use of the app engine/session still targets the isolated test DB.
- Pytest will **fail closed** if `TEST_DATABASE_URL` is missing or unsafe.
- The test suite will:
  - Run Alembic migrations to head on the test database at session start.
  - Create a per-test transaction and roll it back after each test for isolation.
- Example: `make test` (or `./run.sh test`); uses **`infra/compose.dev.yaml`** at repo root per the Makefile.

## Safe Patterns (Enforced)
- Single DB path: all tests must use the `db_session` fixture. Direct `SessionLocal`/`engine`/`create_engine` imports in tests are blocked.
- Destructive tests: must be marked `@pytest.mark.destructive` and only run with `ALLOW_DESTRUCTIVE_TESTS=1` or `--allow-destructive-tests`.
- Never truncate or drop dev/prod tables. All DB tests run in an isolated test DB with per-test transactions and rollbacks.
- Schema guard: DB tests skip if core tables (e.g., `users`, `broker_accounts`) are missing in the test DB.
- Misconfig guard: DB tests skip if `TEST_DATABASE_URL` is unset or equals `DATABASE_URL`.
- Alembic: test migrations run only against `TEST_DATABASE_URL`.

## Env Guidance
- Leave production `.env` untouched.
- Local dev uses tracked defaults (`infra/env.dev.defaults`) plus local overrides.
- CI exports safe env vars from workflow YAML — do not put secrets in tracked files.
- Do not run backend tests against the dev database in production mode; use `TEST_DATABASE_URL` for isolated runs.

## Do/Don't
- Do: use the `db_session` fixture provided in `backend/tests/conftest.py`.
- Do: assume Alembic has upgraded the test DB to head before tests run.
- Don’t: call `init_db()` or instantiate `SessionLocal()` directly in tests.
- Don’t: rely on app `DATABASE_URL`; all DB tests must run on `TEST_DATABASE_URL`.

## Goals
- Fast unit tests for services and clients
- Focused integration tests for brokers and market data
- Smoke tests for API routes

## How to run

**Prefer the [Makefile](../Makefile) at repo root** (see [docs/axiomfolio/README.md](README.md)#makefile-quick-reference). All commands below are from repo root.

- **Backend only** (isolated DB): `make test` (or `./run.sh test`)
- **Frontend only** (lint + type-check + test): `make test-frontend` or `make frontend-check`
- **Both:** `make test-all`

Individual frontend steps: `make frontend-lint`, `make frontend-typecheck`, `make frontend-test`.

Focused runs: `make test-up` (if defined in Makefile) or run pytest inside the compose service that maps to the API you are changing — follow patterns in `apis/*/pytest.ini` / `conftest.py` for that package.

## Scopes
- Unit: deterministic logic (parsers, transforms, dedupe)
- Integration (flagged): real broker/market API using env credentials
- API: minimal happy-path per route

## Conventions
- Read secrets from env (never hardcode account numbers)
- Mark networked tests with @pytest.mark.integration
- Use AsyncMock/patch for SDKs in unit tests

## Test Plan (from TEST_PLAN.md)
Pyramids:
- Unit: fast, pure logic (parsers, transforms, dedupe)
- Integration: broker SDKs/APIs via env; FlexQuery XML fixtures; DB interactions
- API smoke: minimal happy paths per route

Suites:
- models/: uniqueness, FKs, invariants
- services/clients/: ibkr_client, ibkr_flexquery_client, tastytrade_client, schwab_client (placeholder)
- services/portfolio/: account_config_service, broker_sync_service, ibkr_sync_service, tastytrade_sync_service
- api/: holdings, options, live, statements, dividends; SSR filters and shapes
- category_engine: auto-categorization rules, drift computation, rebalance order generation
- rule_evaluator: condition tree evaluation, signal generation
- order_engine: idempotency, status transitions
- risk_gate: pre-trade checks, circuit breakers

Conventions (plan):
- pytest markers: @pytest.mark.integration for networked tests
- Env-driven secrets; never hardcode account numbers
- Run: `docker-compose exec backend pytest -q` or per-file

