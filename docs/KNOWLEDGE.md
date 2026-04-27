---
owner: ea
last_reviewed: 2026-04-26
doc_kind: reference
domain: personas
status: active
---
# Paperwork Labs — Knowledge Base

Organizational memory for Paperwork Labs (FileFree, LaunchFree, Distill, Trinkets). AI agents read this at session start. Update after significant decisions, learnings, or pattern discoveries.

**Last Updated**: 2026-04-26
**Version**: 10.8 (D90 — Medallion 0.D strict import gate)

---

## Front and Center — Pending / Open Items

### Must-Act-On

- **D29 — Brand assets**: Ideogram v3 wordmark + Figma/Canva monogram still needed for all products
- **D37 — Domain migration**: filefree.tax → filefree.ai redirect not yet configured
- **D56 — Shared auth**: Basic Auth is interim; `packages/auth/` with Auth.js v5 migration pending
- **D62 — Reliability patterns**: Idempotency, circuit breakers, dual-path reconciliation, OpenTelemetry, k6 load tests must ship in Phase 7 (P7.18-P7.22) before January 2027
- **Q3 — Column Tax**: Demo call + pricing + sandbox access needed by September 2026

### Should-Track

- **Q1 — OCR accuracy**: Cloud Vision + GPT-4o-mini on real W-2s is UNVALIDATED. Test with 20+ real W-2s in Sprint 2.
- **D25 — Legal review**: Privacy/Terms pages need counsel review before January 2027
- **D34 — n8n credentials**: RESOLVED (D80). All credentials in n8n UI + wired to container env vars for Code nodes.
- **D24 — Sentry**: Error tracking not yet integrated (PostHog analytics is live)
- **UI components**: Evaluate PrismUI / SmoothUI for pre-built animated shadcn components when building product UIs (Phase 2+). Current stack: framer-motion + tailwindcss-animate.

### Open Architecture Questions

- **Q2 — Render 512MB**: Monitor memory under tax season load. Upgrade trigger: sustained >80%
- **Q4 — Postiz MCP**: Test MCP vs REST API reliability on self-hosted Postiz
- **Q5 — Origin Financial**: Monitor competitive threat. Revisit SEC RIA at 100K+ users
- **Q6 — April Tax**: Evaluate as Column Tax alternative for interim e-file partnership

---

## Archived Decisions Index (D1–D30, D36)

Full text in [docs/archive/KNOWLEDGE-ARCHIVE.md](archive/KNOWLEDGE-ARCHIVE.md).

| D# | Summary | Date |
|----|---------|------|
| D1 | PaddleOCR → Cloud Vision for OCR | 2026-03-09 |
| D2 | Railway → Render for backend hosting | 2026-03-09 |
| D3 | Render Standard → Starter ($7/mo, 512MB) | 2026-03-09 |
| D4 | Own IRS MeF Transmitter as North Star | 2026-03-09 |
| D5 | Column Tax as interim e-file partner | 2026-03-09 |
| D6 | Skip Claude Code, stay on Cursor | 2026-03-09 |
| D7 | GitHub Issues + Projects (not Linear) | 2026-03-09 |
| D8 | Tiered OCR architecture (3 tiers) | 2026-03-09 |
| D9 | Docker Compose dev-only, managed prod | 2026-03-09 |
| D10 | Self-host Postiz + n8n on Hetzner | 2026-03-09 |
| D11 | Postiz only (no Buffer) | 2026-03-09 |
| D12 | TikTok Spark Ads + Meta Boost (tax season) | 2026-03-09 |
| D13 | n8n as persona automation layer | 2026-03-09 |
| D14 | Revenue: refund-moment monetization | 2026-03-09 |
| D15 | Tax Optimization Plan $29/yr | 2026-03-09 |
| D16 | Co-founder: Product/Eng + Partnerships | 2026-03-09 |
| D17 | Tiered partnership strategy | 2026-03-09 |
| D18 | Docker dev environment complete | 2026-03-09 |
| D19 | Project structure cleanup | 2026-03-09 |
| D20 | Multi-persona review + ops stack | 2026-03-09 |
| D21 | Production infrastructure complete | 2026-03-09 |
| D22 | Auth: Google One-Tap + Apple + email | 2026-03-09 |
| D23 | Sprint 1 complete | 2026-03-09 |
| D24 | PostHog analytics foundation | 2026-03-10 |
| D25 | Legal pages live (needs counsel review) | 2026-03-10 |
| D26 | Agent autonomy: n8n workflows wired | 2026-03-10 |
| D27 | TASKS.md v8 checkbox overhaul | 2026-03-10 |
| D28 | Temporal: PostgreSQL → Elasticsearch | 2026-03-10 |
| D29 | Brand assets removed (pending regen) | 2026-03-10 |
| D30 | Postiz MCP activated | 2026-03-10 |
| D36 | ~~Wyoming LLC~~ → SUPERSEDED by D54 (CA) | 2026-03-12 |

