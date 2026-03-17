# Paperwork Labs — Knowledge Base

Organizational memory for Paperwork Labs (FileFree, LaunchFree, Distill, Trinkets). AI agents read this at session start. Update after significant decisions, learnings, or pattern discoveries.

**Last Updated**: 2026-03-16

---

## Decisions

### D1: PaddleOCR -> Google Cloud Vision API (2026-03-09)
- **Context**: Needed to choose OCR engine for W-2 text extraction.
- **Decision**: Use GCP Cloud Vision `DOCUMENT_TEXT_DETECTION` instead of self-hosted PaddleOCR.
- **Alternatives**: PaddleOCR (self-hosted), AWS Textract, Google Document AI W-2 Parser ($0.30/doc).
- **Rationale**: PaddleOCR needs 500MB-2GB+ RAM in production with documented memory leak history, forcing a $25/mo Render Standard instance. Cloud Vision costs $0.0015/page (1K free/mo), has zero hosting overhead, and Google does NOT store images or use them for training. At our scale (<8K users/mo), Cloud Vision is cheaper even with per-request costs because the hosting savings outweigh API costs.
- **Reversibility**: Easy. OCR engine is abstracted behind `services/ocr_service.py`. Can swap back to PaddleOCR at scale (10K+ users/mo) if self-hosting becomes cheaper.

### D2: Railway -> Render for Backend Hosting (2026-03-09)
- **Context**: Evaluating PaaS providers for FastAPI backend.
- **Decision**: Use Render (Starter plan, $7/mo, 512MB).
- **Alternatives**: Railway (usage-based ~$5-12/mo), Fly.io (~$5-15/mo), GCP Cloud Run.
- **Rationale**: Railway has 26 incidents in the last 30 days vs Render's 6 (4x worse reliability). For a tax filing app where trust is everything, reliability during tax season outweighs Railway's ~$200/year savings from usage-based pricing. Railway's serverless cold starts (1-10s) stacked with Neon cold starts (300-800ms) create unacceptable first-request latency.
- **Reversibility**: Easy. Render -> Railway migration is straightforward.

### D3: Render Standard -> Render Starter (2026-03-09)
- **Context**: Without PaddleOCR, the backend is a lightweight FastAPI app making HTTP calls.
- **Decision**: Downgrade from Render Standard ($25/mo, 2GB) to Render Starter ($7/mo, 512MB).
- **Rationale**: FastAPI + SQLAlchemy + deps need ~200-300MB. 512MB is sufficient without ML model hosting. Saves $18/mo = $216/year.
- **Reversibility**: Easy. One-click upgrade in Render dashboard.

### D4: Own IRS MeF Transmitter as North Star (2026-03-09)
- **Context**: Need e-file capability but IRS certification takes ~10 months.
- **Decision**: Build own MeF transmitter (target January 2027) as the #1 strategic priority. $0/return, full control, permanent "free forever" sustainability.
- **Alternatives**: Permanent Column Tax partnership, TaxBandits API, manual PDF-only.
- **Rationale**: Owning the transmitter eliminates third-party dependency and per-return cost. IRS ATS testing opens once per year in October — missing it delays by a full year. EFIN application is the longest lead item (45 days).
- **Reversibility**: Hard. Significant engineering investment. But Column Tax stays as fallback.

### D5: Column Tax as Interim E-File Partner (2026-03-09)
- **Context**: Need e-file for October 2026 extension season while MeF transmitter is in IRS certification.
- **Decision**: Integrate Column Tax SDK with transparent cost-passthrough pricing (no markup).
- **Rationale**: Honest messaging builds trust: "We're completing IRS certification. E-file at cost until then, or download PDF free." Free PDF download always available as alternative.
- **Reversibility**: Easy. Column Tax SDK is isolated to one integration module.

### D6: Skip Claude Code (2026-03-09)
- **Context**: Evaluated whether to add Claude Code ($20-100/mo) alongside Cursor.
- **Decision**: Skip. Cursor (current plan) is sufficient.
- **Rationale**: We're building a financial app with SSNs. Cursor's interactive review model is better for security-sensitive code than Claude Code's autonomous approach. Adding Claude Code is marginal benefit for $20-100/mo. Re-evaluate after MVP ships.
- **Reversibility**: Easy. Install anytime.

### D7: Skip Linear, Use GitHub Issues + Projects (2026-03-09)
- **Context**: Needed project management tooling.
- **Decision**: GitHub Issues + Projects for task tracking. Notion for knowledge base.
- **Alternatives**: Linear (free tier), Notion-only, TASKS.md-only.
- **Rationale**: GitHub Projects is free, already integrated, auto-updates with PRs, supports kanban boards and sub-issues. Adding Linear means another tool for a solo founder. TASKS.md stays as the authoritative spec; GitHub Issues becomes the live tracker.
- **Reversibility**: Easy. Linear has free tier, can migrate anytime.

### D8: Tiered OCR Architecture (2026-03-09)
- **Context**: Need reliable W-2 field extraction at minimum cost.
- **Decision**: Three-tier approach: (1) Cloud Vision + GPT-4o-mini ($0.002/doc), (2) GPT-4o vision fallback ($0.02/doc) for low confidence, (3) manual entry as last resort.
- **Rationale**: Tier 1 handles ~90% of docs at negligible cost. Tier 2 catches edge cases. Tier 3 ensures no user is blocked. Average blended cost stays near $0.004/doc.
- **Reversibility**: Easy. Tiers are independent modules.

### D9: Docker Compose DEV ONLY, Managed Services for Prod (2026-03-09)
- **Context**: Needed clear dev vs prod separation.
- **Decision**: Docker Compose for local dev (PostgreSQL, Redis, FastAPI, Next.js). Production uses Render native buildpack (render.yaml), Vercel git deploy, Neon, Upstash. No production Dockerfiles.
- **Rationale**: Managed services handle scaling, SSL, monitoring. Docker Compose provides consistent local dev. render.yaml gives infrastructure-as-code for prod without Docker complexity.

---

## Learnings

### L1: PaddleOCR Production Memory (2026-03-09)
PaddleOCR Docker docs recommend `--shm-size=8G`. Runtime memory usage ranges from 500MB to 20GB+ depending on document complexity. Version 3.0.x had memory leak issues fixed in 3.2. Not viable for a $7/mo 512MB instance.

### L2: Railway Reliability (2026-03-09)
Railway had 26 incidents in the last 30 days, 38 in last 90 days. Notable: Feb 11, 2026 — abuse detection system falsely terminated legitimate databases affecting 3% of services. Jan 28-29, 2026 — GitHub auth failures from uncached OAuth tokens. For a tax app during tax season, this is disqualifying.

### L3: Google Cloud Vision Privacy (2026-03-09)
For online (immediate) operations, images are processed in memory and NOT persisted to disk. Google does NOT use images for training. Does NOT share with third parties. Complies with Cloud Data Processing Addendum. Acceptable for W-2 images containing SSNs.

### L4: Google Document AI W-2 Parser Pricing (2026-03-09)
The specialized W-2 parser costs $0.30 per classified document — 176x more expensive than basic Cloud Vision OCR ($0.0017/doc including GPT). At 1K users, that's $300/mo vs $1.70/mo. Basic OCR + GPT-4o-mini structured output is the right tier for us.

### L5: Neon Free Tier Cold Starts (2026-03-09)
Free tier auto-suspends after 5 minutes of inactivity. Cold start latency: 300-800ms. During tax season (constant traffic), this is negligible. During off-season development, slightly annoying but not blocking. 104 max connections, 10GB storage on free tier.

### L6: GPT-4o-mini Structured Outputs (2026-03-09)
GPT-4o-mini achieves 100% schema adherence with Structured Outputs (`response_format: {type: "json_schema"}`). No post-processing needed. Ideal for mapping OCR text to W-2 Pydantic schema.

### L7: Google Cloud Vision Layout Preservation (2026-03-09)
`DOCUMENT_TEXT_DETECTION` returns hierarchical structure: Pages -> Blocks -> Paragraphs -> Words -> Symbols, each with bounding box coordinates. Sufficient spatial information for GPT to map text to W-2 fields.

### L8: Postiz v2.12+ Requires Temporal (2026-03-10)
Postiz switched from cron to Temporal for background job scheduling in v2.12.0. The `ghcr.io/gitroomhq/postiz-app:latest` image requires a Temporal server at port 7233. Without it, the backend fails to start: `Error: connect ECONNREFUSED ::1:7233`. Fix: add `temporalio/auto-setup:1.28.1` + its own `postgres:16-alpine` to Docker Compose, set `TEMPORAL_ADDRESS: temporal:7233` in Postiz env. Reference: https://docs.postiz.com/installation/docker-compose

---

## Patterns

### P1: SSN Isolation Pipeline
SSN is extracted via regex (`\d{3}-?\d{2}-?\d{4}`) from OCR raw output on our server. A masked placeholder (XXX-XX-XXXX) replaces it in all text sent to OpenAI. SSN is stored only in our encrypted database. This pattern is OCR-engine-agnostic — works with Cloud Vision, PaddleOCR, or any text source.

### P2: Tiered Service Architecture
For any ML/AI pipeline: start with the cheapest option, add more expensive fallbacks for edge cases. The majority of requests are handled cheaply; only exceptions escalate. Apply this pattern to OCR, AI insights, and future features.

### P3: Infrastructure-as-Code via render.yaml
All production infrastructure defined in `render.yaml` at repo root. Changes to infrastructure go through the same PR review process as code changes. No manual Render dashboard configuration.

---

## Open Questions

### Q1: Cloud Vision + GPT-4o-mini W-2 Accuracy (UNVALIDATED)
Google recommends their $0.30/doc Document AI W-2 Parser for tax forms. Our approach (basic Cloud Vision OCR + GPT-4o-mini field mapping) is 176x cheaper but has NOT been tested with real W-2 images. Validation plan: test with 20+ real W-2s during Sprint 2 (Task 1.2). If accuracy < 95%, increase GPT-4o vision fallback usage.

### Q2: Render Starter 512MB Under Load
FastAPI + deps need ~200-300MB. Under concurrent requests during tax season peak, memory usage may spike. Monitor during beta. Upgrade trigger: sustained >80% memory utilization.

