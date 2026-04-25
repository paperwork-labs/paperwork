---
owner: strategy
last_reviewed: 2026-04-24
doc_kind: spec
domain: company
status: active
---
# Paperwork Labs — Venture Master Plan (Summary)

**Derived from**: VENTURE_MASTER_PLAN.md (full version: 3509 lines)
**Purpose**: Compact context for n8n workflows and cheaper AI models
**Last synced**: 2026-03-18
**Do not edit directly** — regenerate from VENTURE_MASTER_PLAN.md when strategy changes

---

## 1. Venture Overview

**Entity**: Paperwork Labs LLC (California). DBAs: FileFree, LaunchFree, Trinkets, Distill.

**Products**:

| Product | Domain | Status | Launch |
|---------|--------|--------|--------|
| FileFree | filefree.ai | In development | January 2027 |
| LaunchFree | launchfree.ai | In development | Summer 2026 |
| Distill | distill.tax | In development | Summer 2026 |
| Trinkets | tools.filefree.ai | Scaffolded | Phase 1.5 |
| Studio / Command Center | paperworklabs.com | Live (Tier 1 complete) | Live |

**Team**: Two co-founders. Founder 1 (Product/Engineering) owns all code. Founder 2 (Partnerships/Revenue) sources and closes financial product partnerships.

**Monthly burn**: ~$278/mo. Breakdown: Hetzner $6 + Render x2 $14 + Google Workspace $6 + domains ~$20 + OpenAI ~$10 + ElevenLabs $5 + cyber insurance ~$150 (est. amortized) + CA franchise tax ~$67 (est. amortized). Vercel/Neon/Upstash free tier until scale triggers.

**Critical dates**: LLC + EIN today (blocks EFIN, bank, Stripe). EFIN application this week (45-day IRS processing). Cyber insurance before first SSN. MeF XML dev June 2026. ATS Oct 2026. Comms test Nov 2026. Tax season Jan 2027.

---

## 2. North Stars

- **FileFree**: Own IRS MeF Transmitter (January 2027) — e-file at $0/return. EFIN + ATS certification in progress.
- **LaunchFree**: State Filing Engine covering all 50 states (Summer 2026) — automate LLC formation via state APIs, portal automation, print-and-mail.
- **Distill**: Full B2B compliance automation platform (Summer 2026) — CPA SaaS + Formation API + Tax API + Compliance API at api.distill.tax.
- **Venture-wide**: Build shared compliance infrastructure that powers both free consumer products and paid B2B APIs. The infrastructure IS the product.

---

## 3. Revenue Model

**Consumer** (free forever): Partnership referrals, refund routing, financial product recommendations, audit shield, Tax Optimization Plan ($29/yr), RA credits (LaunchFree), Compliance-as-a-Service ($49-99/yr). No filing fees from consumers.

**B2B** (Distill): CPA SaaS $49-199/mo, Formation API $20-40/filing, Tax API $5-15/return, Compliance API per-action.

**Key numbers**:
- Cost per user: $0.06 (FileFree); ~$0.50/filing (LaunchFree)
- ARPU (Scenario B): $8.05 (FileFree); $12-18 (LaunchFree formations)
- 77% of FileFree revenue from partnerships (refund routing + financial referrals)
- Year 1 projections: Pessimistic $15K, Moderate $64K, Aggressive $264K
- Plan B: Self-serve affiliates (Betterment, SoFi, Wealthfront, Impact.com, CJ) if no partnership deals — ~$6.5K-37K Year 1

**FileFree streams**: Refund routing HYSA (2-4%), financial referrals (1-1.5%), audit shield (3-5%), Tax Opt Plan (2-3%). **LaunchFree streams**: RA credits, banking/payroll referrals, Compliance-as-a-Service (8-18% attach).

---

## 4. Current Phase Status

**Complete**: Phase 1 (Monorepo restructure), Phase 4 Tier 1 (Studio/Mission Control/Agent Monitor/Infra health).

**In progress**: Phase 0 (domains, Workspace done; LLC, EFIN, domain migration, GDrive, social handles, legal setup not started).

