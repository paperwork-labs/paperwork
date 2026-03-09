# FileFree — Unified Build Tasks

**Version**: 7.0 | **Updated**: 2026-03-09

Work through these in order. Each task is scoped for one PR. Reference [PRODUCT_SPEC.md](PRODUCT_SPEC.md) for UX specs, [.cursorrules](../.cursorrules) for coding conventions, [PRD.md](PRD.md) for business context, [PARTNERSHIPS.md](PARTNERSHIPS.md) for partner playbook.

**Founding team**: Two co-founders. Founder 1 (Product/Engineering) owns all code tasks. Founder 2 (Partnerships/Revenue) owns partner outreach tasks (marked with "Founder 2" below). See [PARTNERSHIPS.md](PARTNERSHIPS.md) for the full playbook.

**AI-agent-assisted development**: Each task is scoped for 4-8 hours of focused work with AI coding agents. The entire core MVP (Sprint 0 through Sprint 3) targets ~6 weeks of calendar time.

**Critical dates:**
- March 9: Sprint 0 business ops begin (EFIN, LLC, social accounts, Hetzner VPS, affiliate applications)
- March 16: Foundation complete (Docker, Next.js, FastAPI, DB) — DONE
- March 16: Landing page content live on filefree.tax (Task 0.4b)
- March 30: OCR demo working + try-before-signup live
- April 5-15: Content push for tax deadline — OCR demo is the marketing asset
- April 15 - May 31: Full MVP (auth, filing flow, tax calc, PDF, polish)
- June 2026: Column Tax sandbox access confirmed (Founder 2 negotiated)
- October 2026: Column Tax e-file live + IRS ATS testing begins for own transmitter
- January 2027: Own MeF transmitter live = FREE E-FILE (NORTH STAR)

---

## Sprint 0: Business Operations (March 9 — parallel with coding)

Non-code tasks that must happen immediately. These run in parallel with Sprint 1.

**Status key**: DONE = complete, PARTIAL = in progress, blank = not started.

### Task B.1 — EFIN Application (Form 8633)

**APPLY THIS WEEK.** 45-day IRS processing time is the longest lead item.

Requirements:
- PTIN (Preparer Tax Identification Number) — apply at irs.gov/ptin
- IRS e-Services account — register at irs.gov
- ID.me identity verification
- Fingerprinting appointment (for non-credentialed applicants)
- Submit Form 8633 electronically via e-Services

Expected approval: ~late April 2026. This unblocks MeF system access.

### Task B.2 — Company Setup

- Register LLC/Corp if not already done
- Set up business bank account
- Create social media accounts: TikTok (@filefree), Instagram (@filefree.tax), Twitter/X (@filefreetax), YouTube (FileFree)
- Pin post on all accounts: "Coming soon — file your taxes in 5 minutes, free."

### Task B.3 — Legal Drafts

- Draft v1 privacy policy (plain English, CCPA/GDPR compliant) — disclose AI processing of tax data, SSN isolation
- Draft v1 terms of service with tax preparation disclaimers
- Note: AI advisory content must be positioned as "tax education" not "tax advice" (IRS Circular 230)

### Task B.4 — Notion Workspace (Company HQ) — DONE

- ~~Create Notion workspace: "FileFree HQ"~~
- ~~Pages: Strategy, Product Roadmap, Decision Log, Content Calendar, Legal/Compliance, Financials~~
- ~~Decision Log: record every strategic decision with date, rationale, alternatives considered~~
- ~~Connect to Cursor via .cursor/mcp.json (Notion MCP)~~

### Task B.5 — Column Tax Outreach

- Book Column Tax demo call (columntax.com/contact-us)
- Goal: understand SDK, negotiate pricing (target $10-15/return), get sandbox access
- This is backup/interim only — own MeF transmitter is the priority

### Task B.6 — Social Media Infrastructure + Ad Accounts — PARTIAL

**Spin up the social media operations stack (parallel with coding):**

**Hetzner VPS** (EUR 5.49/mo, CX33: 8GB RAM, 4 vCPU, 80GB SSD) — server provisioned at 204.168.147.100, deploy configs in `infra/hetzner/`, DNS configured. Bootstrapped: Docker, Caddy, firewall installed. All services running.
- Postiz (social media scheduler) + n8n (workflow automation) + PostgreSQL + Redis deployed via `infra/hetzner/compose.yaml`
- Single shared `filefree_ops` database within PostgreSQL
- **n8n persona workflows imported** (6 workflows: Social Content Generator, Growth Content Writer, Weekly Strategy Check-in, QA Security Scan, Partnership Outreach Drafter, CPA Tax Review). Workflow JSONs in `infra/hetzner/workflows/`. OpenAI API key credential added in n8n UI — DONE.

