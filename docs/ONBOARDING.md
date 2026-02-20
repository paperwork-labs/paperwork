Onboarding (Humans + Agents)
===========================

This repo is a Docker-first monorepo.

- Backend: FastAPI + SQLAlchemy + Alembic
- Frontend: React + Vite + Chakra UI
- State: Postgres + Redis

Golden rules
------------

1) **Never run tests against the dev database.**
   - Backend tests are designed to **fail closed** if `TEST_DATABASE_URL` is missing or unsafe.
   - The only supported backend test entrypoint is `./run.sh test` (or `make test`).

2) **No direct pushes to `main`.**
   - Dependabot PRs may auto-merge after CI passes.
   - Everything else lands via PR.

3) **Infra is canonical under `infra/`.**
   - Dev stack: `infra/compose.dev.yaml` + `infra/env.dev`
   - Test stack: `infra/compose.test.yaml` + `infra/env.test`

Prerequisites
-------------
- Docker Desktop
- `make`
- Node is only needed on host if you run the frontend outside Docker (not recommended).

Quick start (dev stack)
-----------------------
- `./run.sh start`
- `./run.sh status`
- `./run.sh logs`

Local dev (frontend on host, backend on host)
---------------------------------------------
If you run the frontend with `npm run dev` and the backend separately (e.g. `uvicorn` on port 8000), login can time out because the dev proxy targets `http://backend:8000` (Docker hostname). Do one of the following:

1. **Proxy target:** In the frontend directory create or edit `.env` and set:
   - `VITE_PROXY_TARGET=http://localhost:8000`
   Then restart the Vite dev server. API requests to `/api/v1` will be proxied to your local backend.

2. **Direct API URL:** Alternatively set:
   - `VITE_API_BASE_URL=http://localhost:8000/api/v1`
   The frontend will call the backend directly (no proxy). Ensure the backend allows CORS for your frontend origin.

Run tests (safe, isolated DB)
-----------------------------
- `./run.sh test`

Other useful targets:
- Backend only (isolated DB): `make test`
- Frontend unit checks: `make test-frontend`
- Both: `make test-all`

Notes:
- This uses `infra/compose.test.yaml` with `postgres_test` + an isolated Docker volume.
- `infra/env.test` is untracked; if missing, `./run.sh test` copies from `infra/env.test.example`.

Migrations (dev DB only)
------------------------
- Apply migrations:
  - `./run.sh migrate`
- Create an autogenerate migration:
  - `./run.sh makemigration "add new table"`
- Downgrade:
  - `./run.sh downgrade -1`
- Stamp head:
  - `./run.sh stamp`

CI (GitHub Actions)
-------------------
- Workflow: `.github/workflows/ci.yml`
  - Backend: pytest runs in Docker (same isolation as local)
  - Frontend: lint + typecheck + unit tests

PR automation
-------------
See `docs/PR_AUTOMATION.md`.


