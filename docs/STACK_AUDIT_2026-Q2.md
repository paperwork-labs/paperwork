---
last_reviewed: 2026-05-01
---

# Stack Audit - 2026 Q2

**Audit date:** 2026-04-29  
**Auditor:** Brain (autonomous read-only audit, WS-49)  
**Source-of-truth files inspected:** `package.json`, `pnpm-workspace.yaml`, `pyproject.toml`, `requirements.txt`, `render.yaml`, `vercel.json`, `Dockerfile`, `.github/workflows/*`, `apis/brain/app/config.py`

## Executive Summary

- KEEP: 32
- UPGRADE: 30 (S=12, M=18, L=0)
- REPLACE: 3 (S=0, M=2, L=1)
- Total est. effort: 80 person-days

Paperwork's frontend platform is ahead of most small-company stacks: React 19, Next.js 16, Tailwind 4, current Clerk, current Vercel AI SDK, and a real shared UI package are already in place. The truthful risks are lower in the UI framework layer and higher in Python/runtime consistency, package-management discipline, observability, deployment drift, and durable scheduling.

The highest-impact upgrade candidates are:

- Standardize Python runtimes on 3.13 where supported, or explicitly pin services that must remain on 3.11.
- Replace ad hoc `pip install -r requirements.txt` dependency management with `uv` lockfiles per API.
- Finish Render repo-pointer / Blueprint sync drift for AxiomFolio services.
- Make observability production-grade: Sentry DSNs across apps, OTel exporter, logs, alerts, and Langfuse v4.
- Normalize Zod v4, TypeScript 6, Node LTS, and pnpm patch levels across the monorepo.

## Frontend

| Layer | Current | Latest stable | Verdict | Why | Cost | Replace with |
|---|---|---|---|---|---|---|
| React | `19.2.5` in active Next apps; `@paperwork-labs/pwa` still peers `18.2 || 19` | `19.2.5` | KEEP | Active apps are already on current React. Keep `pwa` dual peer support for package compatibility. | S | - |
| Next.js | `16.2.4`; App Router under `apps/*/src/app`; archived Vite tree excluded from workspace | `16.2.4` | KEEP | The active app layer is current and standardized on App Router. Pages Router usage found only in archived AxiomFolio Vite code. | S | - |
| Next rendering mode | App Router with mixed Server/Client Components; `next dev --turbopack` in apps | App Router + Turbopack | KEEP | The repo has made the right strategic move: App Router is universal in active apps and Turbopack is used for dev. | S | - |
| Turbopack / Webpack | Turbopack in dev scripts; production `next build` uses Next defaults | Turbopack where Next supports it | KEEP | Avoid forcing production bundler config unless a build bottleneck appears. | S | - |
| Tailwind CSS | `tailwindcss 4.2.4`, `@tailwindcss/postcss 4.2.4`; old `tailwind.config.ts` files remain | `4.2.4` | KEEP | Version is current. Config cleanup is debt, not a stack change. | S | - |
| shadcn/ui | Owned components in `packages/ui/src/components/*`: accordion, badge, button, card, checkbox, command, dialog, dropdown-menu, form, input, label, popover, progress, radio-group, select, separator, sheet, skeleton, switch, textarea, tooltip | shadcn copy-owned Radix pattern | KEEP | Copy-owned components are appropriate for this repo. Do not chase a package abstraction that would reduce ownership. | S | - |
| `@paperwork-labs/ui` | `0.0.1`, framework-agnostic exports, purity CI, consumed by all active apps | Internal design system with Storybook coverage | UPGRADE | The package is real and protected, but still early: broaden Storybook coverage, publish component API docs, and keep app-specific styling out. | M | - |
| State management | TanStack Query `5.100.5` in several apps, latest `5.100.6`; Zustand `5.0.11` / `5.0.0` in FileFree/LaunchFree | TanStack Query `5.100.6`; Zustand `5.0.11` | KEEP | The split is right: server state in Query, small client state in Zustand. Patch-level drift is too small to drive a separate workstream. | S | - |
| Forms | `react-hook-form 7.74.0`; `@hookform/resolvers 5.2.2` | `7.74.0` | KEEP | Current, proven, and integrated with shared form components. | S | - |
| Validation | Mixed `zod 3.24/3.25` in FileFree/Studio and `zod 4.3.6` in LaunchFree/data/filing-engine | `4.3.6` | UPGRADE | Mixed major versions increase schema sharing risk across packages. Normalize to Zod 4 after checking resolver and API schema behavior. | M | - |
| Charts | `recharts 3.8.1`; `lightweight-charts 5.2.0` in AxiomFolio/design | `recharts 3.8.1`; `lightweight-charts 5.2.0` | KEEP | Both are current and fit the product split: Recharts for business dashboards, Lightweight Charts for trading UI. | S | - |
| Rich text / markdown | `react-markdown 10.1.0`, `remark-gfm 4.0.1`, `rehype-sanitize 6.0.0`; no full editor found | Markdown renderers; editor only if product requires it | KEEP | Current need is safe markdown rendering, not a collaborative editor. Avoid introducing TipTap/Lexical until there is a real authoring surface. | S | - |
| Animation | `framer-motion 12.38.0`, plus CSS/Tailwind motion helpers | `12.38.0` | KEEP | Current and aligned with brand intent. Continue centralizing motion primitives in app/package utilities. | S | - |