**Postiz setup:**
- Connect accounts: TikTok (@filefree), Instagram (@filefree.tax), X (@filefreetax), YouTube (FileFree)
- Generate API key for REST API + MCP integration
- Test scheduling a post to each platform
- Try Postiz MCP in Cursor (known reliability issues with self-hosted — use REST API as fallback)

**Ad accounts:**
- TikTok Ads Manager: create business account, add payment method, install TikTok Pixel on filefree.tax
- Meta Ads Manager: create business account, connect Instagram, add payment method, install Meta Pixel
- Do NOT launch ads yet — wait until Week 3 when organic content proves which formats work

**Content prep:**
- AI drafts first 10 posts via [social.mdc](../.cursor/rules/social.mdc) persona (scripts, captions, hooks)
- Record first 5 founder-led videos (see [social.mdc](../.cursor/rules/social.mdc) for topics)
- Schedule Week 2 content in Postiz

**Acceptance**: Postiz is live and can schedule to all 4 platforms. Ad accounts created. First 10 posts drafted. First 5 videos recorded.

### Task B.7 — Partnership Foundation (Founder 1) — DONE

Set up the partnership infrastructure and documentation for Founder 2.

- ~~Create `docs/PARTNERSHIPS.md` (standalone playbook for partnerships co-founder)~~
- ~~Create `.cursor/rules/partnerships.mdc` (AI persona for partnership support)~~
- ~~Create Notion workspace "FileFree HQ" with Partnership Pipeline database~~
- ~~AI-generate Pitch Package: Executive Summary (2 pages), Revenue Model one-pager, Partnership Hit List~~
- ~~Share Notion workspace with Founder 2~~
- ~~AI-draft all outreach templates in [PARTNERSHIPS.md](PARTNERSHIPS.md) Section 4~~

**Acceptance**: Founder 2 has a Notion workspace, a standalone playbook, outreach templates, and a pitch package — everything needed to start operating independently.

### Task B.8 — Affiliate Applications (Either co-founder)

Apply to affiliate networks for the top 4 HYSA/investment partners. These are online applications — no calls, no product needed.

- Create Impact.com publisher account, apply for Marcus by Goldman Sachs
- Create Impact.com publisher account, apply for Wealthfront
- Create CJ Affiliate publisher account, apply for Betterment
- Apply to Fidelity affiliate/advisor program (in-house)
- Use Template A from [PARTNERSHIPS.md](PARTNERSHIPS.md) for "describe your audience" fields

**Acceptance**: Applications submitted to all 4 partners. Approval expected in 1-2 weeks.

### Task B.9 — Column Tax Demo Call (Founder 2)

Book and run the Column Tax demo call to secure interim e-file capability.

- Book demo at columntax.com/contact-us
- AI preps call brief: volume projections (2K-5K first season, 30K+ at scale), pricing targets ($10-15/return), SDK technical questions, white-labeling options
- Founder 2 runs the call. Founder 1 joins for technical questions if needed.
- Goal: confirm pricing, get sandbox access by June 2026

**Acceptance**: Column Tax pricing confirmed. Sandbox access timeline established.

### Task B.10 — Legal Drafts v1

Draft initial legal documents needed before landing page goes live.

- Draft v1 privacy policy (plain English, CCPA/GDPR compliant) using [legal.mdc](../.cursor/rules/legal.mdc) persona
- Draft v1 terms of service with tax preparation disclaimers
- Include AI processing disclosure, SSN isolation explanation, data deletion rights
- Note: AI advisory content must be positioned as "tax education" not "tax advice" (IRS Circular 230)

**Acceptance**: Privacy policy and ToS drafts ready for legal review before landing page ships.

### Task B.11 — Agent Autonomy (n8n Workflow Wiring)

Make the 6 imported n8n persona workflows autonomous by connecting their outputs to real systems. No code changes — all configuration in n8n UI.

**Workflow wiring:**
- **Social Content Generator** → drafts post → creates Notion page in Content Calendar → optionally schedules in Postiz via API
- **Growth Content Writer** → drafts blog post → creates Notion page for review
- **Weekly Strategy Check-in** (already on Monday 9am cron) → writes summary to Notion Decision Log
- **QA Security Scan** → creates GitHub Issue with findings
- **Partnership Outreach Drafter** → creates Notion entry in Partnership Pipeline
- **CPA Tax Review** → creates Notion page with review notes

**Prerequisites:**
- Notion API key added as n8n credential (Settings > Credentials > Notion)
- GitHub personal access token added as n8n credential
- Postiz API key added as n8n credential (generate in Postiz UI)
- Each workflow needs 2-3 additional nodes (API calls to Notion/GitHub/Postiz)

**Acceptance**: All 6 workflows produce output in their target systems when triggered. Weekly Strategy Check-in fires automatically on Monday mornings.

---

## Sprint 1: Foundation + Get Live (Week 1-2)

### Task 0.1 — Docker Dev Environment — DONE