---

## Active Decisions

### D31 — n8n Database Isolation (2026-03-10)
- **Decision**: Separate `n8n` database on existing PostgreSQL. Postiz Prisma migrations were overwriting n8n tables.

### D32 — Frontend Auth + Protected Routes (2026-03-10)
- **Decision**: Zustand auth store, React Query hooks, register/login pages with Zod validation, Next.js middleware for route protection, 30-min idle timeout.

### D33 — Sprint 3 Complete + OAuth + Demo Refund Estimate (2026-03-11)
- **What shipped**: Full filing flow, tax calculator (integer cents, 4 statuses, 7 brackets, 100% coverage), Google + Apple Sign In, 127 tests. Monthly burn: $12.49/mo.

### D34 — Centralized Config + Credential Safety (2026-03-08)
- **Decision**: Zod-validated config modules (server-config.ts, client-config.ts). Credential registry in CREDENTIALS.md. Gitleaks in CI. n8n workflows re-imported (inactive, pending credential setup).

### D35 — Venture Master Plan v1 (2026-03-12)
- **Decision**: Single authoritative master plan. pnpm monorepo. Federated identity. 50-state data pipeline. 30+ AI agents.

### D37 — Domain Strategy: .ai Brand Family (2026-03-12)
- **Decision**: Purchased launchfree.ai + filefree.ai. Migrate filefree.tax → filefree.ai. Pattern: [product]free.ai.

### D38 — Trinkets Product Line + Agent Pipeline (2026-03-12)
- **Decision**: "Trinkets" = client-side utility tools. 3-stage Trinket Factory agent pipeline. Phase 1.5 in execution plan.

### D39 — AI Model Routing: 9 Models, 7 Roles (2026-03-12)
- **Decision**: Systematic routing owned by AI Ops Lead persona. Gemini 2.5 Flash default. Claude Sonnet for code/compliance. GPT-4o for creative.

### D40 — AI Operations Lead Persona (2026-03-12)
- **Decision**: `agent-ops.mdc` owns model routing, cost monitoring, persona audits, new model evaluation.

### D41 — RA Pricing: Wholesale Volume Tiers (2026-03-12)
- **Decision**: CorpNet volume pricing. $99/yr → $79 at 500+ → $49 at 1,000+ users.

### D42 — Agent Org Chart: Full Company from Day One (2026-03-12)
- **Decision**: All 44 agents defined. Active/Standby/Planned status. Governance protocol with APPROVE/CONCERN/BLOCK verdicts.

### D43 — All 50 States + Major Schedules at Launch (2026-03-12)
- **Decision**: January 2027: 1040 + Schedule 1/B/C + 1099-NEC/INT/DIV + dependents + ALL 50 state returns.

### D44 — Quality-First AI Model Philosophy (2026-03-12)
- **Decision**: Use BEST model for the task. Only downgrade when cheaper produces EQUIVALENT quality.

### D45 — Founder 2: Outcome-Driven (2026-03-12)
- **Decision**: No time-commitment specs. AI handles prep, Founder 2 does what requires a human.

### D46 — AI Branding: Outcomes Over Technology (2026-03-12)
- **Decision**: Lead with "free, 5 minutes, accurate." Mention AI only to explain WHY, never as headline.

### D47 — Slack as Agent Hub (2026-03-12)
- **Decision**: Slack as central company hub with functional channels. n8n posts to channels. Google Workspace email aliases.

### D48 — Side Projects: ReplyRunner/FittingRoom NO-GO (2026-03-12)
- **Decision**: Axiomfolio and Jointly DEFER to Year 2+. ReplyRunner and FittingRoom NO-GO.

### D49 — MeF Local Validation Engine (2026-03-12)
- **Decision**: Local XML validation engine BEFORE ATS submission. IRS schemas from irs.gov. States piggyback on federal.

### D50 — Self-Serve Affiliates as Plan B Revenue (2026-03-12)
- **Decision**: Most fintech affiliate programs are self-serve (Impact.com, CJ). Founder 1 applies in Phase 0.

### D51 — Tiered State Tax Engine (2026-03-12)
- **Decision**: Tier 1 (~30 conforming): JSON config. Tier 2 (~12 semi): config + modifiers. Tier 3 (~5 independent: CA, NJ, PA, MA, NH): custom modules.

### D52 — Doc Hygiene: Anti-Bloat Rules (2026-03-12)
- **Decision**: Collapse completed phases. Rotate KNOWLEDGE.md every 6 months. Archive superseded docs. Master plan target: under 3,500 lines.

### D53 — Alert Routing: Slack Not Discord (2026-03-12)
- **Decision**: All alerts route through Slack. Discord references removed.

### D54 — LLC Name: Paperwork Labs LLC, California (2026-03-12)
- **Decision**: Register as "Paperwork Labs LLC" in California. Domain: paperworklabs.com. Zero trademark risk. Supersedes D36 (Wyoming).

