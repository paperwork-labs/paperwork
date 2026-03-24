# AxiomFolio — AI Agent Entry Point

Welcome, agent. This is a quantitative portfolio intelligence platform built for swing trading using Stage Analysis (Oliver Kell / Weinstein refined). Read this file first, then dive into the relevant domain.

## Tech Stack

| Layer | Stack |
|-------|-------|
| Backend | Python 3.11, FastAPI, Celery, PostgreSQL 16, Redis, SQLAlchemy 2.0, Alembic |
| Frontend | React 19, TypeScript 5, Vite, Chakra UI v3, React Query, Recharts, lightweight-charts |
| Infra | Docker Compose (dev), Render (prod), Cloudflare (DNS/CDN), GitHub Actions (CI) |
| Brokers | IBKR (FlexQuery + Gateway), TastyTrade (SDK), Schwab (OAuth) |

## Three Pillars

1. **Portfolio** — Read-only broker sync (positions, trades, tax lots, options, balances). Multiple brokers aggregated into unified models.
2. **Intelligence** — Market data pipeline: OHLCV → indicators → MarketSnapshot (latest) + MarketSnapshotHistory (daily ledger). Stage Analysis with SMA150 anchor, 10 sub-stages, Market Regime Engine.
3. **Strategy** — Rule evaluator, backtester, signal generator, order engine with risk gates and exit cascade.

## Persona Rules

Context-specific AI rules activate based on which files you're editing:

| Persona | File | Trigger | Domain |
|---------|------|---------|--------|
| Staff Engineer | `engineering.mdc` | Always | Architecture, code conventions, tech stack |
| Quant Analyst | `quant-analyst.mdc` | `indicator_engine*`, `stage*`, `regime*`, `backtest*` | Stage Analysis, financial math, indicators |
| Portfolio Manager | `portfolio-manager.mdc` | `portfolio*`, `order*`, `risk*`, `execution*` | Position sizing, risk gates, exit cascade, brokers |
| UX Lead | `ux-lead.mdc` | `*.tsx`, `*.css` | Chakra v3, design system, accessibility, charts |
| Ops Engineer | `ops-engineer.mdc` | `tasks/*`, `celery*`, `compose*`, `Makefile` | Pipelines, Celery, Docker, monitoring |
| Git Workflow | `git-workflow.mdc` | Always | Branch naming, commits, PR standards |
| Token Management | `token-management.mdc` | Always | Delegation rules, chat lifecycle, decision logging |

## Key Documentation

| Doc | Purpose | When to Read |
|-----|---------|--------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System overview, data models, pipelines | Understanding the system |
| [KNOWLEDGE.md](docs/KNOWLEDGE.md) | Decision log with rationale | Before making architectural changes |
| [TASKS.md](docs/TASKS.md) | Current sprint plan with acceptance criteria | Before starting work |
| [PRD.md](docs/PRD.md) | Product requirements, vision, competitive positioning | Understanding the "why" |
| [Stage_Analysis_v4.docx](Stage_Analysis_v4.docx) | Complete Stage Analysis trading system specification | Any indicator/stage/regime work |
| [ONBOARDING.md](docs/ONBOARDING.md) | Quick start, Docker, dev workflow | First time in repo |

## Key Files

| Area | Path | Notes |
|------|------|-------|
| Indicator engine | `backend/services/market/indicator_engine.py` | All indicator computation — stages, RS, TD Sequential, ATR |
| Regime engine | `backend/services/market/regime_engine.py` | Market Regime R1–R5 (when built) |
| Stage classifier | Within indicator_engine.py | SMA150 anchor, 10 sub-stages |
| IBKR sync pipeline | `backend/services/portfolio/ibkr/pipeline.py` | Orchestrates FlexQuery sync |
| Order manager | `backend/services/execution/order_manager.py` | Single execution path |
| Risk gate | `backend/services/execution/risk_gate.py` | Position sizing, limits |
| Job catalog | `backend/tasks/job_catalog.py` | All scheduled tasks with metadata |
| Market dashboard | `frontend/src/pages/MarketDashboard.tsx` | Main market view |
| Theme | `frontend/src/theme/system.ts` | Chakra v3 design tokens |
| Chart constants | `frontend/src/constants/chart.ts` | Stage colors, heat scales |

## Development Commands

```bash
make up              # Start dev stack (all services)
make down            # Stop
make test            # Backend tests (isolated DB)
make test-all        # Backend + frontend tests
make migrate-up      # Apply migrations
make task-run TASK=module.task  # Run a Celery task
make logs            # Tail service logs
```

## Before You Code

1. Read `docs/KNOWLEDGE.md` for recent decisions
2. Check `docs/TASKS.md` for current sprint
3. Create a feature branch (`feat/`, `fix/`, `chore/`, `docs/`, `refactor/`)
4. After significant decisions, add to `docs/KNOWLEDGE.md`