**Branch**: `feat/0.1-docker-dev-environment`

Set up local development with Docker Compose.

**docker-compose.yml**:
- PostgreSQL 15 (user: filefree, password: filefree_dev, db: filefree_dev)
- Redis 7 (sessions)
- FastAPI backend (volume-mounted, hot reload, port 8000)
- Next.js frontend (volume-mounted, hot reload, port 3000)

**Dockerfiles**:
- `api/Dockerfile` — Python 3.11-slim, install requirements, expose 8000
- `web/Dockerfile.dev` — Node 20-alpine, npm install, expose 3000

**Also create**:
- `.gitignore` — Node, Python, .env, .next, __pycache__, venv, docker volumes, uploads/
- `.env.example` files for both frontend and backend
- `README.md` with setup instructions
- Named volumes for postgres data persistence
- `Makefile` — targets: `dev` (docker compose up), `test` (run all tests), `lint` (ruff + eslint), `format` (ruff format + prettier), `migrate` (alembic upgrade head), `seed` (seed test data), `clean` (docker compose down -v)
- `.python-version` — `3.11` (pyenv/asdf compatible)
- `.node-version` — `20` (nvm/fnm compatible)
- `pyproject.toml` — ruff + mypy configuration ONLY (deps stay in requirements.txt for wider compatibility)

**Important:** Docker Compose is for LOCAL DEVELOPMENT ONLY. Production uses Render native buildpack (render.yaml) + Vercel git deploy. No production Dockerfiles needed.

Health checks on all services. API waits for healthy postgres and redis before starting.

**Test isolation**: Separate `filefree_test` database created via `infra/init-test-db.sh`. Tests use transactional rollback (no data persists). Test schema auto-created from SQLAlchemy models. `conftest.py` overrides `get_db` dependency for full isolation.

**Acceptance**: `docker compose up` starts everything, frontend on :3000, API /health returns `{ "status": "healthy" }`. `make dev`, `make test`, `make lint` all work. Tests never touch dev database.

---

### Task 0.2 — Next.js Frontend Init + Design System — DONE

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

**Design system** (see [PRODUCT_SPEC.md](PRODUCT_SPEC.md)):
- `tailwind.config.ts`: dark mode 'class', Indigo primary + Slate neutrals, Inter + JetBrains Mono
- `globals.css`: CSS custom properties for all tokens in `:root` and `.dark`
- `next-themes`: defaultTheme="dark"
- Inter via `next/font/google`, weights 400/500/600/700

**Foundational files**:
- `src/lib/utils.ts` — `cn()`, `formatCurrency()`, `formatSSN()`
- `src/lib/motion.ts` — Framer Motion presets
- `src/lib/api.ts` — axios instance with withCredentials, error interceptor
- `src/types/index.ts` — TypeScript interfaces matching [PRD.md](PRD.md) data models

Base layout: dark background, fonts, metadata, QueryClientProvider, ThemeProvider.

**Acceptance**: Runs on :3000 with dark theme, design tokens work, shadcn components render.

---

### Task 0.3 — FastAPI Backend Init + Database — DONE

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
- All SQLAlchemy models per [PRD.md](PRD.md) Section 5 (includes Waitlist table)
- `tax-data/2025.json`: brackets, standard deductions ($15,750/$31,500/$15,750/$23,625), source citations

**Alembic**: async, initial migration.

**Acceptance**: /health returns healthy, Alembic creates all tables.

---

### Task 0.4 — Infrastructure + Deploy — DONE

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

### Task 0.4b — Landing Page Content

**Branch**: `feat/0.4b-landing-page`

Build the actual landing page content. Infrastructure is done (Task 0.4) but filefree.tax has no content yet.

**Landing page** (`src/app/page.tsx`):
- Hero: "Taxes shouldn't make you cry." / "Snap your W2. Get your return in minutes. Actually free."
- Email capture: "Get early access" → POST /api/v1/waitlist (already live)
- 3-step "How it works": Snap → We read it → Download your return
- Trust badges: "256-bit encrypted", "We never sell your data", "Your data is deleted when you ask"
- Anti-TurboTax hook: "Unlike TurboTax, we don't ask 60 questions or charge hidden fees."
- Mobile-first, dark theme, gradient accents, fast
- Social media links in footer
- Privacy policy and ToS links in footer (link to /privacy and /terms — pages from Task B.10)

**Acceptance**: filefree.tax is shareable, email capture works, page loads in < 2s, responsive 375px-1440px.

---

### Task 0.5 — Analytics Foundation

**Branch**: `feat/0.5-analytics`

Wire up analytics before the landing page goes live. Pulled forward from Task 2.7 — we need attribution from day one.

**PostHog**:
- Install posthog-js + posthog-react
- PII filter before any event (no email, no SSN in events)
- Key events: `page_view`, `waitlist_signup`, `cta_click`
- UTM parameter capture (already in frontend code, needs PostHog integration)
- Funnel: landing → waitlist_signup