### D55 — Command Center: paperworklabs.com (2026-03-12)
- **Decision**: Move command center to paperworklabs.com. Founder's personal site separate.

### D56 — Auth Architecture: Admin Allowlist (2026-03-12)
- **Decision**: Basic Auth on Studio `/admin` while shared auth package migration is pending. Target: `packages/auth/` with Auth.js v5. Updated per D76: 1 Workspace seat, Olga via personal email.

### D57 — Trinkets Domain: tools.filefree.ai (2026-03-12)
- **Decision**: Subdomain inherits parent authority. Graduation at 10K monthly visits.

### D58 — PostHog-First Experimentation (2026-03-13)
- **Decision**: Phase 1: PostHog feature flags. Phase 2: Thompson Sampling bandit. Phase 3: ML collaborative filtering.

### D59 — Data Intelligence from Day One (2026-03-13)
- **Decision**: Full Data Intelligence layer. Track KPIs from day one. Lifecycle campaigns via n8n. ChurnGuard AI at Phase 2.

### D60 — Credit Score: Phase 1.5 (2026-03-13)
- **Decision**: Soft pull via TransUnion reseller (Array/SavvyMoney, $0.50-2.00/pull). FCRA compliance review ($500-1K).

### D61 — Package Rename: cross-sell → intelligence (2026-03-13)
- **Decision**: `packages/intelligence/` replaces `packages/cross-sell/`. Modules: profile builder, partner matcher, experimentation, data intelligence, campaign triggers.

### D62 — Reliability Architecture: 5 Must-Haves (2026-03-13)
- **Decision**: Idempotency keys, circuit breakers, dual-path reconciliation, OpenTelemetry tracing, k6 load testing. Phase 7 (P7.18-P7.22).

### D63 — Adjacent Revenue: 3 Tier 1 Extensions (2026-03-13)
- **Decision**: (1) Compliance-as-a-Service $49-99/yr, (2) Quarterly Tax Estimator, (3) Refund Splitting + Goal-Based Savings.

### D64 — Dual-Path Tax Calculation Reconciliation (2026-03-13)
- **Decision**: Every return runs forward + reverse verification. Delta > $1 flags for review. Nightly batch reconciliation.

### D65 — Financial Marketplace: 4-Stage Evolution (2026-03-14)
- **Decision**: Stage 1 (affiliate, 0-5K), Stage 2 (smart matching + Fit Scores, 5K-25K), Stage 3 (partner API + auction CPA, 25K-50K), Stage 4 (full marketplace, 50K+). Architecture designed for Stage 4 from day 1.

### D66 — Strategic-from-Day-1 Architecture (2026-03-14)
- **Decision**: Six foundational components designed for full marketplace end-state: data model, recommendation engine, event taxonomy, consent architecture, partner dashboard, PARTNERSHIPS.md tiers.

### D67 — Business Tax Filing: 1065 + 1120-S (2026-03-16)
- **Decision**: Phase 10 (Year 2). $49/return (1065), $99/return (1120-S). First business return free for LaunchFree LLC formers.

### D68 — Scale Growth Playbook: 4 Channels (2026-03-16)
- **Decision**: (1) Tax Season Surge, (2) B2B API Distribution, (3) Community-Led Growth, (4) B2B CPA Outreach. Path to 2M users by Year 5.

### D69 — Distill: B2B Tax Automation (2026-03-16)
- **Decision**: distill.tax as separate B2B brand. CPA SaaS ($49-199/mo) + Tax API. Shares OCR pipeline with FileFree.

### D70 — Package Split: data/ → data/ + tax-engine/ + document-processing/ (2026-03-16)
- **Decision**: Three packages with different ownership cycles. `packages/tax-engine/` is the independently testable core.

### D71 — Distill: Separate B2B Brand (2026-03-16)
- **Decision**: "Distill" = extract pure essence. Consumer "Free family" + B2B "Distill" under Paperwork Labs umbrella.

### D72 — State Filing Engine: 3-Tier Architecture (2026-03-16)
- **Decision**: Tier 1 (state APIs), Tier 2 (Playwright portal automation), Tier 3 (print-and-mail via Lob). Stripe Issuing for payments.

### D73 — "Paperwork Labs" Naming Everywhere (2026-03-16)
- **Decision**: Standardize company name across all docs, personas, README, agent context.

### D74 — Distill Accelerated to Summer 2026 (2026-03-16)
- **Decision**: All Distill products (CPA SaaS, Formation API, Tax API, Compliance API) pulled to Summer 2026. Runs parallel with Phases 5-6.

### D75 — Agent-Driven Operations Model (2026-03-16)
- **Decision**: n8n auto-detects 50-state data changes. Playwright portal health checks. Cursor agents handle maintenance. Filing Engine hourly status checks.