**Upcoming** (reference TASKS.md for full task breakdown):
- Phase 1.5: First Trinket + Agent Pipeline Test (3-5 days) — financial calculators, tool-layout, Trinket Factory pipeline validation
- Phase 2: 50-State Data Infrastructure (P2.1-P2.10) — packages/data scaffold, Source Registry, AI-extract tax + formation, human review, state engine, n8n validators
- Phase 3: LaunchFree MVP + State Filing Engine — formation wizard, Articles of Organization PDF, backend service, P3.4a-h (orchestrator, portal configs, Delaware ICIS, Playwright automation, Stripe Issuing, filing tracker, portal health, manual fallback queue), RA credits, Stripe, dashboard, legal pages
- Phase 4 Tier 2-3: Analytics, Support inbox, Social command, State Data observatory; Revenue intelligence, Campaign control, User intelligence (when revenue flows)
- Phase 5: User Intelligence Platform — venture identity, cross-product consent, packages/intelligence, email templates, campaigns, event tracking, experimentation, KPI dashboards, lifecycle workflows, partner auth scaffold
- Phase 6: Agent restructure + social pipeline — persona updates, faceless content pipeline (n8n), 12 new workflows, Notion → GDrive
- Phase 7: FileFree Season Prep (October 2026) — resume Sprint 4, Column Tax, TaxAudit, Refund Plan + Form 8888, transactional emails, marketing refresh, 1099-NEC/Schedule C, dependents, Schedule B/1, 50-state engines, MeF schemas, local validation, ATS submission, reliability patterns (idempotency, circuit breakers, reconciliation, OpenTelemetry, k6)
- Phase 8: FileFree Launch (January 2027) — MeF transmitter go-live, Tax Opt Plan, Product Hunt, paid amplification, Schedule A/D mid-season
- Phase 9: Distill full B2B platform (Summer 2026) — CPA onboarding, bulk upload, dashboard, tax software export, Formation API, Tax API, Compliance API, Stripe B2B billing

**Key milestones**: EFIN application THIS WEEK (45-day IRS processing) → ATS Oct 2026 → Comms test Nov 2026 → MeF Jan 2027. LLC + EIN blocks bank, Stripe, trademarks. Cyber insurance before first SSN. Column Tax demo/pricing by Sep 2026.

**Pre-code blockers** (Section 0G): EFIN application (this week), cyber liability insurance $1M (before first SSN), data breach response plan, 1hr attorney consult (before Phase 3), self-serve affiliate apps (April 2026).

---

## 5. Competitive Moat (6-Point Summary)

1. **State Filing Engine** — Proprietary 50-state portal automation + Delaware ICIS API. Same engine serves LaunchFree ($0) and Distill Formation API ($20-40/filing). Multi-year head start. Near-zero marginal cost.
2. **Cross-product data compound** — User who files taxes + forms LLC + tracks quarterly estimates has 20+ data-point profile. Tax return data is court-admissible income verification. Competitors need 2-3 years to build equivalent depth.
3. **Agent-maintained compliance data** — 50-state formation rules, fees, filing procedures via n8n workflows. States change continuously; agents detect and update configs. Requires both data layer AND maintenance system.
4. **Cost structure moat** — ~$278/mo burn vs CK's 1,300+ employees. 1 founder + AI agents. Profitability at Scenario A (~$65K revenue).
5. **Retention lock-in** — 80% of tax filers stick with same software YoY (PCMag). Capture a 22-year-old, own them 10+ years.
6. **B2B distribution flywheel** — Distill CPA firms refer to consumer FileFree. Consumer users convert to CPA leads. Bidirectional. No competitor has both free consumer + B2B CPA automation.

**Competitor snapshot**: Origin Financial (closest, $12.99/mo, SEC RIA). Taxu.io (free basic + paid business, 2M+ users). MagneticTax (B2B CPA, YC S25, no consumer). FreeTaxUSA, Cash App Taxes, ZenBusiness (established, no formation + marketplace). Key takeaway: no single competitor combines free personal tax + free LLC formation + B2B CPA + compliance SaaS + intelligence marketplace.

---

## 6. Tech Stack Summary

**Frontend**: Next.js 14+ (App Router), TypeScript strict, Tailwind CSS 4+, shadcn/ui, Framer Motion, Vercel AI SDK, React Hook Form + Zod, @tanstack/react-query, Zustand. Per-product themes via `[data-theme]`.

**Backend**: FastAPI (Python 3.11+), SQLAlchemy 2.0 async, PostgreSQL 15+ (Neon), Redis (Upstash), Pydantic v2, Alembic migrations.

**Infra**: Vercel (frontend), Render Starter x2 (APIs), GCP (Cloud Vision, Cloud Storage), Hetzner CX33 (n8n, Postiz, Redis). Zero AWS.

**AI**: Cloud Vision DOCUMENT_TEXT_DETECTION → GPT-4o-mini structured extraction → GPT-4o vision fallback (<85% confidence). SSN regex-extracted locally, NEVER sent to LLMs. State data: Gemini 2.5 Flash/Pro. Tax verification: o4-mini. Brand/social: GPT-4o. Code/compliance: Claude Sonnet. See docs/AI_MODEL_REGISTRY.md.

**Monorepo structure** (target): `apps/` (filefree, launchfree, distill, studio, trinkets), `apis/` (filefree, launchfree), `packages/` (ui, auth, analytics, data, tax-engine, document-processing, filing-engine, intelligence, email).

