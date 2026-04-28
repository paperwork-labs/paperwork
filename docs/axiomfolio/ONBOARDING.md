---
owner: engineering
last_reviewed: 2026-04-24
doc_kind: template
domain: company
status: active
---
# Onboarding (Humans + Agents)

This repo is a Docker-first monorepo.

- **Backend:** FastAPI + SQLAlchemy + Alembic + Celery (workers + **Celery Beat** for schedules)
- **Frontend:** React 19 + TypeScript 5 + Vite + **shadcn/ui** (Radix primitives) + **Tailwind CSS** + TanStack React Query v5 + Recharts + lightweight-charts v5
- **State:** PostgreSQL + Redis

**Use the [Makefile](../Makefile) at repo root** for dev and test commands (see [README.md](README.md)#makefile-quick-reference). After quick start, see [ARCHITECTURE.md](ARCHITECTURE.md) and [README.md](README.md) for the full doc index.

UI styling lives in Tailwind utilities, shared components under `frontend/src/components/ui/`, and global CSS variables — not a Chakra-style token file.

## Golden rules

1) **Never run tests against the dev database.**
   - Backend tests are designed to **fail closed** if `TEST_DATABASE_URL` is missing or unsafe.
   - Use **`make test`** (or `./run.sh test`) from repo root. See [TESTS.md](TESTS.md).

2) **No direct pushes to `main`.**
   - Dependabot PRs may auto-merge after CI passes.
   - Everything else lands via PR.

3) **Infra is canonical under `infra/`.**
   - Dev stack: `infra/compose.dev.yaml` + env defaults (`infra/env.dev.defaults`; copy/symlink locally as needed).
   - Tests: root `make test` runs pytest inside compose services defined in **`infra/compose.dev.yaml`** (there is no separate test-only compose file).

Prerequisites
-------------
- Docker Desktop
- `make`
- Node is only needed on host if you run the frontend outside Docker (not recommended).

Quick start (dev stack)
-----------------------
From repo root (prefer Makefile):
- `make up` — start full dev stack (backend, frontend, Postgres, Redis, Celery worker, Celery Beat, and all profile services by default) (or `./run.sh start`)
- `make ps` — container status (or `./run.sh status`)
- `make logs` — tail backend, Celery worker, **Celery Beat**, frontend, and Ladle logs (or `./run.sh logs`)

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
From repo root, use the **Makefile** (see [README.md](README.md)#makefile-quick-reference):

- **Backend only:** `make test` (isolated test DB; never touches dev DB)
- **Frontend only:** `make test-frontend` (install + lint + type-check + tests; same as `make frontend-check`)
- **Both:** `make test-all`

Equivalent: `./run.sh test` for backend where supported. Notes: uses the same **`infra/compose.dev.yaml`** stack as dev; backend tests target isolated DB URLs (`TEST_DATABASE_URL`) rather than a second compose file.

Migrations (dev DB only)
------------------------
From repo root (Makefile):

- Apply: `make migrate-up` (or `./run.sh migrate`)
- Create: `make migrate-create MSG="add new table"` (or `./run.sh makemigration "add new table"`)
- Downgrade: `make migrate-down REV=-1` (or `./run.sh downgrade -1`)
- Stamp head: `make migrate-stamp-head` (or `./run.sh stamp`)

CI (GitHub Actions)
-------------------
- Workflow: `.github/workflows/ci.yaml`
  - Backend: pytest runs in Docker (same isolation as local)
  - Frontend: lint + typecheck + unit tests

PR automation
-------------
See `docs/axiomfolio/PR_AUTOMATION.md`.