### D76 — Google Workspace: 1 Seat + Aliases (2026-03-16)
- **Decision**: 1 seat ($6/mo). Primary: paperworklabs.com. Alias domains: filefree.ai, launchfree.ai, distill.tax. Olga via personal email + ADMIN_EMAILS.

### D77 — Repo Migration + Docs Audit (2026-03-16)
- **Milestone**: Repo moved to `paperwork-labs/paperwork`. Full docs audit: URLs, emails, burn rate updated.

### D78 — Hetzner Transfer + Slack-First n8n (2026-03-17)
- **Decision**: Server transferred to Paperwork Labs billing. 5 new Slack-first workflows. All 6 existing workflows updated. AGENTS.md added.

### D79 — AI Advisory + Internal Animation Primitives (2026-03-18)
- **Decision**: Lightweight advisory baseline (`/api/advisory` + `/advisory` playground). Internal framer-motion primitives over third-party animation kits.

### D80 — Infra Observability System + Credential Wiring (2026-03-18)
- **Decision**: Implemented 5-layer Slack-first observability: Layer 0 (native GitHub/Vercel/GDrive Slack apps), Layer 1 (deploy-time verification with Slack notifications), Layer 2 (n8n self-health check every 30min), Layer 3 (external GH Action canary every 6h), Layer 4 (daily briefing infra section). Auto-deploy n8n workflows via GitHub Action on merge to main. Wired n8n credentials (GitHub PAT + Slack Bot Token) to container env vars for Code node access. Infra score: ~90%. Remaining gaps: domain DNS (filefree.ai, launchfree.ai), LLC/EFIN business blockers. Ready for Phase 2.
- **Alternatives**: Datadog/PagerDuty (overkill + expensive), single-layer alerting (too fragile), manual checks (what we were doing — failed silently).
- **Reversibility**: Fully reversible — each layer is independent.

### D81 — Vault-First Credentials + P2.3/P2.4 State Data (2026-03-19)
- **Decision**: Studio Secrets Vault is the **canonical** store for API keys and credentials. Agents and scripts use `./scripts/sync-secrets.sh` → `.env.secrets` (or `./scripts/vault-get.sh NAME`); Bearer `SECRETS_API_KEY` is primary auth, **Basic Auth** (Studio admin) is fallback when local Bearer is stale. Extraction scripts load `.env.secrets` via `dotenv` (shell `source` breaks on `&` in values). Documented in `.cursor/rules/secrets-ops.mdc`. Completed AI extraction of **51 jurisdictions** tax + formation JSON into `packages/data` (DC tax uses Tax Foundation state rates page; formation uses `ai_extraction_fallback` when SOS sites block bots — P2.5 human review required for those rows).
- **Alternatives**: Only Vercel env / only n8n UI credentials (fragmented); committing keys (never).
- **Reversibility**: Vault remains source of truth; local files gitignored.

### D82 — Six-Layer Data Quality Strategy (2026-03-19)

**Context**: AI extraction of 50-state tax data for TY2024-2026 produced unit conversion errors (dollars stored as cents, basis points off by 10-100x). Oklahoma rates were completely fabricated. Idaho rate was 10x too high.

**Decision**: Implement defense-in-depth with 6 layers:
1. **Extraction guardrails**: Better prompts with unit examples
2. **Range checks** (P2.5 review CLI): rate_bps ≤ 1500, deductions ≥ $1K, exemptions ≥ $100
3. **Cross-year consistency** (P2.7+): Advisory warnings when rate delta > 200 bps or deduction change > 25%. Hard fail at catastrophic thresholds (rate delta > 1000 bps, deduction change > 1000%).
4. **Known-good anchors** (P2.7+): Hardcoded expected values for CA, TX, CO, NY, OK, IL, GA, ID — canary tests that fail immediately if extraction drifts.
5. **External cross-validation** (P2.8-P2.10): n8n workflows scraping Tax Foundation and state DOR sites for automated comparison.
6. **Human review gate**: `pnpm review:approve` refuses to stamp data unless all checks pass.

**Alternatives**: (a) Manual CPA review of all 153 JSONs — doesn't scale, (b) Only range checks — misses plausible-but-wrong values like OK at 8% vs correct 4.75%.

**Reversibility**: Fully reversible. Test thresholds can be adjusted. Anchor values can be updated with legislation changes.

### D83 — Deterministic Data Over AI Extraction (2026-03-19)

**Context**: AI extraction of 50-state tax data (TY2024-2026) produced widespread errors — wrong rates (MO 250 bps vs correct 495), missing brackets (NY 6.85% vs correct 10.9%), wrong tax types (ID listed as progressive, actually flat since 2023), hallucinated standard deductions (GA $12K vs correct $5.4K). Root cause: for TY2024/2025, the extraction script fetched only the Tax Foundation **aggregate** rates page (a summary table with top marginal rates only), and GPT hallucinated bracket data, standard deductions, and filing-status breakdowns from insufficient context.