**Sentry** (lightweight):
- @sentry/nextjs with source maps
- Error boundaries
- Alert on >10 errors/5min

**Acceptance**: PostHog dashboard shows page views and waitlist signups. UTM parameters attached to events. Sentry catches frontend errors.

---

## Sprint 2: OCR Demo for April 15 (March 22 - April 15)

Ship the "wow moment" — anonymous W2 scanning — to ride the April 15 traffic spike.

### Task 1.1 — Camera Component + Image Quality

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

### Task 1.2 — Tiered OCR Pipeline (Cloud Vision + GPT) + Demo Endpoint

**Branch**: `feat/1.2-ocr-pipeline`

**Backend OCR — Tiered Pipeline (Cloud Vision + GPT)**:

`services/image_processor.py`:
- preprocess_image(image_bytes): auto-rotate via EXIF, contrast normalization (Pillow), resize to optimal OCR dimensions, return processed image bytes
- Uses Pillow only (no OpenCV needed — Cloud Vision handles document detection)

`services/ocr_service.py`:
- process_document(image_bytes, document_type):
  1. Preprocess image via image_processor
  2. Call GCP Cloud Vision `DOCUMENT_TEXT_DETECTION` — returns hierarchical text (pages/blocks/paragraphs/words) with bounding box coordinates. $0.0015/page.
  3. Extract SSN via regex (`\d{3}-?\d{2}-?\d{4}`) from Cloud Vision text output LOCALLY — NEVER send to GPT (replace with masked placeholder XXX-XX-XXXX)
  4. **Primary path**: GPT-4o-mini structured output — send scrubbed OCR text + bounding box positions, maps to W-2 Pydantic schema (~$0.001/doc)
  5. **Fallback path** (if low confidence <85%): GPT-4o vision receives actual image for direct extraction (~$0.02/doc)
  6. Post-validate: SSN format (9 digits), EIN format (XX-XXXXXXX), wage amounts numeric, cross-field consistency
  7. Return extraction_data + confidence_scores

- No model initialization needed (Cloud Vision is a remote API call — no memory overhead)
- MOCK MODE: if OPENAI_API_KEY not set, return realistic hardcoded W2 data. Essential for dev.
- MOCK GCV MODE: if GOOGLE_APPLICATION_CREDENTIALS not set, return realistic hardcoded OCR output. Essential for dev without GCP credentials.

`services/storage_service.py`: GCP Cloud Storage upload, signed URL, local filesystem fallback for dev.

`services/document_service.py`:
- upload_document(db, file, document_type, filing_id, user_id): save to GCP Cloud Storage, create Document record, trigger background processing
- demo_extract(file, document_type): process without storage, return data directly (for try-before-signup)

**Routers** (`routers/documents.py`):
- POST `/api/v1/documents/demo-upload` — anonymous, rate limited (3/day/IP), no persistent storage, returns extraction data directly
- POST `/api/v1/documents/upload` — authenticated, full pipeline (used later in Task 1.5)
- GET `/api/v1/documents/{id}/status` — poll extraction status
- GET `/api/v1/documents/{id}/data` — full data
- PATCH `/api/v1/documents/{id}/data` — user corrections

**Accuracy Validation (REQUIRED):** Test the Cloud Vision + GPT-4o-mini pipeline against 20+ real W-2 images. Document per-field accuracy (employer name, EIN, wages, federal withholding, SSN, employee name/address). Target: 95%+ accuracy on Tier 1. If accuracy < 95%, increase GPT-4o vision fallback usage. Log results in [KNOWLEDGE.md](KNOWLEDGE.md).

**Acceptance**: Demo endpoint works without auth, Cloud Vision extracts text from W2 images, GPT-4o-mini maps fields correctly, SSN never sent to OpenAI, rate limiting works, mock mode returns realistic data. Accuracy validation results documented.

---

### Task 1.3 — Try-Before-Signup Frontend

**Branch**: `feat/1.3-try-before-signup`

The viral entry point: snap a W2 without an account, see the magic.

**Flow**:
1. Landing page CTA "Snap Your W2 — See It In Action" → opens camera/upload (NO auth required)
2. On capture: upload to demo-upload endpoint
3. Show loading: animated gradient orb "Reading your W2..."
4. On success: extracted data cascades in field by field (50ms stagger animation)
5. Show extracted employer name, wages, withheld amounts
6. Gate: "Create a free account to save your return and calculate your refund" → register page
7. Store extracted data in sessionStorage
8. On register: transfer sessionStorage data to new Filing + TaxProfile

**Implementation**:
- `src/app/demo/page.tsx` — the try-before-signup flow
- `src/components/demo/extraction-reveal.tsx` — animated field cascade
- Update landing page CTA to link to /demo