### Q3: Column Tax SDK Availability and Pricing
Need to book demo call and negotiate pricing. Target: $10-15/return cost-passthrough. Sandbox access needed by September 2026 for October launch.

### Q4: Postiz MCP Reliability with Self-Hosted Instances
GitHub issues #846 and #984 report MCP connection failures (SSE handshake timeouts, 404s) on self-hosted Postiz. Community MCP package (`mcp-postiz-server`) is third-party maintained. Fallback: Postiz REST API works reliably. Test MCP first; use REST API if needed.

### Q5: Origin Financial — Competitive Threat Analysis (HIGH THREAT)
**Threat Level**: HIGH. Origin (useorigin.com) is a VC-backed all-in-one financial platform with ~100K users, SEC-registered investment advisor (RIA), and AI-powered tax filing via April Tax partnership. $12.99/mo subscription model. Features: budgeting, investing, tax filing, AI financial advisor, credit monitoring. Target demographic overlaps directly with FileFree (young professionals, 25-40).

**Why HIGH**: (1) SEC RIA registration gives them legal authority to provide personalized financial advice -- something FileFree cannot do without similar registration. (2) April Tax partnership (getapril.com) provides IRS-authorized e-file capability TODAY, not January 2027. (3) 100K user base proves willingness to pay for all-in-one financial management. (4) VC funding enables aggressive growth that bootstrapped Paperwork Labs cannot match dollar-for-dollar.

**Why NOT fatal**: (1) Origin charges $12.99/mo ($156/yr) -- FileFree is free forever. Price-sensitive Gen Z and young adults (our core demographic) won't pay $156/yr when free exists. (2) Origin has no LLC formation product -- LaunchFree is uncontested. (3) Origin's tax filing is a white-label (April Tax), not proprietary -- they don't control the filing engine. We will own ours (MeF transmitter). (4) No B2B play -- Distill is uncontested. (5) The "all-in-one" approach requires $12.99/mo subscription economics; our free-tier + marketplace model can reach 10x their volume.

**Strategic response**: Don't try to out-Origin Origin on the advisory/investment side. Own "free tax filing for young people" and "free LLC formation" as category-defining positions. Let Origin validate the "AI financial platform" market category while we capture the price-sensitive majority they can't serve profitably. Revisit SEC RIA registration at 100K+ users if advisory revenue justifies it.

### Q6: April Tax (getapril.com) as Column Tax Alternative
April Tax is an AI-native tax filing infrastructure provider. IRS-authorized e-file transmitter. Powers Origin's 100K-user tax filing (proving production readiness at scale). Offers embeddable tax filing API for platforms. Evaluate as potential Column Tax alternative for interim e-file partnership. Key questions: (1) API pricing vs Column Tax? (2) Embeddable SDK quality? (3) State coverage? (4) Do they accept bootstrapped partners or only VC-backed? Contact: getapril.com. This does NOT change the MeF transmitter north star (D4) -- April Tax would be an interim partner like Column Tax, replaced by our own transmitter in January 2027.

---

## Decisions (Continued)

### D10: Self-Host Postiz + n8n on Shared Hetzner VPS (2026-03-09)
- **Context**: Needed social media scheduling tool and automation engine for content workflows.
- **Decision**: Self-host both Postiz (social scheduling) and n8n (workflow automation) on one Hetzner CX33 VPS (8GB RAM, $7.50/mo). Separate databases, shared PostgreSQL + Redis.
- **Alternatives**: Postiz hosted ($29/mo) + separate n8n VPS ($7/mo) = $36/mo. Buffer free ($0) + no automation.
- **Rationale**: Both are Docker Compose apps needing the same deps. One server is simpler and saves $258/year vs hosted Postiz. n8n starts stopped and activates for Phase 2 autonomous workflows.
- **Reversibility**: Easy. Can migrate to hosted Postiz anytime. Can move n8n to separate server if memory constrained.

### D11: Skip Buffer, Postiz from Day One (2026-03-09)
- **Context**: Evaluated Buffer (free, 3 channels, 10 posts/channel) vs Postiz (open-source, 28+ platforms, API, MCP).
- **Decision**: Skip Buffer entirely. Postiz is the only social tool from day one.
- **Rationale**: Buffer free tier is too limiting (10 scheduled posts per channel). Postiz has REST API for programmatic scheduling, which enables n8n automation. No point in starting with a tool we'd outgrow in week 2.

### D12: Paid Amplification via TikTok Spark Ads + Meta Boost (2026-03-09)
- **Context**: $11.38 max CAC means paid acquisition must be surgical, not broad.
- **Decision**: $200-500/mo during tax season only (March-April). TikTok Spark Ads (boost organic winners, $3-10 CPM) + Meta/IG boost ($8-12 CPM). Intermittent bursts, not continuous daily ads.
- **Rationale**: Spark Ads boost your own posts and engagement persists permanently. Only boost content the algorithm already validated (>1K organic views). TikTok minimum $20/day means $200/mo covers ~10 days of targeted bursts. Off-season: $0 paid.

### D13: n8n as Persona Automation Layer (2026-03-09)
- **Context**: Cursor personas (.mdc files) are context files, not autonomous agents. They only work during interactive sessions.
- **Decision**: Use n8n workflows as the autonomous execution layer for personas. Same system prompts from .mdc files, but triggered by cron instead of human interaction.
- **Rationale**: No custom agent framework needed. n8n is visual, no-code, production-tested. Each workflow takes ~30 minutes to build. Total for 5 persona workflows: ~3 hours.

### D14: Revenue Model Pivot — Kill Monthly Subscription, Monetize the Refund Moment (2026-03-09)
- **Context**: Original revenue model centered on AI Tax Advisor at $9.99/month ($120/year). No evidence Gen Z pays monthly for a service used once a year. Mint Premium (similar positioning) achieved only ~2-3% conversion.
- **Decision**: Replace monthly subscription with refund-moment monetization (Credit Karma playbook). Primary revenue: refund routing to HYSA partners ($50-100/funded account via IRS Form 8888) + financial product referrals ($50-200/referral). Secondary: audit shield ($19-29/yr), Tax Optimization Plan ($29/yr annual purchase, NOT monthly), refund advance ($3-5 rev share). B2B API remains Phase 3.
- **Alternatives**: Keep $9.99/mo subscription (unvalidated), freemium with premium features (complex filing only), embedded banking/neobank (too complex for solo founder).
- **Rationale**: Credit Karma was acquired for $7.1B on the referral model alone. Marcus pays $50-100 per HYSA referral (public program). The refund moment is the highest-intent financial decision point of the year for a 22-year-old. Every revenue stream in the revised model has a direct comp that proves it works. Revised Scenario B ARPU: $8.05 (vs prior $10.16), but with higher confidence — every line item has market evidence.
- **Reversibility**: Easy. The Tax Optimization Plan can be re-priced or converted to monthly if validation shows demand. Refund routing partnerships can be added/removed independently.

### D15: Tax Optimization Plan at $29/year, Not $9.99/month (2026-03-09)
- **Context**: Needed to preserve the "advisory" revenue stream but reframe for realistic Gen Z purchasing behavior.
- **Decision**: Annual one-time purchase at $29/year during filing, not a $9.99/month recurring subscription.
- **Rationale**: Tax advice is seasonal — users don't think about taxes May-December. Monthly subscriptions for annual-use products have high churn. $29/year is less than the cost of one TurboTax filing, anchored to the filing moment when willingness to pay is highest. If the W-4 adjustment alone saves $200/year, the ROI is obvious.

### D16: Co-Founder Structure — Product/Eng + Partnerships/Revenue (2026-03-09)
- **Context**: Solo founder risk was the #1 strategic risk (CRITICAL severity). Partnership-dependent revenue streams (refund routing + financial referrals) account for 77% of Scenario B revenue but require dedicated relationship management that a solo engineer would struggle to execute.
- **Decision**: Two co-founder structure. Founder 1 owns product, engineering, infrastructure, tax calculations, OCR pipeline, content creation, and IRS certification. Founder 2 (FAANG partnerships background) owns partner outreach, deal negotiation, and revenue stream activation on an outcome-driven basis, supported by AI persona (partnerships.mdc).
- **Alternatives**: Solo founder + hire later, solo founder + contractor for BD, single founder doing everything.
- **Rationale**: The delta between Scenario A (no partnerships, $438K) and Scenario B (partnerships in place, $805K) is $367K at 100K users. Having a dedicated partnerships person with enterprise deal experience directly addresses the most fragile revenue assumption (refund routing attach rate) and reduces the solo founder burnout risk from CRITICAL to HIGH. Her FAANG experience means she knows how enterprise partnership agreements, rev-share negotiations, and compliance work.
- **Reversibility**: Easy. Roles are cleanly separated. Either founder can operate independently if needed.

### D17: Tiered Partnership Strategy — Affiliate First, Direct Deals at Scale (2026-03-09)
- **Context**: Partnership revenue requires signed agreements with financial product companies (HYSA, investment, lending, insurance). Cold outreach to enterprise partners pre-product is low-probability. Need a pragmatic path from zero to revenue.
- **Decision**: Four-phase tiered approach. Phase 1 (NOW): affiliate network applications (self-serve, $50-100/funded). Phase 2 (500+ users): activate affiliate links, track conversion. Phase 3 (5K+ users): upgrade to direct partnerships ($100-200+/funded, 2-3x affiliate rates). Phase 4 (10K+): expand to lending, insurance, credit, B2B API.
- **Alternatives**: Cold outreach to direct partnerships immediately (low probability pre-product), skip partnerships and rely on Tax Optimization Plan revenue only (leaves $367K/yr on the table), hire a BD agency (expensive, misaligned incentives).
- **Rationale**: Affiliate programs (Marcus via Impact, Wealthfront via Impact, Betterment via CJ) accept applications without a live product. This lets us have revenue infrastructure ready at launch. Direct partnerships require volume proof — moving to Phase 3 at 5K+ users gives us conversion data to negotiate 2-3x higher payouts.
- **Reversibility**: Easy. Each phase is independent. Can skip phases or stay at affiliate level indefinitely.

