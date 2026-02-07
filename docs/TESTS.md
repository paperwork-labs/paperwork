Testing Strategy
================

Test Database Isolation (Backend)
---------------------------------
- Tests run against a dedicated Postgres database in Docker (`postgres_test`).
- **Safety invariant:** in tests, `DATABASE_URL` **must equal** `TEST_DATABASE_URL` so any accidental use of the app engine/session still targets the isolated test DB.
- Pytest will **fail closed** if `TEST_DATABASE_URL` is missing or unsafe.
- The test suite will:
  - Run Alembic migrations to head on the test database at session start.
  - Create a per-test transaction and roll it back after each test for isolation.
- Example (Docker):
  - Run: `./run.sh test` (this uses `infra/compose.test.yaml` + `infra/env.test`).

Safe Patterns (Enforced)
------------------------
- Single DB path: all tests must use the `db_session` fixture. Direct `SessionLocal`/`engine`/`create_engine` imports in tests are blocked.
- Destructive tests: must be marked `@pytest.mark.destructive` and only run with `ALLOW_DESTRUCTIVE_TESTS=1` or `--allow-destructive-tests`.
- Schema guard: DB tests skip if core tables (e.g., `users`, `broker_accounts`) are missing in the test DB.
- Misconfig guard: DB tests skip if `TEST_DATABASE_URL` is unset or equals `DATABASE_URL`.
- Alembic: test migrations run only against `TEST_DATABASE_URL`.

Env Guidance
------------
- Leave production `.env` untouched.
- Local dev uses `infra/env.dev` (untracked); tests use `infra/env.test` (untracked).
- CI should copy `infra/env.test.example` to `infra/env.test` for safe defaults.
- Do not run backend tests outside the isolated test compose stack unless you intentionally set `TEST_DATABASE_URL` to `postgres_test` and `_test` DB name.

Do/Don't
--------
- Do: use the `db_session` fixture provided in `backend/tests/conftest.py`.
- Do: assume Alembic has upgraded the test DB to head before tests run.
- Don’t: call `init_db()` or instantiate `SessionLocal()` directly in tests.
- Don’t: rely on app `DATABASE_URL`; all DB tests must run on `TEST_DATABASE_URL`.

Goals
-----
- Fast unit tests for services and clients
- Focused integration tests for brokers and market data
- Smoke tests for API routes

How to run
----------
- Recommended:
  - `./run.sh test`

- Backend only (isolated DB):
  - `make test`

- Frontend unit checks:
  - `make test-frontend`

- Both:
  - `make test-all`

- Focused (still isolated):
  - `make test-up`
  - `docker compose --project-name axiomfolio_test --env-file infra/env.test -f infra/compose.test.yaml run --rm backend_test bash -lc "python -m pytest backend/tests/test_client_tastytrade.py -q"`

Scopes
------
- Unit: deterministic logic (parsers, transforms, dedupe)
- Integration (flagged): real broker/market API using env credentials
- API: minimal happy-path per route

Conventions
-----------
- Read secrets from env (never hardcode account numbers)
- Mark networked tests with @pytest.mark.integration
- Use AsyncMock/patch for SDKs in unit tests

