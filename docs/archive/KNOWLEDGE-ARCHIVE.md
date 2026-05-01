# Knowledge Base Archive

Historical decisions, learnings, and patterns archived from KNOWLEDGE.md per D52 (Doc Hygiene rules). These entries are baked into the current architecture and no longer require daily reference. Full context preserved here; one-line summaries remain in the main KNOWLEDGE.md.

**Archived**: 2026-03-18

---

## Archived Decisions (D1–D30, D36)

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
- **Decision**: Downgrade from Render Standard ($25/mo, 2GB) to Render Starter ($7/mo, 512MB). FastAPI + deps need ~200-300MB. 512MB is sufficient without ML model hosting.

### D4: Own IRS MeF Transmitter as North Star (2026-03-09)
- **Decision**: Build own MeF transmitter (target January 2027) as the #1 strategic priority. $0/return, full control, permanent "free forever" sustainability.
- **Rationale**: Owning the transmitter eliminates third-party dependency and per-return cost. EFIN application is the longest lead item (45 days).

### D5: Column Tax as Interim E-File Partner (2026-03-09)
- **Decision**: Integrate Column Tax SDK with transparent cost-passthrough pricing. Free PDF download always available as alternative.

### D6: Skip Claude Code (2026-03-09)
- **Decision**: Skip. Cursor (current plan) is sufficient for security-sensitive financial code.

### D7: Skip Linear, Use GitHub Issues + Projects (2026-03-09)
- **Decision**: GitHub Issues + Projects for task tracking. Free, already integrated, auto-updates with PRs.

### D8: Tiered OCR Architecture (2026-03-09)
- **Decision**: Three-tier: (1) Cloud Vision + GPT-4o-mini ($0.002/doc), (2) GPT-4o vision fallback ($0.02/doc) for low confidence, (3) manual entry.

### D9: Docker Compose DEV ONLY, Managed Services for Prod (2026-03-09)
- **Decision**: Docker Compose for local dev. Production uses Render native buildpack, Vercel git deploy, Neon, Upstash. No production Dockerfiles.

### D10: Self-Host Postiz + n8n on Shared Hetzner VPS (2026-03-09)
- **Decision**: Self-host both on one Hetzner CX33 VPS (8GB RAM, $7.50/mo). Separate databases, shared PostgreSQL + Redis.

### D11: Skip Buffer, Postiz from Day One (2026-03-09)
- **Decision**: Skip Buffer entirely. Postiz has REST API for programmatic scheduling + n8n automation.

### D12: Paid Amplification via TikTok Spark Ads + Meta Boost (2026-03-09)
- **Decision**: $200-500/mo during tax season only. Spark Ads boost organic winners. Off-season: $0 paid.

### D13: n8n as Persona Automation Layer (2026-03-09)
- **Decision**: Use n8n workflows as the autonomous execution layer for personas. Same system prompts from .mdc files, triggered by cron instead of human interaction.

### D14: Revenue Model — Monetize the Refund Moment (2026-03-09)
- **Decision**: Kill monthly subscription. Primary revenue: refund routing to HYSA partners ($50-100/funded account) + financial product referrals ($50-200/referral). Secondary: audit shield ($19-29/yr), Tax Optimization Plan ($29/yr), refund advance. Credit Karma playbook.

### D15: Tax Optimization Plan at $29/year (2026-03-09)
- **Decision**: Annual one-time purchase at $29/year during filing, not $9.99/month recurring. Tax advice is seasonal.

### D16: Co-Founder Structure — Product/Eng + Partnerships/Revenue (2026-03-09)
- **Decision**: Two co-founder structure. Founder 1 owns product/engineering. Founder 2 (FAANG partnerships background) owns partner outreach and deal negotiation.

### D17: Tiered Partnership Strategy (2026-03-09)
- **Decision**: Phase 1: affiliate applications (self-serve). Phase 2: activate links. Phase 3 (5K+ users): direct partnerships (2-3x rates). Phase 4 (10K+): expand categories.

### D18: Docker Dev Environment — Task 0.1 Complete (2026-03-09)
- **Milestone**: Docker Compose with 4 services, Makefile with 17 commands, separate dev/prod Dockerfiles.

### D19: Project Structure Cleanup (2026-03-09)
- **Milestone**: Renamed `filefree-api/` → `api/`, `filefree-web/` → `web/`. Created `infra/` and `docs/` folders.

