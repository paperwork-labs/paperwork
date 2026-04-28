# AxiomFolio — AI Agent Entry Point

> **Canonical location (as of 2026-04-23)**: `apis/axiomfolio/` inside the
> [paperwork monorepo](https://github.com/paperwork-labs/paperwork). The
> standalone `paperwork-labs/axiomfolio` repo is archived — do not open
> new PRs against it. CI lives at the monorepo root
> ([.github/workflows/axiomfolio-ci.yml](../../.github/workflows/axiomfolio-ci.yml))
> and the dev stack is driven from
> [infra/compose.dev.yaml](../../infra/compose.dev.yaml). See
> [docs/INFRA.md](../../docs/INFRA.md) for the full architecture and
> [AGENTS.md (root)](../../AGENTS.md) for cross-product persona rules.

Welcome, agent. This is a quantitative portfolio intelligence platform built for swing trading using Stage Analysis (Oliver Kell / Weinstein refined). Read this file first, then dive into the relevant domain.

## Tech Stack

| Layer | Stack |
|-------|-------|
| Backend | Python 3.11, FastAPI, Celery, PostgreSQL 18 (shared across monorepo dev stack; tests use `axiomfolio_test` DB on same instance), Redis, SQLAlchemy 2.0, Alembic |
| Frontend | Next.js 16 (App Router), React 19, TypeScript 5, Radix UI, Tailwind CSS, shadcn/ui-style components, TanStack Query, Recharts, lightweight-charts |
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

- `app/services/execution/risk_gate.py` — Position sizing, max order value, stage caps
- `app/services/execution/order_manager.py` — Order execution path, broker routing
- `app/services/execution/exit_cascade.py` — Stop loss, trailing stops
- `app/services/risk/circuit_breaker.py` — Drawdown protection, kill switch

### Authentication / authorization

- `app/api/routes/auth.py` — Login, tokens, password reset
- `app/api/security.py` — JWT encoding/decoding
- `app/api/dependencies.py` — Auth dependencies, role checks

### Core financial calculations (data integrity)

- `app/services/market/indicator_engine.py` — RSI, ATR, MACD, ADX, Stage Analysis
- `app/services/market/stage_classifier.py` — Weinstein stage classification (10 sub-stages)
- `app/services/market/regime_engine.py` — Market Regime R1–R5

### Configuration (system stability)

- `app/config.py` — Environment variables, feature flags
- `app/alembic/versions/*.py` — Database migrations
- `app/tasks/job_catalog.py` — Celery schedules, timeouts

### Dependency manifests (supply chain / reproducible builds)

- `pyproject.toml` and lock files — Python dependencies
- `apps/axiomfolio/package.json` and lock files — Frontend dependencies  
  Use the same approval bar as other danger zones for major upgrades or security-sensitive dependency changes.

## Three Pillars

1. **Portfolio** — Read-only broker sync (positions, trades, tax lots, options, balances). Multiple brokers aggregated into unified models.
2. **Intelligence** — Market data pipeline: OHLCV → indicators → MarketSnapshot (latest) + MarketSnapshotHistory (daily ledger). Stage Analysis with SMA150 anchor, 10 sub-stages, Market Regime Engine.
3. **Strategy** — Rule evaluator, backtester, signal generator, order engine with risk gates and exit cascade.

**Medallion layers (D127, D145, Wave 0):** `app/services/` is described in four layers plus an ops escape hatch:

- **bronze** — raw broker and market ingestion (read-only to external world)
- **silver** — indicators, regime, stage, enriched portfolio analytics
- **gold** — strategies, candidates, picks, narratives, backtests
- **execution** — order placement, broker router, risk gates, approval workflow
- **ops** — cross-cutting infra (auth, notifications, billing, observability); escape hatch, no layer rules

Every file under `app/services/` carries a `medallion: <layer>` docstring tag (Phase 0.A). CI enforces import-layer rules via `make medallion-check` (Phase 0.B): bronze → (ops only), silver → (bronze + ops), gold → (silver + bronze + ops), execution → (gold + silver + bronze + ops). Cross-layer exceptions require a `# medallion: allow <reason>` waiver.

New code must be created under `app/services/<layer>/` from the first commit. Some existing files are still at grandfathered paths (e.g. `market/*` files are tagged `silver` but not yet under `silver/`); Phase 0.C of Wave 0 completes the rename pass. See [Medallion Architecture](docs/ARCHITECTURE.md#medallion-architecture) in `docs/ARCHITECTURE.md`, decision **D127** / **D145** in `docs/KNOWLEDGE.md`, and the live audit in `docs/plans/MEDALLION_AUDIT_2026Q2.md`.

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
| Indicator engine | `app/services/market/indicator_engine.py` | All indicator computation — stages, RS, TD Sequential, ATR |
| Regime engine | `app/services/market/regime_engine.py` | Market Regime R1–R5 (when built) |
| Stage classifier | `app/services/market/stage_classifier.py` | SMA150 anchor, 10 sub-stages |
| IBKR sync pipeline | `app/services/portfolio/ibkr/pipeline.py` | Orchestrates FlexQuery sync |
| Order manager | `app/services/execution/order_manager.py` | Single execution path |
| Risk gate | `app/services/execution/risk_gate.py` | Position sizing, limits |
| Job catalog | `app/tasks/job_catalog.py` | All scheduled tasks with metadata |
| Market dashboard | `../../apps/axiomfolio/src/components/market/MarketDashboardClient.tsx` | Main market view (Next.js) |
| Theme | `../../apps/axiomfolio/src/app/axiomfolio.css` | Tailwind tokens, dark canvas |
| Stage / chart tokens | `../../apps/axiomfolio/src/lib/stageTailwind.ts` | Stage colors, badge classes |

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
