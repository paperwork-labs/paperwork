# AxiomFolio — AI Agent Entry Point

Welcome, agent. This is a quantitative portfolio intelligence platform built for swing trading using Stage Analysis (Oliver Kell / Weinstein refined). Read this file first, then dive into the relevant domain.

## Tech Stack

| Layer | Stack |
|-------|-------|
| Backend | Python 3.11, FastAPI, Celery, PostgreSQL 18 (dev Docker; test compose uses 16-alpine), Redis, SQLAlchemy 2.0, Alembic |
| Frontend | React 19, TypeScript 5, Vite, Radix UI, Tailwind CSS, shadcn/ui-style components, TanStack Query, Recharts, lightweight-charts |
| Infra | Docker Compose (dev), Render (prod), Cloudflare (DNS/CDN), GitHub Actions (CI) |
| Brokers | IBKR (FlexQuery + Gateway), TastyTrade (SDK), Schwab (OAuth) |

## IRON LAWS (Never Violate)

| Rule | Enforcement |
|------|-------------|
| Monetary values use `Decimal`, never `float` | Code review |
| All indicator computation via `compute_full_indicator_series()` | `indicator_engine.py` |
| Single execution path: OrderManager → RiskGate → BrokerRouter | Never bypass |
| DB sessions passed as parameters | Never create sessions inside services |
| Celery `time_limit` must match `job_catalog.py` `timeout_s` | Task decorator |
| Lock TTL must be >= task `hard_time_limit` | `task_utils.py` |
| SMA150 is the primary stage anchor | `stage_classifier.py` |

## DANGER ZONES (Ask Before Modifying)

These paths match `.cursor/rules/protected-regions.mdc`. Get explicit approval before editing.

### Capital protection (financial loss)

- `backend/services/execution/risk_gate.py` — Position sizing, max order value, stage caps
- `backend/services/execution/order_manager.py` — Order execution path, broker routing
- `backend/services/execution/exit_cascade.py` — Stop loss, trailing stops
- `backend/services/risk/circuit_breaker.py` — Drawdown protection, kill switch

### Authentication / authorization

- `backend/api/routes/auth.py` — Login, tokens, password reset
- `backend/api/security.py` — JWT encoding/decoding
- `backend/api/dependencies.py` — Auth dependencies, role checks

### Core financial calculations (data integrity)

- `backend/services/market/indicator_engine.py` — RSI, ATR, MACD, ADX, Stage Analysis
- `backend/services/market/stage_classifier.py` — Weinstein stage classification (10 sub-stages)
- `backend/services/market/regime_engine.py` — Market Regime R1–R5

### Configuration (system stability)

- `backend/config.py` — Environment variables, feature flags
- `backend/alembic/versions/*.py` — Database migrations
- `backend/tasks/job_catalog.py` — Celery schedules, timeouts

### Dependency manifests (supply chain / reproducible builds)

- `pyproject.toml` and lock files — Python dependencies
- `frontend/package.json` and lock files — Frontend dependencies  
  Use the same approval bar as other danger zones for major upgrades or security-sensitive dependency changes.

## Three Pillars

1. **Portfolio** — Read-only broker sync (positions, trades, tax lots, options, balances). Multiple brokers aggregated into unified models.
2. **Intelligence** — Market data pipeline: OHLCV → indicators → MarketSnapshot (latest) + MarketSnapshotHistory (daily ledger). Stage Analysis with SMA150 anchor, 10 sub-stages, Market Regime Engine.
3. **Strategy** — Rule evaluator, backtester, signal generator, order engine with risk gates and exit cascade.

## Trading North Star

14 non-negotiable principles. See [TRADING_PRINCIPLES.md](docs/TRADING_PRINCIPLES.md).

| # | Principle | Code Enforcement |
|---|-----------|------------------|
| 1 | Risk First | MAX_SINGLE_POSITION_PCT |
| 2 | Cut Losses | exit_cascade |
| 3 | Portfolio Heat | (TODO) |
| 4 | Size by Volatility | compute_position_size |
| 5 | Conviction Scaling | STAGE_CAPS × regime_mult |
| 6 | R-Multiple | (TODO) |
| 7 | Stage Discipline | stage caps block wrong stages |
| 8 | Regime Gate | REGIME_LONG_ACCESS |
| 9 | Relative Strength | RS Mansfield in scan |
| 10 | Mechanical Rules | RuleEvaluator |
| 11 | Let Winners Run | adaptive trailing |
| 12 | Volume Confirms | vol_ratio check |
| 13 | Review Trades | (TODO: journal) |
| 14 | Expectancy | paper validation |

## Persona Rules

Context-specific AI rules activate based on which files you're editing:

| Persona | File | Trigger | Domain |
|---------|------|---------|--------|
| Staff Engineer | `engineering.mdc` | Always | Architecture, code conventions, tech stack |
| Quant Analyst | `quant-analyst.mdc` | `indicator_engine*`, `stage*`, `regime*`, `backtest*` | Stage Analysis, financial math, indicators |
| Portfolio Manager | `portfolio-manager.mdc` | `portfolio*`, `order*`, `risk*`, `execution*` | Position sizing, risk gates, exit cascade, brokers |
| Risk Manager | `risk-manager.mdc` | `risk*`, `circuit*` | Capital protection |
| Swing Trader | `swing-trader.mdc` | `scan*`, `stage*` | SEPA entries |
| Systematic Trader | `systematic-trader.mdc` | `backtest*` | System validation |
| UX Lead | `ux-lead.mdc` | `*.tsx`, `*.css` | Radix UI, Tailwind, design system, accessibility, charts |
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
| [Stage_Analysis.docx](Stage_Analysis.docx) | Complete Stage Analysis trading system specification | Any indicator/stage/regime work |
| [ONBOARDING.md](docs/ONBOARDING.md) | Quick start, Docker, dev workflow | First time in repo |

## Key Files

| Area | Path | Notes |
|------|------|-------|
| Indicator engine | `backend/services/market/indicator_engine.py` | All indicator computation — stages, RS, TD Sequential, ATR |
| Regime engine | `backend/services/market/regime_engine.py` | Market Regime R1–R5 (when built) |
| Stage classifier | `backend/services/market/stage_classifier.py` | SMA150 anchor, 10 sub-stages |
| IBKR sync pipeline | `backend/services/portfolio/ibkr/pipeline.py` | Orchestrates FlexQuery sync |
| Order manager | `backend/services/execution/order_manager.py` | Single execution path |
| Risk gate | `backend/services/execution/risk_gate.py` | Position sizing, limits |
| Job catalog | `backend/tasks/job_catalog.py` | All scheduled tasks with metadata |
| Market dashboard | `frontend/src/pages/MarketDashboard.tsx` | Main market view |
| Theme | `frontend/src/styles/` | Tailwind config, design tokens |
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