**State Filing Engine** (packages/filing-engine): Tier 1 (Delaware ICIS API), Tier 2 (Playwright portal automation ~48 states), Tier 3 (print-and-mail ~2 states). Stripe Issuing for programmatic state fee payment. Shared by LaunchFree and Distill Formation API.

**OCR pipeline**: Pillow preprocess → Cloud Vision DOCUMENT_TEXT_DETECTION → regex SSN extract (local, masked) → GPT-4o-mini field mapping → GPT-4o vision if <85% confidence. Blended cost ~$0.005/doc. W-2 images: GCP Cloud Storage, 24hr auto-delete.

**Security**: Never log PII. SSN never to LLMs. Rate limits: 5 req/min auth, 20 req/min upload, 5 uploads/day/user. CORS per product domain. Account deletion cascade from day one.

---

## 7. Agent Architecture

**16 personas** in `.cursor/rules/*.mdc`: EA, engineering, strategy, legal, cfo, qa, partnerships, ux, growth, social, tax-domain, cpa, agent-ops, brand, workflows, git-workflow.

**n8n workflows** on Hetzner: EA daily (7am PT → #daily-briefing), EA weekly (Sunday 6pm → #weekly-plan), Thread Handler (Slack event → persona routing), Decision Logger (#decisions), PR summary, state validators, compliance monitor, infra health, social pipeline, campaign engine.

**Slack integration**: Thread Handler routes by channel and keyword. Channels: #daily-briefing (C0ALLJWR1HV), #engineering (C0ALLEKR9FZ), #decisions (C0AM2310P8A), #filing-engine (C0AMWB887KJ), #general (C0AM01NHQ3Y). Use `./scripts/slack-persona.sh <persona> <channel_id> "<message>"` — never Slack MCP for posting (sends as founder account).

**EA runs**: Daily briefing (7am PT): tasks due, phase status, agent overnight report, infra health, filing engine health, blockers, quick wins, partnerships update. Weekly plan (Sunday 6pm PT): completed/missed tasks, sprint progress, next priorities, cross-workstream view, financial snapshot, agent health. Decision logging: "log this" in #decisions → KNOWLEDGE.md D## entry.

**Workflow specs**: venture-agent-thread-handler (Slack event → thread history → load persona → fetch docs → GPT response → reply). venture-ea-daily (cron 7am → GitHub docs + n8n history + Render + Vercel → compose → Slack + GDrive). venture-ea-weekly (cron Sunday 6pm → weekly summary). venture-pr-summary (GitHub webhook). venture-decision-logger (#decisions).

**Model routing** (automated workflows): GPT-4o-mini (bulk extraction, summaries). Gemini 2.5 Flash (default workhorse). o4-mini (tax/financial math). GPT-4o (brand voice, social scripts). Claude Sonnet (code, compliance, UPL). See docs/AI_MODEL_REGISTRY.md and VMP Section 0E.

**Deploy workflows**: `infra/hetzner/workflows/` — ea-daily.json, ea-weekly.json, sprint-close.json, sprint-kickoff.json. Import via n8n. See `scripts/deploy-n8n-workflows.sh`.

---

## 8. Key Active Decisions

See **KNOWLEDGE.md Front-and-Center** for open items. Must-act-on: D29 (brand assets), D37 (domain migration), D56 (shared auth), D62 (reliability patterns), Q3 (Column Tax). Should-track: Q1 (OCR accuracy), D25 (legal review), D34 (n8n credentials), D24 (Sentry). Open architecture: Q2-Q6 (Render 512MB, Postiz MCP, Origin Financial, April Tax).

**Do not duplicate** — this section points to KNOWLEDGE.md; keep that doc as source of truth for active decisions.

---

## Appendix: Quick Reference

**Key domain concepts**: FileFree — Filing, TaxProfile, Document, TaxCalculation, Submission. LaunchFree — Formation, StatePortalConfig, FilingSubmission, ComplianceCalendar. Distill — Firm, Client, Partner, BulkUpload.

**Form coverage (Jan 2027 launch)**: 1040 + Schedules 1, B, C + 1099-NEC/INT/DIV + dependents + ALL 50 state returns. Covers ~80% of US filers. Schedule A/D mid-season (Feb 2027). Business returns (1065, 1120-S) Year 2.

**Partnership milestones**: Self-serve affiliate apps (Apr), Column Tax demo (May), sandbox (Jun), RA wholesale (Jul), DCIS credentials (Apr), Stripe Issuing (May), TaxAudit (Sep), banking partner (Oct).

**Valuation scenarios** (marketplace-stage): A Seed 5K users $75K-325K. B Traction 25K $1.5M-4M. C Growth 50K $7.5M-20M. D Scale 200K $64M-96M. Cost structure advantage: profitable at Scenario A ($65K).