**Discovery**: Tax Foundation publishes **structured HTML tables** with exact rates, brackets (single + MFJ), standard deductions, and personal exemptions for all 51 jurisdictions, for every tax year. This data is deterministically parseable — no AI needed for core fields.

**Decision**: Replace AI-dependent extraction with **deterministic parsing** for all compliance data:

- **Tax data**: Parse Tax Foundation HTML tables directly in TypeScript. Unit conversion (`$` → cents, `%` → bps) in code, not by AI. AI only used for supplementary fields TF doesn't publish (notable credits/deductions, local tax details, reciprocity).
- **Formation data**: Parse aggregated fee tables (worldpopulationreview.com, chamberofcommerce.org) for numeric fields (filing fees, annual report fees). AI extraction only for non-numeric fields (naming rules, filing methods, RA requirements) from individual SOS sites — these are strings/booleans, not unit-conversion-prone numbers.
- **Principle**: Authoritative structured sources over AI extraction for compliance data. AI fills gaps only. The data layer should be rock-solid infrastructure, not probabilistic output.
- **Implication for Distill**: Raw data was never the product. The product is computation (tax engine), automation (State Filing Engine), and compliance infrastructure (monitoring, e-file). This realization sharpens Distill's value proposition.

**Supersedes**: D82's Layer 1 ("better prompts") is replaced by "no AI in the core data path." Layers 2-6 (range checks, cross-year, anchors, monitoring, human review) still apply as defense-in-depth.

**Alternatives**: (a) Re-extract with better AI prompts — still probabilistic, ~96-98% ceiling, (b) Manual CPA review — doesn't scale, (c) Deterministic parse + AI only for gaps — chosen, ~99.9% for core fields.

**Reversibility**: Fully reversible. AI extraction scripts remain in repo for supplementary data and fallback.

**Status**: SUPERSEDED by D84 — all supplementary data now also deterministic. Zero AI extraction paths remain.

### D84 — 100% Deterministic Data Pipeline, Zero AI (2026-03-20)

**Context**: D83 replaced AI extraction for core tax/formation data but preserved AI-extracted supplementary fields (DOR URLs, local tax flags, reciprocity agreements, personal exemption phase-outs) from old JSONs. The founder's directive: "build as if this was the first time" — no AI inheritance.

**Decision**: Eliminate all AI-extracted data. Every field in every JSON is now sourced from either a deterministic parser or a curated constant map.

**Tax data** (153 JSONs across TY2024-2026):
- Core fields (brackets, rates, deductions, exemptions): Tax Foundation XLSX — deterministic parse
- DOR URLs: Curated `DOR_URLS` map (51 official state revenue department URLs)
- Local income tax: Curated `LOCAL_INCOME_TAX_STATES` set (15 states, sourced from Tax Foundation + FTA)
- Reciprocity: Curated `RECIPROCITY_MAP` (16 states with specific state-pair lists, sourced from FTA + state DOR)
- Personal exemption phase-outs: Curated `PERSONAL_EXEMPTION_PHASES_OUT` set (5 states: CA, CT, NY, OR, RI)
- Implicit 0% brackets: Explicitly added for states where first bracket starts above $0 (DE, MO, ND, OK, ID, MS)

**Formation data** (51 JSONs):
- Filing fees, annual fees, deadlines, processing times, publication: llcrequirements.com HTML table
- Franchise tax: discern.com HTML table
- Filing offices, SOS URLs: Source registry + curated overrides (AZ=ACC, DE=Division of Corps, etc.)
- Operating agreements, naming rules, RA requirements: Curated constants

**What was deleted**:
- `extract-tax.ts`, `extract-formation.ts`, `extract-utils.ts`, `parse-formation-fees.ts` — all AI extraction scripts
- `openai` and `dotenv` from devDependencies
- All existing-JSON fallback logic from `parse-tax-foundation.ts`
- `ai_extraction` and `ai_extraction_fallback` enum values → renamed to `sos_extraction` / `sos_extraction_unverified`

**Verification**: 4-persona review (Engineering, Tax Domain, CPA, QA) — all PASS. 1,757 tests pass. Zero `ai_extraction` strings remain in `packages/data/`.

**Maintenance model**: `pnpm parse:tax` + `pnpm parse:formation` are idempotent scripts. n8n `data-source-monitor` watches Tax Foundation, llcrequirements.com, and discern.com for changes. When a source updates: re-run parser, review diff, commit. No AI drift to worry about.

**Supersedes**: D83 (which still used AI for supplementary fields). D82 Layers 2-6 still apply as defense-in-depth.

### D85 — MCP-First Brain Architecture (2026-03-29)

**Context**: Brain API needed tool execution capabilities (GitHub, infra health, AxiomFolio trading, memory). Two approaches: build our own iterative agent loop with native tool_use, or expose tools as an MCP server and let LLM providers handle the loop.