## Backend (Python)

| Layer | Current | Latest stable | Verdict | Why | Cost | Replace with |
|---|---|---|---|---|---|---|
| Python version | Root `.python-version` is `3.11`; FileFree/Brain Dockerfiles use `3.11.9`; Brain mypy targets `3.13`; CI mixes 3.11 and 3.13 | Python `3.13.x` stable; 3.11 still supported | UPGRADE | Runtime and type-check targets disagree. Standardize on 3.13 for Brain first, then move FileFree/LaunchFree after dependency smoke tests. | M | - |
| FastAPI | Brain `>=0.115.0`; FileFree/LaunchFree `>=0.136.1`; AxiomFolio `==0.136.1` | `0.136.1` | UPGRADE | Most services are current, but Brain's broad lower bound can install materially different behavior across environments. Pin/raise Brain to the current line. | S | - |
| Pydantic | `>=2.13.3` or `==2.13.3`; Pydantic v2 everywhere inspected | `2.13.3` | KEEP | Correct major version and current release. | S | - |
| SQLAlchemy | FileFree `>=2.0.36`; Brain `>=2.0.49`; AxiomFolio `==2.0.49`; LaunchFree imports SQLAlchemy but requirements omit it | `2.0.49` | UPGRADE | SQLAlchemy 2 is correct, but LaunchFree's requirements do not match code imports. Add explicit deps or remove dead DB code before provisioning. | S | - |
| Alembic | FileFree/Brain `>=1.14.0`; AxiomFolio `==1.18.4`; LaunchFree commented deploy spec expects Alembic but requirements omit it | `1.18.4` | UPGRADE | Migration tooling is correct where live, but LaunchFree's preserved service spec and requirements are out of sync. | S | - |
| APScheduler | Brain `apscheduler[sqlalchemy]>=3.11.0`; SQLAlchemy job store; in-process singleton on Render | `3.11.2` | UPGRADE | Fine for the current one-instance Brain service, but pin to latest patch and keep the misfire guard. | S | - |
| HTTP client stack | Brain/FileFree use `httpx 0.28.1`; AxiomFolio also pins `requests 2.33.1` and `aiohttp 3.13.5` | `httpx 0.28.1`; `aiohttp 3.13.5`; `requests 2.33.1` | REPLACE | Three HTTP stacks increase retry, timeout, and telemetry inconsistency. Keep SDK-required `requests` only where unavoidable; use `httpx` for first-party HTTP. | M | `httpx` |
| Pytest + plugins | FileFree `pytest>=8.3.0`, Brain `>=8.3.0`, AxiomFolio `==9.0.3`; `pytest-asyncio` ranges from `0.24.0` to `1.3.0` | `pytest 9.0.3`; `pytest-asyncio 1.3.0` | UPGRADE | Test behavior can diverge by API. Normalize versions before deeper CI triage. | S | - |
| Ruff | Root config; Brain `>=0.15.11`; AxiomFolio `==0.15.12`; FileFree `>=0.8.0` | `0.15.12` | UPGRADE | Ruff is the right tool and nearly current, but FileFree's lower bound is stale. Align all APIs to `0.15.12`. | S | - |
| Mypy | Root `strict=true`; Brain strict but 18 modules ignored; FileFree strict; AxiomFolio has no mypy pin/config in requirements beyond legacy Black/isort | `1.20.2` | UPGRADE | Strict mode exists, but ignore-error islands and version drift hide real type debt. Upgrade mypy and shrink ignore lists per service. | M | - |
| Python package manager | `pip install -r requirements.txt`; no `uv.lock` / Poetry lock found | `uv` with lockfiles | REPLACE | Unlocked requirements make "latest" installs non-reproducible in production and CI. Adopt `uv` per API with committed locks and controlled upgrade batches. | M | `uv` |
| Redis client | Brain/FileFree `redis>=5.2.0`; AxiomFolio `redis==7.4.0`; local Redis 7, Render Key Value reports Redis 8.1.4 | `redis-py 7.4.0` | UPGRADE | Client and server are acceptable, but Brain/FileFree should pin/raise client bounds and confirm `redis.asyncio` usage in async paths. | S | - |
| Celery | AxiomFolio `celery==5.6.3`, Flower `2.0.1`, Redis broker/result backend | `5.6.3` | KEEP | Correct fit for AxiomFolio workers and heavier market-data jobs. Keep it isolated from Brain's lighter APScheduler use. | S | - |
| OpenTelemetry | AxiomFolio pins OTel `1.41.1` plus instrumentation `0.62b1`; exporter optional by env | `1.41.1` | UPGRADE | Library versions are current, but exporter configuration is optional and therefore not a reliable production signal yet. | M | - |