### D18: Docker Dev Environment — Task 0.1 Complete (2026-03-09)
- **Context**: Repo was entirely documentation — no code, no dev environment. Needed to create the complete local development stack as the foundation for all subsequent engineering tasks.
- **Decision**: Docker Compose with 4 services (PostgreSQL 15, Redis 7, FastAPI backend, Next.js frontend). Makefile with 17 commands. Separate Dockerfiles for dev (Docker Compose) vs production (Render native buildpack via render.yaml). Health checks on all services with dependency ordering.
- **Alternatives**: Dev containers (VS Code), local-only (no Docker), Nix flakes. Docker Compose chosen for team portability and parity with production services.
- **Key files created**: `infra/compose.dev.yaml`, `Makefile`, `api/Dockerfile`, `web/Dockerfile.dev`, `api/requirements.txt`, `api/app/main.py` (health endpoint), `web/package.json`, `pyproject.toml` (ruff + mypy), `render.yaml` (production IaC), `infra/env.dev.example`, `.python-version`, `.node-version`, `.gitignore`.
- **Reversibility**: Easy. All infrastructure as code, no state outside Docker volumes.

### D19: Project Structure Cleanup (2026-03-09)
- **Context**: Initial scaffolding used verbose directory names (`filefree-api/`, `filefree-web/`), scattered env files, docs cluttering the root, and a premature OCR validation script. User wanted a cleaner structure inspired by their AXIOMFOLIO project.
- **Decision**: Renamed `filefree-api/` → `api/`, `filefree-web/` → `web/`. Created `infra/` folder for compose + env files (per-environment: `env.dev.example`, `env.prod.example`). Created `docs/` folder for all strategy/product documents. Deleted premature `scripts/validate_ocr.py`. Consolidated env files into single `infra/env.dev.example`. Confirmed monorepo as correct architecture for solo founder + AI agents.
- **Alternatives**: Separate repos (rejected — AI agents need full context), `backend/`+`frontend/` naming (user chose `api/`+`web/`), keep docs at root (user chose `docs/` for cleaner root).
- **Reversibility**: Easy. Just file moves and renames.

### D20: Multi-Persona Review + Ops Stack + Render MCP (2026-03-09)
- **Context**: Before writing application code, ran a self-review using all 12 AI personas to validate groundwork. Also needed to provision the Hetzner ops stack (Postiz + n8n) and integrate Render MCP for deployment automation.
- **Decision**: (1) Fixed stale doc paths across 4 persona files (strategy.mdc, partnerships.mdc, workflows.mdc, cfo.mdc) — all `KNOWLEDGE.md`/`TASKS.md` references updated to `docs/` prefix. (2) Updated Hetzner CX33 pricing from $7.50 to EUR 5.49/mo across docs and persona files. (3) Created `infra/hetzner/` with Docker Compose (Postiz + n8n + PostgreSQL + Redis), env template, bootstrap script, and README. (4) Made CORS origins configurable via `FRONTEND_URL` env var. (5) Fixed Makefile to use `docker compose run --rm` instead of `exec` for cold-start compatibility. (6) Mounted `pyproject.toml` into API container for linter config access. (7) Replaced root `TASKS.md` duplicate with redirect to `docs/TASKS.md`. (8) Added guard messages for unscaffolded Makefile targets (migrate, seed). (9) Integrated Render MCP (24 tools) for programmatic deployment management — create services, set env vars, monitor deploys/logs/metrics without dashboard.
- **Alternatives**: Manual Render dashboard (rejected — MCP enables AI-driven deployment). Skip Hetzner until post-MVP (rejected — content/social ops need to start immediately for audience building).
- **Reversibility**: Easy. All changes are config/docs. Hetzner stack is fully containerized.

