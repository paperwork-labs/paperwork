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

```bash
# Clone
git clone https://github.com/your-org/filefree.git
cd filefree

# Copy environment variables
cp filefree-api/.env.example filefree-api/.env
cp filefree-web/.env.example filefree-web/.env

# Start everything (option A: Makefile)
make dev

# Start everything (option B: direct)
docker compose up

# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# API docs: http://localhost:8000/docs
```

## Project Structure

```
filefree/
├── filefree-web/          # Next.js frontend
│   ├── src/
│   │   ├── app/           # App Router pages
│   │   ├── components/    # React components (custom + shadcn/ui)
│   │   ├── lib/           # Utilities, API client, motion presets
│   │   ├── hooks/         # Custom React hooks
│   │   ├── types/         # TypeScript interfaces
│   │   └── stores/        # Zustand stores
│   └── ...
├── filefree-api/          # FastAPI backend
│   ├── app/
│   │   ├── models/        # SQLAlchemy data models
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── routers/       # API route handlers
│   │   ├── services/      # Business logic (OCR, tax calc, storage)
│   │   ├── repositories/  # Database access layer
│   │   └── utils/         # Encryption, security, PII scrubbing
│   ├── tax-data/          # IRS tax brackets and deductions (JSON)
│   ├── alembic/           # Database migrations
│   └── tests/
├── .cursorrules           # AI coding conventions
├── .cursor/rules/         # AI persona context files (10 personas + workflows)
├── KNOWLEDGE.md           # Organizational memory (decisions, learnings, patterns)
├── STRATEGY_REPORT.md     # McKinsey-style strategic assessment (living doc)
├── PRD.md                 # Product Requirements Document
├── PRODUCT_SPEC.md        # UX & Product Specification
├── TASKS.md               # Build task breakdown
├── Makefile               # Dev commands (make dev, test, lint, format, migrate)
├── render.yaml            # Render Blueprints (production IaC)
├── pyproject.toml         # Ruff + mypy configuration
└── docker-compose.yml     # Local dev only
```

## Key Documents

- **[PRD.md](PRD.md)** — Business strategy, competitive analysis, revenue model, e-file strategy
- **[TASKS.md](TASKS.md)** — Sprint-by-sprint build plan with acceptance criteria
- **[PRODUCT_SPEC.md](PRODUCT_SPEC.md)** — UX specification, design system, component specs
- **[KNOWLEDGE.md](KNOWLEDGE.md)** — Organizational memory: decisions, learnings, patterns, open questions
- **[STRATEGY_REPORT.md](STRATEGY_REPORT.md)** — McKinsey-style strategic assessment (living document, updated per review cycle)
- **[.cursorrules](.cursorrules)** — AI coding conventions and tech stack rules

## Architecture Highlights

- **Tiered OCR Pipeline**: GCP Cloud Vision + GPT-4o-mini structured outputs. $0.002/doc vs $0.30 for Google's own Document AI W-2 Parser. SSN extracted locally via regex, never sent to AI APIs. GPT-4o vision fallback for low-confidence extractions.
- **Zero AWS**: Entire stack runs on Vercel + Render Starter ($7/mo) + Neon + Upstash + GCP Cloud Storage/Vision.
- **Docker = Dev Only**: Docker Compose for local dev. Production uses Render native buildpack (render.yaml) + Vercel git deploy.
- **North Star**: Own IRS MeF transmitter for free e-file (January 2027). Currently in IRS certification process.
- **AI Personas**: `.cursor/rules/` contains 10 persona files + workflow playbooks. Each persona has trigger conditions, quality gates, and handoff protocols.