## Backend (Node)

| Layer | Current | Latest stable | Verdict | Why | Cost | Replace with |
|---|---|---|---|---|---|---|
| Node.js | `.node-version` is `20`; root engine `>=20.9.0`; CI uses Node 20 and 22 | Node 24 LTS | UPGRADE | Node 20 is no longer the best long-term baseline for a Next 16 stack. Move CI and local runtime to a single current LTS after Vercel compatibility check. | M | - |
| pnpm | Root `packageManager` is `pnpm@10.32.1`; latest observed `10.33.2` | `10.33.2` | UPGRADE | Safe patch bump; keeps Corepack and lockfile-gate aligned. | S | - |
| TypeScript | Most apps/packages `^5.6.0`; `packages/vault` `^5.9.3`; design app `^6.0.3` | `6.0.3` | UPGRADE | TS 6 is already introduced in design, but the main apps remain on 5.6. Upgrade as a coordinated monorepo batch. | M | - |

## Database

| Layer | Current | Latest stable | Verdict | Why | Cost | Replace with |
|---|---|---|---|---|---|---|
| Postgres | Local dev `postgres:17-alpine`; AxiomFolio Render Postgres 18 `basic_1gb`; docs still mention Neon/Postgres 15+ for FileFree/Brain/LaunchFree | Postgres 18 | UPGRADE | Production reality is split and partly undocumented. Declare exact DB versions per service and move non-Axiom databases to Postgres 18 when provider support is verified. | M | - |
| Connection pooling | Studio uses `@neondatabase/serverless` and falls back to `DATABASE_URL_UNPOOLED`; no explicit PgBouncer/pooler contract found | Managed pooler / serverless driver per runtime | UPGRADE | Works at current scale but is not a documented capacity plan. Define pooled vs unpooled URLs for each service before traffic spikes. | M | - |
| ORM choice | SQLAlchemy 2 for Python APIs; `@neondatabase/serverless` direct SQL for Studio; no Drizzle found | SQLAlchemy 2 + typed SQL where needed | KEEP | SQLAlchemy is the right backend ORM. Studio's direct Neon access is narrow admin/data glue, not enough to justify Drizzle yet. | S | - |
| Migrations | Alembic in Python APIs; AxiomFolio CI checks single head; no Drizzle migrations | Alembic for Python-owned schemas | KEEP | Alembic is the right tool for current ownership. Add a Studio migration tool only if Studio starts owning schema changes. | S | - |
| Vector store | Brain uses pgvector for episode memory; `pgvector>=0.3.0`; SQL vector similarity in `memory.py` | `pgvector 0.4.2` | UPGRADE | The architecture is good, but the dependency lower bound is stale and should be pinned/raised with embedding regression tests. | S | - |