### D21: Production Infrastructure Complete (2026-03-09)
- **Context**: All foundational infrastructure needed before application development is now provisioned and verified. This closes out Sprint 0 infrastructure tasks.
- **Decision**: Full production stack deployed and verified:
  - **Vercel** (frontend): filefree.tax + www.filefree.tax live (Valid Configuration, auto-deploy from `main`). Hobby tier.
  - **Render** (API): filefree-api live at api.filefree.tax. Custom domain verified, TLS certificate issued. Starter plan ($7/mo). Auto-deploy from `main`. DATABASE_URL wired to Neon with auto-normalization (postgresql:// -> postgresql+asyncpg://, sslmode -> ssl, channel_binding stripped). Alembic migrations run automatically on startup.
  - **Neon** (database): `filefree` project created (Postgres 17, AWS US East 1). Connection pooling enabled via pgbouncer. Connection string set on Render as `DATABASE_URL` with `postgresql+asyncpg://` prefix for SQLAlchemy async compatibility.
  - **Hetzner** (ops VPS): CX33 server `filefree-ops` running at 204.168.147.100. Fully bootstrapped: Docker, Caddy (reverse proxy + auto TLS), UFW firewall. Services running: PostgreSQL (healthy), Redis (healthy), n8n (https://n8n.filefree.tax), Postiz (https://social.filefree.tax).
  - **DNS** (Spaceship): 6 records configured for filefree.tax — A record (Vercel), CNAME www (Vercel), CNAME api (Render), A records for n8n/social/ops (Hetzner). Updated to Vercel's recommended project-specific values.
  - **MCP integrations**: Render (24 tools — deploy, env vars, logs, metrics), Notion (workspace management), GitHub, Context7 (library docs).
- **Cleanup**: Removed empty placeholder directories `api/alembic/` and `api/tax-data/` — will be scaffolded when needed in Sprint 1 (Alembic) and Sprint 2 (tax data).
- **What's next**: Sprint 1 coding (Task 0.2 frontend foundation, Task 0.3 backend foundation, Task 0.4 landing page). Parallel: Hetzner bootstrap, EFIN application, affiliate applications, legal drafts.
- **Reversibility**: N/A — this is a milestone, not a reversible decision.

### D22 — Auth Architecture: Google One-Tap + Apple + Email/Password (2026-03-09)
- **Decision**: Authentication strategy uses Google One-Tap (~60%), Apple Sign In (~25%), and email/password (~15%). TikTok Login rejected (no email returned, regulatory risk). FastAPI owns all auth — validates social tokens server-side, creates Redis sessions, sets HTTP-only cookies.
- **Alternatives considered**: Auth.js/NextAuth (rejected: session management must be server-side for CCPA deletion, security audits, revocation), TikTok Login (rejected: no email, privacy concerns), Firebase Auth (rejected: vendor lock-in, less control).
- **Impact**: User model includes `auth_provider`, `auth_provider_id`, `email_verified` fields and nullable `password_hash`. Config includes Google/Apple OAuth vars (empty = disabled in dev). Actual OAuth endpoints are Task 2.1.
- **Reversibility**: Low cost to add more providers later; the `auth_provider` enum is extensible.

### D23 — Sprint 1 Complete + Gen Z Branding Removed (2026-03-09)
- **Context**: Sprint 1 foundation work complete. Full persona review (12 personas) identified 7 doc inconsistencies and a branding issue. All fixed.
- **What shipped**:
  - Frontend design system: Tailwind v4, 22 shadcn components, Inter + JetBrains Mono fonts, dark indigo/violet theme, attribution UTM capture, Framer Motion presets, axios API client with response envelope interceptor
  - Backend foundation: 7 SQLAlchemy models (User, Filing, Document, TaxProfile, TaxCalculation, Submission, Waitlist) with cascade deletes, BaseRepository + WaitlistService, response envelope, AES-256 encryption, PII scrubber, correlation ID middleware, SlowAPI rate limiter, 16 passing tests
  - Alembic configured for async migrations. Neon DB connected + migrated. Auto-migration on startup via lifespan handler.
  - 2025 tax data (Rev. Proc. 2024-40, P.L. 119-21)
  - Hetzner ops stack fully bootstrapped: Docker, Caddy, n8n (live at n8n.filefree.tax), Postiz (live at social.filefree.tax)
- **Branding change**: Removed "Gen Z" from all user-facing copy (README, layout metadata, page content, API description). Product leads with benefits ("Free AI-powered tax filing"), not demographic labels. Internal strategy docs retain the demographic insight where analytically relevant.
- **Monthly burn**: $12.49/mo (Hetzner VPS $5.49 + Render Starter $7). Vercel Hobby (free), Neon free tier, Upstash free tier.
- **Inconsistencies fixed**: TASKS.md (Temporal reference, separate DBs, docker-compose.yml path, Gen Z FAQ), .cursorrules + engineering.mdc (Vercel tier Hobby not Pro), env.prod.example (missing auth vars), KNOWLEDGE.md D21 (Hetzner bootstrapped).
- **Reversibility**: N/A — milestone.

### D24 — PostHog Analytics Foundation (2026-03-10)
- **Context**: Need attribution and event tracking before landing page goes live. Can't measure what we don't track.
- **Decision**: Integrated PostHog (`posthog-js`) with PII scrubbing (SSN + email patterns stripped from all events). PostHogProvider wraps the app, tracks page views on route changes. UTM parameters from `attribution.ts` registered as super properties. Key events wired: `waitlist_signup`, `waitlist_signup_error`. PostHog project API key set in `web/.env.production`.
- **Key files**: `web/src/lib/posthog.ts` (init + scrub + track), `web/src/components/posthog-provider.tsx`, `web/src/components/providers.tsx` (wraps app).
- **Sentry**: Not yet integrated (Task 0.5 remaining work).
- **Reversibility**: Easy. PostHog is a standalone analytics provider, no app logic depends on it.

### D25 — Legal Pages Live (2026-03-10)
- **Context**: Landing page needs privacy policy and terms of service linked in footer before going live.
- **Decision**: Created `/privacy` and `/terms` pages using the `legal.mdc` persona. Privacy policy discloses AI processing (Cloud Vision, OpenAI), SSN isolation, data deletion rights, no data selling, CCPA/GDPR compliance. Terms cover "tax education not tax advice" (Circular 230), free pricing, e-file partner disclosure.
- **Key files**: `web/src/app/privacy/page.tsx`, `web/src/app/terms/page.tsx`.
- **Reversibility**: Easy. Pages can be updated independently. Should be reviewed by actual legal counsel before January 2027 launch.

### D26 — Agent Autonomy: n8n Workflows Wired (2026-03-10)
- **Context**: 6 n8n persona workflows were imported but had no output destinations — they generated AI content but didn't save it anywhere.
- **Decision**: Added Notion/GitHub output nodes to all 6 workflows. Social Content Generator, Growth Content Writer, Weekly Strategy Check-in, Partnership Outreach Drafter, CPA Tax Review all output to Notion databases. QA Security Scan outputs to GitHub Issues. All credentials configured in n8n UI (OpenAI, Notion API key, GitHub PAT). Workflow JSONs updated in `infra/hetzner/workflows/`.
- **Postiz v2.12+ Temporal requirement**: Postiz updated from cron-based to Temporal-based job scheduling. Added `temporal` (auto-setup:1.28.1) + `temporal-db` (postgres:16-alpine) services to Hetzner compose. Also fixed Caddy reverse proxy port (was 4200, Postiz runs on 5000).
- **Reversibility**: Easy. Workflows are independent, credentials can be rotated.

### D27 — TASKS.md v8: Checkbox Overhaul + Docs Consistency (2026-03-10)
- **Context**: TASKS.md used `~~strikethrough~~` for completed items, which doesn't render as visual checkboxes in many markdown viewers. User couldn't track progress.
- **Decision**: Replaced all `~~strikethrough~~` with `[x]` checkboxes. Added `[ ]` checkboxes to all uncompleted items in active tasks. Added sprint progress summaries (`> Progress: X/Y complete`) at the top of each sprint section. Deleted root `TASKS.md` (was a 3-line redirect to `docs/TASKS.md`). Fixed stale cost/pricing references across `docs/PRD.md`, `docs/STRATEGY_REPORT.md`, `docs/PARTNERSHIPS.md` (Vercel Hobby free, total burn $12.49/mo). Updated 6 persona `.mdc` files for consistency.
- **Reversibility**: N/A — documentation improvement.

### D28 — Temporal Visibility: PostgreSQL to Elasticsearch (2026-03-10)
- **Context**: Postiz returned 502 Bad Gateway. Root cause: Temporal v1.28.1 has a hardcoded limit of 3 Text search attributes in its SQL (PostgreSQL) visibility backend. Postiz v2.12+ registers 4+ custom search attributes, exceeding the limit and crashing Temporal, which cascaded to Postiz.
- **Decision**: Switched Temporal's visibility store from PostgreSQL to Elasticsearch 7.17.27. Added `temporal-elasticsearch` service to `infra/hetzner/compose.yaml` (256MB JVM heap, single-node). Set `ENABLE_ES=true`, `ES_SEEDS=temporal-elasticsearch`, `ES_VERSION=v7` on Temporal. Recreated Temporal databases for clean ES setup.
- **Alternatives**: Patch Temporal dynamic config (failed — hardcoded in binary), downgrade Postiz (no cron-based versions available), use Temporal Cloud ($200/mo — overkill).
- **Rationale**: Elasticsearch has no search attribute limits. 256MB heap fits within Hetzner CX33's 8GB RAM alongside all other services.
- **Reversibility**: Moderate. Would require re-creating Temporal databases to switch back to SQL visibility.

### D29 — Brand Assets Removed (2026-03-10)
- **Context**: AI-generated logo assets (wordmark, monogram, avatar, OG image) were rejected as low quality.
- **Decision**: Deleted all AI-generated brand images from `web/public/brand/` and `web/public/filefree-og.png`. Updated `brand.mdc` to mark logo assets as pending. Favicon SVG retained (text-based, acceptable quality).
- **Next**: Generate wordmark via Ideogram v3 with refined prompt. Generate monogram via Figma/Canva.
- **Reversibility**: Easy. New assets drop into the same paths.

### D30 — Postiz MCP Activated (2026-03-10)
- **Context**: Postiz was running but not connected to Cursor for AI-assisted social media management.
- **Decision**: Generated Postiz API key via UI, configured `mcp-postiz-server` in `.cursor/mcp.json` with API URL pointing to `https://social.filefree.tax/api/public/v1`.
- **Note**: API key stored only in local `.cursor/mcp.json` (gitignored). Also needs to be added as n8n credential for workflow automation.
- **Reversibility**: Easy. Rotate key in Postiz UI.

### D32 — Frontend Auth + Protected Routes (2026-03-10)
- **Context**: Backend auth API was complete (Task 2.1, PR #9) but no frontend UI existed. Users couldn't register, login, or access protected routes.
- **Decision**: Built full frontend auth system: Zustand auth store, React Query hooks, register/login pages with Zod validation, Next.js middleware for route protection, 30-min idle timeout with "Still there?" dialog. Also fixed SQLAlchemy enum value mismatch across all models (values_callable for lowercase enum persistence), added csrf_token to /me endpoint for session restoration, added global nav with Sign In/Sign Up buttons, replaced waitlist hero with "Get Started Free" CTA.
- **Alternatives considered**: Server-side auth via NextAuth.js — rejected because our backend already handles sessions via Redis cookies; adding NextAuth would duplicate auth state and add complexity.
- **Impact**: Auth flow is fully functional end-to-end. Protected routes (/file/*, /dashboard/*) redirect to login. Landing page now directs to registration.
- **PRs**: #10 (auth), nav+CTA polish on feat/2.2-nav-polish branch.

### D33 — Sprint 3 Complete + OAuth + Demo Refund Estimate (2026-03-11)
- **Context**: Sprint 3 (Full MVP) shipped in PRs #10-#12. All 7 tasks complete: backend auth, frontend auth, filing flow, tax calculator, return summary, component library, CI/analytics. OAuth (Google/Apple Sign In) added via PR #12 with server-side token verification, account linking, and frontend SDK integration.
- **What shipped**:
  - Full filing flow: W-2 upload -> data confirmation -> filing status selection -> tax summary with animated refund
  - Tax calculator engine: integer cents, 4 filing statuses, 7 federal brackets (2025 rates, Rev. Proc. 2024-40 + P.L. 119-21), 100% test coverage
  - Google Sign In + Apple Sign In: server-side token verification (`google-auth`, `python-jose` for Apple JWKS), social login endpoints, account linking (same-email local+social), frontend SDK components
  - Frontend test infrastructure: Vitest + React Testing Library + happy-dom, 38 tests
  - GitHub Actions CI: 7 jobs (API Lint, API Tests, Web Lint, Web Tests, Web Build, Vercel, Vercel Preview)
  - Demo improvements: blur threshold lowered (30->15), softer info toast, blur score tracked in PostHog for calibration, client-side tax estimator shows estimated refund/owed with animated CurrencyDisplay before signup
  - Component library: SSNInput (masked, toggle visibility), CurrencyDisplay (count-up animation), SecureBadge, SkeletonCard
- **Total tests**: 89 backend + 38 frontend = 127 across 10 test files
- **PRs**: #10 (frontend auth), #11 (Sprint 3 tasks 2.3-2.7), #12 (OAuth social login)
- **Monthly burn**: $12.49/mo (unchanged)
- **Reversibility**: N/A — milestone.

### D31 — n8n Database Isolation (2026-03-10)
- **Context**: n8n and Postiz shared the same PostgreSQL database (`filefree_ops` / `ops`). When Postiz was recreated (to add MAIN_URL + ES visibility), its Prisma migrations dropped/overwrote n8n's tables. n8n logged `relation "public.user" does not exist` repeatedly.
- **Decision**: Created a separate `n8n` database on the existing PostgreSQL instance. Updated `infra/hetzner/compose.yaml`: `DB_POSTGRESDB_DATABASE: n8n` (was `${POSTGRES_DB:-ops}`). Restarted n8n — migrations ran cleanly on the fresh database.
- **Impact**: n8n requires re-setup: owner account registration, workflow re-import (6 JSONs in `infra/hetzner/workflows/`), credential re-configuration (OpenAI, Notion, GitHub).
- **Reversibility**: Easy. Point n8n back to shared DB if needed (not recommended).

### D34 — Centralized Config System + Credential Safety (2026-03-08)
- **Context**: Frontend had 14 raw `process.env` reads scattered across 10 files with no validation. `web/.env.production` was tracked in git with the PostHog API key committed. No secrets scanner existed. n8n had zero workflows after D31 database isolation.
- **Decision**: Built a company-wide credential management system:
  1. **Zod-validated config modules**: `server-config.ts` (server-only: N8N_API_KEY, GITHUB_TOKEN) and `client-config.ts` (client: apiUrl, posthogKey, googleClientId, etc.) replace all scattered `process.env` reads. Mirrors backend's Pydantic BaseSettings pattern.
  2. **Credential registry**: `docs/CREDENTIALS.md` maps every credential across all systems (29 credentials, 7 categories) to purpose, location, rotation policy, and owner. QA audits against this document.
  3. **Env file fix**: Moved PostHog key from tracked `.env.production` to gitignored `.env.local`. Tracked env files now contain only non-secret defaults.
  4. **Gitleaks in CI**: `gitleaks/gitleaks-action@v2` runs on every PR, blocks merge if secrets detected. `.gitleaksignore` suppresses historical PostHog key.
  5. **n8n workflows re-imported**: All 6 persona workflows imported via REST API (inactive, pending credential setup in n8n UI).
  6. **Shared types**: `web/src/types/ops.ts` eliminates type duplication between ops route and page.
- **Alternatives**: Vault/SSM (overkill for current scale), no validation (status quo, fragile), per-file validation (too scattered).
- **Impact**: Single source of truth for every `process.env` read. New credentials must be added to `CREDENTIALS.md` before merge. CI catches accidental secret commits. Backend config unchanged (already solid with Pydantic).
- **PR**: #14
- **Reversibility**: Easy. Config modules are drop-in wrappers — can revert to raw `process.env` reads if needed.

### D35 — Venture Master Plan v1 (2026-03-12)
- **Context**: Multi-product venture strategy finalized after 5 plan iterations and 2 deep research sessions.
- **Decision**: Single authoritative master plan covering FileFree, LaunchFree, Trinkets, and command center. pnpm workspace monorepo. Federated identity. 50-state AI data pipeline. Faceless social pipeline. 30+ AI agents.
- **Alternatives**: Separate repos (rejected: 70% frontend sharing), Turborepo (rejected: overkill for <5 apps), Series LLC (rejected: limited precedent).
- **Reversibility**: Major architectural decision — reversing monorepo would be expensive.

### D36 — Company Structure: Single LLC + DBAs (2026-03-12) — SUPERSEDED by D54
- **Context**: Evaluated single LLC, holding company + subsidiaries, and Series LLC.
- **Original Decision**: Single Wyoming LLC ($103 filing fee). **SUPERSEDED**: See D54 -- decided Paperwork Labs LLC in California instead. Wyoming rejected because founder is a CA resident (would require foreign registration, double RA fees, and CA franchise tax anyway).
- **Alternatives**: Personal name LLC (rejected: signals "small operation"), Series LLC (rejected: limited legal precedent).
- **Reversibility**: Easy to convert to holding company later.

### D37 — Domain Strategy: .ai Brand Family (2026-03-12)
- **Context**: Needed unified brand presence across products.
- **Decision**: Purchased launchfree.ai + filefree.ai (March 2026, ~$440 for 2-year reg). Migrate filefree.tax to filefree.ai. Pattern: [product]free.ai.
- **Alternatives**: Keep .tax (rejected: .ai signals AI differentiator), .com (rejected: filefree.com is Intuit's).
- **Reversibility**: Permanent redirect from .tax preserves old links.

### D38 — Trinkets Product Line + Agent Pipeline (2026-03-12)
- **Context**: Wanted to test AI agent infrastructure end-to-end while generating passive revenue.
- **Decision**: "Trinkets" = collection of client-side utility tools (financial calculators first). 3-stage Trinket Factory agent pipeline: GPT-5.4 Discovery -> Claude Sonnet PRD -> Claude Sonnet Build. Phase 1.5 in execution plan.
- **Alternatives**: Manual tool selection (rejected: doesn't test agent pipeline), full SaaS tools (rejected: too complex for testing purposes).
- **Reversibility**: Low-cost experiment, easy to abandon.

### D39 — AI Model Routing Strategy: 9 Models, 7 Roles (2026-03-12)
- **Context**: Multiple AI models available with varying cost/quality tradeoffs. Needed systematic assignment.
- **Decision**: 9-model routing strategy owned by AI Ops Lead persona. Decision tree prioritizes cheapest model that achieves required quality. Gemini 2.5 Flash as default workhorse. Claude Sonnet for code/compliance. GPT-4o for creative. See Section 0E of master plan.
- **Alternatives**: Single model for everything (rejected: wasteful), ad-hoc selection (rejected: inconsistent costs).
- **Reversibility**: Easy — swap models in n8n workflow nodes.

### D40 — AI Operations Lead Persona (2026-03-12)
- **Context**: Model routing decisions were ad-hoc across different conversations.
- **Decision**: Created `agent-ops.mdc` persona that owns all model routing, cost monitoring, persona audits, and new model evaluation. Has final say on model assignments — engineering implements but doesn't choose.
- **Alternatives**: Engineering chooses models (rejected: no cost accountability), single model policy (rejected: too rigid).
- **Reversibility**: Persona file is just a .mdc — easy to modify or remove.

### D41 — RA Pricing Strategy: Wholesale Volume Tiers (2026-03-12)
- **Context**: Initial RA pricing assumed $125/yr wholesale from Northwest RA. Research showed this was only for Wyoming; nationwide wholesale pricing varies significantly.
- **Decision**: Partner RA with CorpNet volume pricing. Charge $99/yr initially (cheaper than ZenBusiness $199, LegalZoom $299). Drop to $79/yr at 500+ users, $49/yr at 1,000+ users. DIY RA deferred indefinitely.
- **Alternatives**: DIY RA (rejected: requires 50-state physical addresses + E&O insurance), flat $49/yr from day 1 (rejected: not profitable until 1,000+ volume).
- **Reversibility**: Can switch RA partners or adjust pricing at any time.

### D42 — Agent Org Chart: Full Company from Day One (2026-03-12)
- **Context**: Stress test recommended right-sizing agents from 43 to 20. Founder pushed back -- agents are employees and the company structure should be complete.
- **Decision**: All 44 agents (24 Cursor personas + 20 n8n workflows) defined in a hierarchical org chart from day one. Agents have Active/Standby/Planned status. Standby = system prompt ready but not deployed. Full governance protocol: multi-agent consensus with APPROVE/CONCERN/BLOCK verdicts and escalation to parent nodes.
- **Alternatives**: Right-size to 20 with build triggers (rejected: doesn't model a real company), flat structure with no governance (rejected: no checks and balances).
- **Reversibility**: Can always defer/shelve Planned agents. Governance protocol is process, not infrastructure.

### D43 — FileFree Form Coverage: All 50 States + Major Schedules at Launch (2026-03-12)
- **Context**: Previous plan suggested launching with top 10-15 states. Founder insisted on all 50.
- **Decision**: January 2027 launch covers 1040 + Schedule 1 + B + C + 1099-NEC/INT/DIV + dependents + ALL 50 state returns. Mid-season (Feb 2027) adds Schedule A + D. Year 2 adds E, SE, HSA, K-1. Data-driven state engine makes marginal effort per state minimal.
- **Alternatives**: Top 10 states only (rejected: marginal effort delta not worth it), simple returns only (rejected: limits TAM significantly).
- **Reversibility**: Can always delay specific schedules if MeF testing scope is too large.

### D44 — Quality-First AI Model Philosophy (2026-03-12)
- **Context**: Original routing principle was "cheapest model that works." Founder prefers quality over cost.
- **Decision**: Use the BEST model for the task. Only downgrade when cheaper model produces EQUIVALENT quality, not just "good enough." GPT-5 should be evaluated immediately upon release.
- **Alternatives**: Cost-first routing (rejected: founder willing to pay for quality), single premium model for everything (rejected: wasteful for bulk extraction).
- **Reversibility**: Cost philosophy is a guideline, easily adjusted.

### D45 — Founder 2 Framing: Outcome-Driven (2026-03-12)
- **Context**: Plan specified "2-3 hrs/wk" for Founder 2. This felt prescriptive and limiting.
- **Decision**: Removed all time-commitment references. Founder 2 is framed as "outcome-driven, flexible commitment" -- AI handles all prep, Founder 2 does what requires a human (calls, emails, negotiations).
- **Alternatives**: Keep time specification (rejected: unnecessarily constraining).
- **Reversibility**: Can always add time expectations back if needed.

### D46 — AI Branding: Lead with Outcomes, Not Technology (2026-03-12)
- **Context**: Question of whether promoting "AI-powered" helps or hurts trust in financial services.
- **Decision**: Lead with outcomes ("free, 5 minutes, accurate"), not "AI-powered." Mention AI when it explains WHY something is free/fast, but never as headline value prop. Competitors (Credit Karma, FreeTaxUSA) barely mention AI -- users care about results.
- **Alternatives**: AI-forward branding (rejected: research shows it hurts trust for advice/judgment), hide AI entirely (rejected: misses speed/cost explanation opportunity).
- **Reversibility**: Easy to adjust messaging emphasis.

### D47 — Slack as Agent Communication Hub (2026-03-12)
- **Context**: Agents need persistent two-way communication with founder beyond ephemeral Cursor chat.
- **Decision**: Slack as central company hub with 10 functional channels. n8n posts agent output to channels. Founder can reply/command in channels. Professional email aliases on Google Workspace (filefree.ai, launchfree.ai, distill.tax, paperworklabs.com) route to founder inbox.
- **Alternatives**: Discord (rejected: already have Slack workspace), Notion comments (rejected: wife can't use it easily), custom dashboard (rejected: unnecessary build).
- **Reversibility**: Channel structure is config, easy to reorganize.

### D48 — Side Projects Evaluation (2026-03-12)
- **Context**: Founder has 4 side projects (axiomfolio, replyrunner, jointly, fittingroom) that needed evaluation.
- **Decision**: ReplyRunner and FittingRoom are NO-GO (low alignment, crowded/complex markets). Axiomfolio and Jointly are DEFER to Year 2+ (good alignment but require Plaid integration costs that aren't viable pre-revenue). Full analysis in docs/FOUNDER_SIDE_PROJECTS.md.
- **Alternatives**: Build one alongside main products (rejected: context-switching risk), abandon all (rejected: axiomfolio and jointly have genuine venture alignment).
- **Reversibility**: Can revisit deferred projects anytime when revenue supports Plaid costs.

### D49 — MeF Local Validation Engine: Zero-Risk ATS Strategy (2026-03-12)
- **Context**: Concern that testing 50 state MeF schemas in one ATS window may not be feasible.
- **Decision**: Build a local XML validation engine BEFORE submitting to ATS. IRS publishes all schemas (irs.gov/downloads/irs-schema). State schemas from E-Standards (statemef.com). ATS only requires ~13 test scenarios for 1040. State returns piggyback on federal submission (not 50 separate tests). Local validation achieves 100% pass rate before ATS submission. CA FTB and MA DOR (independent systems) use Column Tax as e-file partner in Year 1 only.
- **Alternatives**: Submit to ATS blind and iterate (rejected: wastes testing window cycles), federal-only in Year 1 (rejected: unnecessary since piggyback makes states trivial).
- **Reversibility**: Pipeline is additive. Can always fall back to Column Tax for any state.

### D50 — Plan B Revenue Upgrade: Self-Serve Affiliates (2026-03-12)
- **Context**: Original Plan B ($3.5K-19K) assumed HYSA referrals require partnerships. Research shows most fintech affiliate programs (Betterment, SoFi, Wealthfront, Ally, Robinhood, Chime, Acorns) are self-serve applications on Impact.com and CJ Affiliate.
- **Decision**: Revised Plan B to $6.5K-37K. Founder 1 applies to all self-serve programs in Phase 0 (one afternoon of form fills). Founder 2 raises revenue ceiling with premium terms but doesn't set the floor.
- **Alternatives**: Wait for Founder 2 (rejected: unnecessary delay for self-serve programs), skip affiliates entirely (rejected: leaving money on the table).
- **Reversibility**: Can add/remove affiliate programs at any time.

### D51 — Tiered State Tax Engine Architecture (2026-03-12)
- **Context**: 50-state tax calculations vary from trivial (flat % of federal income) to complex (CA has ~40 modification items).
- **Decision**: Three-tier engine. Tier 1 (~30 conforming states): JSON config only. Tier 2 (~12 semi-conforming): config + modifier functions. Tier 3 (~5 independent: CA, NJ, PA, MA, NH): custom calculation modules. Budget 2 extra weeks in Phase 7 for Tier 3.
- **Alternatives**: Single engine for all states (rejected: CA/NJ complexity can't fit in JSON config), custom module per state (rejected: massive over-engineering for conforming states).
- **Reversibility**: Can always add more states to Tier 3 if JSON config proves insufficient.

### D52 — Doc Hygiene: Anti-Bloat Rules (2026-03-12)
- **Context**: 15 docs / 8,773 lines total. Master plan at 3,000+ lines. Risk of docs becoming unreadable.
- **Decision**: Anti-bloat rules in Section 8: collapse completed phases to one-line summaries, rotate KNOWLEDGE.md every 6 months, archive superseded docs. Moved STRATEGY_REPORT.md, UTILITY_SITES_STRATEGY.md, SOCIAL_ROADMAP.md to docs/archive/. Master plan target: under 3,500 lines.
- **Alternatives**: Split master plan into multiple docs (rejected: loses single source of truth), no archival (rejected: docs grow indefinitely).
- **Reversibility**: Can always restore archived docs from git history.

### D53 — Alert Routing: Slack Not Discord (2026-03-12)
- **Context**: Section 7B routed alerts to Discord. Section 14 established Slack as the company hub. Inconsistency.
- **Decision**: All alerts route through Slack #ops-alerts. Discord references removed. Consistent with Section 14 Slack hub architecture.
- **Alternatives**: Keep both Slack and Discord (rejected: unnecessary tool sprawl), use Discord only (rejected: Slack is already the company hub).
- **Reversibility**: Channel routing is n8n config, trivial to change.

### D54 — LLC Name: Paperwork Labs LLC (2026-03-12)
- **Context**: Naming research across multiple sessions. Toast-themed names rejected (Toast Inc. litigation risk). Butterside Labs rejected ("butters" slang). Founder discovered paperworklabs.com available.
- **Decision**: Register as "Paperwork Labs LLC" in California. Domain: paperworklabs.com (purchased). Thematic fit: both products eliminate paperwork. "Labs" differentiates from Canadian "Paperwork Forms" company and follows tech holding company convention. Zero trademark risk in our classes.
- **Alternatives**: Paperwork LLC (no "Labs" -- Canadian company overlap), Toastworks LLC (Toast Inc. risk), Crisp Labs LLC (less thematic fit), Sharma Ventures LLC (personal name signals small operation).
- **Reversibility**: LLC name is permanent but can be amended (~$30 CA filing fee). Domain is just DNS.

### D55 — Command Center: paperworklabs.com (2026-03-12)
- **Context**: Command center was on sankalpsharma.com. With Paperwork Labs as the holding company, the admin dashboard should live on company infrastructure, not the founder's personal domain.
- **Decision**: Move command center (apps/studio) to paperworklabs.com. sankalpsharma.com becomes the founder's personal portfolio/blog site. Cleaner separation: company ops on company domain, personal brand on personal domain.
- **Alternatives**: Keep on sankalpsharma.com (rejected: mixing personal and company, awkward for Olga's admin access and future team/investors).
- **Reversibility**: DNS change, trivial.

### D56 — Auth Architecture: Admin Allowlist (2026-03-12)
- **Context**: Need admin access for two founders (Sankalp + Olga) across all products.
- **Decision**: Shared `packages/auth/` using Auth.js v5 (NextAuth). User auth: Google OAuth + Apple Sign-In. Admin auth: same OAuth flow + email allowlist check (`ADMIN_EMAILS` env var with sankalp@paperworklabs.com + Olga's personal email). No separate admin login, no role system. Trinkets have no auth -- public tools with cross-sell CTAs. (Updated per D76: 1 Workspace seat, Olga uses personal email for admin access.)
- **Alternatives**: Separate admin app (over-engineered), personal Gmail for auth (messy separation of concerns), role-based system (unnecessary for 2 admins).
- **Reversibility**: Allowlist is an env var, trivial to update.

### D57 — Trinkets Domain: Subdomain + Graduation (2026-03-12)
- **Context**: Considered individual SEO-friendly domains per trinket vs tools.filefree.ai subdomain.
- **Decision**: Stay on tools.filefree.ai. SEO research confirms subdomain inherits some parent authority, individual domains start at DA 0. At Year 1 revenue of $50-300, buying 15+ domains is negative ROI. Use subdirectory-style paths (tools.filefree.ai/calculators/mortgage) for topical clustering. Graduation criteria: if a trinket exceeds 10K monthly visits, consider standalone domain with 301 redirect.
- **Alternatives**: Individual domains per trinket (rejected: negative ROI, DA 0 startup, Google EMD devaluation since 2012), subdirectories on filefree.ai (rejected: tighter coupling with main product).
- **Reversibility**: Can always buy standalone domains later and 301 redirect.

### D58 — Experimentation Platform: PostHog-First (2026-03-13)
- **Context**: CK's Darwin runs 22K models/month. Needed a lightweight experimentation framework that grows with us. Researched Google's user simulation paper (2024), Capital One's FinTRec (2025), Meta's PEX framework.
- **Decision**: Three-phase approach. Phase 1: PostHog feature flags + simple A/B (already in stack, free tier 1M events/mo). Phase 2 (10K+ users): Thompson Sampling bandit for partner ranking (~200 lines Python). Phase 3 (50K+ users): ML collaborative filtering. FTC compliance constraint baked in: never test "pre-approved" language.
- **Alternatives**: Build custom experimentation platform (rejected: premature at our scale), Optimizely/LaunchDarkly (rejected: paid, unnecessary complexity for Phase 1).
- **Reversibility**: PostHog feature flags are config, trivial to change. Bandit/ML layers are additive.

### D59 — Data Intelligence: Design for Post-Production from Day One (2026-03-13)
- **Context**: Tax filing is seasonal, LLC formation is one-time. Without retention and data intelligence, users churn after the transaction. The data compounds year-over-year and becomes the moat.
- **Decision**: Broaden from "retention" to full "Data Intelligence & Analytics" layer (Section 4L). Track company KPIs from day one (activation rate, MAU, partner conversion, churn, LTV). Build lifecycle campaigns (7 trigger-based via n8n). Deploy churn prediction via ChurnGuard AI (open-source, PostHog+Stripe) at Phase 2. Web push notifications (Phase 2+, opt-in, max 2/week).
- **Alternatives**: Build custom analytics (rejected: PostHog does this), defer analytics to Year 2 (rejected: lose data compounding advantage).
- **Reversibility**: Event taxonomy is append-only. KPI definitions can be adjusted. Campaign triggers are n8n config.

### D60 — Credit Score: Phase 1.5 Not Phase 2 (2026-03-13)
- **Context**: CK's moat was 2,500 data points/user, not the credit score itself. FileFree uniquely sees actual tax return data (W-2 Box 1 income, filing status, dependents, refund amount). Adding credit score creates the richest financial profile in fintech. Every month delayed = lost data compounding.
- **Decision**: Move credit score integration from Phase 2 to Phase 1.5 (Launch + 3 months). Soft pull only via TransUnion reseller (Array or SavvyMoney, $0.50-2.00/pull). FCRA compliance review ($500-1K). UX: opt-in, value-first framing ("Won't affect your score").
- **Alternatives**: Wait until Phase 2 (rejected: lose 12 months of credit trajectory data for Year 1 filers), skip credit score entirely (rejected: dramatically limits partner matching quality and revenue).
- **Reversibility**: Soft pull integration is additive. Can be removed if FCRA compliance proves too costly.

### D61 — Package Rename: cross-sell -> intelligence (2026-03-13)
- **Context**: `packages/cross-sell/` was too narrow for the expanded intelligence engine that now includes profile building, partner matching, experimentation, data intelligence, churn prediction, and campaign triggers.
- **Decision**: Rename to `packages/intelligence/`. Updated monorepo structure in Section 2 and Phase 5 tasks. Modules: profile builder, partner matcher, experimentation, data intelligence, campaign triggers.
- **Alternatives**: `packages/recommendation/` (rejected: still too narrow), `packages/analytics/` (rejected: conflicts with existing analytics package for PostHog).
- **Reversibility**: Package rename is a refactor, trivial in a monorepo.

### D62 — Production Reliability Architecture: 5 Must-Haves Before Tax Season (2026-03-13)
- **Context**: FileFree handles SSNs, financial data, and IRS submissions. Tax season concentrates 80% of annual volume into 10 weeks. A double-submit, cascading failure, or undetected calculation bug during this window is catastrophic -- both legally and reputationally.
- **Decision**: Five non-negotiable reliability patterns must be implemented in Phase 7 (P7.18-P7.22) before January 2027 launch: (1) Idempotency keys on all financial endpoints via FastAPI middleware + Redis, (2) Circuit breakers (`pybreaker`) on all external service calls with per-service degradation strategies, (3) Dual-path tax calculation reconciliation pipeline with $1 tolerance and nightly IRS Pub 17 validation, (4) OpenTelemetry distributed tracing across OCR-to-filing pipeline exported to Grafana Cloud free tier, (5) k6 load testing with 4 tax season scenarios and monthly runs from October 2026. Five additional should-have patterns (event sourcing, key rotation, schema registry, multi-region readiness, canary deploys) deferred to Year 1-2.
- **Alternatives**: Ship without reliability patterns (rejected: unacceptable for financial software handling SSNs), implement only observability (rejected: insufficient -- idempotency and circuit breakers prevent data corruption, not just detect it), use paid APM like Datadog (rejected: $15+/host/mo unnecessary at MVP scale when Grafana Cloud free tier covers needs).
- **Reversibility**: All patterns are additive middleware/wrappers. Can be removed or replaced independently.

### D63 — Adjacent Revenue: 3 Tier 1 Extensions (2026-03-13)
- **Context**: The venture's data moat (tax return data, formation data, financial profiles) enables natural product extensions that require minimal new infrastructure. Three "Tier 1" ideas scored highest on alignment + effort + revenue potential.
- **Decision**: Three GO verdicts: (1) Compliance-as-a-Service ($49-99/yr LaunchFree subscription, Phase 3.5) -- annual report reminders, franchise tax tracking, renewal forms. First true SaaS/recurring revenue. Undercuts LegalZoom 3-6x. (2) Quarterly Tax Estimator (Phase 1.5 Trinket + Phase 7 FileFree feature) -- 1040-ES calculator for 1099 workers. Free, drives 4x/year re-engagement and Tax Optimization Plan upsell. Auto-populates from prior return (unique moat). (3) Refund Splitting + Goal-Based Savings (Phase 7 P7.4 expansion) -- IRS Form 8888 for splitting refunds across up to 3 accounts. Transforms post-filing into affiliate conversion moment. $15K-126K revenue potential.
- **Alternatives**: Portfolio tracking (deferred: needs Plaid), insurance marketplace (rejected: heavy compliance, low alignment), crypto tax (rejected: niche + volatile market).
- **Reversibility**: All three are additive features. CaaS is a subscription that can be discontinued. Quarterly estimator is a standalone tool. Refund splitting is a form addition.

### D64 — Reconciliation Strategy: Dual-Path Tax Calculation (2026-03-13)
- **Context**: Tax calculation errors in financial software are not just bugs -- they're legal liabilities. The IRS holds the filer responsible for errors regardless of which software produced them. A single widespread calculation bug could result in penalties for thousands of users and destroy brand trust.
- **Decision**: Every tax return runs through dual-path verification before the user sees results. Path A: forward calculation (income -> deductions -> credits -> refund). Path B: reverse verification (refund -> effective rate -> back-calculate expected income). Delta > $1 flags for manual review. Additionally: nightly batch reconciliation re-runs all day's calculations, and a suite of 20+ IRS Publication 17 worked examples runs as regression tests on every tax engine change. Zero tolerance for calculation mismatches.
- **Alternatives**: Single-path with unit tests only (rejected: unit tests catch known bugs but miss interaction effects and rounding cascades), manual spot-checking (rejected: doesn't scale, introduces human error), third-party tax calculation audit (rejected: expensive, adds dependency, and we can build better in-house validation).
- **Reversibility**: Reconciliation is an additive post-calculation step. Can be disabled (though it shouldn't be).

### D65 — Financial Marketplace Platform: 4-Stage Evolution (2026-03-14)
- **Context**: The venture's data moat (W-2 income, credit score, filing status, LLC data, quarterly estimates, refund splitting) creates the richest per-user financial profile in consumer fintech -- 3-5x deeper than Credit Karma. This data is the foundation for a two-sided financial product marketplace. Credit Karma's Lightbox technology (bidirectional matching between user profiles and lender underwriting models) generated $1.6B+ revenue at ~$11.43 ARPU across 140M mostly-passive users. FileFree's active users (tax filing, LLC formation, quarterly tracking) justify significantly higher per-user value.
- **Decision**: Adopt a 4-stage marketplace evolution, volume-gated: Stage 1 (affiliate links, 0-5K users), Stage 2 (smart matching + Fit Scores + Thompson Sampling bandit, 5K-25K), Stage 3 (partner API + segment marketplace + auction-based CPA, 25K-50K), Stage 4 (full marketplace with partner-submitted eligibility models, 50K+). All architecture (data model, recommendation engine, event taxonomy, consent, partner dashboard) is designed for Stage 4 from day 1 -- only the implementation advances by stage. See Master Plan Section 4O for full roadmap.
- **Alternatives**: Build marketplace incrementally with schema migrations at each stage (rejected: 10x more expensive to rebuild data pipelines and re-consent users than to design correctly upfront), outsource marketplace to third-party (rejected: marketplace IS the product, can't outsource the moat), skip marketplace and stay affiliate-only (rejected: leaves $30-70/user ARPU on the table).
- **Reversibility**: Low (once partners integrate via API and users consent to matching, the marketplace becomes infrastructure). Stage gates provide natural checkpoints to slow or stop if unit economics don't support advancement.

### D66 — Strategic-from-Day-1 Architecture (2026-03-14)
- **Context**: The core insight is that it's much cheaper to design database schemas, API contracts, and data pipelines correctly upfront than to rebuild them later. Traditional startups build incrementally and refactor constantly. With AI-assisted development, we can design for the end-state from day 1 and implement incrementally without costly migrations.
- **Decision**: Six foundational components are designed for the full marketplace end-state (Stage 4) from day 1: (1) Data model includes partner_products, partner_eligibility, fit_scores, partner_bids tables with nullable marketplace columns; (2) Recommendation engine uses a 3-layer pluggable architecture (candidate generation, scoring, ranking) with a stable score() interface; (3) Event taxonomy includes MARKETPLACE EVENTS and PARTNER-SIDE EVENTS blocks from day 1; (4) Consent architecture uses 3-tier system (cross-product, personalized matching, anonymized insights) that covers all 4 marketplace stages without re-consent; (5) Partner dashboard is designed as marketplace portal seed with Stage 1-4 evolution path; (6) PARTNERSHIPS.md uses tiered partner framework (A-D) aligned with marketplace stages. Implementation starts simple (Stage 1: static scoring, flat CPA, basic events) but the schema and interfaces never need breaking changes.
- **Alternatives**: Standard incremental architecture with refactors at each stage (rejected: schema migrations on production data are risky and expensive, re-consenting users at each stage loses 20-40% consent rates), over-engineer everything from day 1 including implementation (rejected: premature optimization wastes time on code that may never execute).
- **Reversibility**: High (tables can be dropped, events can be ignored, tiers can be consolidated). The architecture adds minimal overhead to day 1 development -- most marketplace columns are nullable and ignored until their stage arrives.

### D67 — Business Tax Filing: 1065 + 1120-S as LaunchFree Synergy Multiplier (2026-03-16)
- **Context**: Every LaunchFree LLC former who selects "partnership" or "S-Corp" tax election MUST file a business return (Form 1065 or 1120-S). This is a mandatory compliance obligation, not an optional cross-sell. Business returns are also high-value for Distill CPA firms. No free filing product currently covers business returns -- Taxu.io charges $10-29/mo for business features, TurboTax Business starts at $219.
- **Decision**: Add business tax filing as Phase 10 (Year 2, 2027-2028 season). Forms 1065 (partnership/multi-member LLC) and 1120-S (S-Corp). Price: $49/return (1065), $99/return (1120-S) for consumer. Included in Distill Firm plan. LaunchFree cross-sell: first business return free for LLC formers who selected partnership/S-Corp election. K-1 generation for pass-through income allocation. MeF business return schemas extend existing validation engine.
- **Alternatives**: Skip business filing and stay personal-only (rejected: leaves mandatory cross-sell revenue on the table and weakens LaunchFree synergy), offer free business filing (rejected: business returns are complex, charging is justified and expected -- even Taxu charges for this), partner with existing business filing service (rejected: lose data moat, lose integration tightness with LaunchFree).
- **Reversibility**: Medium. Business filing engine is a significant build (~4-6 weeks) but modular. Can be shelved if demand is insufficient, but LaunchFree LLC data strongly predicts demand.

### D68 — Scale Growth Playbook: 4 Channels to 2M Users (2026-03-16)
- **Context**: The organic-first strategy (Section 5K) projects 5K-23K users in Year 1 -- solid for a bootstrapped launch but far from the 2M+ scale achieved by Taxu.io or Credit Karma. Research into competitor growth strategies revealed 3 patterns: (1) TaxDown's tax season surge marketing (concentrated paid spend during the 10-week filing window), (2) Taxu's B2B API distribution (powering tax filing inside other platforms multiplies user count without per-user acquisition cost), (3) Credit Karma's community-led growth (3 years of zero paid ads, grown entirely on Reddit + word-of-mouth + product virality).
- **Decision**: Add Section 5L with 4 growth channels: (1) Tax Season Surge (5x ad budget Jan-Apr, creator partnerships at 25K+ users), (2) B2B API Distribution (Tax-as-a-Service API at $5-15/return, targeting payroll companies and banking apps in Year 2+), (3) Community-Led Growth (Reddit, Discord, build-in-public), (4) B2B CPA Outreach (Distill as distribution channel -- each CPA firm is a referral source for consumer product). Year 1-5 projection shows path to 1M-2.15M users by Year 5, with B2B API as the key unlock beyond 500K.
- **Alternatives**: Stay organic-only (rejected: caps at ~500K-900K users), raise VC for paid acquisition (rejected: dilution, and CAC for tax filing is high outside of tax season), partner with a single large distributor (rejected: single-point dependency).
- **Reversibility**: High. Each channel is independent. Paid spend can be dialed down. API can be deprecated. Community engagement has no sunk cost.

### D69 — Distill: B2B Tax Automation as Immediate Revenue (2026-03-16)
- **Context**: MagneticTax (YC Summer 2025 batch) raised venture capital to build AI-powered data entry automation for CPA firms -- processing 1040 individual returns into existing tax software. FileFree is building the identical OCR/extraction pipeline (Cloud Vision + GPT tiered extraction) for consumer filing. The B2B product is ~20% incremental engineering on top of Phase 7 infrastructure. Unlike consumer FileFree (free, marketplace revenue at scale), B2B SaaS generates immediate predictable revenue from CPA subscription fees.
- **Decision**: Add "Distill" (distill.tax) as a separate B2B brand with two product lines: Distill for CPAs (SaaS dashboard) and Distill API (Tax-as-a-Service). CPA firms upload client W-2s/1099s in bulk, auto-extract fields via shared OCR pipeline, export to professional tax software (UltraTax, Drake, ProConnect, Lacerte). Pricing: $49/mo (Solo), $99/mo (Team), $199/mo (Firm). Architecture: new `apps/distill/` in monorepo at `distill.tax`, sharing `packages/tax-engine`, `packages/document-processing`, `packages/ui`, `packages/auth` with consumer FileFree. Same `apis/filefree/` backend with firm-scoped B2B routes. Separate brand rationale: "Free" in "FileFree" creates cognitive dissonance for B2B buyers; tax industry standard is separate brands (Intuit: TurboTax vs ProConnect/Lacerte); "Distill" = extract pure essence from raw material, fits naturally under Paperwork Labs (distilling paperwork).
- **Alternatives**: Keep "FileFree Pro" naming (rejected: "Free" in brand name undermines B2B trust, SBI Growth research confirms B2B perception issues), API-only (rejected: CPAs need a UI dashboard), skip B2B (rejected: slower to revenue, wastes shared tech opportunity).
- **Reversibility**: High. Distill is a separate app in the monorepo. Can be shut down without affecting consumer FileFree. Stripe subscriptions can be cancelled. No data coupling beyond shared packages.

### D70 — Package Split Architecture: data/ -> data/ + tax-engine/ + document-processing/ (2026-03-16)
- **Context**: `packages/data/` was overloaded -- holding 50-state formation data, 50-state tax data, tax calculation engine, MeF XML schemas, and document processing pipelines. These have different ownership cycles: tax data = annual IRS update, formation data = per-state SOS changes, tax engine = code changes with every form addition, document processing = OCR pipeline changes independent of tax rules.
- **Decision**: Split into 3 packages: `packages/data/` (50-state formation + tax JSON configs, Zod schemas, state engine API), `packages/tax-engine/` (tax calculation engine, form generators, MeF XML schemas, dual-path reconciliation), `packages/document-processing/` (OCR pipeline client, field extraction schemas, document storage lifecycle, bulk upload queue). This separation is the architectural moat: `packages/tax-engine/` becomes the independently testable, versioned core that powers consumer FileFree, Distill for CPAs, Distill API, business filing, AND future products.
- **Alternatives**: Keep monolithic `packages/data/` (rejected: testing becomes coupled, release cycles conflict, new developer onboarding is harder), split into more than 3 (rejected: over-engineering, interface overhead exceeds benefit at current scale).
- **Reversibility**: Medium. Splitting is easier than re-merging. But interfaces between packages must be stable once other packages depend on them.

### D71 — Distill: Separate B2B Brand for CPA SaaS + Tax API (2026-03-16)
- **Context**: The B2B CPA product was originally named "FileFree Pro." Research revealed that "Free" literally in the brand name creates cognitive dissonance for B2B buyers paying $199/mo (SBI Growth research). Tax industry standard is separate brands (Intuit: TurboTax vs ProConnect/Lacerte). The "tax breakup" ad controversy (Oct 2024) proved consumer brands undermining CPAs creates professional backlash.
- **Decision**: Rename B2B product to "Distill" (distill.tax). Separate brand under Paperwork Labs venture umbrella. "Distill" = extract pure essence from raw material, perfect metaphor for OCR-to-structured-data pipeline. Fits naturally under Paperwork Labs (distilling paperwork). Two product lines under one B2B brand: Distill for CPAs (SaaS dashboard, $49-199/mo) and Distill API (Tax-as-a-Service for platforms, per-return pricing). Consumer brands (FileFree, LaunchFree) remain the "Free family." B2B brand (Distill) is the professional portfolio.
- **Alternatives**: Keep "FileFree Pro" (rejected: "Free" in B2B undermines trust), use a completely unrelated name with no connection to venture (rejected: loses thematic coherence with Paperwork Labs), create separate brands for CPA SaaS vs API (rejected: unnecessary fragmentation, same audience type).
- **Reversibility**: High. Brand rename is documentation + domain + landing page. No architectural changes.

### D72 — State Filing Engine: Build vs Buy, Three-Tier Architecture (2026-03-16)
- **Context**: Initial LaunchFree plan claimed "LaunchFree prepares your LLC filing — it does NOT file for you in most states" due to assumption that 35+ states lacked online filing. Research disproved this: nearly all 50 states have online filing portals. Competitors (LegalZoom, ZenBusiness) DO file for users. The "honest UX" framing was actually a product gap, not a feature. Third-party formation API pricing (CorpNet ~$69-79, FileForms ~$30-60) made wholesale outsourcing incompatible with LaunchFree's "$0 service fee" model.
- **Decision**: Build an in-house State Filing Engine with three tiers: Tier 1 (state APIs, e.g. Delaware ICIS), Tier 2 (Playwright portal automation for ~45 states), Tier 3 (print-and-mail via Lob for ~2 mail-only states). Payment via Stripe Issuing virtual cards. Estimated blended marginal cost: ~$0.25-0.50/filing (actual costs to be validated). This engine serves both LaunchFree (consumer, $0) and Distill Formation API (B2B, $20-40/filing), creating a dual-use infrastructure with near-zero marginal cost.
- **Alternatives**: White-label via CorpNet/FileForms (rejected: $30-80/filing incompatible with free model), preparation-only "honest UX" (rejected: competitors file for users, this is a product gap not a feature), manual submission queue (rejected: doesn't scale).
- **Reversibility**: Low. This is a significant engineering investment. But the infrastructure has dual-use value (consumer + B2B API) that justifies the investment.

### D73 — Embrace "Paperwork Labs" as Company Name Everywhere (2026-03-16)
- **Context**: Documentation and persona files used inconsistent naming — "the venture," "FileFree/LaunchFree venture," "Venture," etc. The holding company (Paperwork Labs LLC) had been registered and paperworklabs.com purchased, but the name wasn't being used consistently across agent context files, documentation headers, or architectural references. This caused agents to have fragmented understanding of the company identity.
- **Decision**: Standardize "Paperwork Labs" as the company name across all documentation, persona files, README, and agent context. Every `.mdc` persona header now starts with "Paperwork Labs [Role]". All doc headers use "Paperwork Labs — [Title]". The `.cursorrules` header opens with "Paperwork Labs — We build tools that eliminate paperwork." Brand hierarchy: Paperwork Labs (company) > consumer brands (FileFree, LaunchFree, Trinkets) + B2B brand (Distill).
- **Alternatives**: Keep "the venture" (rejected: too generic, no brand recognition), use "FileFree" as the umbrella name (rejected: FileFree is one product, using it for the company conflates product and company identity).
- **Reversibility**: High. It's naming. Can change at any time.

### D74 — Accelerate Full Distill Platform to Summer 2026 (2026-03-16)
- **Context**: Original timeline placed Distill CPA SaaS at Phase 9 (January-March 2027) and Formation API at Phase 9.5 (Year 2, 2028). This was based on traditional development estimates. However, Paperwork Labs' operating model (one founder + AI agents shipping at full-team velocity) compresses timelines significantly. Furthermore, ~80% of Distill's infrastructure is shared with consumer products built in Phases 1-3 (tax engine, filing engine, document processing, 50-state data). The incremental B2B work is thin: multi-tenant auth, API keys, billing, docs.
- **Decision**: Pull ALL Distill products to Summer 2026: CPA SaaS, Formation API, Tax API (calculation-only, e-file endpoint activates January 2027 when MeF transmitter ships), and Compliance API. Phase 9 runs in parallel with Phases 5-6, not sequentially after Phase 8. No consumer product is deprioritized. Only two hard deadlines remain external (IRS): MeF ATS testing (October 2026) and tax season (January 2027).
- **Alternatives**: Keep Distill at March 2027+ (rejected: wastes 6+ months of potential B2B revenue, underestimates AI-augmented velocity), launch only CPA SaaS by summer (rejected: APIs are thin incremental work on top of shared infrastructure — no reason to wait).
- **Reversibility**: High. If summer proves too aggressive, individual API launches can slip without affecting consumer products.

### D75 — Agent-Driven Operations Model (2026-03-16)
- **Context**: As Paperwork Labs scales to 4 products across 50 states with continuously changing compliance data, portal UIs, filing fees, and deadlines, manual maintenance is unsustainable for a solo founder. The same AI-augmented development model that builds the products can maintain them.
- **Decision**: Formalize AI agents as the operations team: (1) n8n workflows auto-detect changes in 50-state formation/tax data weekly, flag for human review, (2) Playwright portal health checks run daily against live state portals, alert via Slack if scripts break, (3) Cursor agents handle ongoing code maintenance, bug fixes, and feature additions, (4) Filing Engine status checks run hourly for stuck/failed submissions. This is formalized as a moat: competitors need both the infrastructure AND the operational process to compete.
- **Alternatives**: Hire operations staff (rejected: premature for a bootstrapped venture at this stage), manual monitoring (rejected: doesn't scale across 50 states x 4 products), outsource monitoring (rejected: no vendor covers this specific domain).
- **Reversibility**: High. Agent workflows can be replaced with human processes at any time.

### D76 — Google Workspace Setup: 1 Seat + Aliases (2026-03-16)
- **Context**: VMP and FINANCIALS incorrectly stated "Google Workspace already active on sankalpsharma.com." Founder did not have paid Google Workspace — was on free Gmail. Needed to create Workspace from scratch for @paperworklabs.com and product-domain emails.
- **Decision**: Create new Google Workspace under Paperwork Labs. Sign up with "Just you" (1 seat). Primary domain: paperworklabs.com. Add filefree.ai, launchfree.ai, distill.tax as alias domains. All department emails (hello@, support@, legal@, partnerships@, api@) configured as aliases routing to founder's single inbox. Cost: **$6/mo** (Business Starter), not $12. Olga gets admin panel access via personal email in `ADMIN_EMAILS` env var — no second Workspace seat needed. Use company email (e.g. sankalp@paperworklabs.com) for Cursor, Stripe, and vendor accounts for clean expense/billing separation.
- **Alternatives**: 2 seats ($12/mo) with Olga on olga@paperworklabs.com (rejected: aliases suffice, saves $6/mo); free Gmail + Cloudflare Email Routing (rejected: no proper admin console, SPF/DKIM setup more brittle).
- **Reversibility**: Easy. Add second seat anytime. Update FINANCIALS.md and VMP "Professional Email Aliases" section to reflect $6/mo and "create Workspace" (not "already active").

### D77 — Repo Migration + Docs Audit (2026-03-16)
- **Context**: Repo migrated from personal account to `paperwork-labs` GitHub org and renamed from `filefree` to `paperwork`. Google Workspace created at paperworklabs.com (D76). Many docs still referenced old repo URL (`your-org/filefree`), old Google Workspace setup (`sankalpsharma.com`, 2 seats, $12/mo), old domain (`filefree.tax` as primary), and stale admin emails (`sankalp@sankalpsharma.com`).
- **Decision**: Full docs audit. Fixed: (1) Repo clone URL in README → `paperwork-labs/paperwork`. (2) Google Workspace references across 6 docs → 1 seat, $6/mo, paperworklabs.com primary. (3) Monthly burn recalculated to $278. (4) Admin email allowlist → `sankalp@paperworklabs.com`. (5) filefree.tax → filefree.ai in all active doc URLs/emails. (6) P0.3 Google Workspace task → DONE. (7) `.cursorrules` annotated with "Current vs Target" repo structure note. (8) Removed cursor-context-backup.zip and CURSOR_BACKUP_README.md (transfer artifacts). (9) Added Origin budgeting app as open research question (Q5).
- **Reversibility**: N/A. Cleanup commit.
