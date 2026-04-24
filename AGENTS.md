# Paperwork Labs — Agent Instructions

Paperwork Labs builds tools that eliminate paperwork. This repo is a pnpm + Turborepo monorepo containing 5 products (FileFree, LaunchFree, Distill, Trinkets, AxiomFolio) plus Brain (the shared AI orchestration layer).

## Repo layout

- `apps/` — user-facing frontends (Next.js, Vite)
- `apis/` — self-contained product backends (each with its own Dockerfile, alembic, pyproject.toml)
  - `apis/brain/` — Brain orchestration layer (FastAPI)
  - `apis/filefree/`, `apis/launchfree/` — product APIs
  - `apis/axiomfolio/` — quantitative portfolio intelligence (FastAPI + Celery + Postgres 18). Absorbed 2026-04-23. See [apis/axiomfolio/AGENTS.md](apis/axiomfolio/AGENTS.md).
- `packages/` — shared libs (auth, analytics, vault, UI primitives)
- `docs/` — cross-product philosophy docs (infra, data, orchestration)

## Quick Start

- **Tech stack**: Next.js 14+ + Tailwind CSS v4 + shadcn/ui (frontend), FastAPI + SQLAlchemy + PostgreSQL (backend)
- **Full conventions**: See [.cursorrules](.cursorrules) for complete coding standards, architecture, and security rules
- **Brand guide**: See [.cursor/rules/brand.mdc](.cursor/rules/brand.mdc) for product names, colors, voice
- **Git workflow**: Branch-based development, never push to main. See [.cursor/rules/git-workflow.mdc](.cursor/rules/git-workflow.mdc)

## AI Personas

16 specialized personas guide agent behavior across different domains. Each is defined in `.cursor/rules/`:

| Persona | File | Role |
|---|---|---|
| Executive Assistant | `ea.mdc` | Daily operating partner — briefings, sprint tracking, decision logging, Slack agent interactions |
| Staff Engineer | `engineering.mdc` | Tech stack authority, architecture, code conventions, infrastructure |
| UX/UI Lead | `ux.mdc` | Design system, accessibility, mobile-first, animations |
| Head of Growth | `growth.mdc` | Marketing, content, SEO, viral mechanics |
| Social Media Manager | `social.mdc` | Platform playbooks, paid ads, analytics, creator outreach |
| Chief of Staff | `strategy.mdc` | Business strategy, planning, operating cadence |
| General Counsel | `legal.mdc` | Compliance, EFIN, privacy, tax law, FTC disclosures |
| CFO | `cfo.mdc` | Unit economics, infrastructure spend, vendor evaluation |
| QA Lead | `qa.mdc` | Testing, validation, security audits, PII leak detection |
| Tax Domain Expert | `tax-domain.mdc` | IRS rules, MeF schemas, tax law, bracket calculations |
| CPA / Tax Advisor | `cpa.mdc` | Tax planning strategy, advisory quality, accuracy review |
| Partnership Dev | `partnerships.mdc` | Outreach drafts, pipeline tracking, deal summaries |
| AI Operations Lead | `agent-ops.mdc` | Model routing, cost tracking, persona audits |
| Brand Guide | `brand.mdc` | Product names, color palettes, typography, voice |
| Workflows | `workflows.mdc` | Company playbooks for shipping features, making decisions |
| Git Workflow | `git-workflow.mdc` | Branch naming, PR workflow, commit conventions |

## Invoking a Persona

To activate a specific persona, reference the relevant domain in your prompt:
- Tax questions → Tax Domain Expert
- Cost/spend → CFO
- Legal/compliance → General Counsel
- Code/architecture → Staff Engineer
- "What should I work on?" → Executive Assistant

All personas are always available (alwaysApply: true for core personas). Product-specific personas activate via file globs.

## Agent Workflows (n8n)

11 automated workflows run on n8n (self-hosted). See [infra/hetzner/workflows/](infra/hetzner/workflows/) for details.

Key workflows:
- **Thread Handler**: Responds to Slack thread replies with persona-routed AI responses
- **Daily Briefing**: Posts to #daily-briefing at 7am PT
- **Decision Logger**: Captures decisions from #decisions and commits to KNOWLEDGE.md