## Infrastructure

| Layer | Current | Latest stable | Verdict | Why | Cost | Replace with |
|---|---|---|---|---|---|---|
| Vercel | Task context says Pro confirmed; repo docs still contain Hobby quota incidents and `scripts/vercel-projects.json` maps 6 active apps plus design/accounts placeholders | Vercel Pro for team production apps | KEEP | If Pro is live, Vercel is the right frontend host. Update stale quota docs separately so operators stop optimizing around old Hobby limits. | S | - |
| Render | Root `render.yaml`: FileFree starter, Brain starter, AxiomFolio API/worker standard, Redis starter, Postgres basic-1gb; `RENDER_INVENTORY.md` says Axiom services still point to old repo | Render services + consolidated Blueprint | UPGRADE | Render is a sound fit, but repo-pointer / Blueprint drift is a real deployment risk. Finish F-1 before treating infra as clean. | M | - |
| Cloudflare | Work account migration completed; Brain config still supports account-wide token plus per-zone read tokens | Zone-scoped tokens, least privilege | UPGRADE | DNS ownership is now right; token posture should keep moving from broad account write to scoped operational tokens. | S | - |
| Clerk | `@clerk/nextjs 7.2.7`; embedded auth across active apps; docs note non-Pro branding concern | Clerk Pro / current Clerk SDK | UPGRADE | SDK is current, but plan/branding is not fully settled in repo docs. Upgrade plan only when customer-facing auth polish requires it. | M | - |
| Sentry | `@sentry/nextjs 10.50.0` only in FileFree; docs say DSN not yet integrated historically | `10.50.0` plus DSNs in every customer app | UPGRADE | Dependency is current but observability coverage is partial. Roll Sentry across customer apps with source maps and env validation. | M | - |
| Product analytics | `posthog-js 1.372.1`; shared `@paperwork-labs/analytics`; docs name PostHog as KPI/flags platform | `posthog-js 1.372.3` | KEEP | Correct tool for product analytics and feature flags. Patch bump is trivial but not a stack verdict. | S | - |
| LLM observability | Brain `langfuse>=2.0.0`; self-hosted Langfuse compose uses `langfuse/langfuse:latest`; latest PyPI `4.5.1` | Langfuse v4 | UPGRADE | Langfuse is the right category, but broad lower bound and `latest` Docker tag reduce reproducibility. Pin and upgrade intentionally. | M | - |
| Log/infra observability | AxiomFolio OTel optional; no Better Stack/Datadog/Logtail dependency found; docs say Datadog/PagerDuty overkill | Central logs + alerts | UPGRADE | Current state is not production-observable enough for tax/finance workflows. Add one log drain/alerting path before scale. | M | - |
| Hetzner / n8n / Postiz | Hetzner ops stack hosts n8n and Postiz; n8n scheduled workflows retired in favor of Brain APScheduler, webhooks/slash flows remain | Small ops VM plus Brain-owned crons | KEEP | The split is pragmatic: Brain owns cron-portable schedules, n8n remains for non-cron workflows. | S | - |

## Build / Tooling

