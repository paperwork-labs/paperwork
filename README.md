# FileFree

**Free AI-powered tax filing for Gen Z.** Snap your W-2, get your completed return in minutes. Actually free.

**Live at:** [filefree.tax](https://filefree.tax)

## What This Is

FileFree starts as free tax prep and grows into a year-round AI financial advisor. Filing earns trust. Trust enables everything else.

- **Phase 1 (2026):** Free tax prep — W-2 photo to completed 1040 PDF in under 5 minutes
- **Phase 2 (2027):** Free e-file via own IRS MeF transmitter + AI tax advisor subscription
- **Phase 3 (2028):** Embedded tax engine (B2B API) for fintechs and neobanks

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, Framer Motion |
| Backend | FastAPI (Python 3.11+), SQLAlchemy 2.0 (async), Alembic |
| Database | PostgreSQL 15+ (Neon serverless in production) |
| Cache/Sessions | Redis (Upstash serverless in production) |
| OCR | GCP Cloud Vision + OpenAI GPT-4o-mini (structured outputs) |
| AI Insights | OpenAI GPT-4o |
| File Storage | GCP Cloud Storage (24hr auto-delete lifecycle) |
| Frontend Hosting | Vercel |
| Backend Hosting | Render |
| Local Dev | Docker Compose |

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose)
- [Make](https://www.gnu.org/software/make/) (pre-installed on macOS/Linux)

### Quick Start

```bash
# Clone
git clone https://github.com/your-org/filefree.git
cd filefree

# First-time setup (copies env files)
make setup

# Start everything
make dev

# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# API docs: http://localhost:8000/docs
```

### Available Commands

```bash
make help        # Show all available commands
make dev         # Start all services (with --build)
make dev-d       # Start in background (detached)
make stop        # Stop all services
make test        # Run all tests (in Docker)
make test-local  # Run backend tests (no Docker)
make lint        # Run linters (ruff + eslint)
make format      # Auto-format code
make migrate     # Run database migrations
make clean       # Stop services + remove volumes
make logs        # Tail all logs
make db          # Open psql shell
```

### Without Docker

```bash
# Backend
cd api
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../infra/env.dev.example .env  # edit DATABASE_URL and REDIS_URL for local services
uvicorn app.main:app --reload

# Frontend
cd web
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

## Project Structure

```
filefree/
├── api/                   # FastAPI backend
│   ├── app/
│   │   ├── models/        # SQLAlchemy data models
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── routers/       # API route handlers
│   │   ├── services/      # Business logic (OCR, tax calc, storage)
│   │   ├── repositories/  # Database access layer
│   │   └── utils/         # Encryption, security, PII scrubbing
│   ├── tax-data/          # IRS tax brackets and deductions (JSON)
│   ├── alembic/           # Database migrations
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── web/                   # Next.js frontend
│   ├── src/
│   │   ├── app/           # App Router pages
│   │   ├── components/    # React components (custom + shadcn/ui)
│   │   ├── lib/           # Utilities, API client, motion presets
│   │   ├── hooks/         # Custom React hooks
│   │   ├── types/         # TypeScript interfaces
│   │   └── stores/        # Zustand stores
│   ├── Dockerfile.dev
│   └── package.json
├── docs/                  # Strategy, product, and business docs
│   ├── TASKS.md           # Sprint-by-sprint build plan
│   ├── PRD.md             # Product Requirements Document
│   ├── PRODUCT_SPEC.md    # UX & Product Specification
│   ├── PARTNERSHIPS.md    # Partnership playbook for co-founder
│   ├── PITCH_PACKAGE.md   # Co-founder pitch package
│   ├── STRATEGY_REPORT.md # Strategic assessment
│   └── KNOWLEDGE.md       # Organizational memory (decisions log)
├── infra/                 # Infrastructure configs
│   ├── compose.dev.yaml   # Docker Compose (local dev only)
│   ├── env.dev.example    # Dev environment variables
│   └── env.prod.example   # Production env reference
├── .cursor/rules/         # AI persona context files (11 personas + workflows)
├── .cursorrules           # AI coding conventions
├── Makefile               # Dev commands (make dev, test, lint, format, migrate)
├── render.yaml            # Render Blueprints (production IaC)
├── pyproject.toml         # Ruff + mypy configuration
└── README.md
```

## Key Documents

- **[docs/PRD.md](docs/PRD.md)** — Business strategy, competitive analysis, revenue model, e-file strategy
- **[docs/TASKS.md](docs/TASKS.md)** — Sprint-by-sprint build plan with acceptance criteria
- **[docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md)** — UX specification, design system, component specs
- **[docs/KNOWLEDGE.md](docs/KNOWLEDGE.md)** — Organizational memory: decisions, learnings, patterns
- **[docs/STRATEGY_REPORT.md](docs/STRATEGY_REPORT.md)** — McKinsey-style strategic assessment
- **[docs/PARTNERSHIPS.md](docs/PARTNERSHIPS.md)** — Partnership playbook for the partnerships co-founder
- **[.cursorrules](.cursorrules)** — AI coding conventions and tech stack rules

## Architecture Highlights

- **Tiered OCR Pipeline**: GCP Cloud Vision + GPT-4o-mini structured outputs. $0.002/doc vs $0.30 for Google's own Document AI W-2 Parser. SSN extracted locally via regex, never sent to AI APIs. GPT-4o vision fallback for low-confidence extractions.
- **Zero AWS**: Entire stack runs on Vercel + Render Starter ($7/mo) + Neon + Upstash + GCP Cloud Storage/Vision.
- **Docker = Dev Only**: Docker Compose (`infra/compose.dev.yaml`) for local dev. Production uses Render native buildpack (render.yaml) + Vercel git deploy.
- **North Star**: Own IRS MeF transmitter for free e-file (January 2027). Currently in IRS certification process.
- **AI Personas**: `.cursor/rules/` contains 11 persona files + workflow playbooks. Each persona has trigger conditions, quality gates, and handoff protocols.