**Decision**: MCP-first architecture. Brain exposes 22 tools via FastMCP at `/mcp`. Anthropic's MCP Connector and OpenAI's Responses API MCP connect server-side, discovering and executing tools iteratively without our code managing the loop. Combined with ClassifyAndRoute (D20) for multi-provider model routing via Gemini Flash classification, circuit breaker (D38) per provider, and constitutional safety checks (D37).

**Alternatives Considered**:
1. Native tool_use with client-side dispatch loop — rejected: 3x more code, we manage iteration/parsing, provider-locked
2. LangChain/LlamaIndex frameworks — rejected: adds abstraction layer, vendor lock-in, overhead for our use case
3. Deferred tool execution to Phase 3 — rejected: user requested tools from day one

**Reversibility**: Medium. MCP is an open standard with growing adoption. The tool implementations are provider-agnostic Python functions. If MCP support degrades, we can wrap them in native tool_use with ~2 days of work.

**Impact**: Reduces Brain API code by ~60% vs native loop. Enables multi-provider routing (Anthropic + OpenAI + Gemini). Makes Brain itself a potential MCP server for Distill B2B API.

### D86 — Secret Rotation + Credential Expiry Tracking (2026-03-29)

**Context**: PR #66 rewrote `scripts/populate-vault.sh` to read from `.env.secrets` instead of hardcoding values. However, 23 secrets were already exposed in git history (commits `4b30760`, `af1264e`) with actual values: OpenAI API key, Slack bot token, GitHub PATs, Hetzner passwords, n8n credentials, Postiz JWT, admin password.

**Decision**: Rotate all exposed credentials immediately. Track expiry dates in the vault and TASKS.md. BFG-scrub git history after all rotations complete.

**Rotated so far** (2026-03-29):
- OpenAI API key → new key, updated in vault + Render (brain-api) + GitHub Actions
- GitHub PAT (fine-grained) → "Paperwork Labs Vault" PAT, expires **2026-06-27**, updated in vault + Render (brain-api GITHUB_TOKEN) + GitHub Actions (as GH_PAT_FINEGRAINED — `GITHUB_` prefix reserved by Actions)
- Slack app credentials captured in vault (signing secret, client secret, verification token, app ID, client ID, workspace token)

**Rotated 2026-03-29 (session 2)**:
- Vercel API token → "Infra Health Checks" (Full Account), expires **2026-09-25**
- Studio admin password → updated on Vercel
- All 7 n8n credentials updated via API (2x OpenAI, 2x GitHub, 3x Slack) with new keys
- Vercel Studio env vars updated: ADMIN_ACCESS_PASSWORD, GITHUB_TOKEN
- Render brain-api `VERCEL_API_TOKEN` set

**Still needs rotation** (exposed values still active):
- Hetzner postgres/Redis passwords — run `./scripts/rotate-hetzner-creds.sh` on VPS
- n8n admin password + encryption key — included in Hetzner rotation script
- Postiz JWT secret — included in Hetzner rotation script
- **BLOCKER**: Hetzner qemu-guest agent not running. Password resets fail silently. Must use Rescue Mode (Hetzner dashboard → Rescue tab → Enable rescue & power cycle) to regain SSH access first.
- Slack bot token — reinstall didn't regenerate (Slack keeps token when scopes unchanged). BFG scrub will remove from history.
- Slack alerts webhook URL — replaced with new one, old still in git history

**Credential Expiry Tracking** (implemented 2026-03-29):
- Vault model supports `expires_at` and `last_rotated_at` fields
- `populate-vault.sh` parses `# Expires: YYYY-MM-DD` comments from `.env.secrets`
- Brain job `brain_credential_expiry` (gated by `BRAIN_OWNS_CREDENTIAL_EXPIRY`, export in `infra/hetzner/workflows/retired/credential-expiry-check.json`) runs daily at 8am PT, queries vault, alerts to `#alerts`
- Tiered urgency: 30-day notice → 14-day warning → 7-day urgent → 1-day critical

**Credential Expiry Dates**:
- GitHub PAT "Paperwork Labs Vault": **2026-06-27** (rotate by Jun 13)
- Vercel API token "Infra Health Checks": **2026-09-25** (rotate by Sep 11)
- Slack Expiring Client Secret: **2026-03-30** (auto-revokes, non-critical)

**Alternatives**: Considered ignoring (repo is private, 2-person team) — rejected. These are production credentials for services handling financial data. Even in a private repo, leaked keys can be extracted from cloned copies.

**Reversibility**: N/A (security hygiene, not an architectural decision).

### D87 — Vault Architecture Audit + Security Fix (2026-03-29)

**Context**: Audit of vault architecture revealed two systems: Studio Vault (company ops, live) and Brain UserVault (per-user, stub). Found critical security issue and architectural confusion.