| Layer | Current | Latest stable | Verdict | Why | Cost | Replace with |
|---|---|---|---|---|---|---|
| Monorepo build | Turborepo `2.9.6`, pnpm workspaces, root scripts | `turbo 2.9.6` | KEEP | Current and appropriate. Keep path-filtered CI to control cost. | S | - |
| Vite | Active production apps are Next; design Storybook uses `vite 8.0.10`; archived AxiomFolio Vite excluded | `8.0.10` | KEEP | Vite is only active as Storybook tooling, not product runtime. | S | - |
| Storybook | `storybook 10.3.5`, `@storybook/react-vite 10.3.5`; procedural memory flags known design failure with rolldown/Storybook 10/Vite 8 | `10.3.5` | UPGRADE | Version is current but the design canvas has a known compatibility failure. Fix/pin the integration before treating design CI as trustworthy. | M | - |
| Vitest | Main apps/packages mostly `4.1.5`; Studio still `3.2.4` | `4.1.5` | UPGRADE | Normalize Studio to Vitest 4 in the TS upgrade batch. | S | - |
| Jest | Not found in active packages | Vitest standard | KEEP | No need to add Jest. Vitest is the repo standard. | S | - |
| ESLint | `eslint 10.2.1`, `eslint-config-next 16.2.4` | `10.2.1` | KEEP | Current. Some app `lint` scripts are `next build`, but TS/Next CI still catches most issues. | S | - |
| Prettier / formatting | Prettier `3.8.3` only in FileFree; Ruff format for Python; no Biome found | Prettier `3.8.3` / Ruff format | KEEP | Mixed formatter by language is acceptable. Do not introduce Biome until there is a concrete speed or config pain. | S | - |
| CI quality gates | `ci.yaml`, `code-quality.yaml`, `brain-pre-merge-guards.yml`, `axiomfolio-ci.yml`, golden suite, lockfile gate, gitleaks | GitHub Actions with pinned critical actions | KEEP | CI is broad and improving. The main gap is path-filter blind spots, not the tool choice. | S | - |

## AI / Agent Stack

| Layer | Current | Latest stable | Verdict | Why | Cost | Replace with |
|---|---|---|---|---|---|---|
| Brain LLM provider abstraction | Direct OpenAI, Anthropic, and Google/Gemini calls; router fallbacks in `apis/brain/app/services/router.py` and `llm.py` | Multi-provider router with tool-call support | KEEP | Good architecture: provider abstraction exists and model-specific behavior is tested in golden suites. | S | - |
| Vercel AI SDK | FileFree uses `ai 6.0.168`, `@ai-sdk/react 3.0.170`, `@ai-sdk/openai 3.0.53` | Same | KEEP | Current and appropriate for frontend AI streaming. Brain should remain direct-provider for backend agent control. | S | - |
| OpenAI Python SDK | Brain/FileFree `openai>=1.57.0`; latest PyPI `2.33.0`; AxiomFolio has no OpenAI SDK pin in requirements | `2.33.0` | UPGRADE | Lower bound is old enough to hide API-shape drift. Upgrade behind Brain golden tests. | M | - |
| Anthropic Python SDK | Brain `anthropic>=0.97.0`; latest observed `0.97.0` | `0.97.0` | KEEP | Current. | S | - |
| Embeddings provider | OpenAI `text-embedding-3-small`, 1536 dimensions; pgvector in Postgres | Current OpenAI embeddings + pgvector | KEEP | Good cost/quality choice for Brain memory. Upgrade only if retrieval quality data says it is necessary. | S | - |
| Vector database | Postgres pgvector, no external vector store | pgvector for current scale | KEEP | Correct for current scale and operational simplicity. Avoid Pinecone/Weaviate until Postgres retrieval is measurably insufficient. | S | - |
| Agent memory | `agent_episodes` + hybrid vector/text retrieval in Brain | Postgres-backed hybrid memory with provenance | KEEP | Strong fit for internal agent memory and auditability. Continue improving quality, not replacing storage. | S | - |
| MCP / tool runtime | `fastmcp>=2.6.0`, Brain MCP token, MCP server support | Current FastMCP line | UPGRADE | Confirm and pin FastMCP to an exact current version in the same Python packaging pass. | S | - |

## DevOps