### D20: Multi-Persona Review + Ops Stack (2026-03-09)
- **Milestone**: Fixed stale doc paths, updated Hetzner pricing, created `infra/hetzner/` stack, added Render MCP.

### D21: Production Infrastructure Complete (2026-03-09)
- **Milestone**: Vercel + Render + Neon + Hetzner + DNS all deployed and verified. Monthly burn: $12.49/mo.

### D22: Auth Architecture: Google One-Tap + Apple + Email/Password (2026-03-09)
- **Decision**: Authentication via Google One-Tap (~60%), Apple Sign In (~25%), email/password (~15%). FastAPI owns all auth server-side.

### D23: Sprint 1 Complete (2026-03-09)
- **Milestone**: Frontend design system (22 shadcn components, dark theme), backend foundation (7 models, AES-256, PII scrubber), Hetzner ops stack.

### D24: PostHog Analytics Foundation (2026-03-10)
- **Decision**: PostHog with PII scrubbing. UTM tracking. Sentry not yet integrated.

### D25: Legal Pages Live (2026-03-10)
- **Decision**: Privacy and Terms pages live. Must be reviewed by legal counsel before January 2027.

### D26: Agent Autonomy: n8n Workflows Wired (2026-03-10)
- **Decision**: Added output nodes to all 6 workflows. Postiz v2.12+ required Temporal addition.

### D27: TASKS.md v8: Checkbox Overhaul (2026-03-10)
- **Milestone**: Replaced strikethrough with checkboxes. Added progress summaries.

### D28: Temporal Visibility: PostgreSQL to Elasticsearch (2026-03-10)
- **Decision**: Switched Temporal visibility from PostgreSQL to Elasticsearch 7.17.27 (256MB heap). Fixed Postiz 502s.

### D29: Brand Assets Removed (2026-03-10)
- **Decision**: Deleted AI-generated brand images. Pending: Ideogram v3 wordmark, Figma/Canva monogram.

### D30: Postiz MCP Activated (2026-03-10)
- **Decision**: Postiz API key configured in `.cursor/mcp.json`. Also needs n8n credential.

### D36: Company Structure: Single LLC + DBAs (2026-03-12) — SUPERSEDED by D54
- **Original Decision**: Single Wyoming LLC. **SUPERSEDED**: See D54 — Paperwork Labs LLC in California.

---

## Archived Learnings

### L1: PaddleOCR Production Memory (2026-03-09)
PaddleOCR Docker docs recommend `--shm-size=8G`. Runtime memory 500MB to 20GB+. Not viable for $7/mo 512MB instance.

### L2: Railway Reliability (2026-03-09)
26 incidents in 30 days, 38 in 90 days. False database terminations. Disqualifying for tax season.

### L3: Google Cloud Vision Privacy (2026-03-09)
Images NOT persisted to disk, NOT used for training, NOT shared. Complies with Cloud Data Processing Addendum.

### L4: Google Document AI W-2 Parser Pricing (2026-03-09)
$0.30/doc vs basic OCR + GPT at $0.0017/doc. 176x more expensive.

### L5: Neon Free Tier Cold Starts (2026-03-09)
Auto-suspends after 5 minutes. Cold start: 300-800ms. Negligible during tax season traffic.

### L6: GPT-4o-mini Structured Outputs (2026-03-09)
100% schema adherence with Structured Outputs. Ideal for W-2 Pydantic mapping.

### L7: Google Cloud Vision Layout Preservation (2026-03-09)
Returns hierarchical structure with bounding boxes. Sufficient for GPT to map text to W-2 fields.

### L8: Postiz v2.12+ Requires Temporal (2026-03-10)
Requires Temporal server at port 7233. Fix: add `temporalio/auto-setup:1.28.1` + its own postgres to Docker Compose.

---

## Archived Patterns

### P1: SSN Isolation Pipeline
SSN extracted via regex from OCR output on our server. Masked placeholder in all text sent to OpenAI. Stored only in encrypted database.

### P2: Tiered Service Architecture
Start with cheapest option, add expensive fallbacks for edge cases. Apply to OCR, AI insights, and future features.

### P3: Infrastructure-as-Code via render.yaml
All production infrastructure defined in `render.yaml`. Changes go through PR review.
