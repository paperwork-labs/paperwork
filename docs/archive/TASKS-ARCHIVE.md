# FileFree MVP Build Tasks (Archived)

**Archived**: 2026-03-16 | **Original Version**: 8.3

This document preserves the historical Sprint 0-6 task specifications from the original FileFree MVP build. All sprints in this archive are **COMPLETE** or **SUPERSEDED** by the venture-wide phase plan.

For active build tasks, see [TASKS.md](TASKS.md).
For venture strategy, see [VENTURE_MASTER_PLAN.md](VENTURE_MASTER_PLAN.md).

---

**Founding team**: Two co-founders. Founder 1 (Product/Engineering) owns all code tasks. Founder 2 (Partnerships/Revenue) owns partner outreach tasks (marked with "Founder 2" below). See [PARTNERSHIPS.md](PARTNERSHIPS.md) for the full playbook.

**AI-agent-assisted development**: Each task is scoped for 4-8 hours of focused work with AI coding agents. The entire core MVP (Sprint 0 through Sprint 3) targets ~6 weeks of calendar time.

**Historical dates (all met or superseded):**
- March 9: Sprint 0 business ops begin (EFIN, LLC, social accounts, Hetzner VPS, affiliate applications)
- March 16: Foundation complete (Docker, Next.js, FastAPI, DB) -- DONE
- March 16: Landing page content live on filefree.tax (Task 0.4b) -- DONE
- March 30: OCR demo working + try-before-signup live -- DONE
- March 11: Sprint 3 complete (auth, filing flow, tax calc, OAuth, CI) -- DONE (ahead of schedule)
- March 8: Config + credential safety system -- DONE (PR #14)

---


## Sprint 0: Business Operations (March 9 -- parallel with coding)

Non-code tasks that must happen immediately. These run in parallel with Sprint 1.

> **Progress: 4/11 complete, 1 partial** | B.4, B.7, B.10, B.11 done | B.6 partial | B.1, B.2, B.3, B.5, B.8, B.9 not started

<details>
<summary><strong>Task B.1 -- EFIN Application (Form 8633)</strong></summary>


**APPLY THIS WEEK.** 45-day IRS processing time is the longest lead item.

- [ ] PTIN (Preparer Tax Identification Number) -- apply at irs.gov/ptin
- [ ] IRS e-Services account -- register at irs.gov
- [ ] ID.me identity verification
- [ ] Fingerprinting appointment (for non-credentialed applicants)
- [ ] Submit Form 8633 electronically via e-Services

Expected approval: ~late April 2026. This unblocks MeF system access.


</details>
<details>
<summary><strong>Task B.2 -- Company Setup</strong></summary>


- [ ] Register LLC/Corp if not already done
- [ ] Set up business bank account
- [ ] Create social media accounts: TikTok (@filefree), Instagram (@filefree.tax), Twitter/X (@filefreetax), YouTube (FileFree)
- [ ] Pin post on all accounts: "Coming soon -- file your taxes in 5 minutes, free."


</details>
<details>
<summary><strong>Task B.3 -- Legal Drafts</strong></summary>


- [ ] Draft v1 privacy policy (plain English, CCPA/GDPR compliant) -- disclose AI processing of tax data, SSN isolation
- [ ] Draft v1 terms of service with tax preparation disclaimers
- [ ] Note: AI advisory content must be positioned as "tax education" not "tax advice" (IRS Circular 230)


</details>
<details>
<summary><strong>Task B.4 -- Notion Workspace (Company HQ) -- DONE</strong></summary>


- [x] Create Notion workspace: "FileFree HQ"
- [x] Pages: Strategy, Product Roadmap, Decision Log, Content Calendar, Legal/Compliance, Financials
- [x] Decision Log: record every strategic decision with date, rationale, alternatives considered
- [x] Connect to Cursor via .cursor/mcp.json (Notion MCP)


</details>
<details>
<summary><strong>Task B.5 -- Column Tax Outreach</strong></summary>


- [ ] Book Column Tax demo call (columntax.com/contact-us)
- [ ] Goal: understand SDK, negotiate pricing (target $10-15/return), get sandbox access
- [ ] This is backup/interim only -- own MeF transmitter is the priority


</details>
<details>
<summary><strong>Task B.6 -- Social Media Infrastructure + Ad Accounts -- PARTIAL</strong></summary>


**Spin up the social media operations stack (parallel with coding):**

**Hetzner VPS** (EUR 5.49/mo, CX33: 8GB RAM, 4 vCPU, 80GB SSD):
- [x] Server provisioned at 204.168.147.100, deploy configs in `infra/hetzner/`, DNS configured
- [x] Docker, Caddy, firewall installed
- [x] Postiz + n8n + PostgreSQL + Redis deployed via `infra/hetzner/compose.yaml` (+ Temporal stack for Postiz v2.12+)
- [x] n8n persona workflows imported (6 workflows). OpenAI API key credential added in n8n UI
- [x] Notion API key + GitHub PAT added as n8n credentials

**Postiz setup:**
- [ ] Connect accounts: TikTok (@filefree), Instagram (@filefree.tax), X (@filefreetax), YouTube (FileFree)
- [ ] Generate API key for REST API + MCP integration
- [ ] Test scheduling a post to each platform
- [ ] Try Postiz MCP in Cursor (known reliability issues with self-hosted -- use REST API as fallback)

**Ad accounts:**
- [ ] TikTok Ads Manager: create business account, add payment method, install TikTok Pixel on filefree.tax
- [ ] Meta Ads Manager: create business account, connect Instagram, add payment method, install Meta Pixel
- [ ] Do NOT launch ads yet -- wait until Week 3 when organic content proves which formats work

**Content prep:**
- [ ] AI drafts first 10 posts via social.mdc persona (scripts, captions, hooks)
- [ ] Record first 5 founder-led videos (see social.mdc for topics)
- [ ] Schedule Week 2 content in Postiz

**Acceptance**: Postiz is live and can schedule to all 4 platforms. Ad accounts created. First 10 posts drafted. First 5 videos recorded.


</details>
<details>
<summary><strong>Task B.7 -- Partnership Foundation (Founder 1) -- DONE</strong></summary>


Set up the partnership infrastructure and documentation for Founder 2.

- [x] Create `docs/PARTNERSHIPS.md` (standalone playbook for partnerships co-founder)
- [x] Create `.cursor/rules/partnerships.mdc` (AI persona for partnership support)
- [x] Create Notion workspace "FileFree HQ" with Partnership Pipeline database
- [x] AI-generate Pitch Package: Executive Summary (2 pages), Revenue Model one-pager, Partnership Hit List
- [x] Share Notion workspace with Founder 2
- [x] AI-draft all outreach templates in PARTNERSHIPS.md Section 4

**Acceptance**: Founder 2 has a Notion workspace, a standalone playbook, outreach templates, and a pitch package -- everything needed to start operating independently.


</details>
<details>
<summary><strong>Task B.8 -- Affiliate Applications (Either co-founder)</strong></summary>


Apply to affiliate networks for the top 4 HYSA/investment partners. These are online applications -- no calls, no product needed.

- [ ] Create Impact.com publisher account, apply for Marcus by Goldman Sachs
- [ ] Create Impact.com publisher account, apply for Wealthfront
- [ ] Create CJ Affiliate publisher account, apply for Betterment
- [ ] Apply to Fidelity affiliate/advisor program (in-house)
- [ ] Use Template A from PARTNERSHIPS.md for "describe your audience" fields

**Acceptance**: Applications submitted to all 4 partners. Approval expected in 1-2 weeks.


</details>
<details>
<summary><strong>Task B.9 -- Column Tax Demo Call (Founder 2)</strong></summary>


Book and run the Column Tax demo call to secure interim e-file capability.

- [ ] Book demo at columntax.com/contact-us
- [ ] AI preps call brief: volume projections (2K-5K first season, 30K+ at scale), pricing targets ($10-15/return), SDK technical questions, white-labeling options
- [ ] Founder 2 runs the call. Founder 1 joins for technical questions if needed.
- [ ] Goal: confirm pricing, get sandbox access by June 2026

**Acceptance**: Column Tax pricing confirmed. Sandbox access timeline established.


</details>
<details>
<summary><strong>Task B.10 -- Legal Drafts v1 -- DONE</strong></summary>


Draft initial legal documents needed before landing page goes live.

- [x] Draft v1 privacy policy (plain English, CCPA/GDPR compliant) using legal.mdc persona -- live at `/privacy`
- [x] Draft v1 terms of service with tax preparation disclaimers -- live at `/terms`
- [x] Include AI processing disclosure, SSN isolation explanation, data deletion rights
- [x] AI advisory content positioned as "tax education" not "tax advice" (IRS Circular 230)

**Acceptance**: Privacy policy and ToS v1 live. Linked from landing page footer. Drafts for legal review.


</details>
<details>
<summary><strong>Task B.11 -- Agent Autonomy (n8n Workflow Wiring) -- DONE</strong></summary>


Make the 6 imported n8n persona workflows autonomous by connecting their outputs to real systems.

**Workflow wiring:**
- [x] **Social Content Generator** -> drafts post -> creates Notion page in Content Calendar
- [x] **Growth Content Writer** -> drafts blog post -> creates Notion page for review
- [x] **Weekly Strategy Check-in** (Monday 9am cron) -> writes summary to Notion Decision Log
- [x] **QA Security Scan** -> creates GitHub Issue with findings
- [x] **Partnership Outreach Drafter** -> creates Notion entry in Partnership Pipeline
- [x] **CPA Tax Review** -> creates Notion page with review notes

**Prerequisites (all met):**
- [x] Notion API key added as n8n credential
- [x] GitHub personal access token added as n8n credential
- [x] OpenAI API key added as n8n credential
- [ ] Postiz API key added as n8n credential (generate in Postiz UI -- optional, for social scheduling)

**Acceptance**: All 6 workflows produce output in their target systems when triggered. Weekly Strategy Check-in fires automatically on Monday mornings.

---


</details>

## Sprint 1: Foundation + Get Live (Week 1-2)

> **Progress: 5/6 complete, 1 partial** | 0.1, 0.2, 0.3, 0.4, 0.4b done | 0.5 partial (code done, needs DSN)

<details>
<summary><strong>Task 0.1 -- Docker Dev Environment -- DONE</strong></summary>


**Branch**: `feat/0.1-docker-dev-environment`

Set up local development with Docker Compose.

**docker-compose.yml**:
- PostgreSQL 15 (user: filefree, password: filefree_dev, db: filefree_dev)
- Redis 7 (sessions)
- FastAPI backend (volume-mounted, hot reload, port 8000)
- Next.js frontend (volume-mounted, hot reload, port 3000)

**Dockerfiles**:
- `api/Dockerfile` -- Python 3.11-slim, install requirements, expose 8000
- `web/Dockerfile.dev` -- Node 20-alpine, npm install, expose 3000

**Also create**:
- `.gitignore` -- Node, Python, .env, .next, __pycache__, venv, docker volumes, uploads/
- `.env.example` files for both frontend and backend
- `README.md` with setup instructions
- Named volumes for postgres data persistence
- `Makefile` -- targets: `dev` (docker compose up), `test` (run all tests), `lint` (ruff + eslint), `format` (ruff format + prettier), `migrate` (alembic upgrade head), `seed` (seed test data), `clean` (docker compose down -v)
- `.python-version` -- `3.11` (pyenv/asdf compatible)
- `.node-version` -- `20` (nvm/fnm compatible)
- `pyproject.toml` -- ruff + mypy configuration ONLY (deps stay in requirements.txt for wider compatibility)

**Important:** Docker Compose is for LOCAL DEVELOPMENT ONLY. Production uses Render native buildpack (render.yaml) + Vercel git deploy. No production Dockerfiles needed.

Health checks on all services. API waits for healthy postgres and redis before starting.

**Test isolation**: Separate `filefree_test` database created via `infra/init-test-db.sh`. Tests use transactional rollback (no data persists). Test schema auto-created from SQLAlchemy models. `conftest.py` overrides `get_db` dependency for full isolation.

**Acceptance**: `docker compose up` starts everything, frontend on :3000, API /health returns `{ "status": "healthy" }`. `make dev`, `make test`, `make lint` all work. Tests never touch dev database.

---


</details>
<details>
<summary><strong>Task 0.2 -- Next.js Frontend Init + Design System -- DONE</strong></summary>


**Branch**: `feat/0.2-frontend-design-system`

Create `web/` with Next.js 14 App Router, TypeScript, Tailwind CSS, ESLint, src directory.

**Dependencies**:
- framer-motion, recharts, lucide-react, zustand, @tanstack/react-query
- react-hook-form, @hookform/resolvers, zod, axios
- ai, @ai-sdk/react, @ai-sdk/openai
- @react-pdf/renderer
- clsx, tailwind-merge, next-themes, sonner, vaul, react-dropzone, date-fns, nuqs
- canvas-confetti

**shadcn/ui init**: New York style, Slate base, CSS variables, border-radius 0.5rem. Install: button, input, label, card, dialog, sheet, tooltip, popover, dropdown-menu, select, checkbox, radio-group, switch, textarea, separator, badge, skeleton, progress, form, command, accordion.

**Design system** (see PRODUCT_SPEC.md):
- `tailwind.config.ts`: dark mode 'class', Indigo primary + Slate neutrals, Inter + JetBrains Mono
- `globals.css`: CSS custom properties for all tokens in `:root` and `.dark`
- `next-themes`: defaultTheme="dark"
- Inter via `next/font/google`, weights 400/500/600/700

**Foundational files**:
- `src/lib/utils.ts` -- `cn()`, `formatCurrency()`, `formatSSN()`
- `src/lib/motion.ts` -- Framer Motion presets
- `src/lib/api.ts` -- axios instance with withCredentials, error interceptor
- `src/types/index.ts` -- TypeScript interfaces matching PRD.md data models

Base layout: dark background, fonts, metadata, QueryClientProvider, ThemeProvider.

**Acceptance**: Runs on :3000 with dark theme, design tokens work, shadcn components render.

---


</details>
<details>
<summary><strong>Task 0.3 -- FastAPI Backend Init + Database -- DONE</strong></summary>


**Branch**: `feat/0.3-backend-database`

Create `api/` with structure:
```
api/
├── app/
│   ├── main.py, config.py, database.py
│   ├── models/       (all data models)
│   ├── schemas/      (Pydantic request/response)
│   ├── routers/      (auth, filings, documents, tax, waitlist)
│   ├── services/     (auth, document, ocr, tax_calculator, storage)
│   ├── repositories/ (user, filing, document)
│   └── utils/        (encryption, security, exceptions, pii_scrubber)
├── alembic/ + alembic.ini
├── tax-data/2025.json
├── tests/
├── requirements.txt
└── .env.example
```

**requirements.txt**: fastapi, uvicorn[standard], gunicorn, sqlalchemy[asyncio], asyncpg, alembic, pydantic, pydantic-settings, python-multipart, python-jose[cryptography], passlib[bcrypt], google-cloud-vision, google-cloud-storage, openai, redis, pillow, httpx, slowapi, cryptography, pytest, pytest-asyncio, ruff, mypy, factory-boy.

**Implement**:
- `main.py`: CORS, router prefixes, exception handlers, PII scrubbing middleware, /health
- `config.py`: Pydantic Settings for all env vars
- `database.py`: async SQLAlchemy engine + session + get_db
- `utils/encryption.py`: AES-256 encrypt/decrypt
- `utils/security.py`: hash_password, verify_password, generate_session_token
- `utils/exceptions.py`: custom exceptions with HTTP status mapping
- `utils/pii_scrubber.py`: middleware stripping SSN patterns from logs
- All SQLAlchemy models per PRD.md Section 5 (includes Waitlist table)
- `tax-data/2025.json`: brackets, standard deductions ($15,750/$31,500/$15,750/$23,625), source citations

**Alembic**: async, initial migration.

**Acceptance**: /health returns healthy, Alembic creates all tables.

---


</details>
<details>
<summary><strong>Task 0.4 -- Infrastructure + Deploy -- DONE</strong></summary>


**Branch**: `feat/0.4-landing-deploy`

**Infrastructure** (DONE):
- Vercel live at filefree.tax (Hobby tier, auto-deploy from `main`)
- Render Starter ($7/mo) live at api.filefree.tax (custom domain, TLS)
- Neon PostgreSQL connected + migrated (auto-migration on startup via Alembic)
- DNS configured (Spaceship): A record (Vercel), CNAME www (Vercel), CNAME api (Render), A records for n8n/social/ops (Hetzner)
- `render.yaml` at project root for Render Blueprints IaC
- POST /api/v1/waitlist endpoint live and tested e2e
- Neon URL auto-normalized: `postgresql://` -> `postgresql+asyncpg://`, `sslmode` -> `ssl`, `channel_binding` stripped

**Acceptance**: All services healthy, `api.filefree.tax/health` returns `{"status":"healthy","db_connected":true}`, waitlist endpoint creates records in Neon.

---


</details>
<details>
<summary><strong>Task 0.4b -- Landing Page Content -- DONE</strong></summary>


**Branch**: `feat/0.4b-landing-page`

Build the actual landing page content. Infrastructure is done (Task 0.4) but filefree.tax has no content yet.

**Landing page** (`src/app/page.tsx`):
- Hero: "Taxes shouldn't make you cry." / "Snap your W2. Get your return in minutes. Actually free."
- Email capture: "Get early access" -> POST /api/v1/waitlist (already live)
- 3-step "How it works": Snap -> We read it -> Download your return
- Trust badges: "256-bit encrypted", "We never sell your data", "Your data is deleted when you ask"
- Anti-TurboTax hook: "Unlike TurboTax, we don't ask 60 questions or charge hidden fees."
- Mobile-first, dark theme, gradient accents, fast
- Social media links in footer
- Privacy policy and ToS links in footer (link to /privacy and /terms)

**Acceptance**: filefree.tax is shareable, email capture works, page loads in < 2s, responsive 375px-1440px.

---


</details>
<details>
<summary><strong>Task 0.5 -- Analytics Foundation -- PARTIAL</strong></summary>


**Branch**: `feat/0.5-analytics`

Wire up analytics before the landing page goes live. Pulled forward from Task 2.7.

**PostHog:**
- [x] Install `posthog-js`
- [x] PII scrubbing filter (SSN + email patterns) before any event
- [x] PostHogProvider wrapping app with page view tracking
- [x] UTM parameter capture via attribution.ts -> posthog.register()
- [x] Key events wired: `waitlist_signup`, `waitlist_signup_error`
- [x] PostHog project API key configured in `.env.production`
- [ ] Verify events appearing in PostHog dashboard
- [ ] Set up `page_view` -> `waitlist_signup` funnel

**Sentry** (lightweight):
- [x] @sentry/nextjs with source maps (withSentryConfig in next.config.mjs)
- [x] Error boundaries (global-error.tsx + error.tsx + not-found.tsx)
- [x] Client/server/edge configs with PII scrubbing (SSN pattern redaction)
- [x] Instrumentation hooks for request error capture
- [ ] Set NEXT_PUBLIC_SENTRY_DSN in .env.production and Vercel
- [ ] Alert on >10 errors/5min (configure in Sentry dashboard)

**Acceptance**: PostHog dashboard shows page views and waitlist signups. UTM parameters attached to events. Sentry catches frontend errors.

---


</details>

## Sprint 2: OCR Demo for April 15 (March 22 - April 15)

> **Progress: 4/4 complete** | 1.1, 1.2, 1.3, 1.4 done

Ship the "wow moment" -- anonymous W2 scanning -- to ride the April 15 traffic spike.

<details>
<summary><strong>Task 1.1 -- Camera Component + Image Quality -- DONE</strong></summary>


**Branch**: `feat/1.1-camera-image-quality`

**`src/components/camera/document-camera.tsx`**:
Props: documentType, onCapture, onError.

Features:
1. Rear camera via getUserMedia
2. Live video stream with document-shaped cutout overlay
3. Guide text + capture button with animation
4. "Upload from library" fallback
5. Post-capture quality check and preview

**`src/lib/image-quality.ts`**: blur check, dimension check, file size check.

**`src/components/upload/file-upload-zone.tsx`**: react-dropzone wrapper with drag-over, progress, errors.

**Acceptance**: Camera works mobile + desktop, quality checks catch bad images, upload fallback works.

---


</details>
<details>
<summary><strong>Task 1.2 -- Tiered OCR Pipeline (Cloud Vision + GPT) + Demo Endpoint -- DONE</strong></summary>


**Branch**: `feat/1.2-ocr-pipeline`

**Backend OCR -- Tiered Pipeline (Cloud Vision + GPT)**:

`services/image_processor.py`:
- preprocess_image(image_bytes): auto-rotate via EXIF, contrast normalization (Pillow), resize to optimal OCR dimensions, return processed image bytes
- Uses Pillow only (no OpenCV needed -- Cloud Vision handles document detection)

`services/ocr_service.py`:
- process_document(image_bytes, document_type):
  1. Preprocess image via image_processor
  2. Call GCP Cloud Vision `DOCUMENT_TEXT_DETECTION` -- returns hierarchical text (pages/blocks/paragraphs/words) with bounding box coordinates. $0.0015/page.
  3. Extract SSN via regex (`\d{3}-?\d{2}-?\d{4}`) from Cloud Vision text output LOCALLY -- NEVER send to GPT (replace with masked placeholder XXX-XX-XXXX)
  4. **Primary path**: GPT-4o-mini structured output -- send scrubbed OCR text + bounding box positions, maps to W-2 Pydantic schema (~$0.001/doc)
  5. **Fallback path** (if low confidence <85%): GPT-4o vision receives actual image for direct extraction (~$0.02/doc)
  6. Post-validate: SSN format (9 digits), EIN format (XX-XXXXXXX), wage amounts numeric, cross-field consistency
  7. Return extraction_data + confidence_scores

- No model initialization needed (Cloud Vision is a remote API call -- no memory overhead)
- MOCK MODE: if OPENAI_API_KEY not set, return realistic hardcoded W2 data. Essential for dev.
- MOCK GCV MODE: if GOOGLE_APPLICATION_CREDENTIALS not set, return realistic hardcoded OCR output. Essential for dev without GCP credentials.

`services/storage_service.py`: GCP Cloud Storage upload, signed URL, local filesystem fallback for dev.

`services/document_service.py`:
- upload_document(db, file, document_type, filing_id, user_id): save to GCP Cloud Storage, create Document record, trigger background processing
- demo_extract(file, document_type): process without storage, return data directly (for try-before-signup)

**Routers** (`routers/documents.py`):
- POST `/api/v1/documents/demo-upload` -- anonymous, rate limited (3/day/IP), no persistent storage, returns extraction data directly
- POST `/api/v1/documents/upload` -- authenticated, full pipeline
- GET `/api/v1/documents/{id}/status` -- poll extraction status
- GET `/api/v1/documents/{id}/data` -- full data
- PATCH `/api/v1/documents/{id}/data` -- user corrections

**Acceptance**: Demo endpoint works without auth, Cloud Vision extracts text from W2 images, GPT-4o-mini maps fields correctly, SSN never sent to OpenAI, rate limiting works, mock mode returns realistic data.

---


</details>
<details>
<summary><strong>Task 1.3 -- Try-Before-Signup Frontend -- DONE</strong></summary>


**Branch**: `feat/1.3-try-before-signup`

The viral entry point: snap a W2 without an account, see the magic.

**Flow**:
1. Landing page CTA "Snap Your W2 -- See It In Action" -> opens camera/upload (NO auth required)
2. On capture: upload to demo-upload endpoint
3. Show loading: animated gradient orb "Reading your W2..."
4. On success: extracted data cascades in field by field (50ms stagger animation)
5. Show extracted employer name, wages, withheld amounts
6. Gate: "Create a free account to save your return and calculate your refund" -> register page
7. Store extracted data in sessionStorage
8. On register: transfer sessionStorage data to new Filing + TaxProfile

**Implementation**:
- `src/app/demo/page.tsx` -- the try-before-signup flow
- `src/components/demo/extraction-reveal.tsx` -- animated field cascade
- Update landing page CTA to link to /demo

**Acceptance**: Anonymous user can scan W2, see extracted data, sign up and have data preserved. The cascade animation is genuinely impressive.

---


</details>
<details>
<summary><strong>Task 1.4 -- Content Foundation + Social Media Launch Sprint -- DONE</strong></summary>


**Branch**: `feat/1.4-content-foundation`

This runs in parallel with engineering tasks. Split into code (SEO/pages) and non-code (social execution).

**Technical SEO (code)**:
- `src/app/sitemap.ts` and `src/app/robots.ts`
- Meta tags on all pages via Next.js Metadata API
- OG image (1200x630)
- JSON-LD structured data on landing page
- TikTok Pixel + Meta Pixel installed via `next/script`

**Content pages** (3 articles targeting organic traffic):
- `src/app/guides/how-to-file-taxes-for-free/page.tsx` -- targets "how to file taxes for free 2026"
- `src/app/guides/what-is-a-w2/page.tsx` -- targets "what is a W2 form"
- `src/app/guides/standard-deduction-2025/page.tsx` -- targets "standard deduction 2025 amount"

Each article: genuinely helpful, links to product naturally, FAQ schema markup for snippets.

**/pricing page** (`src/app/pricing/page.tsx`):
- Crystal clear: what's free, what's paid
- Free forever guarantee for core filing (federal + state)
- Premium services listed with prices: Tax Optimization Plan ($29/yr), Audit Shield ($19-29/yr)
- Comparison table: FileFree vs TurboTax vs FreeTaxUSA vs Cash App Taxes
- "What's the catch?" section (there isn't one -- we make money when you choose premium services)

**Acceptance**: All pages have proper meta tags, sitemap generates, pricing page is honest and clear. Pixels installed.

---


</details>

## Sprint 3: Full MVP (April 15 - May 31)

> **Progress: 7/7 complete** | 2.1-2.7 done

Complete filing flow for extension filers.

<details>
<summary><strong>Task 2.1 -- Backend Auth System -- DONE</strong></summary>


**Branch**: `feat/2.1-backend-auth`

Redis sessions: key = `session:{token}`, value = user_id, TTL = 7 days.

**`services/auth_service.py`**: register, login, logout, get_current_user, delete_account (CCPA).

**`routers/auth.py`**:
- POST register -- sets httponly cookie
- POST login -- sets cookie
- POST logout -- clears cookie + session
- GET /me -- current user or 401
- DELETE /account -- delete all data

Cookie: httponly, secure, samesite='lax', max_age=604800.
CSRF: token on login, validate on all state-changing requests.
Rate limiting: 5 req/min on auth via slowapi.

**Acceptance**: Full auth cycle works, CSRF works, rate limiting works. 20 tests covering register (7), login (3), me (3), logout (2), delete (2), CSRF (3), rate limiting (1), cookie properties (1). All 52 tests pass.

---


</details>
<details>
<summary><strong>Task 2.2 -- Frontend Auth + Protected Routes -- DONE</strong></summary>


**Branch**: `feat/2.2-frontend-auth`

**Auth pages**:
- `src/app/auth/layout.tsx` -- centered card on gradient background
- `src/app/auth/register/page.tsx` -- Full Name, Email, Password, Confirm Password, Zod validation
- `src/app/auth/login/page.tsx` -- Email, Password

**State**: Zustand store for auth (user, isAuthenticated). React-query mutations for login/register/logout.

**Middleware**: protect /file/* and /dashboard/*, redirect to /auth/login if no session.

**Session timeout**: 30 min inactivity -> "Still there?" modal.

**Acceptance**: Register, login, protected routes, timeout, logout -- all work end-to-end.

---


</details>
<details>
<summary><strong>Task 2.3 -- Filing Flow Layout + Data Confirmation -- DONE</strong></summary>


**Branch**: `feat/2.3-filing-flow`

**`src/app/file/layout.tsx`**: progress bar, step labels, exit button, AnimatePresence transitions.

**Zustand store** (`use-filing-store.ts`): steps, currentStep, filing data, navigation actions.

**Step routes**:
- `/file` -> creates filing, redirects to first step
- `/file/w2` -> camera component (Task 1.1)
- `/file/identity` -> DL capture or manual entry
- `/file/confirm` -> data confirmation
- `/file/details` -> filing details (Task 2.4)
- `/file/summary` -> return summary (Task 2.5)

**Data confirmation page** (`/file/confirm`):
- Section 1: "Your Information" -- name, address, DOB (editable)
- Section 2: "Your Income" -- per W2 card with employer name, EIN, SSN (masked), wages, withheld
- Confidence indicators (green/yellow/red) with pulsing animation
- OCR auto-fill cascade animation (the magic moment)
- Manual entry fallback with W2 box-number labels
- "Add Another W2" button
- "Everything Looks Right" CTA

**Backend**: filing CRUD endpoints (POST, GET, PATCH), document upload flow.

**Acceptance**: Full navigation works, OCR data renders with confidence, manual fallback works, corrections save.

---


</details>
<details>
<summary><strong>Task 2.4 -- Filing Details + Tax Calculator -- DONE</strong></summary>


**Branch**: `feat/2.4-tax-calculator`

**Filing details** (`/file/details`):
- Filing status: 4 large tappable cards (Single, MFJ, MFS, HoH)
- Standard deduction display (updates on selection)
- Minimal -- only legally required questions
- CTA: "Calculate My Return"

**Tax calculator** (`services/tax_calculator.py`):
- Load from `tax-data/2025.json`
- `get_standard_deduction(filing_status) -> int` (cents)
- `calculate_federal_tax(taxable_income_cents, filing_status) -> int`
- `calculate_return(filing_id, db) -> TaxCalculation`
- ALL CENTS. INTEGER ONLY.

**AI Insights** (generated on calculate):
- Call GPT-4o with user's tax data
- Plain-English explanation + 1-2 personalized tips
- Store in TaxCalculation.ai_insights
- Fallback template if OpenAI fails

**Router**: POST /calculate, GET /calculation.

**Tests** -- 100% coverage:
- Each bracket boundary for all filing statuses
- Zero income, deduction > income
- Refund and owed scenarios
- Correct standard deductions: $15,750 / $31,500 / $15,750 / $23,625
- Validate against IRS Publication 17 examples

**Acceptance**: Calculation correct for all scenarios, 100% test coverage.

---


</details>
<details>
<summary><strong>Task 2.5 -- Return Summary + PDF Generation -- DONE</strong></summary>


**Branch**: `feat/2.5-return-summary-pdf`

**Return summary** (`/file/summary`):
- Refund reveal: animated count-up, green gradient. Owed: calm amber.
- Breakdown card: stagger animation
- Charts: pie ("Where Your Taxes Go"), bar ("Your Refund vs Average")
- AI insights card with sparkle icon
- Tax receipt viral card (shareable graphic)
- CTAs: "Download Your Return (PDF)", "Add State Filing -- Free"

**PDF generation** (GET `/api/v1/filings/{id}/pdf`):
- @react-pdf/renderer
- Cover page: "Your 2025 Federal Tax Return -- Prepared by FileFree"
- Form 1040: field layout matching IRS form, Courier font, all calculated values
- Instructions page: how to submit via IRS Free File or mail
- Footer: "Prepared by FileFree (filefree.tax)"

**Acceptance**: Summary looks beautiful with animations, PDF downloads with correct data.

---


</details>
<details>
<summary><strong>Task 2.6 -- Component Library + Error Handling + Mobile Polish -- DONE</strong></summary>


**Branch**: `feat/2.6-polish`

**Custom components** (on top of shadcn):
- SSNInput: masked, toggle reveal, auto-format, lock icon
- CurrencyDisplay: count-up animation, green/amber coloring
- SecureBadge: lock + "Encrypted & Secure"
- InfoTooltip: popover (desktop) / bottom sheet (mobile)
- EmptyState: icon, title, description, CTA
- StepProgress: animated progress bar with clickable completed steps

**Error handling**:
- Global error boundary (`error.tsx`), custom 404
- Skeleton components for all pages
- Inline validation with field shake animation
- sonner toasts for API errors (never raw)
- Offline detection banner
- Session expiry modal

**Mobile audit** (375px, 390px, 768px, 1024px, 1440px):
- 44px minimum touch targets
- vaul bottom sheets below lg breakpoint
- inputMode attributes (numeric for SSN/currency)
- Sticky bottom bar for Continue
- No horizontal overflow

**Acceptance**: Every error state has designed UI, mobile feels native-quality.

---


</details>
<details>
<summary><strong>Task 2.7 -- Analytics + Monitoring + Production Hardening -- DONE</strong></summary>


**Branch**: `feat/2.7-analytics-production`

**PostHog**:
- posthog-js + posthog-react, PII filter before any event
- Key events: signup, filing_started, step_completed, upload, ocr_completed, filing_completed, share_card, advisory_interest
- Funnel: landing -> demo -> signup -> filing_start -> filing_complete

**Sentry**: @sentry/nextjs, source maps, error boundaries, alert on >10 errors/5min.

**CI**: GitHub Actions -- lint, type check, test, build on PR/push to main.

**Acceptance**: Events fire, PII filtered, Sentry catches errors, CI passes.

---


</details>

## Infrastructure: Config + Credential Safety (March 2026)

> **Progress: 1/1 complete**

<details>
<summary><strong>Task I.1 -- Centralized Config System + Credential Safety -- DONE</strong></summary>


**Branch**: `feat/config-credential-safety`

**Problem**: Frontend had 14 raw `process.env` reads scattered across 10 files with no validation. `web/.env.production` was tracked in git with the PostHog API key committed. No secrets scanner existed. n8n had zero workflows after D31 database isolation.

**What shipped:**
- [x] Zod-validated `server-config.ts` and `client-config.ts` replacing all scattered `process.env` reads
- [x] `docs/CREDENTIALS.md` -- company-wide credential registry (29 credentials, 7 categories)
- [x] PostHog key moved from tracked `.env.production` to gitignored `.env.local`
- [x] Gitleaks secrets scanner added to CI (blocks PRs with leaked credentials)
- [x] `.gitleaksignore` for historical PostHog key
- [x] `web/.env.example` documenting all env vars
- [x] Shared `web/src/types/ops.ts` (DRY types for ops dashboard)
- [x] All 6 n8n persona workflows re-imported via REST API
- [x] Orphaned `SESSION_SECRET` removed from CI

**Acceptance**: Type check clean, 38/38 frontend tests pass, no secrets in tracked files, ops dashboard shows live n8n workflow data.

**PR**: #14

---


</details>

## Sprint 4: Growth + E-File Prep (June - September) -- SUPERSEDED

> **Status**: SUPERSEDED by Venture Phase 7 (FileFree Season Prep). Tasks below preserved as detailed specs. See `docs/VENTURE_MASTER_PLAN.md` Section 7 for venture-wide context.

<details>
<summary><strong>Task 3.1 -- Full Marketing Landing Page</strong></summary>

**Branch**: `feat/3.1-marketing-page`

Replace simple landing page with full marketing page. See PRODUCT_SPEC.md for detailed specs.

- Hero with try-before-signup CTA + animated background
- Social proof: filing counter, testimonials from beta users
- 3-step How It Works with scroll-triggered animations
- Competitive comparison table (honest, fact-based)
- Trust section: security badges, encryption details
- FAQ accordion (5-7 first-time filer questions)
- Footer with legal disclaimers

Lighthouse 95+ on all categories.

**Acceptance**: Looks premium, loads fast, responsive.

</details>
<details>
<summary><strong>Task 3.2 -- Tax Receipt Viral Card + Referral System</strong></summary>

**Branch**: `feat/3.2-viral-referral`

**Tax receipt card**:
- Post-filing: "Share your filing card" option
- Content: filing time, opt-in refund amount, date, FileFree branding, filefree.tax URL
- Formats: Instagram Story (1080x1920), Twitter (1200x675), square (1080x1080)
- Generate server-side via @vercel/og or canvas API
- One-tap share or download

**Referral system**:
- Each user gets unique code on registration (already in User model)
- filefree.tax/ref/{code} -> landing page with referral tracking
- Dashboard card: "Share FileFree -- [referral link]"
- Track: referral clicks, signups, completions

**Acceptance**: Card generates beautifully, share works, referral tracking functions.

</details>
<details>
<summary><strong>Task 3.3 -- Column Tax SDK Integration (Interim E-File)</strong></summary>

**Branch**: `feat/3.3-column-tax-efile`

Integrate Column Tax web SDK into post-summary filing flow. Pre-fill all extracted data. Handle submission status (accepted/rejected). Cost-passthrough pricing.

**Acceptance**: E-file works end-to-end in sandbox, cost-passthrough pricing displays correctly, rejection handling works, free PDF alternative always available.

</details>
<details>
<summary><strong>Task 3.4 -- State Tax Calculation (All 50 States)</strong></summary>

**Branch**: `feat/3.4-state-tax`

Data-driven state tax engine reading from `tax-data/states/{state}.json`. 9 no-income-tax states, 9 flat-tax states, ~32 graduated-bracket states. 100% test coverage.

**Acceptance**: Correct state calculations for all 50 states. JSON data files validated against state DOR publications.

</details>
<details>
<summary><strong>Task 3.5 -- Transactional Emails + Lifecycle</strong></summary>

**Branch**: `feat/3.5-emails`

Transactional (react-email + resend): welcome, email verification, filing confirmation.
Lifecycle drip sequences: abandonment (24h, 72h, 7d), tax deadline reminders, advisory teaser.

**Acceptance**: All emails render, send, are mobile-responsive, CAN-SPAM compliant.

</details>
<details>
<summary><strong>Task 3.6 -- Refund Plan + Financial Partnerships</strong></summary>

**Branch**: `feat/3.6-refund-plan`

Primary monetization screen. Interactive refund allocation UI (Form 8888), partner HYSA/IRA recommendations, Audit Shield upsell, affiliate disclosure compliance.

**Acceptance**: Refund Plan screen renders personalized recommendations. Form 8888 data generates correctly. Affiliate links track properly.

</details>
<details>
<summary><strong>Task 3.7 -- Refund Advance Partner Outreach (Founder 2)</strong></summary>

Cold outreach to Refundo and Green Dot/Republic Bank. Negotiate rev share ($3-5/advance). Goal: one lending partner signed by October 2026.

**Acceptance**: At least one refund advance partner in active negotiation or signed.

</details>
<details>
<summary><strong>Task 3.8 -- Affiliate-to-Direct Partnership Upgrade (Founder 2)</strong></summary>

Phase 3 of tiered partnership strategy. Pull affiliate conversion data, upgrade to direct partnership with 2-3x higher payouts ($100-200+/funded account).

**Acceptance**: At least one affiliate partner upgraded to direct partnership.

</details>

## Sprint 5: October Extension Season Launch -- SUPERSEDED

> **Status**: SUPERSEDED by Venture Phase 7 (P7.2 Column Tax integration).

<details>
<summary><strong>Task 4.1 -- E-File Go-Live + Extension Campaign</strong></summary>

**Branch**: `feat/4.1-efile-launch`

Flip e-file from sandbox to production. Marketing push for extension filers. Monitor acceptance/rejection rates.

**Acceptance**: Real returns accepted by IRS, monitoring dashboard shows health.

</details>

## Sprint 6: January 2027 Full Season -- SUPERSEDED

> **Status**: SUPERSEDED by Venture Phase 8 (FileFree Launch).

<details>
<summary><strong>Task 5.1 -- Tax Optimization Plan (Stripe, $29/year)</strong></summary>

Wire up Stripe for $29/year Tax Optimization Plan. Premium dashboard with W-4 optimizer, year-over-year comparison, IRA/401k calculator.

</details>
<details>
<summary><strong>Task 5.2 -- Financial Product Referral Infrastructure</strong></summary>

Partnership agreements with 2-3 financial products (HYSA, investing, credit card). Referral tracking, attribution, disclosure compliance.

</details>
<details>
<summary><strong>Task 5.3 -- Product Hunt + HN Launch</strong></summary>

Prepare launch assets. Coordinate timing with filing season start. Target first week of February 2027.

</details>
<details>
<summary><strong>Task 5.4 -- Admin Dashboard</strong></summary>

User management, filing queue, OCR accuracy monitor, error log, support queue. @tanstack/react-table.

</details>
<details>
<summary><strong>Task 5.5 -- Accessibility Audit</strong></summary>

WCAG 2.1 AA. Keyboard nav, screen readers, contrast, reduced motion. axe-core in CI.

</details>
<details>
<summary><strong>Task 5.6 -- Dependent Support + Complex Filing</strong></summary>

Add dependent data model, child tax credit calculation. Eventually: 1099 support, itemized deductions.

</details>
<details>
<summary><strong>Task 5.7 -- Own IRS MeF Transmitter (NORTH STAR)</strong></summary>

**Branch**: `feat/5.7-mef-transmitter`

Build MeF XML generator from TaxCalculation data model. Map all Form 1040 fields to IRS MeF XML schema (IRS Publication 4164). Pass 12 mandatory IRS ATS test scenarios. Communication test with IRS MeF production system.

**Acceptance**: Pass all 12 ATS scenarios, communication test succeeds, first production return accepted by IRS.

</details>