| Layer | Current | Latest stable | Verdict | Why | Cost | Replace with |
|---|---|---|---|---|---|---|
| GitHub Actions | 34 workflows: CI, code quality, Vercel promote, PR pipeline, Brain golden suite, medallion, docs, infra health, sprint jobs | GitHub Actions | KEEP | The workflow suite is rich and aligned with the repo's PR discipline. | S | - |
| PR automation | Auto-merge/rebase/triage workflows, Brain PR sweep, Vercel auto-promote | GitHub + Brain orchestration | KEEP | The design is appropriate; cheap-agent PRs still require orchestrator review before merge. | S | - |
| Cron / scheduling | Brain APScheduler in-process with SQLAlchemy job store; AxiomFolio Celery Beat; GitHub scheduled workflows for audits/golden suite | Durable scheduler for critical jobs | REPLACE | Current setup is acceptable for one Brain instance, but L5 autonomy needs durable semantics for critical jobs once missed runs or multi-instance Brain become real risks. | L | Durable workflow runner / external scheduler for critical jobs |
| Secret management | Vercel envs, Render envs, GitHub secrets, Cloudflare tokens, Studio Vault, Brain secrets intelligence | Central inventory + rotation + drift detection | UPGRADE | The building blocks are strong, but secrets still span multiple providers. Keep consolidating registry, drift checks, and scoped tokens. | M | - |
| Deployment model | Vercel for apps; Render for APIs/workers; Hetzner ops; root Render Blueprint plus Vercel project map | Git-driven deploys + declarative IaC | UPGRADE | The model is right, but drift remains: Render Axiom services and design/accounts Vercel placeholders are not fully closed. | M | - |
| Workstream tracking | `apps/studio/src/data/workstreams.json`; priority unique rule; Studio workstreams board | JSON-backed tracker until Brain DB owns it | KEEP | It is good enough for sprint orchestration. Moving to DB is a product/ops feature, not a stack replacement today. | S | - |

## Verdict Roll-Up By Urgency

### KEEP (no action - already best-in-class)

- React 19, Next.js 16 App Router, Turbopack dev, Tailwind 4.
- shadcn copy-owned components and current `@paperwork-labs/ui` architecture.
- TanStack Query + Zustand state split, React Hook Form, Recharts/Lightweight Charts, Framer Motion.
- Pydantic v2, SQLAlchemy 2 ORM choice, Celery for AxiomFolio workers.
- Vercel as frontend host, PostHog analytics, Hetzner/n8n split, Turborepo, Vite as design tooling only, ESLint, Prettier/Ruff formatting, GitHub Actions, Brain provider abstraction, Vercel AI SDK, Anthropic SDK, OpenAI embeddings, pgvector as current-scale vector DB, Brain memory, PR automation, workstream JSON.

### UPGRADE (in-place version bump or config change)

| Layer | Cost | Trigger | Owner workstream |
|---|---|---|---|
| Python runtime standardization | M | Brain already type-checks as 3.13 while Docker/root still say 3.11 | WS-57 batch A |
| FastAPI / SQLAlchemy / Alembic bounds | S | Mixed lower bounds and LaunchFree requirement mismatch | WS-57 batch A |
| APScheduler patch + singleton health | S | Brain scheduler is core autonomy infrastructure | WS-57 batch A |
| Pytest / pytest-asyncio normalization | S | Service-level test behavior drift | WS-57 batch A |
| Ruff / mypy normalization | M | Strict configs exist but versions and ignore islands vary | WS-57 batch A |
| Redis client normalization | S | Redis server/client versions differ by service | WS-57 batch A |
| OpenTelemetry exporter configuration | M | AxiomFolio has OTel libraries but optional/no-op export path | WS-57 batch B |
| Node LTS upgrade | M | `.node-version` remains 20 while Next 16 stack can move forward | WS-57 batch B |
| pnpm patch bump | S | `10.32.1` to `10.33.2` | WS-57 batch A |
| TypeScript 6 monorepo upgrade | M | Design already uses TS 6, apps mostly TS 5.6 | WS-57 batch B |
| Zod 4 normalization | M | Mixed Zod 3/4 across shared schemas | WS-57 batch B |
| `@paperwork-labs/ui` Storybook/API hardening | M | Package is real but design-system docs and examples lag | WS-57 batch B |
| Postgres version declaration / PG18 migration plan | M | Axiom prod is PG18; local is PG17; Neon docs are imprecise | WS-57 batch C |
| Connection pooling contract | M | No explicit pooled/unpooled production contract | WS-57 batch C |
| pgvector lower-bound upgrade | S | Brain memory dependency lower bound is behind latest | WS-57 batch A |
| Render Blueprint/repo-pointer drift | M | `RENDER_INVENTORY.md` says Axiom services still point to old repo | WS-57 batch C |
| Cloudflare scoped-token cleanup | S | Work account is canonical but broad token remains in config | WS-57 batch A |
| Clerk plan/branding decision | M | SDK current, plan/docs inconclusive | Founder decision + WS-57 batch C |
| Sentry rollout | M | Only FileFree dependency found, DSN coverage not proven | WS-57 batch B |
| Langfuse v4 pin/upgrade | M | Brain uses broad `>=2.0.0`, infra uses Docker `latest` | WS-57 batch B |
| Central logs/alerts | M | OTel optional; no Better Stack/Datadog/Logtail path found | Founder decision + WS-57 batch C |
| Storybook 10 / Vite 8 integration repair | M | Known design package incompatibility in procedural memory | WS-57 batch B |
| Vitest 4 normalization | S | Studio remains on Vitest 3 | WS-57 batch A |
| OpenAI Python SDK upgrade | M | Lower bound `>=1.57.0`, latest `2.33.0` | WS-57 batch B |
| FastMCP pin/current version check | S | Broad lower bound in Brain requirements | WS-57 batch A |
| Secrets registry/drift hardening | M | Vault exists but providers remain fragmented | WS-57 batch C |
| Deployment placeholder cleanup | M | Design/accounts Vercel placeholders and Render drift remain | WS-57 batch C |