**Findings & fixes**:
1. **CRITICAL FIX**: `GET /api/admin/secrets/[id]` had zero authentication — anyone guessing a UUID could read plaintext secrets. Added `authenticateSecretsRequest` auth check. The regular `/api/secrets/[id]` route was already authenticated; the admin route was a copy that missed it.
2. **`vault_set` exposed on MCP**: Brain could read vault via MCP tools (vault_list, vault_get) but not write. Added vault_set as Tier 2 write action per D61 design.
3. **Migration drift fixed**: `brain_user_vault` DDL in 001_initial_schema.py had column mismatches vs architecture doc (Section 2) and SQLAlchemy model. Fixed: SERIAL→BIGSERIAL, added description/expires_at/last_rotated_at columns, removed spurious updated_at, added UNIQUE constraint and index.

**Architecture decision (two vaults are correct)**:
- **Studio Vault** = Paperwork Labs company password manager (60 secrets, AES-256-GCM, flat single-tenant). Stays forever as the Super Brain's infrastructure vault.
- **Brain UserVault** (`brain_user_vault`) = per-user/per-org encrypted secret store (D61). Scoped by `(user_id, organization_id, name)`. Designed for when org brains need per-user credentials (Plaid OAuth, bank connections). Currently a stub — keep schema, implement services/routes when Distill org brains are real.
- **Brain vault tools** (vault_list/get/set) currently read/write Studio Vault via HTTP. This is a valid Phase 1 shortcut (founders' vault = company vault). In P2+, add separate user_vault tools for `brain_user_vault`.
- **`packages/vault`** TypeScript client: well-written but unused. Keep for future Studio dashboard consumers.

**Alternatives**: Considered merging into one vault — rejected. Different access patterns (flat company secrets vs multi-tenant user secrets), different auth models, different lifecycle.

**Reversibility**: Fully reversible. The admin auth fix is a one-line addition. vault_set can be unregistered. Migration changes are pre-production.

### D88 — Brain Baseline Audit: 7 Critical Issues Found (2026-03-29)

**Context**: After deploying the Brain (Phase 11), the first Slack dogfooding session revealed the Brain couldn't answer basic project status questions. A holistic audit of Brain code vs BRAIN_ARCHITECTURE.md uncovered 7 critical issues.

**Decision**: Fix all 7 issues in a single "Brain baseline fixes" PR before proceeding with Phase 12 n8n conversions:
1. D13 violation — persona .mdc content not loaded into prompts (only name injected)
2. Duplicate request returns visible "[Duplicate request]" message to Slack
3. Channel-based persona routing is absolute (overrides content signals)
4. Classifier marks status/progress queries as "simple" → disables tools
5. CHANNEL_PERSONA_MAP missing 6 of 12 channels
6. seed_knowledge.py defaults skip_embedding=True → vector search non-functional
7. System prompt tells Brain "no context" but doesn't guide it to use tools

**Alternatives**: Could have fixed incrementally, but these are all interconnected (Brain is non-functional without the ensemble).

**Reversibility**: Fully reversible (code changes only, no data migration).

### D90 — Medallion Phase 0.D: architecture enforced in CI (2026-04-26)

**Decision**: Medallion import layering is **strict by default** (`python scripts/medallion/check_imports.py --app-dir … --strict`). Cross-layer imports that remain intentional use `# medallion: allow …` with a one-line rationale at the import site. Inherited Wave 0.C placeholder waivers are drained: account config/credentials helpers are tagged `ops` where they are cross-tenant infrastructure; Stage Analysis `compute_position_size` lives in `app/services/gold/position_sizing.py` so gold does not depend on `execution/` for that math; `app/services/__init__.py` carries no D88-era re-export shims.

**Rationale**: Without a hard gate, medallion drifts as soon as new broker or strategy code ships; strict mode plus explicit allow lines make exceptions reviewable in PRs.

**Reversibility**: Re-enable `--warn-only` locally for spelunking; do not use in CI.

---

## Open Questions

### Q1: Cloud Vision + GPT-4o-mini W-2 Accuracy (UNVALIDATED)
Test with 20+ real W-2s. If accuracy < 95%, increase GPT-4o vision fallback usage.

### Q2: Render Starter 512MB Under Load
Monitor during beta. Upgrade trigger: sustained >80% memory utilization.

### Q3: Column Tax SDK Availability and Pricing
Book demo call. Target: $10-15/return. Sandbox access needed by September 2026.

### Q4: Postiz MCP Reliability
GitHub issues #846, #984 report MCP failures. Fallback: REST API.

### Q5: Origin Financial — Competitive Threat (HIGH)
VC-backed, ~100K users, SEC RIA, AI tax filing via April Tax. But: charges $12.99/mo vs our free; no LLC product; no B2B play. Strategy: own "free tax filing" and "free LLC" categories. Revisit RIA at 100K+ users.

### Q6: April Tax as Column Tax Alternative
AI-native tax infrastructure, IRS-authorized transmitter, powers Origin's 100K users. Evaluate as interim partner. Does NOT change MeF transmitter north star (D4).

---

## Decision Log (2026-04-25)

Date: 2026-04-25
Decision: Adopt Clerk via Vercel Marketplace as the unified identity provider across FileFree, LaunchFree, Studio admin, Distill, and AxiomFolio (after Next.js migration). Start on Free tier (10K MAUs).
Context: Multiple products today have separate auth: FileFree uses Redis-backed opaque sessions, AxiomFolio uses qm_token JWTs in localStorage, Studio uses HTTP Basic. No cross-product session sharing. User wants "LaunchFree user logs into FileFree without re-registering" experience.
Alternatives: (a) DIY unified-cookie SSO via shared *.paperworklabs.com cookie + custom JWT issuer in Brain, (b) NextAuth.js self-hosted, (c) Auth0, (d) Defer SSO indefinitely.
Rationale: Clerk Marketplace auto-provisions env vars to all linked Vercel projects (saves ~2 days of integration work). Free tier is generous (10K MAUs). Embedded `<SignIn>` + Appearance API allows per-product gradient theming (FileFree violet, LaunchFree teal, Distill blue-slate). Native cross-origin session works. Vercel handles billing.
Reversibility: Medium. Clerk JWTs are standard JWS, verifiable against any JWKS endpoint, so AxiomFolio API verifier code is portable. UI components (`<SignIn>` etc.) are Clerk-specific; replacing them on a frontend would require rewrite. Migration off Clerk would take 2-3 sprints.

---

Date: 2026-04-25
Decision: Brain APScheduler becomes the single owner of all scheduled work; n8n becomes webhook/event-only. APScheduler must use SQLAlchemyJobStore for restart-safe persistence.
Context: Today both n8n (10 cron workflows) and Brain (3 APScheduler jobs) run scheduled work. Duplicate Slack noise, two places to debug, two places to update when a schedule changes. Persona vocabulary forks across the two systems.
Alternatives: (a) Keep dual orchestrators with strict ownership boundaries documented, (b) Move everything to n8n (hide Brain APScheduler entirely), (c) Status quo.
Rationale: Brain already owns persona routing, model selection, memory, and PII scrubbing. Moving crons to Brain colocates "what runs and when" with "what model and which persona." Cuts Slack noise, single place to debug. n8n's strength is visual webhook/event flows — keep it for those. SQLAlchemyJobStore against Postgres makes Brain restart-safe (n8n queue mode equivalent).
Reversibility: Medium. Cron jobs are small Python files; if APScheduler proves unreliable in production we can move them back to n8n in ~1 day. Job state is in Postgres; migration script could lift them.

---

Date: 2026-04-25
Decision: PersonaSpec slugs (the 16 specs in apis/brain/app/personas/) become the only persona identifier across all systems. Studio WORKFLOW_META role labels, system-graph.json owner_persona fields, and n8n persona_pin values must use spec slugs verbatim. CI gate enforces this.
Context: Today persona vocabulary is fragmented across four sources: 16 Brain PersonaSpecs (production runtime), 48 .mdc files in .cursor/rules/ (which conflate personas with 32 IDE/CI guardrails), informal WORKFLOW_META role labels (e.g., "Intern", "Creative Director"), and sparse persona_pin values in n8n. User confused about whether everything flows through Brain personas (it doesn't yet — many n8n workflows skip Brain).
Alternatives: (a) Keep WORKFLOW_META labels as a Studio-only display convention, (b) Status quo with documentation, (c) Map labels to slugs but allow both.
Rationale: Removes drift. If a workflow says "growth" and Brain has a "growth" PersonaSpec, the link is unambiguous. CI can enforce. Studio displays the same name everywhere. Eliminates the four-source confusion.
Reversibility: Easy. Renaming labels is mechanical; if user-facing labels need to differ from internal slugs we can add a label field to PersonaSpec.

---

Date: 2026-04-25
Decision: Enable SQLAlchemyJobStore in Brain APScheduler (Postgres, table `apscheduler_jobs`) and ship opt-in n8n cron shadow jobs (`SCHEDULER_N8N_MIRROR_ENABLED`, default off) posting only to `#engineering-cron-shadow`.
Context: The earlier same-day decision set Brain as the single cron owner, but the codebase still used the in-memory default job store. Restarts on Render would drop the in-process schedule until the process re-registered jobs; ops wanted parity with a durable queue.
Alternatives: (a) Only document "scheduler restarts = benign," (b) Redis job store, (c) external cron hitting HTTP.
Rationale: The app already has Postgres; `SQLAlchemyJobStore` is one import and a sync URL (`postgresql://` from `DATABASE_URL` with `+asyncpg` stripped). Shadow mirrors validate cadence before T2.4 n8n disable. `psycopg2-binary` supplies the sync driver for the job store engine.
Reversibility: Easy. Set job store back to default (dev-only) or clear `apscheduler_jobs` if a bad migration; mirrors are off by default.