**Acceptance**: Anonymous user can scan W2, see extracted data, sign up and have data preserved. The cascade animation is genuinely impressive.

---

### Task 1.4 — Content Foundation + Social Media Launch Sprint

**Branch**: `feat/1.4-content-foundation`

This runs in parallel with engineering tasks. Split into code (SEO/pages) and non-code (social execution).

**Technical SEO (code)**:
- `src/app/sitemap.ts` and `src/app/robots.ts`
- Meta tags on all pages via Next.js Metadata API
- OG image (1200x630)
- JSON-LD structured data on landing page
- TikTok Pixel + Meta Pixel installed via `next/script`

**Content pages** (3 articles targeting organic traffic):
- `src/app/guides/how-to-file-taxes-for-free/page.tsx` — targets "how to file taxes for free 2026"
- `src/app/guides/what-is-a-w2/page.tsx` — targets "what is a W2 form"
- `src/app/guides/standard-deduction-2025/page.tsx` — targets "standard deduction 2025 amount"

Each article: genuinely helpful, links to product naturally, FAQ schema markup for snippets.

**/pricing page** (`src/app/pricing/page.tsx`):
- Crystal clear: what's free, what's paid
- Free forever guarantee for core filing (federal + state)
- Premium services listed with prices: Tax Optimization Plan ($29/yr), Audit Shield ($19-29/yr)
- Comparison table: FileFree vs TurboTax vs FreeTaxUSA vs Cash App Taxes
- "What's the catch?" section (there isn't one — we make money when you choose premium services)

**Social media launch (non-code — uses Postiz from Task B.6)**:
- Daily posting begins: TikTok + IG Reels + X (7/week minimum during tax season)
- Week 2: "Coming soon" + build-in-public content. "Building a free tax app live", "Day 5 of building FileFree"
- Week 3 (app live): shift to "it's live" + demo reactions. "I just filed my taxes in 2 minutes for free"
- First creator outreach: 10 DMs to personal finance micro-influencers (10K-100K followers)
- Content calendar: 4-week plan drafted via [social.mdc](../.cursor/rules/social.mdc) persona, scheduled in Postiz
- Paid amplification: after Week 3, boost top organic posts via TikTok Spark Ads + Meta (see [social.mdc](../.cursor/rules/social.mdc) for playbook). Budget: $200-500/mo in intermittent bursts on winners.

**Acceptance**: All pages have proper meta tags, sitemap generates, pricing page is honest and clear. Pixels installed. 20+ posts scheduled in Postiz. Daily posting cadence established.

---

## Sprint 3: Full MVP (April 15 - May 31)

Complete filing flow for extension filers.

### Task 2.1 — Backend Auth System

**Branch**: `feat/2.1-backend-auth`

Redis sessions: key = `session:{token}`, value = user_id, TTL = 7 days.

**`services/auth_service.py`**: register, login, logout, get_current_user, delete_account (CCPA).

**`routers/auth.py`**:
- POST register — sets httponly cookie
- POST login — sets cookie
- POST logout — clears cookie + session
- GET /me — current user or 401
- DELETE /account — delete all data

Cookie: httponly, secure, samesite='lax', max_age=604800.
CSRF: token on login, validate on all state-changing requests.
Rate limiting: 5 req/min on auth via slowapi.

**Acceptance**: Full auth cycle works, CSRF works, rate limiting works.

---

### Task 2.2 — Frontend Auth + Protected Routes

**Branch**: `feat/2.2-frontend-auth`

**Auth pages**:
- `src/app/auth/layout.tsx` — centered card on gradient background
- `src/app/auth/register/page.tsx` — Full Name, Email, Password, Confirm Password, Zod validation
- `src/app/auth/login/page.tsx` — Email, Password

**State**: Zustand store for auth (user, isAuthenticated). React-query mutations for login/register/logout.

**Middleware**: protect /file/* and /dashboard/*, redirect to /auth/login if no session.

**Session timeout**: 30 min inactivity → "Still there?" modal.

**Acceptance**: Register, login, protected routes, timeout, logout — all work end-to-end.

---

### Task 2.3 — Filing Flow Layout + Data Confirmation

**Branch**: `feat/2.3-filing-flow`

**`src/app/file/layout.tsx`**: progress bar, step labels, exit button, AnimatePresence transitions.

**Zustand store** (`use-filing-store.ts`): steps, currentStep, filing data, navigation actions.

**Step routes**:
- `/file` → creates filing, redirects to first step
- `/file/w2` → camera component (Task 1.1)
- `/file/identity` → DL capture or manual entry
- `/file/confirm` → data confirmation (below)
- `/file/details` → filing details (Task 2.4)
- `/file/summary` → return summary (Task 2.5)

**Data confirmation page** (`/file/confirm`):
- Section 1: "Your Information" — name, address, DOB (editable)
- Section 2: "Your Income" — per W2 card with employer name, EIN, SSN (masked), wages, withheld
- Confidence indicators (green/yellow/red) with pulsing animation
- OCR auto-fill cascade animation (the magic moment)
- Manual entry fallback with W2 box-number labels
- "Add Another W2" button
- "Everything Looks Right" CTA

**Backend**: filing CRUD endpoints (POST, GET, PATCH), document upload flow.

**Acceptance**: Full navigation works, OCR data renders with confidence, manual fallback works, corrections save.

---

### Task 2.4 — Filing Details + Tax Calculator

**Branch**: `feat/2.4-tax-calculator`

**Filing details** (`/file/details`):
- Filing status: 4 large tappable cards (Single, MFJ, MFS, HoH)
- Standard deduction display (updates on selection)
- Minimal — only legally required questions
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

**Tests** — 100% coverage:
- Each bracket boundary for all filing statuses
- Zero income, deduction > income
- Refund and owed scenarios
- Correct standard deductions: $15,750 / $31,500 / $15,750 / $23,625
- Validate against IRS Publication 17 examples

**Acceptance**: Calculation correct for all scenarios, 100% test coverage.

---

### Task 2.5 — Return Summary + PDF Generation

**Branch**: `feat/2.5-return-summary-pdf`

**Return summary** (`/file/summary`):
- Refund reveal: animated count-up, green gradient. Owed: calm amber.
- Breakdown card: stagger animation
- Charts: pie ("Where Your Taxes Go"), bar ("Your Refund vs Average")
- AI insights card with sparkle icon
- Tax receipt viral card (shareable graphic — see [PRODUCT_SPEC.md](PRODUCT_SPEC.md))
- CTAs: "Download Your Return (PDF)", "Add State Filing — Free"

**PDF generation** (GET `/api/v1/filings/{id}/pdf`):
- @react-pdf/renderer
- Cover page: "Your 2025 Federal Tax Return — Prepared by FileFree"
- Form 1040: field layout matching IRS form, Courier font, all calculated values
- Instructions page: how to submit via IRS Free File or mail
- Footer: "Prepared by FileFree (filefree.tax)"

**Refund Plan teaser** (on download/next-steps page):
- "Where should your refund go?" — link to Refund Plan screen (Task 3.6)
- Preview tip based on their data (e.g., "Your refund could earn $55 in a 5.5% APY savings account")
- If pre-launch: email capture for "get notified when financial recommendations are ready"

**Acceptance**: Summary looks beautiful with animations, PDF downloads with correct data, advisory teaser captures interest.

---

### Task 2.6 — Component Library + Error Handling + Mobile Polish

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

### Task 2.7 — Analytics + Monitoring + Production Hardening

**Branch**: `feat/2.7-analytics-production`

**PostHog**:
- posthog-js + posthog-react, PII filter before any event
- Key events: signup, filing_started, step_completed, upload, ocr_completed, filing_completed, share_card, advisory_interest
- Funnel: landing → demo → signup → filing_start → filing_complete

**Sentry**: @sentry/nextjs, source maps, error boundaries, alert on >10 errors/5min.

**CI**: GitHub Actions — lint, type check, test, build on PR/push to main.

**Acceptance**: Events fire, PII filtered, Sentry catches errors, CI passes.

---

## Sprint 4: Growth + E-File Prep (June - September)

### Task 3.1 — Full Marketing Landing Page

**Branch**: `feat/3.1-marketing-page`

Replace simple landing page with full marketing page. See [PRODUCT_SPEC.md](PRODUCT_SPEC.md) for detailed specs.

- Hero with try-before-signup CTA + animated background
- Social proof: filing counter, testimonials from beta users
- 3-step How It Works with scroll-triggered animations
- Competitive comparison table (honest, fact-based)
- Trust section: security badges, encryption details
- FAQ accordion (5-7 first-time filer questions)
- Footer with legal disclaimers

Lighthouse 95+ on all categories.

**Acceptance**: Looks premium, loads fast, responsive.

---

### Task 3.2 — Tax Receipt Viral Card + Referral System

**Branch**: `feat/3.2-viral-referral`

**Tax receipt card**:
- Post-filing: "Share your filing card" option
- Content: filing time, opt-in refund amount, date, FileFree branding, filefree.tax URL
- Formats: Instagram Story (1080x1920), Twitter (1200x675), square (1080x1080)
- Generate server-side via @vercel/og or canvas API
- One-tap share or download

**Referral system**:
- Each user gets unique code on registration (already in User model)
- filefree.tax/ref/{code} → landing page with referral tracking
- Dashboard card: "Share FileFree — [referral link]"
- Track: referral clicks, signups, completions

**Acceptance**: Card generates beautifully, share works, referral tracking functions.

---

### Task 3.3 — Column Tax SDK Integration (Interim E-File, Founder 1 + Founder 2)

**Branch**: `feat/3.3-column-tax-efile`

**Context**: This is the INTERIM e-file solution while our own MeF transmitter goes through IRS certification (see Task 5.7). Column Tax provides e-file capability at cost-passthrough until January 2027. Pricing and sandbox access negotiated by Founder 2 in Task B.9.

**Implementation**:
- Integrate Column Tax web SDK into post-summary filing flow
- Pre-fill all extracted data (name, SSN, income, deductions, calculated tax) via Column Tax API
- White-label Column Tax UI to match FileFree branding where possible
- Handle submission status (accepted/rejected) and surface in FileFree dashboard
- POST /api/v1/filings/{id}/submit, GET /api/v1/filings/{id}/submission

**UX (see [PRODUCT_SPEC.md](PRODUCT_SPEC.md) e-file transition section)**:
- Summary page shows two CTAs: "Download PDF (Free)" and "E-File (~$X, at cost)"
- Transparent messaging: "We're completing IRS e-file certification. Until then, e-file through our certified partner at cost, or download and mail for free."
- On success: return to FileFree celebration screen with confetti
- Free PDF download ALWAYS prominently visible as alternative

**Testing**: Full sandbox testing before October 1 go-live.

**Acceptance**: E-file works end-to-end in sandbox, cost-passthrough pricing displays correctly, rejection handling works, free PDF alternative is always available.

---

### Task 3.4 — State Tax Calculation

**Branch**: `feat/3.4-state-tax`

Top 5 income-tax states: CA, NY, IL, PA, OH.
- Pluggable module per state (brackets, credits, rules)
- No-income-tax states: auto-detect and skip
- Account for SALT cap ($40,000 for 2025)
- State tax results included in summary and PDF

**Acceptance**: Correct state calculations for all 5 states + no-tax state handling.

---

### Task 3.5 — Transactional Emails + Lifecycle

**Branch**: `feat/3.5-emails`

**Transactional** (react-email + resend, notifications@filefree.tax):
- Welcome: "Welcome to FileFree"
- Email verification: 24-hour expiry link
- Filing confirmation: "Your return is ready!" + PDF download link

**Lifecycle** (drip sequences):
- Abandonment: 24h, 72h, 7 days after starting but not completing
- Tax deadline: 2 weeks and 3 days before April 15 / October 15
- Advisory teaser: monthly tip based on filing data (warm up for subscription)

**Acceptance**: All emails render, send, are mobile-responsive, CAN-SPAM compliant.

---

### Task 3.6 — Refund Plan + Financial Partnerships

**Branch**: `feat/3.6-refund-plan`

The primary monetization screen. See [PRODUCT_SPEC.md](PRODUCT_SPEC.md) "Refund Plan Screen" for full UX spec.

**Refund Plan page** (`src/app/filing/[id]/refund-plan/page.tsx`):
- Interactive refund allocation UI (split refund into up to 3 accounts via IRS Form 8888)
- Partner HYSA/IRA recommendation cards with personalized projections
- "3 things that could save you money" recommendation section
- Audit Shield upsell card ($19-29/yr)
- Affiliate disclosure compliance (FTC)
- All recommendations based on user's actual tax data (income, refund amount, filing status)
- Default: keep everything in existing checking. No pressure to change.

**Partner integration architecture** (`services/referrals.py`):
- Referral link generation with UTM tracking per partner
- Conversion webhook handler (partner reports successful signup)
- Revenue attribution tracking in database
- Partner payout reconciliation (monthly)

**Form 8888 integration**:
- When user allocates to partner accounts, generate Form 8888 data
- Include in MeF XML submission or PDF package
- Validate routing/account numbers against partner API

**Dashboard "Tax Tips" card** (`/dashboard`):
- Free tier: one generic monthly tip
- Tax Optimization Plan purchasers: personalized tips, W-4 calculator link, IRA optimizer
- Soft upsell for non-purchasers: "Get your personalized plan — $29/year"

**Tracking**: `refund_plan_viewed`, `refund_routing_selected`, `recommendation_clicked`, `recommendation_converted`, `audit_shield_purchased`, `optimization_plan_purchased`.

**Acceptance**: Refund Plan screen renders personalized recommendations. Form 8888 data generates correctly. Affiliate links track properly. Audit Shield purchase flow works.

---

### Task 3.7 — Refund Advance Partner Outreach (Founder 2)

**Context**: Requires e-file capability (Column Tax integration from Task 3.3 must be close to live).

- Cold outreach to Refundo and Green Dot/Republic Bank
- AI ([partnerships.mdc](../.cursor/rules/partnerships.mdc)) drafts pitch email using Template D from [PARTNERSHIPS.md](PARTNERSHIPS.md)
- Founder 2 personalizes and sends
- Negotiate rev share ($3-5/advance)
- Goal: one lending partner signed by October 2026 e-file launch

**Acceptance**: At least one refund advance partner in active negotiation or signed.

---

### Task 3.8 — Affiliate-to-Direct Partnership Upgrade (Founder 2, when 5K+ users)

**Context**: Phase 3 of the tiered partnership strategy. Only begin when we have conversion data to prove our value.

- Pull affiliate conversion data from top-performing partners
- AI drafts direct partnership pitch using Template C from [PARTNERSHIPS.md](PARTNERSHIPS.md)
- Founder 2 reaches out to affiliate account managers for upgrade discussions
- Target: 2-3x higher payouts ($100-200+/funded account), co-marketing, API integration
- Negotiate with Marcus, Wealthfront, or Betterment (whichever has highest conversion)

**Acceptance**: At least one affiliate partner upgraded to direct partnership with higher payout terms.

---

## Sprint 5: October Extension Season Launch

### Task 4.1 — E-File Go-Live + Extension Campaign

**Branch**: `feat/4.1-efile-launch`

- Flip e-file from sandbox to production
- Marketing push: "Haven't filed yet? Do it in 5 minutes. Free."
- Email blast to waitlist + existing users
- Social media campaign targeting extension filers
- Monitor e-file acceptance/rejection rates

**Acceptance**: Real returns accepted by IRS, monitoring dashboard shows health.

---

## Sprint 6: January 2027 Full Season (October - January)

### Task 5.1 — Tax Optimization Plan (Stripe, $29/year)
Wire up Stripe for $29/year Tax Optimization Plan. Premium dashboard with W-4 optimizer, year-over-year comparison, IRA/401k calculator. Annual one-time purchase at filing time, not a monthly subscription.

### Task 5.2 — Financial Product Referral Infrastructure
Partnership agreements with 2-3 financial products (HYSA, investing, credit card). Referral tracking, attribution, disclosure compliance. In-app recommendations based on tax data.

### Task 5.3 — Product Hunt + HN Launch
Prepare launch assets. Coordinate timing with filing season start. Target first week of February 2027.

### Task 5.4 — Admin Dashboard
User management, filing queue, OCR accuracy monitor, error log, support queue. @tanstack/react-table.

### Task 5.5 — Accessibility Audit
WCAG 2.1 AA. Keyboard nav, screen readers, contrast, reduced motion. axe-core in CI.

### Task 5.6 — Dependent Support + Complex Filing
Add dependent data model, child tax credit calculation. Eventually: 1099 support, itemized deductions.

### Task 5.7 — Own IRS MeF Transmitter (NORTH STAR)

**Branch**: `feat/5.7-mef-transmitter`

**This is the #1 long-term strategic priority.** Owning our e-file infrastructure means $0/return, full control, no third-party dependencies, and "free forever" becomes permanently sustainable.

**Prerequisites** (from Sprint 0):
- EFIN approved (Form 8633, applied March 2026)
- e-Services MeF system access granted

**Implementation**:

`services/mef_generator.py`:
- Build MeF XML generator from TaxCalculation data model
- Map all Form 1040 fields to IRS MeF XML schema (IRS Publication 4164)
- Generate valid MeF XML envelope with required headers, manifests, and digital signatures
- Support: Form 1040, Schedule 1, Schedule B (interest/dividends), state returns (top 5 states)

`services/mef_transmitter.py`:
- Submit MeF XML to IRS SOAP web service
- Handle acknowledgments (accepted/rejected)
- Parse rejection codes and map to user-friendly messages
- Retry logic for transient failures

**IRS ATS Testing (October 2026)**:
- Submit 12 mandatory test scenarios to IRS Assurance Testing System
- Scenarios include: single filer, MFJ, various income levels, refund/owed, state returns
- Must pass ALL 12 scenarios to receive production authorization
- ATS opens once per year in October — missing this window delays by a full year

**Communication Test (November 2026)**:
- Submit test transmission to IRS MeF production system
- Verify end-to-end connectivity and XML validation

**Go-Live (January 2027)**:
- Switch from Column Tax SDK to own MeF transmitter for all simple returns
- E-file becomes FREE for all users
- Keep Column Tax as fallback for edge cases / complex returns not yet supported
- Monitor acceptance/rejection rates closely in first 2 weeks

**Acceptance**: Pass all 12 ATS scenarios, communication test succeeds, first production return accepted by IRS.

---

## How to Use This Document

1. Start each task by creating a branch: `feat/{task-number}-short-description`
2. Read [.cursorrules](../.cursorrules) for coding conventions
3. Reference [PRODUCT_SPEC.md](PRODUCT_SPEC.md) for detailed UX specs
4. Reference [PRD.md](PRD.md) for business context and competitive strategy
5. Complete the task, test it, create a PR, merge, move on
6. Each PR should be self-contained and deployable
7. After each sprint, review analytics and adjust priorities based on data