### REPLACE (swap library/service)

| Layer | Replace with | Cost | Trigger | Owner workstream |
|---|---|---|---|---|
| Python package management via raw `pip`/requirements | `uv` + committed lockfiles per API | M | Reproducibility and upgrade safety | WS-57 batch B |
| First-party HTTP usage split across `requests`/`aiohttp`/`httpx` | `httpx` as default first-party client | M | Timeout/retry/telemetry consistency | WS-57 batch B |
| In-process-only critical scheduling for future L5 autonomy | Durable workflow runner or external scheduler for critical jobs only | L | Only after Brain grows beyond one scheduler instance or missed-run risk becomes unacceptable | WS-57 batch D |

## Founder Decisions Required

- Clerk plan upgrade: green-light if Clerk Pro/custom branding changes recurring spend by more than $50/mo or affects auth topology.
- Central logs/alerting vendor: choose vendor/spend cap before adding Better Stack, Datadog, or equivalent paid log drains.
- Durable workflow runner replacement for critical Brain jobs: approve only if we move beyond the current one-instance scheduler model or need non-reversible workflow semantics.

## Methodology + Provenance

- Read these files: `package.json`, `pnpm-workspace.yaml`, `apps/*/package.json`, `packages/*/package.json`, `pyproject.toml`, `apis/*/pyproject.toml`, `apis/*/requirements.txt`, `render.yaml`, `apis/*/Dockerfile`, `apps/*/vercel.json`, `.github/workflows/ci.yaml`, `.github/workflows/code-quality.yaml`, `.github/workflows/vercel-promote-on-merge.yaml`, `.github/workflows/brain-pre-merge-guards.yml`, `.github/workflows/brain-golden-suite.yaml`, `.github/workflows/axiomfolio-ci.yml`, `apis/brain/app/config.py`, `infra/compose.dev.yaml`, `scripts/vercel-projects.json`, `docs/infra/RENDER_INVENTORY.md`, `docs/infra/VERCEL_PROJECTS.md`, `docs/infra/VERCEL_QUOTA_AUDIT_2026Q2.md`, `docs/runbooks/cloudflare-ownership.md`, `docs/infra/CLERK_*.md`, and related observability / infra docs found by search.
- Queried latest stable package versions with `npm view` for frontend/tooling packages and `python -m pip index versions` for Python packages.
- Could not access: live Vercel billing plan, live Clerk billing plan, live Render dashboard state, live Cloudflare token scopes, live Sentry/PostHog/Langfuse dashboards. Manual founder/operator review is needed for those.
- Confidence per verdict: high for package versions and repo-local architecture; medium for provider plans, live deployment drift, and production observability because those depend on live accounts outside the repo.
