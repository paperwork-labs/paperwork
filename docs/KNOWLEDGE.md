# FileFree Knowledge Base

Organizational memory for FileFree. AI agents read this at session start. Update after significant decisions, learnings, or pattern discoveries.

**Last Updated**: 2026-03-09

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
- **Decision**: Two co-founder structure. Founder 1 owns product, engineering, infrastructure, tax calculations, OCR pipeline, content creation, and IRS certification. Founder 2 (FAANG partnerships background) owns partner outreach, deal negotiation, and revenue stream activation at 2-3 hours/week, supported by AI persona (partnerships.mdc).
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
  - **Render** (API): filefree-api live at api.filefree.tax. Custom domain verified, TLS certificate issued. Free tier (upgrade to Starter $7/mo when billing added). Auto-deploy from `main`. DATABASE_URL wired to Neon.
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
  - Alembic configured for async migrations (migration not yet generated against Neon)
  - 2025 tax data (Rev. Proc. 2024-40, P.L. 119-21)
  - Hetzner ops stack fully bootstrapped: Docker, Caddy, n8n (live at n8n.filefree.tax), Postiz (live at social.filefree.tax)
- **Branding change**: Removed "Gen Z" from all user-facing copy (README, layout metadata, page content, API description). Product leads with benefits ("Free AI-powered tax filing"), not demographic labels. Internal strategy docs retain the demographic insight where analytically relevant.
- **Monthly burn**: $5.49/mo (Hetzner VPS only). Vercel Hobby (free), Render free tier, Neon free tier, Upstash free tier.
- **Inconsistencies fixed**: TASKS.md (Temporal reference, separate DBs, docker-compose.yml path, Gen Z FAQ), .cursorrules + engineering.mdc (Vercel tier Hobby not Pro), env.prod.example (missing auth vars), KNOWLEDGE.md D21 (Hetzner bootstrapped).
- **Reversibility**: N/A — milestone.
