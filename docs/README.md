# AxiomFolio documentation

This folder contains onboarding, architecture, domain pillars (connections, portfolio, market data), operations runbooks, and reference docs. Use the table below to find the right doc for your task.

---

## Doc map

| Doc | Purpose | Read when |
|-----|---------|-----------|
| [ONBOARDING.md](ONBOARDING.md) | Quick start, golden rules, Docker-first | New to repo |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System overview, pillars, modules, pipelines | Understanding the system |
| [CONNECTIONS.md](CONNECTIONS.md) | Settings → Connections (brokers, IB Gateway, TV, vault) | Integrating brokers/OAuth/credentials |
| [BROKERS.md](BROKERS.md) | Broker implementation guide (add a broker, sync, credentials) | Implementing or debugging broker sync |
| [PORTFOLIO.md](PORTFOLIO.md) | Portfolio pillar (sync flow, routes, pages, file map) | Working on portfolio features |
| [MARKET_DATA.md](MARKET_DATA.md) | Market data ingest, indicators, scheduling | Working on market data/coverage |
| [PRODUCTION.md](PRODUCTION.md) | Deploy, env, DNS, Cloudflare, CI/CD | Deploying or operating prod |
| [ENCRYPTION_KEY_ROTATION.md](ENCRYPTION_KEY_ROTATION.md) | Rotate Fernet key (invalidates credentials) | Rotating encryption key |
| [MODELS.md](MODELS.md) | Data models (Position, Trade, Option, etc.) | Understanding DB/API shapes |
| [TESTS.md](TESTS.md) | Test strategy, DB isolation, how to run | Writing or running tests |
| [FRONTEND_UI.md](FRONTEND_UI.md) | Chakra v3, Ladle, component map | Frontend theming/components |
| [ROADMAP.md](ROADMAP.md) | Section-based execution roadmap | Planning / status |
| [PR_AUTOMATION.md](PR_AUTOMATION.md) | Dependabot, agent PR flow, merge rules | Opening/merging PRs |

---

## Doc map (diagram)

```mermaid
flowchart LR
  Onboarding[ONBOARDING]
  Arch[ARCHITECTURE]
  Connections[CONNECTIONS]
  Brokers[BROKERS]
  Portfolio[PORTFOLIO]
  MarketData[MARKET_DATA]
  Production[PRODUCTION]
  RefDocs["Reference docs"]

  Onboarding --> Arch
  Arch --> Connections
  Arch --> Brokers
  Arch --> Portfolio
  Arch --> MarketData
  Arch --> Production
  Arch --> RefDocs
```

Typical path: start with **ONBOARDING**, then **ARCHITECTURE** for the big picture; use **CONNECTIONS**, **PORTFOLIO**, or **MARKET_DATA** for domain work; **PRODUCTION** and **ENCRYPTION_KEY_ROTATION** for operations; **MODELS**, **TESTS**, **FRONTEND_UI**, **ROADMAP**, **PR_AUTOMATION** as needed.

---

## Makefile (quick reference)

**Use the [Makefile](../Makefile) at repo root** for dev and test commands. Run from the repository root.

| Target | Purpose |
|--------|---------|
| `make up` | Start dev stack (backend, frontend, worker, Postgres, Redis). |
| `make down` | Stop dev stack. |
| `make test` | Run backend tests (isolated test DB; never touches dev DB). |
| `make test-frontend` | Run frontend checks: install, lint, type-check, test. |
| `make test-all` | Backend + frontend tests. |
| `make frontend-lint` | Lint only. |
| `make frontend-typecheck` | Type-check only. |
| `make frontend-test` | Frontend unit tests only. |
| `make frontend-check` | Full frontend suite (lint + type-check + test). |
| `make ladle-up` | Start Ladle (component explorer). |
| `make ladle-build` | Build Ladle. |
| `make task-run TASK=module.task` | Run a Celery task (dev). |
| `make migrate-up` | Apply Alembic migrations (dev DB). |
| `make migrate-create MSG="message"` | Create a new migration. |

Details: [ONBOARDING.md](ONBOARDING.md) (quick start), [TESTS.md](TESTS.md) (how to run tests).
