---
owner: strategy
last_reviewed: 2026-04-25
doc_kind: plan
domain: company
status: active
---
# Paperwork Labs — Venture Master Plan v1

**Date**: March 12, 2026 (last meaningful refresh) | **Supersedes**: All prior strategy plans including deep_research_tightening (5 plans archived). The previous standalone summary (archived as `docs/archive/VMP-SUMMARY-2026-03-18.md`) was folded into the **TL;DR** below on 2026-04-25.

---

## TL;DR (compact summary)

> Read this section if you have 5 minutes; the rest is the full strategy at ~3,500 lines. The compact summary used to live in a separate `VMP-SUMMARY.md` so n8n workflows and cheap models could load it cheaply; with the persona platform doing routing centrally that split is no longer needed and the summary is folded back in here.

**Entity**: Paperwork Labs LLC (California). DBAs: FileFree, LaunchFree, Trinkets, Distill.

**Products**:

| Product | Domain | Status | Launch |
|---------|--------|--------|--------|
| FileFree | filefree.ai | In development | January 2027 |
| LaunchFree | launchfree.ai | In development | Summer 2026 |
| Distill | distill.tax | In development | Summer 2026 |
| Trinkets | tools.filefree.ai | Scaffolded | Phase 1.5 |
| Studio / Command Center | paperworklabs.com | Live (Tier 1 complete) | Live |
| AxiomFolio | axiomfolio.com | Absorbed into monorepo 2026-04-23 | Live (Render) |

**Team**: Two co-founders. Founder 1 (product / engineering) owns code. Founder 2 (partnerships / revenue) sources financial-product partnerships.

**Monthly burn**: ~$278/mo. Vercel / Neon / Upstash on free tier until scale triggers.

**North stars**:

- **FileFree** — own IRS MeF Transmitter (January 2027), e-file at $0/return.
- **LaunchFree** — State Filing Engine across all 50 states (Summer 2026), automate LLC formation via state APIs + portal automation + print-and-mail.
- **Distill** — full B2B compliance automation platform (Summer 2026): CPA SaaS + Formation API + Tax API + Compliance API at api.distill.tax.
- **Venture-wide** — shared compliance infrastructure powering both free consumer products and paid B2B APIs. The infrastructure is the product.

**Revenue model**:

- **Consumer (free forever)**: partnership referrals, refund routing, financial-product recommendations, audit shield, Tax Optimization Plan ($29/yr), RA credits (LaunchFree), Compliance-as-a-Service ($49–99/yr). No filing fees from consumers.
- **B2B (Distill)**: CPA SaaS $49–199/mo; Formation API $20–40/filing; Tax API $5–15/return; Compliance API per-action.
- Cost per user: $0.06 (FileFree); ~$0.50/filing (LaunchFree).
- Year-1 projections: pessimistic $15K, moderate $64K, aggressive $264K.
- Plan B: self-serve affiliates (Betterment, SoFi, Wealthfront, Impact.com, CJ) — ~$6.5K–37K Year 1.

**Phase status (Apr 2026)**:

- Complete: Phase 1 (monorepo restructure), Phase 4 Tier 1 (Studio / Mission Control / Agent Monitor / Infra Health).
- In progress: Phase 0 (LLC, EFIN, domain migration, GDrive, social handles, legal setup), Phase 1.5 (Trinket Factory pilot), Phase 2 (50-state data infrastructure).
- Upcoming: LaunchFree MVP, Distill B2B, FileFree season prep / launch, agent restructure + social pipeline. See [TASKS.md](TASKS.md) for the full task breakdown.

**Pre-code blockers**: EFIN application this week (45-day IRS processing); cyber liability insurance ($1M) before first SSN; data breach response plan; 1 hr attorney consult before Phase 3.

**Competitive moat (6 points)**:

1. Proprietary 50-state State Filing Engine (Delaware ICIS API + portal automation + Tier-3 print-and-mail) shared by LaunchFree ($0) and Distill Formation API ($20–40/filing).
2. Cross-product data compound — tax + formation + quarterly estimates → 20+ data-point profile per user; competitors need 2–3 years of build to replicate.
3. Agent-maintained 50-state compliance data — n8n workflows + Brain detect rule changes and update configs; both data layer and maintenance system are proprietary.
4. Cost moat — ~$278/mo burn vs CK's 1,300+ FTE; profitability at Scenario A (~$65K revenue).
5. Retention lock-in — 80 % of tax filers stick with the same software year-over-year (PCMag); capture a 22-year-old, own them 10+ years.
6. B2B distribution flywheel — Distill CPA firms refer to consumer FileFree; consumer users convert to CPA leads. No competitor combines free consumer tax + free LLC formation + B2B CPA + compliance SaaS.

**Tech stack**:

- Frontend: Next.js 14+ App Router · TypeScript strict · Tailwind 4+ · shadcn/ui · Framer Motion · Vercel AI SDK · React Hook Form + Zod · TanStack Query · Zustand. Per-product themes via `[data-theme]`.
- Backend: FastAPI (Python 3.11+) · SQLAlchemy 2 async · PostgreSQL 15+ (Neon) · Redis (Upstash) · Pydantic v2 · Alembic.
- Infra: Vercel (frontend) · Render Starter ×2 (APIs) · GCP (Cloud Vision, Cloud Storage) · Hetzner CX33 (n8n, Postiz, Redis). Zero AWS.
- AI routing: Cloud Vision DOCUMENT_TEXT_DETECTION → GPT-4o-mini structured extraction → GPT-4o vision fallback (<85 % confidence). SSN regex-extracted locally, **never** sent to LLMs. State data: Gemini 2.5 Flash / Pro. Tax verification: o4-mini. Brand / social: GPT-4o. Code / compliance: Claude Sonnet. Authoritative routing: [docs/AI_MODEL_REGISTRY.md](AI_MODEL_REGISTRY.md).
- Monorepo target: `apps/` (filefree, launchfree, distill, studio, trinkets, axiomfolio), `apis/` (filefree, brain, axiomfolio, launchfree-future), `packages/` (ui, auth, analytics, data, tax-engine, document-processing, filing-engine, intelligence, email, pwa).

**Agent architecture**:

- 16 personas in `.cursor/rules/*.mdc` and `apis/brain/app/personas/*.yaml`: ea, engineering, strategy, legal, cfo, qa, partnerships, ux, growth, social, tax-domain, cpa, agent-ops, brand, workflows, infra-ops, git-workflow.
- n8n workflows on Hetzner are now **2-node webhook → brain** wires. Heavy lifting is centralised in Paperwork Brain (persona platform + chain strategies). See [docs/BRAIN_ARCHITECTURE.md](BRAIN_ARCHITECTURE.md) and [docs/INFRA.md](INFRA.md).
- Slack: Brain bot is installed in every channel; persona pin routes per-channel. Use Brain webhook / Slack adapter, not the Slack MCP, for outbound posts.
- EA cadence: daily briefing 7am PT → `#daily-briefing`; weekly plan Sunday 6pm PT → `#weekly-plan`; CFO Friday digest 18:00 UTC → `#cfo`.

**Open / active decisions**: see [KNOWLEDGE.md](KNOWLEDGE.md) Front-and-Center. Must-act-on: D29 (brand assets), D37 (domain migration), D56 (shared auth), D62 (reliability patterns), Q3 (Column Tax). Should-track: Q1 (OCR accuracy), D25 (legal review), D34 (n8n credentials), D24 (Sentry).

---

## 0. Venture Overview

**Model**: One human + AI agent workforce + partnerships co-founder (outcome-driven, flexible commitment)

**Products**:

- **LaunchFree** (launchfree.ai) -- Free LLC formation service ($0 service fee; user pays state filing fees only, disclosed upfront). AI-powered 50-state comparison helps users pick the cheapest, best-fit state. Revenue: RA credits, banking/payroll/insurance referrals. Launches Summer 2026.
- **FileFree** (filefree.ai) -- Free tax filing. Revenue: refund routing, financial referrals, audit shield, Tax Opt Plan. Launches January 2027.
- **Distill** (distill.tax) -- B2B compliance automation platform. Four product lines: Distill for CPAs (SaaS dashboard, $49-199/mo), Distill Tax API ($5-15/return), Distill Formation API ($20-40/filing), Distill Compliance API (per-action). Upload client docs, auto-extract via shared OCR pipeline, export to professional tax software. ~80% shared tech with consumer products. Launches Summer 2026. See Section 1C.
- **Trinkets** (tools.filefree.ai) -- Collection of simple utility tools (financial calculators, converters, generators). Revenue: AdSense + cross-sell to main products. Complexity: LOW. Built as `apps/trinkets/` in monorepo. See Section 0F.

**HQ**: paperworklabs.com -- Venture command center, admin dashboard, agent monitor, intelligence campaigns. Public portfolio page + authenticated `/admin/` panel.

**Personal site**: sankalpsharma.com -- Founder's personal portfolio/blog. Links to Paperwork Labs and products. Separate from company ops.

**Entity**: Paperwork Labs LLC (California). DBA filings for "FileFree", "LaunchFree", "Trinkets", and "Distill". See Section 0B for naming research, legal structure, and CA vs WY comparison.

**Trademark status**: "FILEFREE" and "LAUNCHFREE" to be filed on USPTO Supplemental Register. See Section 0C for full trademark and legal risk framework.

**Domains purchased**: paperworklabs.com, filefree.ai, launchfree.ai, distill.tax (March 2026). Existing: filefree.tax, sankalpsharma.com. Also owned: axiomfolio.com, launchfree.llc, taxfilefree.com (not actively used). Defensive purchase recommended: formationapi.com (~$12/yr, redirect to distill.tax/formation).

**AI Model Strategy**: 9 models across 7 roles. See Section 0E for authoritative routing registry (owned by AI Ops Lead persona).

**Monthly burn (real)**: ~$278/mo. Breakdown: Hetzner $6 + Render x2 $14 + Google Workspace $6 (1 seat, paperworklabs.com) + domains ~$20 + OpenAI ~$10 + ElevenLabs $5 + cyber insurance ~$150 (est. $1,800/yr amortized) + CA franchise tax ~$67 (est. $800/yr amortized). At scale add: Stripe fees (2.9%+$0.30 per transaction), variable AI costs (~$0.005-0.02/OCR doc, ~$15-17/mo social pipeline), partner wholesale costs. Vercel/Neon/Upstash all free tier until scale triggers listed in FINANCIALS.md.

---

## 0B. LLC Naming: Research-Backed Decision

### DECIDED: Paperwork Labs LLC (March 2026)

**Name**: Paperwork Labs LLC
**Domain**: paperworklabs.com (purchased March 2026)
**Website**: Clean static portfolio page at paperworklabs.com (see spec below)

### Why "Paperwork Labs"

**Thematic fit**: Both FileFree and LaunchFree literally eliminate paperwork (tax forms, LLC filings). The name is a wink at the problem we solve. "Labs" signals "we build things" -- the standard convention for multi-product tech holding companies.

**Research-backed**:

- "Labs" suffix is the #2 most common compound naming pattern in successful tech companies (23% of YC-backed companies use compound constructions) ([source: TrademarkLens](https://trademarklens.com/guides/us-tech-startup-naming-trends))
- .com available (paperworklabs.com) -- critical since 67%+ of successful startups use .com
- Zero existing companies named "Paperwork Labs" in US tech/fintech
- "PAPERWORKS" trademark (Serial #98659864) is Class 016 (paper stationery) -- no conflict with our Class 036/042
- paperwork.to (Dubai Document AI startup) is in a completely different market/country -- no confusion for a US holding LLC
- "Paperwork Forms" (Canada, 1 employee, municipality forms) is a different name -- "Labs" differentiates

**Names considered and rejected**:

- Toastworks LLC -- Toast Inc. (NYSE: TOST, $25B) sued Toast Labs Inc. in 2016. Too risky.
- Halftoast LLC -- Still in Toast Inc. blast radius.
- Butterside Labs -- "Butters" is British slang for ugly. Unnecessary baggage.
- Crisp Labs LLC -- Clean but less thematically connected than "Paperwork."
- Sharma Ventures LLC -- Personal name signals "small operation," not scalable.

### paperworklabs.com Static Site

Clean, minimal holding company portfolio page. Not a product site -- a company page.

- **Content**: Company name, one-liner ("We build tools that eliminate paperwork"), portfolio cards for FileFree / LaunchFree / Distill / Trinkets with links, team section (Sankalp + Olga Sharma), legal footer
- **Tech**: Static page served from `apps/studio/` on Vercel free tier with `paperworklabs.com` custom domain
- **Design**: Studio/Command Center zinc palette (neutral, professional)
- **Legal footer**: "Paperwork Labs LLC | California | FileFree, LaunchFree, Distill, and Trinkets are products of Paperwork Labs LLC"
- **Cost**: $0/yr hosting (Vercel free), ~$12/yr domain renewal

### Structure (Confirmed -- California LLC)

**Why California, not Wyoming (DECIDED March 2026)**:

The original plan recommended Wyoming. After analysis, California is the clear choice for a CA-resident founder:


| Factor                     | Wyoming                                                     | California                               |
| -------------------------- | ----------------------------------------------------------- | ---------------------------------------- |
| Filing fee                 | $100                                                        | $70                                      |
| Annual report              | $60/yr                                                      | $0 (no annual report required)           |
| Franchise tax              | $0 (but CA charges you anyway since founder is CA resident) | $800/yr (first year exempt for new LLCs) |
| RA cost                    | $25-29/yr                                                   | $49-125/yr                               |
| Privacy                    | Excellent (no owner disclosure)                             | Poor (public disclosure required)        |
| Foreign registration in CA | Required (~$70 extra)                                       | Not needed                               |
| Asset protection           | Strong (charging order protection for single-member)        | Weak                                     |
| **Year 1 total**           | **~$1,094** (with CA foreign reg + franchise tax)           | **~$119** (first year franchise exempt)  |
| **Year 2+ total**          | **~$985/yr**                                                | **~$849/yr**                             |


**Bottom line**: Wyoming's $0 income tax doesn't help a CA resident -- California taxes all your income regardless of where the LLC is formed. Wyoming would require foreign LLC registration in CA ($70), double RA fees, and double compliance. The only real Wyoming advantages (privacy, charging order protection) don't justify ~$975/yr extra pre-revenue.

**Revisit trigger**: When revenue exceeds $250K and asset protection justifies dual-state cost, consider Wyoming holding company with CA subsidiary.

**Now (pre-revenue):** Single California LLC (Paperwork Labs LLC) + DBA filings for "FileFree", "LaunchFree", "Trinkets", and "Distill"

- California filing: $70
- DBA filing: ~$10-25 per name
- Franchise tax: $0 first year (exempt for new LLCs), $800/yr after
- RA: ~$49/yr
- Total year 1: ~$119-145

**At $50K+ combined revenue:** Convert to holding company structure

- Parent LLC (Paperwork Labs LLC) stays as-is
- Create FileFree LLC (subsidiary)
- Create LaunchFree LLC (subsidiary)
- Create Distill LLC (subsidiary)
- Each subsidiary has its own bank account, EIN, and liability shield
- Clean separation for future acquisition or investment

---

## 0C. Trademark and Legal Risk Framework

### CRITICAL: filefree.com Is Owned by Intuit

**Confirmed via WHOIS** (March 11, 2026):

- Domain: filefree.com
- Registrar: MarkMonitor Inc. (Intuit's enterprise registrar)
- Created: June 29, 1999 (27 years ago)
- Status: clientDeleteProhibited, clientTransferProhibited, clientUpdateProhibited
- DNS: Akamai (same infrastructure as intuit.com)

Intuit has owned this domain since before TurboTax even offered online filing. They also faced FTC enforcement for deceptive "free" advertising (TurboTax "free" was ruled misleading because ~100M filers were ineligible). This means Intuit is HYPERSENSITIVE to "free" branding in the tax space.

### Trademark Risk Analysis

**"FileFree" as a trademark:**

- Likely **descriptive** ("file [taxes] free") -- the USPTO would probably refuse registration on the Principal Register without proof of secondary meaning (requires 5 years of substantially exclusive commercial use)
- CAN be registered on the **Supplemental Register** immediately -- this establishes a priority date, allows use of (R) symbol on the Supplemental Register
- Being descriptive is a **double-edged sword**: harder for US to register, but also harder for Intuit to claim exclusive rights to a descriptive phrase
- **FreeTaxUSA** (TaxHawk, Inc.) successfully built and defended a descriptive mark in the same space -- but they've been operating since 2001

**"LaunchFree" as a trademark:**

- Also descriptive, but NO known competitor claims it
- Easier to defend than FileFree -- no Intuit domain conflict
- Same registration strategy: Supplemental Register first

### Trademark Filing Plan


| Mark                           | Classes                                                   | Register              | Cost            | Timeline                                         |
| ------------------------------ | --------------------------------------------------------- | --------------------- | --------------- | ------------------------------------------------ |
| FILEFREE (stylized wordmark)   | Class 036 (Financial services), Class 042 (SaaS)          | Supplemental Register | $350 x 2 = $700 | File after product launch (need specimen of use) |
| LAUNCHFREE (stylized wordmark) | Class 035 (Business formation services), Class 042 (SaaS) | Supplemental Register | $350 x 2 = $700 | File after product launch                        |
| DISTILL (stylized wordmark)    | Class 042 (SaaS), Class 035 (Business services)           | Supplemental Register | $350 x 2 = $700 | File after Distill launch (Phase 9)              |
| FILEFREE (logo/design mark)    | Class 036, Class 042                                      | Supplemental Register | $350 x 2 = $700 | File with wordmark, separate application         |
| Total                          |                                                           |                       | ~$2,800         | All within 90 days of respective launches        |


After 5 years of commercial use: petition to move to Principal Register with evidence of acquired distinctiveness (user counts, media coverage, brand recognition surveys).

### STRICT LEGAL GUIDELINES (All Personas Must Follow)

**Brand Name Rules:**

1. ALWAYS write "FileFree" (one word, two capital F's). NEVER "File Free", "file free", "Filefree", "FILE FREE", "File-Free"
2. ALWAYS write "LaunchFree" (one word, L and F capitalized). NEVER "Launch Free", "launch free", "Launchfree"
3. When used in a sentence, the brand name is a PROPER NOUN: "FileFree helps you file taxes" (not "file free with FileFree")
4. NEVER use "file free" as a verb phrase in marketing copy. Say "file your taxes for free" or "file at zero cost" -- keep the brand name and the concept separate
5. Domain references: always `filefree.ai` (primary) -- NEVER reference `filefree.com` anywhere, ever. `filefree.tax` is retained as a redirect only.

**FTC "Free" Compliance Rules:**

1. Our service taIS actually free for ALL users. This is our strongest legal position. The moment we add a condition that makes filing not-free for some users, we are exposed to the EXACT FTC action that hit Intuit
2. DOCUMENT THIS COMMITMENT: "Filing is free. 100% of filers. 100% of the time. No income limits. No complexity limits for supported forms. No asterisks. No small print."
3. If we EVER add paid tiers for filing, the free tier must remain fully functional -- not artificially limited to push users to pay
4. RA credits on LaunchFree: MUST clearly disclose that base RA price is $49/yr and credits reduce or eliminate the cost. Cannot advertise "Free RA" without immediately visible qualification

**Circular 230 Compliance (Tax Content):**

1. We provide TAX EDUCATION, not TAX ADVICE. This distinction is legally critical.
2. Every screen, email, social post, or AI response that discusses tax topics must include: "This is general tax information, not tax advice. For advice specific to your situation, consult a qualified tax professional."
3. NEVER say "you should" + tax action (e.g., "you should claim the standard deduction"). ALWAYS say "many filers in your situation" or "the standard deduction is typically..."
4. Social media: EVERY tax tip post ends with the disclaimer. No exceptions. Build it into the Postiz template.

**UPL (Unauthorized Practice of Law) Compliance (LLC Content):**

1. We provide BUSINESS FORMATION SERVICES, not LEGAL ADVICE.
2. NEVER say "you should form in Delaware" or "you need an operating agreement." ALWAYS say "many entrepreneurs choose Delaware because..." or "operating agreements are commonly used to..."
3. Every LaunchFree formation page includes: "LaunchFree provides business formation services. We are not a law firm and do not provide legal advice. For legal questions specific to your situation, consult a licensed attorney."
4. State-specific recommendations: present data ("Wyoming charges $100, Delaware charges $140, California charges $70 + $800 annual franchise tax") and let the user decide. Don't recommend.

**Cross-Sell Email Compliance:**

1. Opt-in checkbox (unchecked by default) on every signup form: "I consent to [LLC Name] using my information across FileFree, LaunchFree, and related services to send me product updates and recommendations. I can unsubscribe from any product at any time."
2. Every email includes: physical business address (CAN-SPAM), one-click unsubscribe, clear sender identification
3. Cross-product emails only sent to users who opted in
4. FTC disclosure on any partner/affiliate recommendation: "We may earn a commission if you sign up through this link."

**Content Review Gate:**
Every piece of user-facing content (email, social post, in-app message, landing page copy) must pass this checklist before publishing:

- Brand names spelled correctly (FileFree, LaunchFree -- proper nouns, correct casing)
- "Free" claims are 100% accurate with no hidden conditions
- Tax content uses education framing, not advice ("many do X" not "you should X")
- Legal content uses services framing, not advice
- Circular 230 / UPL disclaimer present where applicable
- FTC affiliate disclosure present if recommending partner products
- CAN-SPAM compliant (unsubscribe, physical address, honest subject line)
- No reference to filefree.com anywhere

### Legal Risk Matrix (Stress Test Addition)


| Risk                                              | Severity | Gap                                                                                                                                                                                                                 | Remediation                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **50-state data errors -> incorrect LLC filings** | CRITICAL | Disclaimers cover opinions, not facts. Wrong filing fees or deadlines = negligence exposure even with disclaimers.                                                                                                  | Add source-linking on every data point ("Fee: $70, source: CA SOS, last verified: 2026-03-01"). Add prominent "last verified" date on every state page. Add user confirmation step ("I confirm I've verified this fee on [state SOS link]"). Add ToS data accuracy disclaimer: "Filing fees and deadlines are sourced from state government websites and verified monthly. We make every effort to keep this data current but cannot guarantee accuracy. Always verify with your state's Secretary of State before filing." |
| **FTC "Free" scrutiny**                           | HIGH     | "Free LLC" headline is misleading re: state fees. RA credit system is a landmine ("free RA" claim). Intuit precedent heightens FTC scrutiny of "free" claims in adjacent spaces.                                    | **RULES**: (1) NEVER use "Free LLC" as a standalone headline. Always: "Free LLC Formation Service" or "$0 Service Fee." (2) State filing fees must appear in the same visual field as any "free" claim -- not below the fold, not on a different page. (3) RA credits: NEVER say "Free RA." Always: "RA starting at $49/yr. Earn credits to reduce your cost." (4) Every landing page with "free" in the headline must pass FTC Free Guide compliance review.                                                               |
| **AI operating agreements (UPL risk)**            | HIGH     | "AI-generated, state-specific operating agreement" crosses from template fill-in to document drafting. LegalZoom survived UPL challenges specifically because they did NOT auto-generate -- they offered templates. | **DECISION**: Use template model, not generation. LaunchFree provides state-specific operating agreement TEMPLATES (pre-written by a licensed attorney, stored as PDFs). AI EXPLAINS clauses ("This section covers member voting rights. Most single-member LLCs use...") but does NOT select, modify, or draft clause language. Marketing: "Operating agreement template included" not "AI-generated operating agreement." The attorney consultation (Section 0G #3) should validate this approach.                        |
| **Cross-sell consent language**                   | MEDIUM   | Current: "I'd like to hear about other [LLC Name] products." Too vague for CCPA and lacks per-brand granularity. Missing TCPA gap if SMS is ever added.                                                             | **FIX**: Replace with explicit cross-product data use: "I consent to [LLC Name] using my information across FileFree, LaunchFree, and related services to send me product updates and recommendations. I can unsubscribe from any product at any time." Add separate SMS consent checkbox if SMS is ever added (TCPA requires express written consent for marketing texts). Add per-brand unsubscribe capability in email footer.                                                                                           |


### Legal Protection Checklist (Stress Test Addition)

Before collecting ANY user PII or processing ANY tax/legal data:


| Item                                      | Status   | Deadline         | Notes                                                                                                                                  |
| ----------------------------------------- | -------- | ---------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| E&O + Cyber liability insurance ($1M)     | NOT DONE | Before first SSN | $1,500-3,000/yr. Covers data breach, errors in tax calcs, professional liability                                                       |
| Data breach response plan (SANS template) | NOT DONE | Before first SSN | 2-page doc: discovery, containment, notification, remediation. State AG notification timelines vary (CA: 72hrs)                        |
| Terms of Service (attorney-reviewed)      | NOT DONE | Before launch    | Limitation of liability, arbitration clause, data accuracy disclaimer, AI-assisted filing disclosure                                   |
| Privacy Policy (CCPA + state laws)        | NOT DONE | Before launch    | Data collection, retention (24hr for images), sharing (Cloud Vision, OpenAI -- with SSN masking), deletion rights                      |
| Tax filing disclaimer (Circular 230)      | NOT DONE | Before launch    | On every screen that touches tax data                                                                                                  |
| LLC formation disclaimer (UPL)            | NOT DONE | Before launch    | On every LaunchFree page                                                                                                               |
| Startup attorney consultation             | NOT DONE | Before Phase 3   | 1 hour, ~$300-500. Key questions: UPL boundaries for AI formation guidance, RA liability exposure, tax prep liability vs CPA liability |


**Liability Comparison -- How Competitors Handle It**:


| Company                                   | Approach                                                                                                          | Key Protections                                                                                                                     |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Credit Karma Tax** (now Cash App Taxes) | "Not a substitute for professional tax advice." Accuracy guarantee (pays IRS penalties if their math is wrong).   | Strong ToS limitation of liability. E&O insurance. Accuracy guarantee builds trust.                                                 |
| **FreeTaxUSA**                            | "$100K accuracy guarantee." Covers IRS penalties from calculation errors.                                         | Clear "education not advice" framing. Guarantee is capped and excludes user input errors.                                           |
| **LegalZoom**                             | "We are not a law firm." Survived multiple UPL lawsuits by positioning as document preparation, not legal advice. | Operating agreement TEMPLATES, not custom drafting. Clear disclaimers on every page. Separate lawyer marketplace for actual advice. |
| **TurboTax**                              | Expert review add-on ($$$). Free tier has no accuracy guarantee.                                                  | Massive legal team. FTC consent decree for "free" advertising.                                                                      |


**Our approach**: Follow FreeTaxUSA model for tax (accuracy guarantee capped at $10K, covers OUR calculation errors only, not user input errors). Follow LegalZoom model for LLC (templates, not drafting). Get E&O insurance before collecting any data.

### 50-State Data Accuracy Standard (Stress Test Addition)

Every state data point displayed to users must meet this standard:

1. **Source-linked**: Every fee, deadline, and requirement shows its source ("CA SOS, last verified 2026-03-01")
2. **Freshness visible**: "Last verified" date displayed prominently. If >90 days old, show warning badge.
3. **User confirmation**: Before any filing action, user sees: "Please verify this information on [state SOS website link] before proceeding. Filing fees and requirements can change."
4. **Automated freshness**: n8n State Data Validator (Agent #21) checks DAILY for volatile states (CA, NY, TX, FL, IL, WA, NJ, MA, GA, PA) and WEEKLY for all others. Any state >30 days since last verification shows yellow warning. Any state >60 days triggers red alert to Compliance Monitor and EA daily briefing.
5. **Error correction**: If a user reports incorrect data, treat it as a P0 bug. Fix within 24 hours, notify affected users, log in incident report.

---

## 0D. Valuation Estimate (Marketplace-Stage Analysis)

### Comparable Companies


| Company              | Revenue       | Valuation                             | Multiple      | Model                                    | ARPU    | Users |
| -------------------- | ------------- | ------------------------------------- | ------------- | ---------------------------------------- | ------- | ----- |
| Credit Karma         | ~$1.6B (2023) | $8.1B (2020 acq)                      | 7.1x revenue  | Free credit scores, Lightbox marketplace | ~$11.43 | 140M  |
| LegalZoom            | $751M LTM     | $994M EV (2026)                       | 1.3x revenue  | LLC formation + compliance, $79-299/pkg  | ~$150   | ~5M   |
| ZenBusiness          | Est. $200M+   | $1B+ (last raise)                     | ~5x revenue   | LLC formation, $0-349/pkg                | ~$100   | ~2M   |
| Formation Nation     | Est. $20-30M  | $49M cash + $15M earnout + $50M stock | ~3-4x revenue | LLC formation (Inc Authority brand)      | N/A     | N/A   |
| FreeTaxUSA (TaxHawk) | Est. $50-100M | Private (est. $200-500M)              | ~4-5x est.    | Free federal, $15 state                  | ~$5-10  | ~10M  |


### Credit Karma Benchmark Math

CK's numbers define the ceiling for this business model:

- CK revenue: $1.6B (FY2023). $2.3B (FY2025).
- CK users: 140M+
- CK ARPU: ~$11.43 ($1.6B / 140M). Low because most users are passive (check score, leave).
- CK acquisition price: $8.1B = 7.1x revenue = **$57.86 per user** in enterprise value
- CK valued at: **~$81 in enterprise value per $1 of ARPU** ($57.86 / $11.43 * $16 adjusted)

**Why FileFree's per-user value exceeds CK's**: CK knows credit history (backward-looking). FileFree knows actual income, tax liability, refund amount, filing status, dependents, employer, business ownership, credit score, AND quarterly engagement behavior. This is 3-5x deeper per user. Deeper data = higher conversion = higher ARPU at lower user counts. A user with verified W-2 income + credit score is not a lead -- it's a pre-qualified customer.

### Fintech M&A Market Context (Q1 2026)

- Fintech M&A median: **4.4x** EV/Revenue (overall). North America premium: **6.4x** ([source: WindsorDrake Q4 2025](https://windsordrake.com/fintech-valuation-report/))
- AI WealthTech: **14-16x** EV/Revenue (premium for AI-native platforms)
- "Scaled Winners" fintech: **6-8x** (strong fundamentals, proven unit economics)
- Strategic acquisition share: **78%** (+23% YoY) -- buyers want profitable, integrated platforms, not growth-at-all-costs
- Median deal size: **$6.5M** (+29% YoY)
- Key buyer priorities: profitability, AI capabilities, recurring revenue, platform integration depth

### Our Venture Valuation Scenarios (Marketplace-Stage Aligned)

Each scenario maps to a marketplace stage (Section 4O). Multiples expand as the platform evolves from one-way affiliate links to a two-sided marketplace with network effects.


| Scenario       | Users | Mktplace ARPU | Product Rev | Mktplace Rev | Total Revenue | Multiple | Valuation | Stage   | What Unlocks It                                                 |
| -------------- | ----- | ------------- | ----------- | ------------ | ------------- | -------- | --------- | ------- | --------------------------------------------------------------- |
| A: Seed        | 5K    | $3-7          | $15K-50K    | $15K-35K     | $25K-65K      | 3-5x     | $75K-325K | Stage 1 | First tax season + LaunchFree launch + compliance SaaS          |
| B: Traction    | 25K   | $8-15         | $150K-250K  | $200K-375K   | $300K-500K    | 5-8x     | $1.5M-4M  | Stage 2 | Smart matching + Fit Scores + tiered CPA + data reciprocity     |
| C: Growth      | 50K   | $15-35        | $500K-750K  | $750K-$1.75M | $1.25M-2M     | 6-10x    | $7.5M-20M | Stage 3 | Partner API live + auction CPA + segment marketplace            |
| D: Scale       | 200K  | $25-50        | $2M-$3M     | $5M-$10M     | $8M+          | 8-12x    | $64M-96M  | Stage 4 | Full marketplace + multi-product + partner-submitted models     |
| E: CK Playbook | 500K+ | $35-80+       | $4M-$8M     | $17.5M-$40M  | $25M+         | 10-15x   | $250M+    | Stage 4 | Marketplace network effects + data licensing + advisory product |


### Per-User Enterprise Value at Each Stage


| Stage   | Users | Valuation (mid) | Value/User | CK Comparison ($57.86/user) | Justification                                                |
| ------- | ----- | --------------- | ---------- | --------------------------- | ------------------------------------------------------------ |
| Stage 1 | 5K    | $200K           | $40        | 0.7x CK                     | Pre-traction, data asset nascent                             |
| Stage 2 | 25K   | $2.75M          | $110       | 1.9x CK                     | Data 3-5x deeper, Fit Scores proving conversion lift         |
| Stage 3 | 50K   | $13.75M         | $275       | 4.8x CK                     | Marketplace dynamics, network effects beginning, auction CPA |
| Stage 4 | 200K  | $80M            | $400       | 6.9x CK                     | Full marketplace, multi-product, partner-submitted models    |


**Why per-user value exceeds CK**: CK had 140M users but most were passive score-checkers (check score, leave, come back next month). Our users actively file taxes, form LLCs, track quarterly estimates, split refunds, and engage with compliance calendars. Active financial engagement > passive score monitoring. Quality over quantity.

### Stress Tests

**Formation Nation comp caveat**: LegalZoom paid ~$115M for Formation Nation (Inc Authority), a mature business with $20-30M revenue. Formation MARKET commands 3-4x revenue. A pre-revenue startup needs 10K+ users with MoM growth before acquisition interest materializes.

**Multiple reality check**: Scenarios D and E assume marketplace dynamics take hold (two-sided network effects, partner bidding, ML matching). A single-product affiliate business stays at 3-5x. The jump to 8-15x requires proof that the marketplace is working: partners bidding against each other, ML matching outperforming static, and ARPU growing with user count (marketplace effect). Without these proof points, cap expectations at Scenario C.

**Cost structure advantage**: At $278/mo burn, the venture is profitable by Scenario A ($65K revenue, moderate case). This is extraordinary -- most fintech startups burn $50K-500K/mo and don't reach profitability until Series B. Early profitability unlocks organic growth without dilution, which means the founder retains near-100% equity through Scenario C. That ownership percentage, multiplied by $7.5M-20M valuation, is the real founder wealth creation path.

**What makes the valuation story unique**: No single competitor combines free personal tax filing + free LLC formation + compliance SaaS + financial intelligence marketplace + quarterly engagement + refund splitting. The combination IS the moat. Each product individually is worth 3-5x. The cross-sell data + marketplace platform creates a portfolio premium that pushes multiples to 6-10x+. The platform IS the data, and the data compounds with every user.

---

## 0E. AI Model Routing Strategy (Authoritative -- Owned by AI Ops Lead)

**Last reviewed**: March 12, 2026 | **Next review**: April 12, 2026

### Routing Principle: Quality-First

Use the best model for the task. Only downgrade when a cheaper model produces equivalent quality (not "good enough" -- equivalent). The founder is willing to pay more for better results. Cost optimization happens by routing to the right tier, not by forcing cheaper models where quality suffers.

The AI Ops Lead persona (`agent-ops.mdc`) owns this registry and all model routing decisions. Engineering implements but does not choose models.

**GPT-5 readiness**: When GPT-5 releases, evaluate immediately. If it outperforms current assignments at comparable cost, swap. Do not wait for a scheduled review cycle.

### Model Landscape (March 2026)


| #   | Model             | Input/1M | Output/1M | Context | Role                                                                                                                       |
| --- | ----------------- | -------- | --------- | ------- | -------------------------------------------------------------------------------------------------------------------------- |
| 1   | GPT-4o-mini       | $0.15    | $0.60     | 128K    | **The Intern**: cheapest bulk extraction, classification, summaries                                                        |
| 2   | Gemini 2.5 Flash  | $0.30    | $2.50     | 1M      | **The Workhorse**: smart + cheap. Wins 5/8 benchmarks vs GPT-4o at 81% less cost. Default for non-specialized tasks.       |
| 3   | o4-mini           | $1.10    | $4.40     | 200K    | **The Math Brain**: budget reasoning. 99.5% AIME 2025. Tax/financial verification.                                         |
| 4   | Gemini 2.5 Pro    | $1.25    | $10.00    | 1M      | **The Researcher**: #1 Chatbot Arena. Deep analysis, long-context research, SEO content.                                   |
| 5   | GPT-4o            | $2.50    | $10.00    | 128K    | **The Creative Director**: brand voice, social scripts, marketing copy. Confirmed superior "distinctive narrative pull."   |
| 6   | GPT-5.4           | $2.50    | $15.00    | 1M      | **The Autonomous Agent**: only model with native computer-use. Browsing, form filling, competitor analysis.                |
| 7   | Claude Sonnet 4.6 | $3.00    | $15.00    | 200K    | **The Senior Engineer + Lawyer**: code (79.6% SWE-bench), compliance, instruction adherence, templates.                    |
| 8   | Claude Opus 4.6   | $5.00    | $25.00    | 1M      | **The Principal Engineer**: escalation only. 80.8% SWE-bench (only 1.2% above Sonnet). For >32K output, extended autonomy. |
| 9   | o3                | $10.00   | $40.00    | 200K    | **Nuclear Option**: complex multi-step reasoning. Dense visual analysis. Almost never needed.                              |


### Decision Tree

```
Is it deterministic? ──YES──> Code (Tier 0, $0)
        │ NO
Is it high-volume + simple? ──YES──> GPT-4o-mini ($0.15/$0.60)
        │ NO
Needs math reasoning? ──YES──> o4-mini ($1.10/$4.40)
        │ NO
Brand voice / creative copy? ──YES──> GPT-4o ($2.50/$10)
        │ NO
Browse websites autonomously? ──YES──> GPT-5.4 ($2.50/$15)
        │ NO
Code gen or compliance? ──YES──> Claude Sonnet ($3/$15)
        │ NO
Default ──> Gemini 2.5 Flash ($0.30/$2.50)
```

### Model x Workflow Registry

**FileFree**


| Workflow                      | Model            | Tier | Why                                           | ~Cost/Run |
| ----------------------------- | ---------------- | ---- | --------------------------------------------- | --------- |
| OCR field mapping (>85% conf) | GPT-4o-mini      | 1    | Cheapest structured output                    | $0.001    |
| OCR field mapping (<85% conf) | GPT-4o vision    | 2B   | Needs image understanding                     | $0.02     |
| Tax calc verification         | o4-mini          | 2    | 99.5% AIME math reasoning                     | $0.005    |
| Tax explanations (streaming)  | Claude Sonnet    | 2A   | Accuracy-critical, Circular 230               | $0.005    |
| Refund optimization tips      | Claude Sonnet    | 2A   | Educational framing, cautious                 | $0.005    |
| Error messages                | Gemini 2.5 Flash | 1.5  | Smart enough, 83% cheaper than Sonnet         | $0.001    |
| FAQ generation                | Gemini 2.5 Flash | 1.5  | General intelligence, not compliance-critical | $0.001    |


**LaunchFree**


| Workflow                                | Model            | Tier | Why                                                                 | ~Cost/Run |
| --------------------------------------- | ---------------- | ---- | ------------------------------------------------------------------- | --------- |
| State data structuring                  | GPT-4o-mini      | 1    | Cheapest Zod schema mapping                                         | $0.001    |
| State data deep validation              | Gemini 2.5 Pro   | 2    | 1M context, #1 Arena, 50% cheaper than Sonnet                       | $0.01     |
| State fee lookups                       | Gemini 2.5 Flash | 1.5  | Simple lookup, 90% cheaper than Sonnet                              | $0.001    |
| Formation guidance AI                   | Claude Sonnet    | 2A   | UPL compliance, cautious framing                                    | $0.01     |
| Operating agreement template assistance | Claude Sonnet    | 2A   | Template selection/assembly + clause explanations (no drafting)     | $0.03     |


**Trinket Factory**


| Workflow                    | Model            | Tier | Why                                           | ~Cost/Run |
| --------------------------- | ---------------- | ---- | --------------------------------------------- | --------- |
| Market discovery (browsing) | GPT-5.4          | 2C   | Computer-use for competitor sites             | $0.02     |
| SEO keyword analysis        | Gemini 2.5 Flash | 1.5  | Data analysis, no computer-use needed         | $0.005    |
| 1-pager from template       | Claude Sonnet    | 2A   | Best instruction adherence                    | $0.02     |
| PRD from template           | Claude Sonnet    | 2A   | Technical spec, structured output             | $0.03     |
| Code generation             | Claude Sonnet    | 2A   | 79.6% SWE-bench, best for code                | $0.10     |
| Massive refactor            | Opus 4.6         | 3    | Escalation: >32K output or multi-hour session | $0.50     |


**Social Content Pipeline**


| Workflow          | Model            | Tier    | Why                                       | ~Cost/Run |
| ----------------- | ---------------- | ------- | ----------------------------------------- | --------- |
| Script generation | GPT-4o           | 2B      | Brand voice, "distinctive narrative pull" | $0.01     |
| Image prompt gen  | Gemini 2.5 Flash | 1.5     | Accuracy, not voice. 81% cheaper.         | $0.002    |
| Image generation  | DALL-E 3         | Special | Purpose-built                             | $0.04     |
| Voiceover         | ElevenLabs Flash | Special | Purpose-built                             | $0.05     |
| Content calendar  | Gemini 2.5 Flash | 1.5     | Analytical, not creative                  | $0.002    |


**Intelligence & Marketing**


| Workflow            | Model            | Tier | Why                             | ~Cost/Run |
| ------------------- | ---------------- | ---- | ------------------------------- | --------- |
| Email copy          | GPT-4o           | 2B   | Brand voice critical            | $0.01     |
| Landing page copy   | GPT-4o           | 2B   | Conversion-focused creative     | $0.01     |
| SEO blog content    | Gemini 2.5 Pro   | 2    | Long-form research, 50% cheaper | $0.02     |
| Compliance review   | Claude Sonnet    | 2A   | CAN-SPAM, FTC, Circular 230     | $0.005    |
| Content Review Gate | Claude Sonnet    | 2A   | Constraint-following            | $0.01     |
| A/B test variants   | Gemini 2.5 Flash | 1.5  | Volume, test many cheaply       | $0.002    |


**Command Center / Ops**


| Workflow             | Model          | Tier | Why                            | ~Cost/Run |
| -------------------- | -------------- | ---- | ------------------------------ | --------- |
| Analytics digest     | GPT-4o-mini    | 1    | Cheapest summarization         | $0.001    |
| Competitive intel    | Gemini 2.5 Pro | 2    | Analytical depth, 1M context   | $0.02     |
| Source monitoring    | GPT-4o-mini    | 1    | Simple diff comparison         | $0.001    |
| Financial modeling   | o4-mini        | 2    | Math reasoning for projections | $0.005    |
| Legal policy updates | Claude Sonnet  | 2A   | Legal precision                | $0.02     |


### Role Distribution Summary


| Model             | Role                                | % of Tasks |
| ----------------- | ----------------------------------- | ---------- |
| GPT-4o-mini       | The Intern                          | 15%        |
| Gemini 2.5 Flash  | The Workhorse (default catch-all)   | 25%        |
| o4-mini           | The Math Brain                      | 5%         |
| Gemini 2.5 Pro    | The Researcher                      | 10%        |
| GPT-4o            | The Creative Director               | 10%        |
| GPT-5.4           | The Autonomous Agent                | 10%        |
| Claude Sonnet 4.6 | The Senior Engineer + Lawyer        | 20%        |
| Opus 4.6          | The Principal Engineer (escalation) | 3%         |
| o3                | Nuclear Option                      | 2%         |


### Monthly Cost Estimates


| Stage                | AI Agent Costs | Notes                                      |
| -------------------- | -------------- | ------------------------------------------ |
| Pre-launch (testing) | ~$4/mo         | 50 test docs, 30 test videos, 1-2 trinkets |
| Launch (100 users)   | ~$15/mo        | Real OCR, explanations, social             |
| Growth (1K users)    | ~$40/mo        | Higher volume, cross-sell campaigns        |
| Scale (10K users)    | ~$110/mo       | Still tiny vs $15-50/yr revenue per user   |


### Implementation

All model routing is implemented via **n8n** (the unified orchestration layer). Each n8n workflow node specifies its model via the AI Agent node's provider + model selection. No separate orchestration platform (Ruflo, etc.) is needed. n8n supports OpenAI, Anthropic, and Google providers natively.

### Interactive Session Guidance (Cursor IDE)

The routing strategy above covers **automated workflows** (n8n, batch operations). For interactive human-AI pair programming in Cursor:


| Session Type                             | Recommended Model               | Rationale                                                                                                                                                 |
| ---------------------------------------- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Strategy / architecture / deep reasoning | Claude Opus 4.6                 | Quality delta matters for high-stakes decisions ($100K+ impact). Deeper reasoning chains, better multi-dimensional tradeoff analysis, catches edge cases. |
| Complex multi-file refactors             | Claude Opus 4.6                 | 1M context window, 80.8% SWE-bench, handles large scope without losing context.                                                                           |
| Routine coding / component building      | Claude Sonnet 4.6               | 79.6% SWE-bench (only 1.2% below Opus). 40% cheaper. Identical quality for scoped tasks.                                                                  |
| Quick fixes / single-file edits          | Claude Sonnet 4.6 or fast model | Minimal quality difference for small scope.                                                                                                               |


**Verdict**: Using Opus for strategy sessions is **not overkill**. Opus for thinking, Sonnet for typing.

### Maintenance Protocol (AI Ops Lead Responsibility)

1. **New model release**: Evaluate benchmarks + pricing vs current assignments. Generate swap recommendation within 48 hours.
2. **Monthly**: Pull API usage from provider dashboards, calculate cost per workflow, flag anomalies. Update `docs/AI_MODEL_REGISTRY.md`.
3. **Quarterly**: Full persona audit + model assignment review.
4. **When adding workflows**: Consult this registry's decision tree before choosing a model.

---

## 0F. Trinkets: Utility Tool Revenue Stream

### Overview

Trinkets is a collection of simple, client-side utility tools (financial calculators, converters, generators) that serve three purposes:

1. **Test the agent infrastructure** -- the Trinket Factory pipeline validates our end-to-end agent workflow (Discovery -> PRD -> Build)
2. **Build shared libraries** -- the first trinket establishes reusable patterns (`packages/tool-template`)
3. **Passive revenue** (bonus) -- AdSense monetization, cross-sell to FileFree/LaunchFree

### Market Reality (Data-Backed)

The utility tool space is dominated by established players:

- **iLovePDF**: 216M monthly visits, DA 91, ~$4M/yr (ads + premium). Founded 2010.
- **SmallPDF**: 61M monthly visits, DA 83, ~$11M/yr (freemium SaaS at $9/mo). Founded 2013.
- **PDF2Go**: 5-12M monthly visits, ~$670K/yr (AdSense + credits). Founded 2009.

SEO reality for new domains: 3-6 months for long-tail keywords (KD < 30), 6-12 months for meaningful traffic, 12+ months for competitive keywords. A new domain will NOT rank for "pdf to word" (KD 80+) within Year 1.

**Revenue projections (conservative)**: Year 1: ~$50-300. Year 2: ~$5K-20K. Year 3+: $20K-100K if SEO compounds.

### The Trinket Factory Agent Pipeline

Instead of manually picking tools, the agent infrastructure discovers, specs, and builds them:

```
Stage 1: DISCOVERY (GPT-5.4)
  Computer-use: browse competitor sites, analyze UX/pricing/SEO
  + Gemini Flash for SEO keyword analysis
  Output: 1-pager from template (docs/templates/trinket-one-pager.md)
  -> Human reviews -> Approve/Reject

Stage 2: SPEC (Claude Sonnet)
  Takes approved 1-pager as input
  Writes precise PRD from template (docs/templates/trinket-prd.md)
  -> Human reviews -> Approve/Reject

Stage 3: BUILD (Claude Sonnet)
  Takes approved PRD + established pattern from first trinket
  Generates code, creates PR for human review
  79.6% SWE-bench = best code quality
```

### First Trinket: Financial Calculators

Pre-decided idea (agent validates, not selects). Includes:

- Mortgage calculator, compound interest, savings goal, budget planner
- All client-side JavaScript (zero API costs, zero server costs)
- Aligns with FileFree's financial brand (cross-sell opportunity)
- Hosted on Vercel free tier as `apps/trinkets/` in the monorepo

### Technical Pattern

```
apps/trinkets/                  (Next.js SSG, Vercel free, tools.filefree.ai)
  src/app/
    calculators/
      mortgage/page.tsx
      compound-interest/page.tsx
      savings-goal/page.tsx
      budget-planner/page.tsx
    converters/                  (future: pdf-to-word, image converters)
    generators/                  (future: qr-code, invoice, etc.)
  src/components/
    tool-layout.tsx              (shared: header, cross-sell CTA, ad slots, footer)
    seo-head.tsx                 (per-tool JSON-LD, meta tags)
    ad-unit.tsx                  (Google AdSense)
    cross-sell-cta.tsx           (links to FileFree/LaunchFree)
```

**URL structure**: Use subdirectory-style paths for topical clustering (helps Google understand authority):

- `tools.filefree.ai/calculators/mortgage`
- `tools.filefree.ai/calculators/compound-interest`
- `tools.filefree.ai/converters/pdf-to-word` (future)

All processing is browser-based (pdf-lib, heic2any, browser-image-compression, qrcode.js). Zero server cost. Zero backend needed. No auth required -- cross-sell CTAs funnel traffic to FileFree/LaunchFree.

### Domain Strategy

Stay on `tools.filefree.ai` subdomain. Do NOT buy individual domains per trinket. SEO research confirms: subdomain inherits some authority from parent domain, individual domains start at DA 0 and cost $10-15/yr each. At Year 1 trinkets revenue of $50-300, buying 15+ domains is negative ROI.

**Graduation criteria**: If a single trinket exceeds 10K monthly visits, consider buying a standalone domain and 301-redirecting from the subdomain URL. This is a growth optimization, not a launch decision.

### Build Timing

Phase 1.5: After monorepo restructure (Phase 1), before 50-state data pipeline (Phase 2). Time budget: 3-5 days. Then hands-off for 6 months while building main products. Check traffic at Month 6.

---

## 0F-2. AI Branding in Financial Services: Help or Hurt?

**Research finding**: AI branding in financial services is a double-edged sword. The answer depends on what you're branding as AI-powered.

**Where "AI-powered" HELPS trust**:

- **Automation / speed**: "AI reads your W-2 in seconds" -- people trust AI for tedious data entry
- **Cost reduction**: "AI eliminates the middleman, so filing is free" -- people understand AI = cheaper
- **Accuracy in calculation**: "AI double-checks your math" -- people trust computers with arithmetic
- **Data analysis**: "AI compares all 50 states to find the best fit" -- people trust AI for research

**Where "AI-powered" HURTS trust**:

- **Advice / judgment**: "AI-powered tax advice" -- people want human judgment for high-stakes decisions
- **Legal documents**: "AI-generated operating agreement" -- legal liability anxiety
- **Personal data handling**: Over-emphasizing AI processing of SSNs or financial data creates concern

**Our approach**: Use "AI-powered" for process/speed/cost messaging, NEVER for advice/judgment messaging. Say "AI handles the tedious stuff so you don't have to" not "AI tells you what to do." The product is the human experience of simplicity, not the AI behind it.

**Competitors' approach**: Credit Karma barely mentions AI. TurboTax emphasizes "expert review" (human). FreeTaxUSA doesn't mention tech at all. Cash App Taxes focuses on "free + easy." Takeaway: users care about outcomes (free, fast, accurate), not the technology stack.

**DECISION**: Lead with outcomes ("free, 5 minutes, accurate"), not with "AI-powered." Mention AI when it explains WHY something is free or fast, but never as the headline value prop. The brand voice speaks as a competent friend, not as a robot.

---

## 0G. Critical Pre-Code Actions (Stress Test Finding)

These are existential risk mitigations that cost under $5K total. Complete before writing any product code (i.e., before Phase 1).


| #   | Action                                                        | Cost                                        | Deadline                              | Blocks                                                                                                                                                                                                                         |
| --- | ------------------------------------------------------------- | ------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | **Get cyber liability insurance** (E&O + cyber, $1M coverage) | $1,500-3,000/yr                             | Before first SSN is collected         | Phase 7 (FileFree launch). Non-negotiable for handling SSNs. A single breach without it is company-ending.                                                                                                                     |
| 2   | **Draft data breach response plan**                           | $0 (self-authored from SANS/NIST templates) | Before first SSN is collected         | Phase 7. Need: notification timeline by state tier, template notification letter, forensics firm contact, first-call list.                                                                                                     |
| 3   | **1-hour startup attorney consultation**                      | ~$300-500                                   | Before Phase 3 (LaunchFree MVP)       | Two specific questions: (a) does AI-assisted operating agreement survive UPL analysis in CA, TX, NY, FL? (b) is wholesale RA arrangement structured to minimize agency liability?                                              |
| 4   | ~~**Decide LLC name**~~                                       | $0                                          | ~~Hard deadline: 2 weeks from today~~ | **DONE** -- Paperwork Labs LLC (California). See Section 0B.                                                                                                                                                                   |
| 5   | **Apply for EFIN (Form 8633)**                                | $0                                          | THIS WEEK                             | Phase 8 (MeF transmitter). 45-day IRS processing. Chain: EFIN -> Software Developer ID -> ATS testing (October 2026) -> Comms test (November) -> Go-live (January 2027). Every day of delay compresses the October ATS window. |


**Why this section exists**: The stress test identified that the plan has strong technical architecture but weak operational/legal preparedness. These 5 actions are the highest-ROI items in the entire plan — they cost <$5K and prevent catastrophic outcomes. None require code.

---

## 0H. Repo Rename (Deferred)

The repo is currently named `fileFree` (the original product). Now that "Paperwork Labs" is confirmed, rename to `paperwork-labs` when ready. Do this during a quiet period when no PRs are open, no agents are running, and no CI is in-flight. **Ask the founder before executing this rename.**

**What changes**: GitHub repo name, Render blueprint references, Vercel project names, all `package.json` names, import paths referencing the repo, DNS CNAME records, and `.cursor/rules/` absolute path references.

**When**: After LLC filing (Phase 0.6) and during a quiet window. Not urgent -- the rename is cosmetic and can happen anytime.

---

## 0I. PII Data Lifecycle (CCPA-First)

**Applicability**: CCPA/CPRA (California), not GDPR (US-only product). CCPA applies once we hit thresholds (50K+ consumers/year or $25M revenue). Pre-threshold, we follow CCPA voluntarily because (a) we're a California LLC and (b) it's the right thing to do and builds trust.

### Data Inventory


| Data Element          | Product            | Sensitivity | Storage                    | Encryption                           |
| --------------------- | ------------------ | ----------- | -------------------------- | ------------------------------------ |
| SSN                   | FileFree           | Critical    | Neon DB (encrypted column) | AES-256, separate key                |
| W-2 images            | FileFree           | Critical    | GCP Cloud Storage          | At-rest encryption, 24hr auto-delete |
| Name, email, address  | All                | High        | Neon DB                    | At-rest encryption                   |
| Filing status, income | FileFree           | High        | Neon DB                    | At-rest encryption                   |
| LLC owner info        | LaunchFree         | High        | Neon DB                    | At-rest encryption                   |
| Credit score          | Future (Phase 1.5) | High        | Neon DB (encrypted column) | AES-256, separate key                |
| Refund/owed amount    | FileFree           | Medium      | Neon DB                    | At-rest encryption                   |
| Event/behavioral data | All                | Low         | PostHog + Neon             | Standard                             |


### Retention Policy

- **W-2 images**: 24 hours (GCP Cloud Storage lifecycle policy). Auto-deleted. Non-negotiable.
- **Tax return data**: 7 years (IRS statute of limitations for amended returns). User can request deletion but must be informed of the retention requirement.
- **LLC formation data**: Indefinite (user's ongoing business records, needed for compliance calendar).
- **Credit score snapshots**: 2 years (enough for trajectory analysis). Older snapshots aggregated, raw deleted.
- **User account data**: Until deletion request + 30-day processing window.
- **Event/behavioral data**: 3 years (sufficient for ML training and cohort analysis). Anonymized after 3 years if needed for aggregate analytics.

### Deletion Rights

Account deletion endpoint available from day one (CCPA requirement). Cascade:

1. Neon DB: soft-delete user record, hard-delete PII fields after 30-day grace period
2. GCP Cloud Storage: delete any remaining W-2 images (should already be auto-deleted)
3. Upstash Redis: clear all session data for user
4. Venture identity: remove cross-product links
5. Credit score provider: request data deletion via reseller API (Array/SavvyMoney) if user opted in to credit score. Required by FCRA.
6. PostHog: delete user profile (events retained in anonymized form for aggregate analytics)
7. Confirmation email sent to user upon completion
8. 30-day response window (CCPA requirement)

### Consent Architecture (Marketplace-Grade, 3 Tiers)

Consent is designed for the full marketplace evolution from day 1. By getting Tier 2 consent at signup, we never need to re-consent users when upgrading from Stage 1 to Stage 4. The consent language already covers personalized matching via any method (rules, bandit, ML, partner-submitted models).

**Tier 1 -- Cross-Product Data Use** (existing):

- Opt-in checkbox (unchecked by default) on every signup form
- "Use my data across FileFree and LaunchFree to improve my experience"
- Enables: cross-product email campaigns, segment identification, unified profile

**Tier 2 -- Personalized Product Matching** (covers Stage 1-4 marketplace):

- Opt-in checkbox on Refund Plan screen and post-filing summary
- "Use my financial profile to show me personalized product recommendations from our partners"
- Users who consent see Fit Scores and matched products (marketplace experience)
- Users who don't consent see generic product listings (static affiliate links, no personalization)
- This single consent covers: rules-based matching, bandit optimization, ML scoring, AND partner-submitted eligibility models -- all methods produce "personalized product recommendations"

**Tier 3 -- Anonymized Insights** (Stage 3+):

- Opt-in during credit score check or profile completion
- "Include my anonymized data in aggregate insights shared with financial product partners"
- Enables: segment marketplace (partners see "3,200 users in 700-749 credit band")
- No PII ever shared. Partners see only aggregate counts, demographics, and predicted conversion rates

**Additional controls**:

- **Global Privacy Control (GPC)** signal detection: if browser sends GPC, treat as opt-out for Tier 2 and Tier 3
- **"Do Not Sell or Share My Personal Information"** link in footer of every product (even though we don't sell data -- preemptive CCPA compliance)
- **Per-product unsubscribe** in email footer: users can unsubscribe from FileFree emails without affecting LaunchFree
- **Consent audit trail**: timestamp, IP, consent text version, consent tier stored per user
- **Re-consent**: required only if consent text materially changes (tier addition or language change). Stage upgrades do NOT require re-consent because Tier 2 language already covers all matching methods.

**Privacy policy language (covers all 4 stages)**: "We may use your financial profile (income bracket, credit score range, filing status, state) to match you with financial products from our partners. We never share your personal information with partners. Partners see only anonymized, aggregate data about user segments."

### ADMT Disclosure

Since we use AI for tax calculations, OCR field extraction, LLC formation guidance, and financial recommendations, CCPA 2026 rules require Automated Decision-Making Technology (ADMT) notices. Add to privacy policy:

- What decisions AI makes (tax calculations, document data extraction, partner recommendations)
- How the AI reaches those decisions (rule-based + ML models)
- Right to opt out of automated profiling for partner recommendations
- Human review available for tax calculations (manual entry fallback)

### Risk Assessments

Required by CPRA for sensitive data processing. Assessments must be completed **before processing begins** for each data category:

1. **SSN Processing Assessment** (FileFree): document purpose (tax filing), necessity (IRS requirement), safeguards (AES-256, never sent to LLMs, regex extraction, 24hr image deletion), and risk mitigation
2. **Credit Score Processing Assessment** (Phase 1.5): document purpose (personalized recommendations), consent flow (explicit opt-in), data minimization (score + range only, not full report), and FCRA compliance

---

## 1. Revenue Model (Corrected)

### Timeline

- **H2 2026**: LaunchFree earns revenue (6 months post-launch)
- **Jan-Apr 2027**: FileFree first tax season (4 months, NOT a full year)
- **2028**: Cross-sell kicks in, at-scale attach rates

### FileFree First Tax Season (Jan-Apr 2027)


| Stream                | Pessimistic Rate | Moderate Rate | Aggressive Rate | Rev Per | 5K Filers (Pess.) | 10K Filers (Mod.) | 30K Filers (Agg.) |
| --------------------- | ---------------- | ------------- | --------------- | ------- | ----------------- | ----------------- | ----------------- |
| Refund routing HYSA   | 1%               | 2%            | 4%              | $50     | $2.5K             | $10K              | $60K              |
| Financial referrals   | 0.5%             | 1%            | 1.5%            | $75     | $1.9K             | $7.5K             | $34K              |
| Audit Shield          | 1%               | 3%            | 5%              | $20     | $1K               | $6K               | $30K              |
| Tax Optimization Plan | 1%               | 2%            | 3%              | $29     | $1.5K             | $5.8K             | $26K              |
| Refund advance        | 0%               | 0%            | 0%              | --      | $0                | $0                | $0                |
| **TOTAL**             |                  |               |                 |         | **$7K**           | **$29K**          | **$150K**         |


**Rate justification** (stress test): Credit Karma achieves 2-4% on financial referrals at maturity after years of trust-building with 100M+ profiles. FreeTaxUSA hits 8-12% on audit shield as an established brand. A brand-new product with zero trust history should model Year 1 rates at 40-60% of mature rates. The pessimistic scenario assumes only 5K filers (realistic for a new, unknown product with no marketing budget) and bottom-tier attach rates.

### LaunchFree H2 2026 (~6 months)


| Stream                     | Pess. Volume | Mod. Volume | Agg. Volume | Rev Per | Pess. Total | Mod. Total | Agg. Total |
| -------------------------- | ------------ | ----------- | ----------- | ------- | ----------- | ---------- | ---------- |
| RA credits (1-3% buy)      | 20           | 100         | 150         | $49     | $1K         | $5K        | $7K        |
| Banking referrals (2-5%)   | 40           | 150         | 250         | $50     | $2K         | $7.5K      | $12.5K     |
| Payroll referrals (0.5-1%) | 10           | 30          | 50          | $100    | $1K         | $3K        | $5K        |
| Compliance SaaS (8-18%)    | 80           | 240         | 900         | $49-99  | $3.9K       | $19K       | $89K       |
| **TOTAL**                  |              |             |             |         | **$7.9K**   | **$34.5K** | **$114K**  |


Note: Compliance-as-a-Service revenue begins ~3 months after LaunchFree launch (Phase 3.5). H2 2026 assumes partial-year revenue from early adopters. See Section 1B.1 for full model.

### Combined (Year 1)


| Scenario        | LaunchFree (H2 2026) | FileFree (Jan-Apr 2027) | **Total**  |
| --------------- | -------------------- | ----------------------- | ---------- |
| **Pessimistic** | $7.9K                | $7K                     | **$14.9K** |
| Moderate        | $34.5K               | $29K                    | **$63.5K** |
| Aggressive      | $114K                | $150K                   | **$264K**  |


**Why the pessimistic scenario matters**: It models what happens if (a) user acquisition is slow (5K filers, 1K formations), (b) attach rates are bottom-tier for an unknown brand, and (c) partnerships are self-serve affiliates only (no Founder 2 deals closed). At $14.9K Year 1 revenue, the venture survives (burn is ~$278/mo real cost) but takes longer to reach meaningful revenue. This is the floor, not the target. The compliance SaaS revenue is recurring -- unlike one-time affiliate commissions, it compounds year over year.

**Year 2 (2028)**: $215K-810K (dependent on retention, growth trajectory, partnership maturity, compliance SaaS renewal rates, and Distill Formation API adoption). Includes Distill Formation API: $15K-60K (500-2K API filings @ $30 avg target pricing).

### Plan B Revenue: Zero Partnerships Closed

If Founder 2 closes no deals. Key insight: MOST fintech affiliate programs are self-serve (apply online, no calls, no relationship). The original Plan B underestimated this.

**Confirmed Self-Serve Affiliate Programs** (Founder 1 applies in one afternoon):


| Program                      | Platform     | Commission                  | Application                            |
| ---------------------------- | ------------ | --------------------------- | -------------------------------------- |
| Betterment (HYSA/investing)  | Impact.com   | $25-$1,250 per referral     | Self-serve at betterment.com/affiliate |
| SoFi (banking/investing)     | Impact.com   | $50-$100 per funded account | Self-serve via Impact                  |
| Wealthfront (HYSA/investing) | Direct       | $30-$75 per funded account  | wealthfront.com/affiliates             |
| Ally Bank (HYSA/savings)     | CJ Affiliate | $5-$12 per signup           | Self-serve via CJ dashboard            |
| Robinhood (investing)        | Impact.com   | $5-$20 per funded account   | Self-serve via Impact                  |
| Chime (banking)              | CJ Affiliate | $10-$50 per direct deposit  | Self-serve via CJ                      |
| Acorns (micro-investing)     | CJ Affiliate | $5-$10 per signup           | Self-serve via CJ                      |



| Stream                                                                    | Available Without Partnerships?                | Year 1 Revenue |
| ------------------------------------------------------------------------- | ---------------------------------------------- | -------------- |
| Tax Optimization Plan ($29/yr)                                            | YES -- direct Stripe sale                      | $1.5K-8.7K     |
| Self-serve HYSA affiliates (Betterment, SoFi, Wealthfront)                | YES -- self-serve application                  | $2.5K-15K      |
| Self-serve investment affiliates (Robinhood, Acorns)                      | YES -- self-serve application                  | $1K-5K         |
| Self-serve banking affiliates (Ally, Chime)                               | YES -- self-serve application                  | $500-3K        |
| Trinkets AdSense                                                          | YES -- self-serve                              | $50-300        |
| Audit shield (direct sale via Stripe at $24, partner with individual EAs) | PARTIAL -- no wholesale, but direct sale works | $1K-5K         |
| RA credits                                                                | NO -- requires RA wholesale partner            | $0             |
| Refund advance                                                            | NO -- requires lending partner                 | $0             |
| **TOTAL (Plan B)**                                                        |                                                | **$6.5K-37K**  |


**Plan B is not just survivable -- it's viable.** Founder 2 raises the ceiling (premium partnership terms, co-marketing deals, exclusive rates) but does NOT set the floor. The venture generates meaningful affiliate revenue from self-serve programs that require zero relationship-building. These should be submitted in Phase 0 regardless of Founder 2's availability -- there is no reason to wait.

### Partnership Milestone Deadlines (Hard Dates)


| Milestone                                                          | Owner     | Deadline       | Consequence If Missed                                           |
| ------------------------------------------------------------------ | --------- | -------------- | --------------------------------------------------------------- |
| Submit self-serve affiliate apps (Marcus, Wealthfront, Betterment) | Founder 1 | April 2026     | Delays referral revenue by approval processing time (1-2 weeks) |
| Book Column Tax demo call                                          | Founder 2 | May 2026       | No interim e-file for October extension season                  |
| Column Tax sandbox access                                          | Founder 2 | June 2026      | Cannot test e-file integration; fallback = PDF download only    |
| RA wholesale partner signed (CorpNet or equivalent)                | Founder 2 | July 2026      | Launch LaunchFree without RA service; add later. CorpNet is both an RA wholesale partner AND a formation API alternative ($69-79/filing wholesale). We build our own State Filing Engine instead (see Section 7) to avoid $50-80K/yr wholesale cost at scale. |
| Apply for Delaware DCIS credentials (ICIS API access)             | Founder 1 | April 2026     | Without DCIS ID: no Delaware API filing (Tier 1). Fallback: portal automation (Tier 2). ICIS PublicXMLService requires DCIS ID, RA number, IP registration, sandbox testing. Approval takes 2-4 weeks. |
| Apply for Stripe Issuing access                                   | Founder 1 | May 2026       | Required for programmatic payment of state filing fees during automated submission. Requires Stripe account verification. |
| Purchase formationapi.com (defensive)                             | Founder 1 | April 2026     | ~$12/yr. Redirect to distill.tax/formation. Prevents competitor from registering it. |
| TaxAudit/audit shield partnership                                  | Founder 2 | September 2026 | Launch FileFree without audit shield; add Year 2                |
| At least 1 banking partner confirmed                               | Either    | October 2026   | Refund routing not available for first tax season               |


### Partnership Documentation Strategy

Every partnership gets a comprehensive, agent-produced documentation package. This ensures bulletproof preparation for every partner conversation.

**Per-Partner Package** (generated by Partnership Dev agent + relevant domain agents):

1. **Partner Brief** (1-pager): Company overview, their product, how we integrate, revenue model for both sides, competitive landscape
2. **Integration Spec**: Technical integration requirements, API endpoints, data flow, PII handling
3. **Legal Memo**: Compliance considerations specific to this partner type (FTC disclosures for affiliate, data sharing agreements, Circular 230 for tax-adjacent)
4. **Financial Model**: Revenue projections at 3 volume tiers (pessimistic, moderate, aggressive), margin analysis, break-even point
5. **Pitch Deck** (5 slides): Problem, our product, integration value prop, projected volume, ask

**Quarterly Review Cadence**:

- Q1 (March): Review all active partnerships. Update financial projections with actuals. Identify underperformers.
- Q2 (June): Pipeline review. Score prospects by: revenue potential, integration complexity, strategic value. Prioritize top 3.
- Q3 (September): Pre-season prep. Ensure all tax season partnerships (HYSA, audit shield) are integration-tested.
- Q4 (December): Final partner readiness check before FileFree tax season.

**Legal Doc Freshness**: Compliance Monitor agent (#33) tracks partner agreement expiry dates and data sharing agreement renewal dates. Alerts 30 days before expiry.

### LaunchFree "Free" Framing (Honest, Defensible)

**What's actually free (our service -- $0 forever)**:

- LLC formation filing (document preparation + state submission via Filing Engine): $0
- Operating agreement template (state-specific, attorney-reviewed): $0
- EIN filing walkthrough: $0
- Compliance calendar + reminders: $0
- 50-state comparison AI guide (compares filing fees, annual costs, franchise tax, privacy, speed): $0

**What's NOT free (government fees -- clearly disclosed upfront)**:

- State filing fee: $35-$500 (depends on state)
- We help users find the cheapest legitimate option for their situation

**Cheapest states to form** (marketing content):


| State    | Filing Fee | Annual Cost              | Notes                     |
| -------- | ---------- | ------------------------ | ------------------------- |
| Montana  | $35        | $20/yr                   | Cheapest filing in the US |
| Kentucky | $40        | $15/yr                   | Low ongoing costs         |
| Arkansas | $45        | $150/yr                  | Higher annual             |
| Colorado | $50        | $10/yr                   | Very low annual           |
| Arizona  | $50        | $0/yr (no annual report) | No ongoing state cost     |
| Michigan | $50        | $25/yr                   | Moderate                  |


**Framing language** (use across all marketing):

> "LaunchFree handles the paperwork for $0. You only pay what your state charges -- and we'll help you pick the most affordable one."

**The differentiator**: Competitors (LegalZoom $149+, ZenBusiness $0+$199 upsells, Northwest $39) either charge service fees, bury state fees in the total, or upsell aggressively. LaunchFree's AI state comparison guide is unique -- no competitor helps you choose which state to form in based on your actual situation (home state, business type, budget, privacy needs). This is the moat.

**Competitive comparison**:


| Service        | Service Fee | Upsells                                             | State Fee Transparency        | State Comparison                    |
| -------------- | ----------- | --------------------------------------------------- | ----------------------------- | ----------------------------------- |
| LegalZoom      | $0-$299     | Heavy ($199 RA, $159 operating agreement, $159 EIN) | Buried in total               | No                                  |
| ZenBusiness    | $0          | Heavy ($199/yr Pro, $349/yr Premium)                | Shown separately              | No                                  |
| Northwest      | $39         | Moderate ($125/yr RA included Y1)                   | Shown separately              | No                                  |
| Incfile        | $0          | Heavy ($149-$349 bundles)                           | Shown separately              | No                                  |
| **LaunchFree** | **$0**      | **None (revenue from partner referrals)**           | **Upfront, before you start** | **Yes (AI-powered, all 50 states)** |


### Audit Shield Economics

- **What**: Prepaid IRS audit representation via Enrolled Agent/CPA. Covers defense costs (up to $1M), not taxes owed. 3-year federal coverage.
- **White-label partner**: TaxAudit / Protection Plus (same provider FreeTaxUSA, TaxAct, TurboTax use)
- **Our cost**: $10/return (firm-level wholesale)
- **Our price**: $19-24 (match FreeTaxUSA as low-cost leader)
- **Margin**: $9-14/sale (47-58% gross margin)
- **Attachment rate**: 5-8% first season, 10-15% at scale
- **Action**: Add TaxAudit partnership to Founder 2 pipeline (3-6 month lead time)

### 1B. Adjacent Revenue Streams (Tier 1 -- Natural Extensions)

These three extensions leverage existing product data and infrastructure with minimal new surface area. They are "Tier 1" because they require no new partnerships, no new data sources, and no significant architectural changes -- just smart reuse of what we already build.

#### 1B.1 Compliance-as-a-Service (LaunchFree Add-On)

**What**: After LLC formation, ongoing compliance management -- annual report reminders, franchise tax calculations, state deadline tracking, pre-filled renewal forms.

**Why now**: LaunchFree already captures all state-specific formation data in the 50-state JSON configs (`packages/data`). Compliance deadlines and annual report requirements are a natural extension of the same data set. Zero new infrastructure -- it's calendar math + state fee lookups + email reminders via existing n8n pipeline.

**Revenue model**:


| Metric                         | Conservative | Moderate | Aggressive |
| ------------------------------ | ------------ | -------- | ---------- |
| LaunchFree formations (Year 1) | 1,000        | 2,000    | 5,000      |
| Compliance attach rate         | 8%           | 12%      | 18%        |
| Price                          | $49/yr       | $79/yr   | $99/yr     |
| Annual recurring revenue       | $3,920       | $18,960  | $89,100    |


**Moat leverage**: We already know the user's state, entity type, formation date, and registered agent. Competitors (LegalZoom $299/yr, ZenBusiness $199/yr, Northwest $225/yr) charge 3-6x more for the same service. Our marginal cost is near zero -- no humans involved.

**Implementation**: Phase 3.5 (post-LaunchFree MVP).

- Add `compliance_calendar` table (entity_id, state, requirement_type, due_date, status, reminder_sent_at)
- Extend 50-state JSON configs with annual report deadlines, franchise tax amounts, and renewal URLs
- n8n workflow: daily check for upcoming deadlines -> email reminder at 60/30/7 days -> Slack alert if deadline passes without action
- LaunchFree dashboard: compliance status card showing next deadline, overdue items, and one-click renewal form generation

**Competitive positioning**: "You formed for free. Now stay compliant for $49/yr. LegalZoom charges $299."

#### 1B.2 Quarterly Tax Estimator (FileFree / Trinket)

**What**: For 1099/freelance workers who must pay estimated quarterly taxes (IRS Form 1040-ES). Input: YTD income + expenses. Output: recommended quarterly payment amount, next due date, and downloadable payment voucher PDF.

**Why now**: FileFree already has a tax calculation engine. Quarterly estimates are a simplified version of the annual calculation (apply safe harbor rule: 100% of prior year tax liability or 90% of current year estimated tax, whichever is smaller). This is a year-round engagement hook -- users return 4x/year instead of 1x.

**IRS quarterly deadlines** (each is a natural re-engagement trigger):


| Quarter | Income Period   | Due Date     | Notification Trigger     |
| ------- | --------------- | ------------ | ------------------------ |
| Q1      | Jan 1 -- Mar 31 | April 15     | March 15 email + push    |
| Q2      | Apr 1 -- May 31 | June 15      | May 15 email + push      |
| Q3      | Jun 1 -- Aug 31 | September 15 | August 15 email + push   |
| Q4      | Sep 1 -- Dec 31 | January 15   | December 15 email + push |


**Revenue**: Free (acquisition + retention). Monetize indirectly via:

1. Tax Optimization Plan upsell: "Based on your Q3 income, we found $2,400 in deductions you're missing. Upgrade to see the full breakdown." ($29/yr)
2. Year-round engagement: users who visit 4x/year have 3x higher conversion on financial product referrals vs. one-time filers
3. SEO traffic: "quarterly tax calculator" has 12K monthly searches with moderate competition

**Moat leverage**: Prior-year filing data from FileFree auto-populates safe harbor calculations. No other free estimator has this context. Credit Karma's estimator requires manual input every time. Ours says: "Based on your 2026 return, your Q1 2027 estimated payment is $1,847."

**Implementation** (two-phase):

1. **Phase 1.5 (Trinket)**: Basic manual-input calculator at `tools.filefree.ai/calculators/quarterly-tax`. No auth required. SEO-optimized landing page. CTA: "File your annual return for free with FileFree."
2. **Phase 7 (FileFree feature)**: Auto-populated from prior return data. Logged-in users see personalized estimates. Payment voucher PDF generation. Quarterly reminder emails.

#### 1B.3 Refund Splitting + Goal-Based Savings (FileFree Phase 7)

**What**: At the refund moment -- the highest-intent financial moment of the year -- let users split their refund across multiple destinations. IRS Form 8888 (Allocation of Refund) already supports direct deposit to up to 3 accounts.

**Why now**: The refund screen is where affiliate conversion happens. Instead of "here's your refund, goodbye," we say: "Put $1,000 in a HYSA earning 5.0% APY and $500 in a Roth IRA -- your future self will thank you." The user is already in "money mode" and the refund feels like found money.

**How Form 8888 works** (IRS-supported, no partner needed):

- User allocates refund to up to 3 accounts (checking, savings, IRA)
- Each allocation: routing number + account number + amount
- We generate Form 8888 as part of the 1040 package -- IRS handles the split
- Zero custodial risk: money goes directly from IRS to user's accounts

**Revenue model**:


| Metric                        | Conservative | Moderate | Aggressive |
| ----------------------------- | ------------ | -------- | ---------- |
| FileFree filers               | 5,000        | 10,000   | 30,000     |
| Split adoption rate           | 3%           | 5%       | 8%         |
| Splits with affiliate account | 50%          | 60%      | 70%        |
| Avg affiliate commission      | $30          | $50      | $75        |
| Revenue from splits           | $2,250       | $15,000  | $126,000   |


**Moat leverage**: We know the exact refund amount, filing status, age, and (with intelligence layer) the user's full financial profile. We can make goal-appropriate recommendations:

- 24, single, no retirement: "A Roth IRA with your $1,200 split will be worth ~$15,000 by retirement"
- 30, married, new homeowner: "Build your emergency fund -- $2,000 into a HYSA earning 5.0%"
- 22, student loans: "Extra $500 payment on your loans saves you $1,200 in interest"

**Implementation**: Expand P7.4 (Refund Plan screen) to include:

- Refund splitting UI: drag sliders or enter amounts for up to 3 accounts
- Goal templates: "Emergency Fund," "Retirement," "Debt Payoff," "Fun Money"
- Account opening flow: inline affiliate link to partner HYSA/IRA (Betterment, SoFi, Wealthfront)
- Form 8888 PDF generation: trivial addition to existing 1040 PDF pipeline

**Competitive edge**: TurboTax offers refund splitting but buries it in settings. No free filing product makes it the centerpiece of the post-filing experience. We make it the star.

#### 1C. Distill -- B2B Compliance Automation Platform (distill.tax) (Phase 9+)

**What**: Distill is the B2B umbrella brand for all compliance automation products. It started as a CPA tax automation SaaS, but the same infrastructure pattern applies to every compliance vertical: tax extraction, LLC formation, and ongoing entity compliance. "Distill" = extract the pure essence from complex government paperwork. The name works across verticals: distill W-2 data into structured fields, distill 50-state requirements into one API call, distill annual report deadlines into automated filings.

**Brand architecture (why one B2B brand, not separate brands per vertical):**

Companies like Stripe (Payments, Atlas, Issuing, Identity), Twilio (SMS, Voice, Email), and Plaid (Auth, Identity, Transactions, Income) use one brand for multiple API products. This works because: (1) developers hate juggling multiple platforms -- one login, one API key, one billing relationship is a massive UX advantage; (2) cross-sell is frictionless ("add Formation API to your Distill plan"); (3) brand equity compounds with every vertical added. The Intuit model (separate brands per vertical: TurboTax, QuickBooks, ProConnect) only makes sense with separate sales teams and marketing budgets. At 2 founders, the single-brand model is correct.

```
CONSUMER BRANDS (free, own domains, own palettes):
  filefree.ai ......... Free tax filing (violet/purple)
  launchfree.ai ....... Free LLC formation (teal/cyan)
  tools.filefree.ai ... Trinkets / utility tools (amber/orange)

B2B BRAND (paid, one brand, one platform):
  Distill (distill.tax)
    distill.tax ............... Landing page + CPA SaaS dashboard
    api.distill.tax ........... Developer API (tax + formation + compliance)
    docs.distill.tax .......... Unified documentation
    Product lines:
      Distill for CPAs ...... SaaS dashboard, $49-199/mo (Phase 9)
      Distill Tax API ....... Per-return pricing (Summer 2026, calculation-only; e-file January 2027)
      Distill Formation API . Per-filing pricing, $20-40/filing target (Summer 2026)
      Distill Compliance API  State compliance calendars, deadline tracking (Summer 2026)

HOLDING COMPANY:
  paperworklabs.com ... Corporate site, portfolio, command center, admin panel
```

**Four product lines under one brand:**

1. **Distill for CPAs** (SaaS dashboard at distill.tax, Phase 9, Summer 2026) -- Upload client W-2s/1099s in bulk, auto-extract, review, export to tax software. Shares `packages/tax-engine/` and `packages/document-processing/` with FileFree.
2. **Distill Tax API** (api.distill.tax/tax, Summer 2026) -- Headless Tax-as-a-Service for platforms. Per-return pricing ($5-15/return). Calculation-only at launch; e-file endpoint activates January 2027 when MeF transmitter ships. Shares `packages/tax-engine/`.
3. **Distill Formation API** (api.distill.tax/formation, Summer 2026) -- LLC formation as a service for CPAs, law firms, HR platforms, banking apps, accounting software. Per-filing pricing ($20-40/filing target, undercutting incumbent API providers like CorpNet at ~$69-79 and FileForms at ~$30-60). Powered by the same State Filing Engine as LaunchFree (`packages/filing-engine/`).
4. **Distill Compliance API** (api.distill.tax/compliance, Summer 2026) -- State compliance calendars, deadline tracking, annual report reminders, automated alerts. Natural extension of `packages/data/` 50-state configs.

**Why the Formation API matters:** The State Filing Engine we build for LaunchFree is the same infrastructure CPAs, law firms, and fintech apps need. Today they buy from FileForms ($99-399/filing retail) or CorpNet ($99-269/filing retail). Our marginal cost is estimated at ~$0.25-0.50/filing (virtual card fees + compute). We can price at $20-40/filing wholesale and still achieve 90%+ gross margin. The consumer product (LaunchFree) subsidizes the API, and the API subsidizes the consumer product -- a flywheel that single-product API providers cannot replicate.

**Why this exists**: MagneticTax (YC S25) raised venture capital to build exactly the CPA tax extraction product. We build the identical OCR/extraction pipeline for consumer FileFree anyway. The B2B product is ~20% incremental engineering on top of Phase 7 infrastructure. It is the fastest path to predictable revenue because CPAs pay monthly SaaS fees from day 1 -- no marketplace scale required.

**Tech overlap with consumer products (~80% shared per vertical)**:
- OCR pipeline (Cloud Vision + GPT tiered extraction) -- shared with FileFree
- W-2/1099 field extraction + Pydantic schemas -- shared with FileFree
- Tax calculation engine (50-state) -- shared with FileFree
- State Filing Engine (portal automation, state APIs) -- shared with LaunchFree
- 50-state data layer (`packages/data/`) -- shared with FileFree + LaunchFree
- Document storage (GCP Cloud Storage, 24hr lifecycle) -- shared
- SSN isolation (regex extraction, never sent to LLMs) -- shared

**B2B-specific delta for CPA SaaS (~2-3 weeks engineering)**:
- Multi-tenant team management (firm -> preparers -> clients)
- Bulk document upload (drag-and-drop multiple documents, queue through shared OCR pipeline, batch progress tracking)
- Professional dashboard (client list, per-client document status, extraction confidence, review workflow)
- Tax software export: CSV/XML import files for UltraTax (CSV), Drake (XML), ProConnect (CSV), Lacerte (CSV) -- all publicly documented formats
- Stripe B2B billing with seat-based plans and usage metering

**Pricing**:

| Plan | Price | Preparers | Returns/mo | API Access |
| ---- | ----- | --------- | ---------- | ---------- |
| Solo | $49/mo | 1 | 50 | No |
| Team | $99/mo | 3 | 200 | No |
| Firm | $199/mo | Unlimited | 500+ | Yes |

Annual billing discount: 20% (Solo $39/mo, Team $79/mo, Firm $159/mo).

**Revenue projections (Year 1 -- January 2027 launch)**:

| Scenario | CPA Firms | Avg Plan | Monthly Rev | Annual Rev |
| -------------- | --------- | -------- | ----------- | ---------- |
| Conservative | 30 | $79/mo | $2,370 | $28K |
| Moderate | 100 | $99/mo | $9,900 | $119K |
| Aggressive | 300 | $129/mo | $38,700 | $464K |

**Competitive positioning vs MagneticTax**:
- MagneticTax is VC-funded (YC S25) with dedicated burn. We're bootstrapped with consumer filing as the primary product -- the B2B arm is marginal cost.
- MagneticTax only does 1040 data entry. Distill inherits our full form coverage (1040 + Schedules 1, A, B, C, D + 1099-NEC/INT/DIV + 50-state returns) and expands as consumer FileFree adds forms.
- MagneticTax has no consumer product, no financial marketplace, no cross-product data moat. Distill is a revenue-generating arm of a larger platform.

**Distribution**: Target independent CPAs and small firms (1-10 preparers). 75,000+ CPA firms in the US. Tax season creates natural urgency (January-April). Off-season demand: extensions, amendments, prior-year returns, quarterly estimates. See Section 5M for bootstrapped B2B GTM playbook.

**Architecture**: New `apps/distill/` in monorepo with its own Next.js app at `distill.tax`. Shares `packages/tax-engine` (tax calc + form generators), `packages/document-processing` (OCR pipeline + extraction schemas), `packages/ui`, `packages/auth`, `packages/analytics`. Uses the same `apis/filefree/` backend with B2B-specific route group (`/api/v1/pro/*`) and firm-scoped middleware.

**Brand separation**: Distill is a separate brand from FileFree. Consumer FileFree = free, ad-free, trust-first. Distill = professional-grade paid SaaS. They share `packages/tax-engine/` and `packages/document-processing/` but have separate domains, landing pages, and marketing. The word "Free" in "FileFree" creates cognitive dissonance for B2B buyers paying $199/mo (SBI Growth research, Intuit precedent: TurboTax vs ProConnect/Lacerte). "Distill" = extract pure essence from raw material, fits naturally under Paperwork Labs (distilling paperwork).

**Four product lines, all launching Summer 2026**: Distill has four product lines under one B2B brand: **Distill for CPAs** (SaaS dashboard at distill.tax), **Distill Tax API** (headless Tax-as-a-Service at api.distill.tax/tax, calculation-only at launch, e-file January 2027), **Distill Formation API** (LLC formation as a service at api.distill.tax/formation, powered by LaunchFree's State Filing Engine), and **Distill Compliance API** (state compliance calendars, deadline tracking at api.distill.tax/compliance). The CPA SaaS is a UI product. The APIs are headless engines. All share core infrastructure (`packages/tax-engine/`, `packages/filing-engine/`, `packages/data/`) but are distinct products with distinct pricing. AI-augmented development means the incremental B2B work (multi-tenant auth, API keys, billing, docs) ships in weeks, not quarters.

**Multi-tenant data isolation (CRITICAL)**: All Distill API routes use firm-scoped middleware that injects `firm_id` from auth token into every database query. Row-level security (RLS) on PostgreSQL enforced via `SET app.current_firm_id` + RLS policies. No query can return data from a different firm. CPA firm A's client data must never leak to CPA firm B. Security audit required before Distill launch (P9.9).

**Data Processing Agreement (DPA)**: Consumer FileFree users consent directly. Distill is different: the CPA firm is our customer, but the individuals whose W-2s are uploaded are NOT our direct users. We process their PII on behalf of the CPA firm. CPA firms must sign a DPA covering: what data we process, how long we retain it (24hr for images per existing policy), that we do not use client data for consumer product matching, and CCPA/state privacy law compliance. DPA template needed before Distill launch (attorney consult scope item, P9.10).

**Audit trail logging**: Every extraction, edit, export, and submission timestamped with user ID and firm ID. Immutable audit log retained for 7 years (IRS record retention requirement). Exportable as CSV for CPA firm compliance needs. This is a differentiation feature -- CPAs face IRS audits and need proof of every step.

**Distill Formation API revenue projections (launching Summer 2026)**:

| Scenario | Year 2 (2028) | Year 3 (2029) | Basis |
| -------------- | ------------- | ------------- | ----- |
| Conservative | $15K | $150K | 500 API filings @ $30 avg (Year 2), 5K @ $30 (Year 3) |
| Moderate | $36K | $360K | 1.2K API filings @ $30 avg (Year 2), 12K @ $30 (Year 3) |
| Aggressive | $60K | $600K | 2K API filings @ $30 avg (Year 2), 20K @ $30 (Year 3) |

Note: $20-40/filing is target pricing, undercutting incumbent API providers. Marginal cost estimated at ~$0.25-0.50/filing (validated during Phase 3 development). Gross margin target: 90%+.

**Implementation**: Phase 9 (Summer 2026) for full Distill platform — CPA SaaS + all APIs. ~80% shared infrastructure from Phases 1-3. Incremental B2B work: multi-tenant auth, API keys, billing, docs. See TASKS.md Phase 9 + Phase 9.5 for task breakdown.

---

## 2. Architecture

### Monorepo (pnpm workspaces, no Turborepo)

```
venture/
  apps/
    filefree/            (filefree.ai -- Next.js, existing code from web/)
    distill/             (distill.tax -- Next.js, B2B tax automation dashboard, Phase 9)
    launchfree/          (launchfree.ai -- Next.js, scaffolded)
    studio/              (paperworklabs.com -- Next.js, COMMAND CENTER + portfolio)
    trinkets/            (utility tools -- Next.js SSG, Vercel free, Phase 1.5)
  packages/
    ui/                  (22 shadcn components + theme + chat widget)
    auth/                (shared auth: hooks, middleware, session)
    analytics/           (PostHog + attribution + PII scrubbing)
    data/                (50-state formation + tax JSON configs, Zod schemas, state engine API)
    tax-engine/          (tax calculation engine, form generators, MeF XML schemas, dual-path reconciliation)
    document-processing/ (OCR pipeline client, field extraction schemas, document storage lifecycle, bulk upload queue)
    intelligence/        (financial profile, recommendations, experimentation, data intelligence, campaigns)
    email/               (shared email templates, React Email)
  apis/
    filefree/        (Python/FastAPI -- existing code from api/)
    launchfree/      (Python/FastAPI -- scaffolded)
    studio/          (Python/FastAPI -- command center backend, aggregator)
  infra/
    compose.dev.yaml
    hetzner/
    env.dev.example
  docs/
    KNOWLEDGE.md
    templates/
      trinket-one-pager.md
      trinket-prd.md
  pnpm-workspace.yaml
  package.json
  Makefile
  render.yaml
```

### Federated Identity (Separable by Design)

**The tension**: We want seamless SSO for UX, but each product must be independently valuable and separable if acquired.

**The pattern**: Each product owns its own user table in its own database. The venture layer adds SSO and cross-product intelligence on top, but is removable without breaking either product.

```
PRODUCT DATABASES (independent, can be separated):

  filefree DB:
    users: id, email, name, password_hash, ...filefree-specific fields...
           Clerk userId (the only cross-product link; per-product user tables remain separable-by-design) — e.g. optional `clerk_user_id` column

  launchfree DB:
    users: id, email, name, password_hash, ...launchfree-specific fields...
           Clerk userId (the only cross-product link; per-product user tables remain separable-by-design) — e.g. optional `clerk_user_id` column

VENTURE DATABASE (studio, never sold):

  venture_identities: id, email, name, created_at
  identity_products: internal venture id (joins to Clerk userId for SSO), product, product_user_id, first_used
  user_events: id, venture id tied to Clerk userId, event_type, product, metadata, timestamp
  user_segments: venture id tied to Clerk userId, segment, computed_at
```

**How SSO works**: User signs up on FileFree -> FileFree creates its local user, storing **Clerk `userId`** (the only cross-product link; per-product user tables remain separable) -> event fires to studio -> studio creates/updates venture-layer identity rows tied to that **Clerk `userId`** -> if the same person later uses LaunchFree, LaunchFree creates its local user, sends event -> studio links both product user rows through the same **Clerk `userId`**. (Studio may use internal `venture_identity` keys for reporting; they map to the same person via **Clerk `userId`**, not as a second public cross-product id.)

**If FileFree is acquired**: Remove the optional Clerk / venture link columns (`clerk_user_id` and any related venture FK). FileFree still works independently. The buyer gets a complete product with its own user system.

### Authentication Architecture

**User Auth (FileFree, LaunchFree)**:

- Providers: Google OAuth + Apple Sign-In (cover 95%+ of users). Optional email/password fallback.
- Implementation: **Clerk** via `@paperwork-labs/auth-clerk` and `@clerk/nextjs` per app; shared sign-in patterns and JWT verification live in the monorepo package. **Auth.js v5** is not used or planned; see [KNOWLEDGE.md](KNOWLEDGE.md) §D92.
- SSO across subdomains: FileFree/Trinkets can share `.filefree.ai` cookies where Clerk’s deployment allows; LaunchFree and other brands use **Clerk’s satellite** handoff to `accounts.paperworklabs.com`—not a custom cookie across unrelated apex domains. Studio DB may still record identity-product links for intelligence.
- Each product keeps its own user table (separable-by-design). **Clerk userId (the only cross-product link; per-product user tables remain separable-by-design)** is the stable join; Studio venture tables map products to the same person.

**Admin Auth (paperworklabs.com + admin panels on all products)**:

- Current implementation: Basic Auth for Studio admin routes. Username must be in `ADMIN_EMAILS`, password must match `ADMIN_ACCESS_PASSWORD`.
- Admin allowlist stored in environment variable: `ADMIN_EMAILS=sankalp@paperworklabs.com,olga@<personal-email>` (founder's Workspace email + Olga Sharma's personal email per D76)
- Admin routes: `/admin/`* on paperworklabs.com, `/admin/`* on FileFree, `/admin/*` on LaunchFree.
- Migration target: move admin protection fully onto Clerk + allowlist (`@paperwork-labs/auth-clerk` / Studio middleware), retiring Basic when operators sign off; see [docs/infra/CLERK_STUDIO.md](docs/infra/CLERK_STUDIO.md).

**Trinkets Auth**: No auth. Public utility tools. Cross-sell CTAs link to FileFree/LaunchFree where users sign up. If we ever want saved preferences, use localStorage or add optional Google sign-in later.

`**@paperwork-labs/auth-clerk` (from `packages/auth/`)** — `RequireAuth`, `useUser`, `useAdmin`, `SignInShell`, `createClerkAppearance`, FastAPI `paperwork_auth` / JWT verifiers; not a generic Auth.js v5 `packages/auth` plan.

### Cursor Workspace Scoping

**Default: Open the repo root.** All folders are visible in the sidebar. Cursor handles context well with `.cursor/rules/` glob patterns -- venture-level personas use `alwaysApply: true` and are available everywhere. Product-specific personas activate automatically based on file glob patterns.

Focused workspaces are optional for deep-focus sessions where you want to reduce AI context noise:

- **Deep-focus on LaunchFree**: Open `apps/launchfree/` as workspace root
- **Deep-focus on FileFree**: Open `apps/filefree/` as workspace root
- **Deep-focus on shared packages**: Open `packages/` as workspace root

Each `apps/` and `apis/` directory can have its own `.cursor/rules/` with product-specific personas. But the default workflow is: open root, see everything, work on whatever you need.

### Brand Palettes (Multi-Brand Theme System)

**FileFree** (Tax / Trust / Calm): Violet-Indigo family

- Primary: `#4F46E5` (Indigo 600)
- Gradient: `#8B5CF6` -> `#9333EA` (Violet 500 -> Purple 600)
- Background: `#020817` (Slate 950)
- Typography: Inter + JetBrains Mono

**LaunchFree** (Business Formation / Energy / Action): Teal-Cyan family

- Primary: `#0D9488` (Teal 600)
- Gradient: `#14B8A6` -> `#06B6D4` (Teal 400 -> Cyan 500)
- Background: `#0A0F1A` (deep navy)
- Typography: Inter + JetBrains Mono

**Studio/Command Center** (Internal / Data / Ops): Zinc-Neutral family

- Primary: `#71717A` (Zinc 500)
- Background: `#09090B` (Zinc 950)
- Typography: Inter + JetBrains Mono

**Trinkets / Tools** (Utility / Approachable / Helpful): Amber-Orange family

- Primary: `#F59E0B` (Amber 500)
- Gradient: `#F59E0B` -> `#EA580C` (Amber 500 -> Orange 600)
- Background: `#0C0A09` (Stone 950)
- Typography: Inter + JetBrains Mono

**Implementation**: CSS `[data-theme]` selectors in `packages/ui/themes.css`. Each app sets its theme via `<body data-theme="trinkets">`. All shadcn components inherit the right colors automatically. 4 themes: `filefree`, `launchfree`, `studio`, `trinkets`. Uses split complementary color theory for family cohesion with clear differentiation ([source: thegrowthuxstudio.com](https://thegrowthuxstudio.com/split-complementary-colors-what-they-say-about-your-brand-product-and-design-maturity/)).

### Port Map (Local Development)

All ports start from `x001` to avoid conflicts with default ports (3000, 8000) from other projects.


| Service            | Port | Notes                             |
| ------------------ | ---- | --------------------------------- |
| **Frontends**      |      |                                   |
| apps/filefree      | 3001 | Next.js `--port 3001`             |
| apps/launchfree    | 3002 | Next.js `--port 3002`             |
| apps/trinkets      | 3003 | Next.js `--port 3003`             |
| apps/studio        | 3004 | Next.js `--port 3004`             |
| **Backends**       |      |                                   |
| apis/filefree      | 8001 | uvicorn `--port 8001`             |
| apis/launchfree    | 8002 | uvicorn `--port 8002`             |
| apis/studio        | 8003 | uvicorn `--port 8003`             |
| **Infrastructure** |      |                                   |
| PostgreSQL         | 5432 | Default (shared, schema-isolated) |
| Redis              | 6379 | Default (shared, key-prefixed)    |


**Environment variables per app**: Each frontend sets `NEXT_PUBLIC_API_URL=http://localhost:800X` matching its backend.

**Dev commands** (root `package.json` scripts via pnpm):


| Command               | What It Starts    | Use Case                               |
| --------------------- | ----------------- | -------------------------------------- |
| `pnpm dev:filefree`   | 3001 + 8001       | Working on FileFree                    |
| `pnpm dev:launchfree` | 3002 + 8002       | Working on LaunchFree                  |
| `pnpm dev:trinkets`   | 3003 (no backend) | Working on Trinkets (client-side only) |
| `pnpm dev:studio`     | 3004 + 8003       | Working on Studio                      |
| `pnpm dev:all`        | All ports         | Cross-product testing                  |


Each dev command uses `concurrently` to start both frontend and backend. Trinkets has no backend (all client-side processing). `pnpm dev:all` starts everything for integration testing.

### 2B. Production Reliability Architecture

FileFree handles SSNs, financial data, and IRS submissions. A single miscalculation or double-submit during tax deadline surge is catastrophic. These patterns are non-negotiable for a financial product operating at scale during a 10-week annual peak.

#### Tier 1 -- Must-Have Before January 2027

These block tax season launch if absent.

**2B.1 Idempotency Keys**

Every state-changing financial operation (filing submission, refund routing, payment processing) requires a client-generated idempotency key. Backend stores key + result in Redis (TTL 24hr) and returns the cached result on duplicate request.

- Pattern: `X-Idempotency-Key` header on all `POST`/`PUT` to `/api/v1/filings/`*, `/api/v1/payments/*`, `/api/v1/submissions/*`
- Prevents double-submits during tax deadline surge when users rage-click "Submit to IRS"
- Implementation: FastAPI middleware that checks Redis before route handler executes. If key exists, return stored response (HTTP 200 with original result). If not, execute handler, store result, return response
- Key format: client-generated UUIDv4 (frontend generates on form mount, persists in component state)
- Redis schema: `idempotency:{endpoint}:{key}` -> JSON `{status_code, body, created_at}`

**2B.2 Circuit Breakers + Graceful Degradation**

Every external service call wrapped in a circuit breaker. Library: `pybreaker` for Python.

States: CLOSED (normal) -> OPEN (after 5 failures in 60s, fast-fail for 30s) -> HALF-OPEN (allow 1 probe request).

Degradation strategy per service:


| Service             | Circuit Breaker Name | Degradation When Open                                                                                                                             |
| ------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cloud Vision OCR    | `cb_cloud_vision`    | Queue image in Redis, return "processing" status, retry via background task. User sees "Still working on your W-2..."                             |
| OpenAI GPT          | `cb_openai`          | Fall back to rule-based field mapping (regex + position heuristics). Lower accuracy, no AI insights. Flag for re-processing when service recovers |
| IRS MeF Transmitter | `cb_irs_mef`         | Queue submission in PostgreSQL (`submission_queue` table), show user "Submitted, awaiting IRS confirmation." Process queue when circuit closes    |
| Column Tax API      | `cb_column_tax`      | Fall back to PDF download. User can still get their completed return                                                                              |
| Affiliate Tracking  | `cb_affiliate`       | Log conversion event locally in PostgreSQL. Reconcile with affiliate platform later. Zero user impact                                             |


**B2B SLA consideration (Distill)**: Consumer users tolerate "try again later." CPA firms processing 50+ docs/day during tax season need uptime guarantees. Minimum SLA for Distill: 99.5% uptime during tax season (January-April). Circuit breaker degradation must be transparent to CPA users: show degradation status in Distill dashboard, queue requests rather than dropping them, and send email notification when service recovers. SLA is documented in Distill terms of service and monitored via the Filing Health Dashboard (Section 2B.4).

**2B.3 Tax Calculation Reconciliation Pipeline**

Dual-path verification for every tax return:

- **Path A (Forward)**: Income -> deductions -> credits -> tax liability -> payments/withholding -> refund or balance due
- **Path B (Reverse)**: Refund + total tax paid -> effective tax rate -> back-calculate expected taxable income -> compare against Path A taxable income

If Path A and Path B taxable income delta exceeds **$1 tolerance**, flag return for manual review before showing results to user. This catches rounding errors, logic bugs, and data corruption.

Additional safeguards:

- Nightly batch reconciliation job: re-runs all day's calculations and compares against stored results. Any mismatch alerts `#ops-alerts`
- IRS Publication 17 test vector suite: 20+ worked examples from IRS publications, run as regression tests on every tax engine change
- Seasonal audit: before January launch, run ALL test vectors through the engine and publish a coverage report

**2B.4 Structured Observability (OpenTelemetry)**

Instrument the full OCR-to-filing pipeline with distributed tracing. Each filing gets a trace ID that follows it end-to-end.

```
Trace: filing-{uuid}
├── ocr.upload (image received, size, format)
├── ocr.preprocess (auto-rotate, contrast, resize)
├── ocr.cloud_vision (API call, response time, text block count)
├── ocr.field_mapping (GPT model used, confidence scores per field)
├── tax.calculate (engine version, calculation time, result hash)
├── tax.reconcile (Path A vs Path B delta, pass/fail)
├── filing.pdf_generate (page count, render time)
├── filing.submit (MeF XML size, transmission time)
└── filing.ack (IRS acknowledgment status, turnaround time)
```

Stack:

- OpenTelemetry SDK (Python `opentelemetry-api` + `opentelemetry-sdk`)
- Exporter: OTLP to Grafana Cloud free tier (50GB traces/mo, 50GB logs/mo, 10K metrics series)
- Dashboard: single "Filing Health" view with pipeline success rate, p50/p95/p99 latency per span, OCR confidence distribution, reconciliation delta distribution
- Alerting: Grafana alerting rules for p99 > 60s, error rate > 1%, reconciliation failure rate > 0.1%

**2B.5 Load Testing (Tax Season Patterns)**

Tax filing follows a power-law distribution: 80% of annual volume in 10 weeks (Jan 20 -- Mar 31), 40% in the final 2 weeks before April 15. The system must handle 10x average daily load without data loss.

Tool: k6 (open-source, scriptable in JavaScript, runs in CI).

Test scenarios:


| Scenario       | Concurrency       | Duration   | What It Tests                                            |
| -------------- | ----------------- | ---------- | -------------------------------------------------------- |
| Steady state   | 100 users         | 1 hour     | Baseline throughput, resource consumption                |
| Deadline surge | 100 -> 1,000 ramp | 15 minutes | Auto-scaling, queue depth, error rate under spike        |
| OCR bottleneck | 500 image uploads | 30 minutes | Cloud Vision rate limits, upload queuing, backpressure   |
| Soak test      | 2x average load   | 8 hours    | Memory leaks, connection pool exhaustion, Redis eviction |


Performance budget:

- p95 filing completion (upload to result): < 30 seconds
- p99 filing completion: < 60 seconds
- Zero data loss under any load scenario
- Error rate < 0.1% at 10x average load

Cadence: monthly runs starting October 2026. Results posted to `#ops-alerts` with trend comparison to previous run.

#### Tier 2 -- Should-Have (Year 1-2)

**2B.6 Event Sourcing for Filing State Machine**: Filing status transitions (draft -> processing -> review -> submitted -> accepted/rejected) stored as an append-only event log, not a mutable status column. Enables: full audit trail, replay for debugging, temporal queries ("what was the status at 3pm?"), and compliance evidence. Defer to post-launch; current status column works for MVP volume.

**2B.7 Encryption Key Rotation**: AES-256 keys for PII at-rest encryption need rotation capability without downtime. Design: key versioning (each encrypted value tagged with key version), background re-encryption job, zero-downtime rotation. Implement before 10K users or before any SOC 2 audit.

**2B.8 Schema Registry + API Contract Testing**: As the monorepo grows (3 APIs, 4 frontends), API contracts become fragile. Use OpenAPI specs as source of truth, auto-generate TypeScript clients via `openapi-typescript`, and run contract tests in CI. Custom CI step detects breaking changes before merge.

**2B.9 Multi-Region Readiness**: Neon supports read replicas. Render supports multi-region. Design the data layer for eventual multi-region deployment (read replicas for tax season surge, primary in us-west). Don't implement until 50K+ users, but don't make architectural decisions that prevent it.

**2B.10 Progressive Rollout + Canary Deploys**: Feature flags (PostHog) for gradual rollout of new tax forms and calculation changes. Canary deploys via Render (deploy to 10% of traffic, monitor error rate, auto-promote or rollback). Critical for mid-season form releases (Schedule A in February 2027).

---

## 3. paperworklabs.com: The Command Center (Detailed Spec)

The command center is the control plane for the entire venture. It is what makes the "one human + AI agents" model operationally viable. 14 admin pages organized in 3 tiers based on operational priority, plus a public docs viewer.

### Tier 1 -- Build First (enables daily operations)

**P4.1 Company Landing Page** (`/` -- public, paperworklabs.com)

- Hero: "Paperwork Labs" wordmark, one-liner ("We build tools that eliminate paperwork")
- Portfolio: Cards linking to FileFree, LaunchFree, and Trinkets with descriptions and status badges
- Team: Sankalp + Olga Sharma
- Footer: legal info ("Paperwork Labs LLC | California"), social links, contact email
- Data source: Static

**P4.2 Admin Auth** (`/admin/`* -- protected)

- Current: Basic Auth guard in `apps/studio/src/middleware.ts`
- Admin gate: `ADMIN_EMAILS` env var allowlist + shared `ADMIN_ACCESS_PASSWORD`
- Target: migrate to `withAdminAuth` from shared `packages/auth/` after package extraction
- No role system for now (two founders only)

**P4.3 Studio-API Scaffold** (Backend)

- FastAPI on Hetzner CX33 (shared with n8n, Postiz)
- Aggregator backend: pulls data from all external APIs (Render, Vercel, n8n, PostHog, Stripe)
- PostgreSQL for venture_identities, user_events, campaigns

**P4.4 Mission Control Dashboard** (`/admin`)

- Activity feed: live terminal-style log of all agent actions (monospace, auto-scroll, new entries from top)
- Summary cards: total users, revenue this month, active agents, uptime
- Quick links to each product's admin
- Data sources: n8n executions, Render health, Vercel deployments, PostHog events, Stripe revenue
- **Compliance Status Indicator**: traffic-light badge (green/yellow/red) for: cyber insurance active, data breach plan current, EFIN cert valid, privacy policy reviewed within 90 days, ToS reviewed within 90 days. Data from Compliance & Security Monitor agent (#33).
- **Data Integrity Dashboard**: per-state freshness badges (green: <30 days, yellow: 30-60 days, red: >60 days since last verification). Volatile states (CA, NY, TX, FL, IL) validated daily. Drill-down shows source URLs and last-verified timestamps. Data from State Data Validator agent (#21).

**P4.5 Agent Monitor** (`/admin/agents`)

- List of all n8n workflows with status (active/paused/failed)
- Last execution time, success/failure count, average execution duration
- Click into any workflow to see recent executions and logs
- Alert badges for failed executions
- Data source: n8n API (workflows + executions endpoints)

**P4.6 Infrastructure Health** (`/admin/infrastructure`)

- Render services: status, deploy history, resource usage
- Vercel deployments: status per app
- Hetzner VPS: CPU, RAM, disk from monitoring API
- Neon databases: connection count, storage used
- Upstash Redis: command count, memory
- Data sources: Render API, Vercel API, Hetzner API, Neon API, Upstash API

### Tier 2 -- Build Next (enables growth operations)

**P4.7 Analytics** (`/admin/analytics`)

- PostHog dashboard embeds or API pulls
- Key metrics: DAU, signup funnel, feature usage, retention
- Per-product breakdown
- Data source: PostHog API

**P4.8 Support Inbox** (`/admin/support`)

- All support conversations (chat widget + email) in one feed
- AI response drafts, human overrides
- Conversation status: open, resolved, escalated
- Data source: PostgreSQL (conversation store on Hetzner)

**P4.9 Social Media Command** (`/admin/social`)

- View scheduled posts across all platforms
- Approve/reject AI-drafted content
- Performance metrics per post
- Data source: Postiz API

**P4.10 State Data Observatory** (`/admin/data`)

- All 50 states with freshness indicators (green/yellow/red)
- Last verified date, data sources, change history
- Alert for states with stale data (>30 days since verification)
- Data source: `packages/data/` JSON files + n8n validator results

### Tier 3 -- Build When Revenue Flows

**P4.11 Revenue & Spend Intelligence** (`/admin/revenue`)

- Stripe revenue by product, stream, time period
- Affiliate revenue from partner dashboards
- MRR, churn, ARPU calculations
- **Spend overview panel**: monthly burn by category (infra, AI/ML, domains, SaaS tools, legal, marketing). Data from `docs/FINANCIALS.md` Monthly Actuals section (EA logs, CFO analyzes). Trend chart showing burn rate over time.
- Data source: Stripe API + affiliate dashboard APIs + FINANCIALS.md

**P4.12 Campaign Control** (`/admin/campaigns`)

- Create/manage cross-sell campaigns
- Target segments, message templates, schedule
- Performance: open rate, click rate, conversion
- Data source: Campaign tables in studio DB

**P4.13 User Intelligence** (`/admin/users`)

- Venture identity browser: see all users across products
- Segments: "Filed taxes + formed LLC", "High income + no LLC", etc.
- Cross-product journey visualization
- Data source: Venture identity DB + cross-product queries

**P4.14 Docs Viewer** (`/docs` -- public, no auth needed)

- Renders company docs from the git repo as clean, readable HTML pages
- Pages: Master Plan, Financials, Knowledge Base, Tasks, AI Model Registry
- Uses `react-markdown` or `next-mdx-remote` to render markdown fetched from GitHub API (raw content URL)
- Clean typography, table styling, anchor links for section navigation
- Responsive and mobile-friendly -- designed for non-technical readers
- No GitHub account needed to read
- **Primary use case**: Founder shares `paperworklabs.com/docs/financials` with wife to review company finances, or `paperworklabs.com/docs/master-plan` to read the full strategy
- Data source: GitHub raw content API (e.g., `https://raw.githubusercontent.com/{owner}/{repo}/main/docs/FINANCIALS.md`)
- Cached with React Query (staleTime: 5 min) so pages load instantly after first visit
- Table of contents sidebar generated from markdown headings

### UX Guidelines (Admin)

- Use shadcn Table components for all list views. No custom data grid libraries.
- Use Recharts (already in stack) for trend charts. Keep to 3 chart types: line, bar, pie.
- No animations or transitions in admin pages. Instant renders.
- Every page loads in <1 second. React Query with aggressive caching (staleTime: 60s for most data, 5s for health checks).
- Activity Feed is the most important UX element -- feels like a live terminal.
- Mobile responsive is nice-to-have, not required (except `/docs` -- that MUST be mobile-friendly).

### 3A. Document Access Strategy

Not everyone in the founder's life uses GitHub or Notion. Documents need to be accessible where people actually are.

**Two-layer system**:


| Doc Type                                                                    | Source of Truth                     | Readable At                      | Collaborative At       | Who Reads                       |
| --------------------------------------------------------------------------- | ----------------------------------- | -------------------------------- | ---------------------- | ------------------------------- |
| Company docs (FINANCIALS, KNOWLEDGE, TASKS, MASTER PLAN, AI_MODEL_REGISTRY) | `docs/*.md` in git repo             | paperworklabs.com/docs/* (P4.14) | Git PRs (founder only) | Founder, wife, future investors |
| Agent outputs (daily briefings, weekly plans, reports)                      | Google Drive (`Paperwork Labs HQ/`)        | Google Drive link sharing        | Google Docs comments   | Founder, wife                   |
| Trinket one-pagers                                                          | Google Docs (created from template) | Google Drive link sharing        | Google Docs comments   | Founder, wife, future team      |
| Trinket PRDs                                                                | Google Docs (created from template) | Google Drive link sharing        | Google Docs comments   | Founder, future engineers       |
| Social content drafts                                                       | Postiz queue                        | Postiz UI                        | Postiz UI              | Founder                         |


**Why not just Google Docs for everything?**

Company docs (financials, master plan, tasks) change frequently via AI agents in Cursor. Markdown in git is the natural output format. Keeping them in git gives version history, PR review, and diff tracking. The Studio docs viewer (P4.14) makes them readable for anyone with a browser.

**Why not just markdown for everything?**

Trinket one-pagers and PRDs need collaborative review -- the founder might want to highlight a section, leave a comment like "I don't think this SEO angle works", or share with wife for a sanity check. Google Docs handles this natively. Markdown in git doesn't.

**Agent output routing**:


| Agent                            | Output Format              | Destination                              |
| -------------------------------- | -------------------------- | ---------------------------------------- |
| EA daily briefing                | Google Doc                 | `Paperwork Labs HQ/Operations/Daily Briefings/` |
| EA weekly plan                   | Google Doc                 | `Paperwork Labs HQ/Operations/Weekly Plans/`    |
| Market Discovery Agent (trinket) | Google Doc (from template) | `Paperwork Labs HQ/Trinkets/One-Pagers/`        |
| PRD Agent (trinket)              | Google Doc (from template) | `Paperwork Labs HQ/Trinkets/PRDs/`              |
| Competitive Intel                | Google Doc                 | `Paperwork Labs HQ/Intelligence/`               |
| Analytics Reporter               | Google Doc                 | `Paperwork Labs HQ/Operations/Analytics/`       |
| Social Content bots              | Postiz queue entry         | Postiz                                   |
| Decision logging (EA)            | Markdown commit            | `docs/KNOWLEDGE.md` in git               |
| Expense logging (EA)             | Markdown commit            | `docs/FINANCIALS.md` in git              |
| Task updates (EA)                | Markdown commit            | `docs/TASKS.md` in git                   |


**Google Drive folder structure** (set up in P0.4):

```
Paperwork Labs HQ/
├── Operations/
│   ├── Daily Briefings/
│   └── Weekly Plans/
├── Trinkets/
│   ├── One-Pagers/
│   └── PRDs/
├── Intelligence/
│   ├── Competitive/
│   └── Analytics/
├── Content/
│   └── Social Drafts/
└── Legal/
    ├── LLC Docs/
    └── Compliance/
```

---

## 3B. 50-State Data Pipeline: The "Never Stale" Architecture

### The Principle

This is an AI-powered data pipeline that populates, validates, and keeps fresh ALL 50 states from day one. The marginal cost of state #11 through #50 is near zero when AI does the extraction.

### Data Structures

**Formation Data** (`packages/data/states/formation/{STATE}.json`):

```json
{
  "state": "WY",
  "state_name": "Wyoming",
  "formation": {
    "entity_types": ["LLC", "Corporation", "Nonprofit"],
    "filing_fee_cents": 10000,
    "filing_fee_source": "https://sos.wyo.gov/Business/docs/LLCFees.pdf",
    "expedited_fee_cents": 10000,
    "expedited_turnaround_days": 1,
    "standard_turnaround_days": 15,
    "online_filing_url": "https://wyobiz.wyo.gov/",
    "filing_method": ["online", "mail"],
    "articles_of_organization_template": true
  },
  "naming_rules": {
    "required_designator": ["LLC", "L.L.C.", "Limited Liability Company"],
    "restricted_words": ["bank", "insurance", "trust"],
    "name_search_url": "https://wyobiz.wyo.gov/Business/FilingSearch.aspx",
    "name_reservation_fee_cents": 5000,
    "name_reservation_duration_days": 120
  },
  "registered_agent": {
    "required": true,
    "must_be_state_resident_or_entity": true,
    "commercial_ra_allowed": true
  },
  "annual_requirements": {
    "annual_report_required": true,
    "annual_report_fee_cents": 6000,
    "annual_report_due": "first day of anniversary month",
    "annual_report_url": "https://wyobiz.wyo.gov/",
    "state_tax_type": "none",
    "franchise_tax": false
  },
  "taxes": {
    "has_state_income_tax": false,
    "corporate_tax_rate": null,
    "sales_tax_rate": 4.0,
    "notes": "Wyoming has no state income tax or corporate tax"
  },
  "last_verified": "2026-03-15",
  "last_verified_source": "Wyoming Secretary of State website",
  "sources": []
}
```

**Tax Data** (`packages/data/states/tax/{STATE}.json`):

```json
{
  "state": "CA",
  "state_name": "California",
  "tax_year": 2025,
  "has_income_tax": true,
  "tax_type": "graduated",
  "brackets": {
    "single": [
      { "min": 0, "max": 1113600, "rate": 1.0 },
      { "min": 1113601, "max": 2639400, "rate": 2.0 }
    ]
  },
  "standard_deduction": {
    "single": 573700,
    "married_joint": 1147400
  },
  "personal_exemption_cents": 15400,
  "source": "California Franchise Tax Board 2025 Tax Rate Schedules",
  "source_url": "https://www.ftb.ca.gov/file/personal/tax-rates.html",
  "all_values_in_cents": true,
  "last_verified": "2026-03-15"
}
```

### Source Registry

Each of the 50 states has a registered data source config:

```typescript
// packages/data/src/sources/index.ts
export const sourceRegistry: Record<StateCode, StateSourceConfig> = {
  WY: {
    sos_url: "https://sos.wyo.gov/",
    dor_url: null,
    tax_foundation_ref: "wyoming",
    aggregator_urls: ["worldpopulationreview.com", "chamberofcommerce.org"],
    scrape_method: "structured_table"
  },
  // ... 49 more states
};
```

### State Engine

```typescript
// packages/data/src/engine/index.ts
export function getStateFormationRules(stateCode: string): StateFormationRules
export function getStateTaxRules(stateCode: string): StateTaxRules
export function calculateStateTax(stateCode: string, income: number, filingStatus: string): TaxResult
export function getAllStates(): StateSummary[]
export function getStateFreshness(): StateFreshnessReport
```

LaunchFree imports formation functions. FileFree imports tax functions. Both share the engine.

### AI-Powered Extraction Pipeline

```
Step 1: Scrape structured tables from Tax Foundation + aggregator sites
Step 2: GPT-4o-mini structured extraction -> 50 JSON files (formation + tax)
Step 3: Cross-validate against state SOS/DOR sites directly
Step 4: Zod schema validation (type safety)
Step 5: Sanity checks (is filing fee within $50-$800 range? Is tax rate within 0-13%?)
Step 6: Human review in batch (~4-6 hours total for all 50 states)
Step 7: PR with all 50 state files, human approves and merges
```

### Three n8n Monitoring Workflows

**1. Weekly Source Monitor** (`venture-source-monitor`)

- Trigger: Weekly cron
- Action: Scrape Tax Foundation + aggregator sites, compute content hashes, detect changes
- If change detected: create GitHub Issue with diff details + source link

**2. Monthly Deep Validator** (`venture-deep-validator`)

- Trigger: Monthly cron (1st of month)
- Action: Scrape all 50 state SOS + DOR sites directly, AI cross-validate against stored data
- Flag discrepancies, generate report for human review

**3. Annual Refresh** (`venture-annual-refresh`)

- Trigger: October (when IRS releases new Revenue Procedure)
- Action: Full federal + state refresh cycle
- Parse new bracket/deduction changes, generate PR with proposed JSON updates

### Validation

- Zod schemas enforce every state file has all required fields
- Sanity checks catch impossible values (negative fees, >100% tax rates)
- Test suite validates all 50 files on every CI run
- Any missing or malformed data fails the build
- 100% test coverage required for the state engine

---

## 4. User Intelligence Platform (Not Just Cross-Sell)

### 4A. The Strategic WHY

This is the Credit Karma playbook. Filing taxes and forming LLCs generates financial profile data -- income, deductions, business type, state, refund size, partner product interest -- that makes every subsequent recommendation more valuable. Each user interaction compounds into a richer profile that drives higher-converting, more relevant partner recommendations.

**Why this matters for valuation**: A pure SaaS tool that files taxes is worth 3-5x revenue. A platform that KNOWS users' financial profiles and can intelligently match them to financial products is worth 8-12x revenue. The difference is the data asset. Credit Karma was acquired for $8.1B not because of free credit scores, but because of 100M financial profiles that enabled targeted product recommendations at 40%+ conversion rates.

**The flywheel**: Free filing -> financial profile data -> better partner recommendations -> higher conversion -> more revenue -> invest in product -> more users -> more data -> better recommendations.

User Intelligence is not a feature. It IS the product.

### 4B. Data Model (Marketplace-Ready from Day 1)

The schema is designed for Stage 4 (full marketplace) from day 1. Stage 1 only fills basic fields; marketplace columns are nullable until their stage arrives. Zero schema migration needed when upgrading stages.

```
CORE IDENTITY (venture database -- studio):

  venture_identities:       id, email, name, created_at
  identity_products:        venture_identity_id, product, product_user_id, first_used
  user_events:              id, venture_identity_id, event_type, product, metadata, timestamp
  user_segments:            venture_identity_id, segment, computed_at

USER FINANCIAL PROFILE (the data moat):

  user_financial_profile:   venture_identity_id, income_bracket, filing_status, has_biz_income,
                            state, refund_amount_bracket, partner_interests[], updated_at,
                            credit_score, credit_score_band, credit_score_date, credit_score_provider,
                            employer_industry (Stage 2+), has_dependents, dependent_count,
                            quarterly_estimate_active (bool), refund_split_used (bool),
                            compliance_subscriber (bool), profile_completeness_score (0-100)

CAMPAIGN ENGINE:

  campaigns:                id, name, segment_target, message_template, channel, status, schedule
  campaign_events:          id, campaign_id, venture_identity_id, event_type, timestamp

MARKETPLACE -- PARTNER SIDE (designed for Stage 4, populated incrementally):

  partner_products:         id, partner_id, partner_name, product_type (hysa/ira/credit_card/loan/insurance/payroll),
                            product_name, affiliate_network (impact/cj/direct/api), affiliate_link,
                            commission_type (cpa/cps/rev_share), commission_amount_cents,
                            min_credit_score (nullable), max_credit_score (nullable),
                            min_income_cents (nullable), states_available[] (nullable = all states),
                            product_details_json, status (active/paused/archived),
                            cpa_bid_cents (nullable, Stage 3+),
                            eligibility_model_id (nullable, Stage 4+),
                            created_at, updated_at
                            -- Stage 1: populated by us from affiliate program docs
                            -- Stage 3+: populated by partners via API

  partner_eligibility:      id, partner_product_id,
                            criteria_type (credit_score_range/income_range/state/age/filing_status/custom),
                            criteria_value_json, created_at
                            -- Stage 1-2: populated by us manually
                            -- Stage 3+: populated by partners via API

  partner_bids:             id, partner_product_id, segment_name (FK to user_segments.segment),
                            bid_cents, bid_type (cpa/monthly_access), status (active/paused),
                            max_daily_impressions (nullable, rate limit),
                            created_at, updated_at
                            -- Empty until Stage 3. Table exists from day 1.
                            -- Bid validation: min bid $10, max bid $500, max 50 active bids per partner

MARKETPLACE -- USER SIDE (the matching output):

  fit_scores:               id, venture_identity_id, partner_product_id,
                            score (0-100), score_version,
                            scoring_method (static/rules/bandit/ml),
                            factors_json (field NAMES + weights only, NEVER raw values -- e.g. {"credit_score_match": 0.3, "income_match": 0.25}, NOT {"credit_score": 742}),
                            computed_at
                            -- Stage 1: score = 50 (flat, ordered by commission)
                            -- Stage 2: score = rules-based match
                            -- Stage 3+: score = ML model output

  recommendations:          id, venture_identity_id, partner_product_id,
                            fit_score, rank_position, placement (refund_plan/dashboard/email/in_app),
                            scoring_method, status (shown/clicked/converted/dismissed),
                            created_at

  recommendation_outcomes:  id, recommendation_id, outcome_type (click/signup/funded/retained_30d),
                            revenue_cents, partner_reported_approval (nullable, Stage 2+),
                            partner_reported_funded_amount_cents (nullable, Stage 2+),
                            timestamp
```

**Key design decisions**:

- `partner_products` stores all partner info including affiliate links (Stage 1), API credentials (Stage 3), and model references (Stage 4) in one table. No migration path needed.
- `fit_scores` records which scoring method produced each score (`scoring_method` enum). This enables A/B testing between scoring backends and provides audit trail for FTC compliance.
- `recommendation_outcomes` includes `partner_reported_`* fields for data reciprocity (Stage 2+). When partners share approval rates and funded amounts back to us, it feeds into the scoring model.
- `profile_completeness_score` on `user_financial_profile` drives recommendation quality: users with complete profiles get Fit Scores, incomplete profiles get generic listings.

### 4C. Event Taxonomy

Every user action with intelligence value captured as an immutable UserEvent. 7 event categories: Acquisition (signup, attribution, referral), FileFree (W2 upload/OCR, filing lifecycle, partner CTAs, e-file), LaunchFree (formation lifecycle, RA, banking/payroll CTAs), Trinkets (tool usage, cross-sell), Credit Score (opt-in, pull, changes), Cross-Product (consent, email lifecycle, notifications), and Marketplace (partner product views/clicks, fit scores, partner-side bidding).

**Full event taxonomy**: [docs/archive/VMP-ARCHIVE.md](../archive/VMP-ARCHIVE.md) Section "4C Event Taxonomy"

### 4D. Segments (Rules-Based, Growing to ML)

**Initial segments (Year 1, rules-based)**:


| Segment                    | Rule                                                         | Action                           |
| -------------------------- | ------------------------------------------------------------ | -------------------------------- |
| `filed_taxes_no_llc`       | Filed via FileFree + no LaunchFree account + has_1099_income | Cross-sell LLC formation         |
| `has_llc_no_taxes`         | Formed LLC via LaunchFree + no FileFree account              | Cross-sell tax filing (seasonal) |
| `high_income_no_ira`       | Income >$75K + no IRA referral click                         | Recommend HYSA/IRA partner       |
| `new_user_7d`              | Signed up in last 7 days                                     | Onboarding email sequence        |
| `abandoned_formation`      | Started formation wizard + didn't complete in 48h            | Nudge email                      |
| `abandoned_filing`         | Started filing + didn't complete in 7 days                   | Nudge email                      |
| `refund_no_routing`        | Got refund >$500 + chose direct deposit (not HYSA)           | HYSA recommendation              |
| `multi_product_user`       | Uses both FileFree and LaunchFree                            | VIP segment, priority support    |
| `high_engagement_trinkets` | Used 3+ trinket tools                                        | Cross-sell to main products      |
| `ra_renewal_approaching`   | RA expires within 30 days                                    | Renewal reminder + credit offer  |


**Phase 1.5 (Launch + 3 months): Credit score integration**:

Add opt-in soft credit pull. "Want personalized financial recommendations? Let us check your credit score -- it won't affect your score." This is the inflection point: income (from tax return) + credit score + filing status = a financial identity richer than what most fintech partners see from their own customers. See Section 4M for the full data moat argument and integration research.

**Year 2 expansion (basic ML with enough data)**:

- Propensity scoring: predict likelihood of cross-product adoption
- Churn prediction: identify users likely to abandon before they do (Section 4L)
- Partner match scoring: rank partner products by predicted conversion per user profile
- Thompson Sampling bandit for partner ranking (Section 4K)
- Credit card and loan recommendations matched to credit score bands

**Year 3 (predictive, proactive)**:

- "Based on your tax profile, you could save $X by forming an LLC before year-end"
- "Users with your income and filing status typically benefit from a HYSA. Here's why."
- Seasonal predictions: anticipate tax season behavior based on prior year patterns
- ML collaborative filtering on user-partner interaction data (Section 4K)
- Full financial profile matching: tax data + LLC data + credit score + spending patterns = personalized "Fit Scores"

### 4E. Recommendation Engine (Pluggable 3-Layer Architecture)

3-layer pipeline designed for Stage 4 from day 1. Interface stays stable across all marketplace stages:

- **Layer 1 (Candidate Generation)**: Eligible products filtered by status, state, credit/income range (Stage 2+), eligibility criteria (Stage 3+)
- **Layer 2 (Scoring)**: Pluggable scorer: static (S1) → rules-based (S2) → Thompson Sampling bandit (S2+) → ML collaborative filtering (S3+). Stable interface: `score(user_profile, product) → FitScore{score, factors, method, confidence}`
- **Layer 3 (Ranking + Rendering)**: Commission-first (S1) → fit-score-first (S2+) → blended fit+bid (S3+). FTC constraint: NEVER "pre-approved"/"guaranteed"; PERMITTED "strong match", "94% fit"

4 campaign rules handle cross-product engagement (post-filing LLC nudge, post-formation tax nudge, abandoned formation recovery, RA credit upsell). Marketplace engine handles product matching on Refund Plan screen.

**Full recommendation engine spec + campaign rules**: [docs/archive/VMP-ARCHIVE.md](../archive/VMP-ARCHIVE.md) Section "4E Recommendation Engine"

### 4F. Journey Mapping

Common user paths with estimated conversion rates at each step:

```
PATH A: FileFree -> LaunchFree (biz income detection)
  File taxes (100%) -> has 1099 income (15% of filers) -> see LLC cross-sell (if opted in)
  -> click CTA (8%) -> start formation (60%) -> complete (75%) -> RA purchase (50%)
  Net conversion: ~0.27% of all filers become LaunchFree RA customers
  Revenue per converted user: $99/yr RA + partner referrals

PATH B: LaunchFree -> FileFree (tax season cross-sell)
  Form LLC (100%) -> receive tax season email (if opted in) -> click CTA (12%)
  -> start filing (70%) -> complete (85%)
  Net conversion: ~7% of LLC formers file taxes via FileFree
  Revenue per converted user: partner referrals + Tax Opt Plan potential

PATH C: Trinkets -> FileFree (financial calculator -> tax filing CTA)
  Use calculator (100%) -> see cross-sell CTA (100%) -> click (2-3%)
  -> sign up for FileFree (40%) -> complete filing (varies by season)
  Net conversion: ~1% of trinket users become FileFree users
  Revenue: low per user but high volume (SEO traffic)

PATH D: FileFree -> HYSA partner (refund routing)
  Complete filing (100%) -> see Refund Plan screen (100%) -> has refund (75%)
  -> click HYSA CTA (8-12%) -> complete HYSA signup (50%)
  Net conversion: ~3-4.5% of filers become HYSA customers
  Revenue per converted user: $25-50 affiliate fee

PATH E: LaunchFree -> FileFree Business Tax Filing (mandatory cross-sell)
  Form LLC (100%) -> select tax election (partnership/S-Corp) (15-20% of formations)
  -> see "File your business taxes with FileFree" CTA at formation + tax season email
  -> click CTA (30-40%, high intent -- they MUST file) -> complete business return (80%)
  Net conversion: ~4-6% of all LLC formers file business taxes via FileFree
  Revenue per converted user: $49-99/return (1065/1120-S)
  This is a MANDATORY obligation -- every LLC taxed as partnership or S-Corp MUST
  file a business return. Unlike optional cross-sells, this is compliance-driven demand.

PATH F: Distill CPA -> Consumer FileFree (CPA referral channel)
  CPA uses Distill (100%) -> CPA recommends personal FileFree to clients
  -> client visits filefree.ai (20-30% referral rate) -> signs up (50%) -> files (85%)
  Net conversion: ~8.5-12.75% of CPA client base becomes FileFree users
  Revenue per converted user: marketplace ARPU (varies by stage)
```

### 4G. Revenue Connection Map

How user intelligence events drive the 77% of revenue from referrals:


| User Data Point           | Eligible Partner Products         | Est. Conversion | Revenue/Conversion |
| ------------------------- | --------------------------------- | --------------- | ------------------ |
| Income >$75K + no IRA     | HYSA (Marcus, Wealthfront)        | 8-12%           | $25-50             |
| Has 1099 income           | LLC formation (LaunchFree)        | 3-5%            | $99/yr RA          |
| Formed LLC, no bank       | Business banking (Mercury, Relay) | 10-15%          | $50-100            |
| Formed LLC, has employees | Payroll (Gusto)                   | 5-8%            | $50-200            |
| Formed LLC, no insurance  | Business insurance (Next)         | 3-5%            | $30-75             |
| Refund >$1K               | HYSA for refund deposit           | 8-12%           | $25-50             |
| Filing complete           | Audit shield (TaxAudit)           | 2-4%            | $15-30             |
| High engagement           | Tax Optimization Plan ($29/yr)    | 5-10%           | $29/yr             |


### 4H. Cross-Product Consent (3-Tier System)

Consent follows the 3-tier architecture defined in Section 0I. Each tier is independent -- users can opt into cross-product emails (Tier 1) without opting into personalized matching (Tier 2).

- **Tier 1 (Cross-product)**: Opt-in checkbox on signup forms. Enables cross-product email campaigns. Per-product unsubscribe in email footer.
- **Tier 2 (Personalized matching)**: Opt-in on Refund Plan screen AND user profile/settings page. Users who download PDF without reaching the Refund Plan screen should see Tier 2 opt-in via follow-up email or next login banner. Enables marketplace Fit Scores and personalized product ranking. Covers all 4 marketplace stages.
- **Tier 3 (Anonymized insights)**: Opt-in during credit score check. Enables segment marketplace (Stage 3+).
- Consent stored per user, per tier, with timestamp + consent text version + IP
- Per-product unsubscribe in email footer: users can unsubscribe from FileFree emails without affecting LaunchFree (and vice versa). Consistent with Section 0C and Section 0I.
- Re-consent required only if consent text materially changes. Marketplace stage upgrades do NOT require re-consent (Tier 2 language covers all matching methods).
- CCPA audit trail maintained for all tiers

### 4I. Campaign System

- Create campaigns targeting specific segments
- Message templates with personalization tokens (name, refund amount, state, LLC name)
- Schedule: immediate, daily, weekly, one-time, event-triggered
- Channels: email, in-app notification, in-app card
- Performance tracking: send, open, click, convert, revenue attributed
- CAN-SPAM compliant: unsubscribe, physical address, honest subject line
- A/B testing: subject lines, send times, template variants (track via campaign_events)
- Suppression rules: max 2 emails/week, no emails within 24h of previous, respect quiet hours

### 4J. Onboarding Email Sequences

**LaunchFree (5-email welcome series)**:

1. Day 0: "Welcome! Here's what's next for your LLC" (compliance checklist, next steps)
2. Day 3: "3 things every new LLC owner forgets" (EIN, operating agreement, bank account)
3. Day 7: "Your compliance calendar (free)" (annual report dates, state deadlines)
4. Day 14: "Banking for your LLC" (partner referral -- Mercury/Relay)
5. Day 30: "Tax season is coming -- FileFree can help" (cross-sell, opt-in only)

**FileFree (3-email post-filing series)**:

1. Day 0: "Your return is filed! Here's your summary" (refund amount, key numbers)
2. Day 7: "5 ways to increase next year's refund" (educational, Circular 230 compliant)
3. Day 30: "Starting a business? LaunchFree makes it free" (cross-sell, opt-in only)

### 4K. Experimentation Platform (Our "Darwin")

Credit Karma's Darwin runs 22,000 models/month and 60B predictions/day powering ~80% of operations. We need a lightweight experimentation framework that grows with us. Research context: Google's 2024 user simulation paper (YouTube Music), Capital One's FinTRec (2025, transformer-based contextual targeting), Meta's PEX framework (heterogeneous treatment effects).

**Phase 1 -- Feature Flags + Simple A/B (Launch)**:

- PostHog feature flags (already in stack, free tier: 1M events/mo)
- A/B test: recommendation card placement, partner ordering, CTA copy
- Track: click-through rate, conversion rate, revenue per impression
- No ML needed. Just measure which recommendation layout converts better.

**Phase 2 -- Multi-Armed Bandit (10K+ users)**:

- Replace static A/B tests with Thompson Sampling bandit for partner ranking
- Auto-allocates traffic to higher-converting partners
- Personalized ranking: different users see different partner orders based on their profile
- Implementation: Python (`scipy.stats.beta`) in the recommendation API, ~200 lines of code

**Phase 3 -- ML Recommendation Models (50K+ users)**:

- Collaborative filtering on user-partner interaction data
- Input: financial profile (income, credit score, state, age, filing status) + behavioral signals (clicks, time on page, past conversions)
- Output: ranked partner list with predicted conversion probability
- Serve via FastAPI

**FTC compliance constraint (MANDATORY)**: CK was fined by the FTC in 2022 for A/B testing "pre-approved" language that was misleading. Our experimentation must NEVER test language implying guaranteed approval. Permitted: "may qualify", "based on your profile", "personalized for you." Prohibited: "pre-approved", "guaranteed", "you qualify." Build this constraint into the experimentation framework as a hard rule.

### 4L. Data Intelligence & Analytics

The intelligence engine is not just recommendations and retention -- it is the full data infrastructure for every downstream analysis the company needs. Design data models from the start so ANY post-production analysis is possible: KPIs, cohort analysis, funnel metrics, LTV, partner performance, churn, campaign effectiveness. The event taxonomy (Section 4C) and data model (Section 4B) already capture the raw material. This section defines what we compute from it.

**Company KPIs (tracked from day one via PostHog + event taxonomy)**:


| KPI                        | Definition                                                     | Source Events                                    | Target             |
| -------------------------- | -------------------------------------------------------------- | ------------------------------------------------ | ------------------ |
| Activation rate            | Signups -> first completed action (filed taxes / formed LLC)   | signup, filing_completed, formation_completed    | >40%               |
| Completion rate            | Started action -> completed                                    | filing_started -> filing_completed               | >80%               |
| Monthly active users (MAU) | Unique users with any event in 30 days                         | All events                                       | Growth metric      |
| DAU/MAU ratio              | Daily active / monthly active (stickiness)                     | All events                                       | >15%               |
| Revenue per user (RPU)     | Total revenue / active users                                   | partner_signup_completed, tax_opt_plan_purchased | Track trend        |
| Lifetime value (LTV)       | Predicted total revenue per user over lifetime                 | All revenue events + retention                   | Compute at Phase 2 |
| Partner conversion rate    | Partner CTA views -> partner signups, per partner, per segment | partner_cta_viewed, partner_signup_completed     | >5%                |
| Churn rate (30-day)        | Users with no activity in 30 days / total users                | All events                                       | <20% off-season    |
| Seasonal return rate       | Users who file in Year N who return in Year N+1                | filing_completed (year-over-year)                | >50%               |
| Net Promoter Score         | Quarterly in-app survey                                        | Custom event                                     | >50                |


**Cohort analysis (built into PostHog, no custom code)**:

- Signup cohort retention: what % of Jan 2027 signups are active in Feb, Mar, Apr...
- Filing cohort: users who filed in Season 1 vs Season 2 (income growth, product adoption)
- Partner cohort: users who engaged with partner recommendations vs those who didn't (LTV difference)

**Funnel metrics (PostHog funnels)**:

- Filing funnel: signup -> W-2 upload -> OCR complete -> review -> submit -> accepted
- Formation funnel: state selected -> name search -> formation started -> completed -> RA purchased
- Partner funnel: CTA viewed -> CTA clicked -> partner signup completed
- Trinket-to-product funnel: tool used -> cross-sell CTA clicked -> signup -> activation

**Churn prediction signals**:

- Days since last login
- Repeat vs one-time filer
- Recommendation engagement (click, convert, ignore)
- Email opt-out status
- Credit score change (score drops = financial stress = re-engagement opportunity)

**Churn prediction model (Phase 2+)**:

- MVP: ChurnGuard AI (open-source, connects PostHog + Stripe, 15-min setup). Fallback if unmaintained at implementation time: PostHog's built-in retention analysis + custom churn scoring via Python (~1 day of engineering).
- Features: login frequency, recommendation engagement, email open rate, conversion history
- Output: risk score (Critical >80% / High 60-80% / Medium 40-60% / Low <40%) per user
- Critical risk users get personalized re-engagement (AI-drafted, founder-approved email)

**Lifecycle campaigns (n8n workflows + packages/email)**:


| Trigger                                | Campaign                                                        | Channel        | Timing                |
| -------------------------------------- | --------------------------------------------------------------- | -------------- | --------------------- |
| Filed taxes, no refund action          | "Your $X refund is coming -- here's where to put it"            | Email + in-app | 3 days post-filing    |
| Filed taxes, 6 months no return        | "Your tax profile is getting smarter" (mid-year check-in)       | Email          | July                  |
| Formed LLC, no banking setup           | "Your LLC needs a bank account"                                 | Email + push   | 7 days post-formation |
| Credit score dropped >20 pts           | "Your credit score changed -- here's what to know"              | Email + in-app | Within 48 hours       |
| Tax season approaching, returning user | "Your W-2 info is pre-filled from last year"                    | Email + push   | January               |
| Annual report deadline approaching     | "Your [state] annual report is due in X days"                   | Email + push   | 30 days before        |
| No login for 90 days                   | Value recap: "Here's what we know about your financial profile" | Email          | At 90 days            |


**Push notifications (Phase 2+)**:

- Web push via service worker (no app store needed)
- Opt-in only, max 2/week, always actionable
- High-value triggers only: credit score change, tax season reminder, deadline alert

**Data as moat**: Every interaction adds data points. Every campaign response adds behavioral signal. Year 2 users have 2 years of income data, credit trajectory, engagement history. This compounds and cannot be replicated by competitors who only see one-time transactions. The data flywheel: more users -> richer profiles -> better recommendations -> higher conversion -> more revenue -> more users.

### 4M. Why Early Credit Score Is the Moat (Not Just a Feature)

Credit Karma's moat wasn't the credit score itself -- Intuit, NerdWallet, and every bank now offer free scores. CK's moat was **2,500 data points per user** accumulated over time. We have a unique advantage CK never had: **we see the user's actual tax return.** That's the most complete financial snapshot that exists.

**What FileFree knows from a single filing that CK doesn't**:

- Exact income (actual W-2 Box 1, not self-reported range)
- Filing status (single, married, HOH -- household composition)
- Dependents (family size, child ages)
- Refund/owed amount (disposable income signal)
- State of residence (cost of living context)
- Employer (stability signal)

**Add credit score to that and we have**:

- Income + creditworthiness = approval odds for any financial product
- Refund amount + credit score = right HYSA vs right credit card recommendation
- Business owner (LaunchFree) + credit score = business credit card, business loan eligibility

Partners will pay a premium to reach users we can describe as "W-2 income $75K, credit score 720+, $3,200 refund, single, CA resident, 28 years old." That's not a lead -- that's a pre-qualified customer. CK charges $25-1,250 per referral because of this.

**Revised phasing -- move credit score to Phase 1.5 (Launch + 3 months)**:

Every month we delay credit score integration, we lose data compounding. A user who files in January 2027 and gives us credit score permission immediately has 12 months of credit trajectory by January 2028. If we wait until Year 2, we have zero trajectory data for returning users. The moat starts building the day we turn on soft pulls.

**Credit score integration research**:

- **Soft pull only**: We only ever do soft pulls. Never affects user's score. Users must understand this.
- **TransUnion reseller (Array, SavvyMoney)**: Easiest path for startups. $0.50-2.00 per pull. No direct bureau contract needed. Array provides embeddable credit score widget.
- **Plaid LendScore**: Cash-flow based scoring (not traditional credit score). Trained on ~1B transactions, 25% better predictive performance than traditional scores. Good for users with thin credit files.
- **CRS Credit API**: Unified three-bureau monitoring. Overkill for Phase 1 but ideal for Phase 3.
- **FCRA compliance**: Required when displaying credit scores. Disclosures, dispute process, adverse action notices. Attorney consultation needed before implementing. Budget: $500-1,000 for FCRA compliance review.
- **Timeline**: Phase 1.5 (3 months post-launch). The soft pull integration is ~1 week of engineering. The FCRA compliance review is the bottleneck.

**UX**: "Want personalized financial recommendations? Let us check your credit score -- it won't affect your score." Subtle, opt-in, value-first framing.

### 4N. Partner Dashboard (Marketplace Portal Seed)

The partner dashboard is not a reporting page -- it is the seed of the Stage 3 self-serve partner portal. Design the database schema and API routes for the full portal from day 1; expose features incrementally by stage.

**Stage 1-2 (internal only, paperworklabs.com/admin/partners)**:

- Admin-only page. No partner login.
- Per-partner conversion funnel: impressions -> clicks -> signups -> funded accounts -> revenue
- Anonymized user demographics per partner (age range, income bracket, state distribution)
- Comparison to category average ("your HYSA converts 2x the average partner")
- Partner data makes us sticky: partners who see their conversion data don't churn

**Stage 2 (partner-facing read-only)**:

- Give top partners read-only access to their own conversion data via partner invite link
- Separate partner auth (API key + partner ID, NOT user auth)
- Partners see: their funnel, their demographics breakdown, their revenue, their rank vs. category
- This is the trust-building step: partners who see data invest more in the relationship

**Stage 3 (self-serve portal, paperworklabs.com/partners)**:

- Partners can: submit/update product details, set eligibility criteria, place CPA bids on segments, view real-time conversion funnel, download anonymized segment reports
- Self-serve onboarding: partner signs up, submits product info, gets API key, starts receiving matched traffic
- Partner API: `POST /api/v1/partners/products`, `PUT /api/v1/partners/products/{id}/eligibility`, `POST /api/v1/partners/bids`

**Stage 4 (full marketplace console)**:

- Partners upload eligibility models (scoring functions), run segment simulations ("how many users match these criteria?"), A/B test bid strategies, and manage products programmatically via API
- Real-time dashboard: live conversion funnel, revenue per hour, segment performance heatmap

### 4O. Financial Marketplace Platform (The Long Game)

This section defines the strategic evolution from affiliate links to a full two-sided financial product marketplace. It is the Credit Karma playbook adapted for a deeper-per-user, lower-volume model. The architecture is designed for Stage 4 from day 1 (see Section 4B data model, Section 4E recommendation engine); only the implementation advances by stage.

#### Why This Is THE Strategic Play

Credit Karma was acquired for $8.1B. Not because of free credit scores (everyone has those now). Because of **Lightbox**: a bidirectional marketplace where lenders upload underwriting models, CK matches them against 140M user profiles, and users see products with ~90% approval odds. Lenders pay CPA ($25-1,250 per approved customer).

CK's ARPU: ~$11.43 ($1.6B revenue / 140M users). CK's per-user enterprise value at acquisition: $57.86 ($8.1B / 140M).

FileFree's per-user data is 3-5x **deeper** than CK's: actual W-2 income (not self-reported), filing status, dependents, refund amount, employer, state, credit score trajectory, LLC formation data, quarterly tax behavior, and refund splitting behavior. Deeper data = higher conversion = higher ARPU at lower user counts.

#### 4-Stage Evolution (Volume-Gated)

**Stage 1 -- Affiliate Links (0-5K users, Year 1)**

- Self-serve affiliate programs (Betterment, SoFi, Wealthfront via Impact.com/CJ Affiliate)
- Static partner links on Refund Plan screen. Rules-based recommendation engine (Section 4E Layer 2: static scoring)
- Revenue: flat CPA/CPS commissions ($25-100 per conversion)
- ARPU: $3-7 (low volume, low attach rates for an unknown brand)
- **What we're really building**: the user profile data asset. Every filing, every credit score check, every refund split, every quarterly estimate adds data points. The product is free. The data is the value.
- **Stage gate to Stage 2**: 5K users with financial profiles AND conversion data across 3+ partner categories

**Stage 2 -- Smart Matching (5K-25K users, Year 2)**

- Thompson Sampling bandit (Section 4K Phase 2) replaces static partner ordering in Section 4E Layer 2
- **Fit Score** visible to users: combines credit score + income bracket + filing status + state + age into a per-product match score (0-100). User sees: "This HYSA is a 94% fit for your profile."
- FTC compliance constraint: NEVER "pre-approved", "guaranteed", "you qualify." Permitted: "strong match", "94% fit", "personalized for you." (FTC v. Credit Karma, Inc., FTC File No. 2023082 -- CK fined in 2022 for misleading "pre-approved" language.)
- Personalized partner ranking: different users see different partner orders based on their profile
- Begin tracking conversion rate per partner per user segment. This data becomes the pitch to upgrade partners from flat affiliate to tiered CPA.
- Negotiate tiered affiliate rates with top-converting partners: "We're sending you pre-qualified leads with 3x your average conversion rate. Your standard affiliate CPA is $50. We want $75."
- **Data reciprocity begins**: negotiate for top partners to share approval rates and funded amounts back to us (see PARTNERSHIPS.md)
- ARPU: $8-15 (higher conversion from personalization + tiered rates)
- **ARPU jump worked example (S1 $5 -> S2 $12)**: Stage 1 at 10K users: 3% attach rate x $50 avg CPA = $1.50 ARPU from affiliates + $2 from Tax Opt Plan + $1.50 from audit shield = $5. Stage 2: personalized ranking lifts attach rate to 6% (2x, documented in CK data), tiered CPA lifts avg to $75 (1.5x) = $4.50 ARPU from affiliates + $3 from Tax Opt Plan (better targeting) + $2 audit shield + $2.50 from refund splitting conversions = $12. The 2x conversion lift from personalized ranking is the primary driver.
- **Stage gate to Stage 3**: 25K users, 3+ partners sharing approval data back, AND conversion data proving personalized ranking outperforms static

**Stage 3 -- Partner API (25K-50K users, Year 2-3)**

- **Key account strategy (chicken-and-egg mitigation)**: Identify 2-3 partners already sharing data at Stage 2 (Tier B). Offer first-mover advantage on the API: priority placement for 6 months, lower platform fees, dedicated onboarding support. These anchor partners prove the API value before broader launch. Without anchor partners, Stage 3 doesn't launch.
- Build partner-facing API (see Section 4N Stage 3 spec):
  - `POST /api/v1/partners/products` -- submit product parameters (APY, min balance, eligibility criteria, credit score ranges)
  - `GET /api/v1/partners/segments` -- anonymized aggregate data on user segments matching criteria ("3,200 users in 700-749 credit band with income >$60K in CA")
  - `POST /api/v1/partners/bids` -- set CPA bids per segment (higher bid = higher ranking for matching users)
- **Segment marketplace**: partners bid on access to user segments, not individual users. No PII shared. Partners see only aggregate counts, demographics, and predicted conversion rates.
- Self-serve partner onboarding: partners sign up, submit product details, set bids, track performance (Section 4N Stage 3)
- Revenue model shifts from flat CPA to **auction-based CPA**: partners compete for top placement. CPA rises to $100-200 for premium segments (high-income, good credit, refund in hand)
- ARPU: $15-35
- **Stage gate to Stage 4**: 50K users, 10+ active API partners, AND auction dynamics demonstrably increasing CPA vs. flat rates

**Stage 4 -- Full Marketplace (50K+ users, Year 3+)**

- Partners upload eligibility models (credit score ranges, income thresholds, state restrictions, custom scoring functions) into a secure sandboxed environment. Models run against anonymized user profiles.
- **Match Confidence** displayed to users: "Based on your financial profile, this product is a strong match." (Never "approved" or "guaranteed.")
- Real-time matching: user's profile updates (new filing, credit score change) instantly re-rank available products
- Partner console shows live conversion funnel: impressions -> clicks -> applications -> approvals -> revenue. Partners optimize in real-time.
- Multi-product marketplace: credit cards, personal loans, HYSA, IRA, business loans (LaunchFree users), insurance, payroll services
- Revenue model: **CPA auction + platform access fees**. Partners pay monthly platform fee ($500-2,000/mo) + CPA on conversions.
- ARPU: $35-80+ (marketplace effect: more partners competing = higher CPAs = higher ARPU at the same user count)

#### Why Multiples Expand at Stage 3-4

Marketplace businesses command premium valuation multiples because of network effects: more partners = better product matching = more users = more partners. A rules-based affiliate product is worth 3-5x revenue. A two-sided marketplace with partner bidding and ML matching is worth 8-15x revenue. The jump from Stage 2 to Stage 3 is where valuation inflects.

Fintech M&A benchmarks (2025-2026): median 4.4x EV/Revenue. North America premium: 6.4x. AI WealthTech: 14-16x. "Scaled Winners": 6-8x. Our target at Stage 3: 6-10x (justified by marketplace dynamics + deeper-per-user data than CK).

#### Competitive Moat: Why a Competitor Can't Just Copy This

Eight compounding advantages that widen over time:

1. **Tax return data is the rarest financial dataset**: No one else gets IRS-quality income verification for free. Banks have transaction data. CK has credit data. Only tax preparers have court-admissible income data. The other free tax preparers (FreeTaxUSA, Cash App Taxes) aren't building marketplaces -- they're features inside larger products.
2. **Cross-product compound profiles**: A user who files taxes AND forms an LLC AND tracks quarterly estimates AND splits their refund has a 20+ data-point financial profile. A competitor starting today needs 2-3 years to build equivalent depth.
3. **Time-series data compounds**: Credit score trajectory over 2+ years, income growth across filings, business formation-to-revenue tracking. Each year of data makes the profile exponentially more valuable for ML matching. A competitor who starts Year 2 is permanently 2 years behind on every user.
4. **Trust built at the mandatory moment**: Tax filing is mandatory. CK is optional. Users who trust you with their SSN and W-2 have crossed the highest trust threshold in consumer finance. That trust transfers directly to financial product recommendations.
5. **Cost structure moat**: 1 founder + AI agents at ~$50/mo infrastructure vs. CK's 1,300+ employees. Even at 50K users, the operation runs lean. Profitability arrives years earlier, which funds growth, which compounds the data advantage.
6. **State Filing Engine** (infrastructure moat): Proprietary portal automation for all 50 states -- the same engine serves LaunchFree consumers at $0 and Distill Formation API partners at $20-40/filing. Building and maintaining 50-state automation (Playwright scripts, state API integrations, print-and-mail fallback) is a multi-year head start. Nobody else has open-sourced this. Near-zero marginal cost means competitors can't undercut without building equivalent infrastructure.
7. **Agent-maintained compliance data** (operational moat): 50-state formation rules, fees, filing procedures, and compliance calendars maintained by AI agents via n8n workflows. This is not just code -- it's operational process. States change fees, update forms, and modify portals continuously. Our agents detect changes automatically and update configs. A competitor would need to build both the data layer AND the maintenance system.
8. **B2B distribution flywheel**: CPA firms using Distill become referral channels for consumer FileFree. No competitor has both a B2B product AND a free consumer product creating bidirectional distribution. Each Distill CPA firm = 50-500 potential consumer users. Each consumer user = potential CPA firm lead. The flywheel accelerates both products simultaneously.

#### Emerging Competitor Landscape (March 2026)


| Competitor                | Model                                                                                        | Threat Level    | Our Advantage                                                                                                                                                                              |
| ------------------------- | -------------------------------------------------------------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Taxu.io**               | Free basic + $10-29/mo business tier. 2M+ users, $5B+ processed. Personal + business filing. | MEDIUM-HIGH     | They charge for business features. We're free across products. They don't have LLC formation. They don't have a marketplace/intelligence play.                                             |
| **Cairn (withcairn.com)** | Free AI LLC formation guide, 50 states. $14.99 for documents.                                | LOW-MEDIUM      | Guide only, not a full service. No ongoing compliance, no cross-sell to tax filing, no data moat.                                                                                          |
| **ZenBusiness Velo**      | $0 LLC + AI assistant. $199-349/yr upsell model.                                             | MEDIUM          | Same upsell-heavy model we're undercutting. No tax filing. No financial marketplace.                                                                                                       |
| **X.TAX**                 | Business-only tax filing, $95-159/return. AI-powered.                                        | LOW             | Not free, not personal filing, no formation, no marketplace. Different market.                                                                                                             |
| **FreeTaxUSA**            | Free federal personal + business forms. $14.99 state. ~150 employees.                        | MEDIUM          | Established but no LLC formation, no AI advisory, no marketplace, no intelligence layer. Feature, not platform.                                                                            |
| **Cash App Taxes**        | Free federal + state. Mobile-first.                                                          | MEDIUM          | Block/Square subsidiary. No formation, no marketplace. Free filing is a feature to drive Cash App adoption, not a standalone product.                                                      |
| **Credit Karma (Intuit)** | Free credit scores + tax filing redirected to TurboTax (2023). 140M users.                   | HIGH (at scale) | CK no longer files taxes directly -- all filing redirected to TurboTax since 2023 Intuit integration. They have scale but won't innovate on filing (cost center). Our threat is real only if we reach 100K+ users. |
| **MagneticTax**           | B2B AI tax prep for CPAs. YC S25. Automates 1040 data entry into existing tax software.      | LOW-MEDIUM      | We build the same OCR/extraction pipeline for consumer filing anyway -- B2B is marginal cost. They're VC-funded with burn; we're bootstrapped. They have no consumer product, no marketplace, no cross-product moat. |
| **NerdWallet**            | Free tax filing via Column Tax partnership. Personal finance marketplace. 20M+ monthly users.| MEDIUM          | NerdWallet's filing is a Column Tax white-label, not proprietary. They're a content/affiliate company, not a tax platform. No formation, no intelligence layer depth. |
| **TaxSlayer**             | Free federal tier (Simply Free). $24.95-64.95 paid tiers. Established brand.                 | LOW-MEDIUM      | Free tier limited to simple returns (no 1099, no itemizing). No LLC formation, no marketplace, no AI advisory. Traditional tax software, not a platform play. |
| **TaxDown**               | AI-powered tax filing. Europe-first, expanding. Celebrity marketing + TikTok Spark Ads.      | LOW (geography) | Europe-focused. If they enter US market, our depth advantage (formation + marketplace + advisory) and cost structure ($278/mo vs VC burn) differentiate. Monitor for US expansion. |
| **Origin Financial**      | VC-backed all-in-one: budgeting, investing, tax filing (via April Tax), AI financial advisor. SEC-registered RIA. ~100K users. $12.99/mo. | HIGH | Closest to our long-term "AI financial advisor" vision. SEC RIA registration is a regulatory moat we lack. April Tax partnership gives them e-file TODAY. BUT: $12.99/mo ($156/yr) prices out our core demographic (price-sensitive Gen Z). No LLC formation, no B2B play. White-label tax filing (not proprietary). Strategy: don't out-Origin Origin on advisory -- own "free for young people" positioning. See KNOWLEDGE.md Q5 for full analysis. |
| **April Tax (getapril.com)** | AI-native tax filing infrastructure. IRS-authorized e-file transmitter. Powers Origin's filing. Embeddable API. | MEDIUM (partner or competitor) | Potential Column Tax alternative for our interim e-file partnership. Production-proven at Origin's scale. Evaluate API pricing and partnership terms. Does NOT change MeF transmitter north star -- interim only. See KNOWLEDGE.md Q6. |
| **TaxWire**               | Global sales tax compliance platform (Avalara competitor). Tax engine API + automated filing. | NONE (different market) | TaxWire handles indirect tax (sales tax/VAT/GST), not income tax. Zero overlap today. Team: ex-TaxJar, ex-Stripe Tax, ex-Avalara. Year 3+ partnership/expansion opportunity for LaunchFree LLC sales tax compliance. |


**Key takeaway**: No single competitor combines free personal tax filing + free LLC formation + B2B CPA automation + financial intelligence marketplace + compliance SaaS. That combination IS the moat. Origin Financial comes closest to our long-term vision but charges $12.99/mo and lacks formation/B2B -- they validate the market category while we capture the free tier. Taxu.io comes closest on the filing side but charges for business features and has no formation/marketplace play. MagneticTax validates the B2B CPA market but lacks a consumer product.

---

## 5. Social Media Pipeline (Faceless / AI-Driven)

### 5A. Strategy: Faceless + Occasional Founder

**Daily (automated, zero founder time)**:

- Faceless educational content: AI script + ElevenLabs voice clone + stock footage/screen recordings + text overlays
- Produced by n8n pipeline, queued in Postiz as drafts
- 1-2 posts/day across TikTok, IG Reels, YouTube Shorts, X

**Weekly (10 min founder time)**:

- 1 quick founder-face video: "This week's tax tip" or "Building FileFree update"
- Recorded on phone, minimal editing
- This 1 video is the trust anchor -- proves a real human is behind it

**Result: ~30 posts/week, <30 min/week founder time** (down from 45-60 min/DAY in original plan)

### 5B. Pipeline Architecture (DIY n8n, ~$0.10/video)

```
[8:00am] n8n cron fires
    |
    v
[Trend Research] n8n fetches trending finance/tax topics (GNews API + Reddit API)
    |
    v
[Script Generation] GPT-4o generates 3 scripts with hooks (brand voice -- see Section 0E)
    |
    v
[Image Generation] GPT-4o generates image prompt -> DALL-E 3 background ($0.04/image)
    |
    v
[Voice Generation] ElevenLabs: cloned founder voice OR brand voice ($0.05/1K chars)
    |
    v
[Visual Assembly] FFmpeg (Hetzner): image + audio + auto-captions -> video
    |
    v
[Platform Optimization] Resize for TikTok/IG/YT/X, add platform-specific captions + hashtags
    |
    v
[Queue in Postiz] n8n pushes to Postiz via REST API as "draft"
    |
    v
[5-min Human Review] Founder opens Postiz, approves/rejects/edits, schedules
    |
    v
[Publish + Track] Postiz publishes -> PostHog tracks UTMs -> n8n pulls analytics weekly
```

**Model routing for content** (per Section 0E):

- Script generation: **GPT-4o** (The Creative Director -- brand voice, narrative pull)
- Image prompts: **GPT-4o** (creative copy)
- Background images: **DALL-E 3** ($0.04/image)
- Voiceover: **ElevenLabs** (not an LLM -- dedicated voice synthesis)
- NOT Gemini or Claude for content scripts (GPT-4o is confirmed superior for "distinctive narrative pull")

### 5C. Cost: ~$3/month for 30 videos (both brands combined)


| Component        | Cost per video   | 30 videos/month |
| ---------------- | ---------------- | --------------- |
| GPT-4o script    | ~$0.01           | $0.30           |
| DALL-E 3 image   | $0.04            | $1.20           |
| ElevenLabs voice | ~$0.05           | $1.50           |
| FFmpeg assembly  | $0 (Hetzner VPS) | $0              |
| **Total**        | **~$0.10**       | **~$3.00**      |


### 5D. Content Themes

**FileFree** (tax/finance):

- Tax tips, refund hacks, "did you know" tax facts
- IRS deadline reminders, filing status guides
- W-2 box explainers, tax myth busters
- "Photo to Done in 5 minutes" product demos

**LaunchFree** (business formation):

- LLC tips, state comparisons, RA explained
- "Your LLC costs less than Netflix"
- Business compliance, annual report reminders
- "3 things every new LLC owner forgets"

### 5E. Hook Bank (Proven Templates)

**FileFree -- Pain hooks** (highest engagement in finance):

1. "The IRS already knows about this. Do you?"
2. "If you made under $75K last year, stop scrolling."
3. "That $89 you paid TurboTax? You didn't have to."

**FileFree -- Curiosity hooks**:
4. "I filed my taxes in 4 minutes. Here's how."
5. "CPAs don't want you to know this about free filing."
6. "Your tax refund isn't a gift. It's money they held hostage."

**FileFree -- Transformation hooks**:
7. "I went from owing $2,000 to getting $1,400 back. One form."
8. "Filing taxes used to take 3 hours. Now it takes 3 minutes."

**LaunchFree -- Formation hooks**:
9. "You can start an LLC for $0 in 10 states."
10. "ZenBusiness charges $199/yr. Here's what you actually need."
11. "3 tax deductions you unlock the day you form an LLC."
12. "Nobody tells you about the $800 California LLC fee."
13. "Stop running your side hustle as a sole prop."

**Production rules**:

- First 1.5 seconds = everything (algorithms judge intro retention)
- Bold text overlay (5-8 words) -- 60%+ of views are silent
- Change visuals every 2-3 seconds to maintain completion rate
- One CTA per video, never more

### 5F. 30-Day Pre-Launch Content Calendar

**Week 1 (Days 1-7): Founder Journey -- Build in Public**

- Day 1: "I quit my job to build a free tax app. Here's why." (X thread + TikTok)
- Day 2: "What TurboTax charges for vs what it costs them" (TikTok comparison)
- Day 3: "Day 1 of building FileFree" (behind-the-scenes TikTok, show code/terminal)
- Day 4: "The IRS has a free filing tool and nobody knows about it" (educational IG Reel)
- Day 5: "How much it actually costs to run a tax app (showing real numbers)" (X thread)
- Day 6-7: Engage with tax-related comments/threads on X, reply to r/tax and r/personalfinance

**Week 2 (Days 8-14): Tax Myths Busted**

- "You don't owe taxes on Venmo payments (unless...)" (TikTok)
- "The tax bracket myth that's costing you money" (TikTok + IG Reel)
- "No, your employer didn't steal your money. Here's what Box 1 actually means" (TikTok)
- "POV: you finally understand your W-2" (TikTok with screen recording of /demo)
- X polls: "What's the most confusing thing about filing taxes?"

**Week 3 (Days 15-21): Product Tease**

- "I scanned a W-2 and my app read every field in 3 seconds" (TikTok screen recording)
- "Before: 45 minutes on TurboTax. After: 3 minutes on FileFree." (TikTok split-screen)
- "This is what free tax filing actually looks like" (IG Reel, honest, no hype)
- Carousel: "5 things you're overpaying for that should be free" (IG)
- YouTube Short: "How AI reads your W-2 (explained in 60 seconds)"

**Week 4 (Days 22-30): Community Building**

- "Who else is stressed about filing? Comment your #1 question" (engagement bait)
- "I'll explain your W-2 in the comments" (TikTok -- comment-driven)
- "The waitlist is open. Here's exactly what FileFree does." (CTA post with link in bio)
- Pin first-week launch post on TikTok/IG with waitlist CTA

### 5G. Platform-Specific Rules

**TikTok** (primary -- cheapest reach for Gen Z):

- Format: Vertical 9:16, 15-60 seconds
- Hook: First 0.5s must stop the scroll. Pattern interrupts, bold text, unexpected statements.
- Audio: Use trending sounds (check TikTok Creative Center weekly)
- CTAs: "Link in bio" (no clickable links in posts). Pin comment with URL.
- Key metric: Completion rate > raw views

**Instagram Reels** (secondary -- better targeting for paid):

- Re-edit TikTok with IG-style captions + 20-30 hashtags + long caption
- Captions: Long-form, storytelling, save-bait ("Save this for tax season")
- Key metric: Saves > likes (saves signal value to algorithm)

**X / Twitter** (thought leadership + community):

- Text-first. Threads for explainers. Quote tweets for engagement.
- Sharp, concise, slightly spicy.
- Reply to people asking tax questions in #taxseason threads.
- Key metric: Quotes > retweets (deeper engagement)

**YouTube Shorts** (long-tail discovery):

- Same vertical video, add subscribe CTA overlay
- Description: Keyword-heavy ("how to file taxes free 2026" type phrases)
- Group into playlists: "Tax Basics", "W-2 Explained", "Money Tips"
- Key metric: Subscriber conversion rate from Shorts

### 5H. Validation Strategy

1. Week 1-2: Build the n8n pipeline (~4 hours using community templates as starting point)
2. Week 2-3: Generate 10 videos per brand (20 total) using the pipeline
3. Post to TikTok + IG with manual review before each post
4. Week 4: Analyze performance. Benchmark: >500 avg views, >40% completion rate
5. If validated: enable auto-scheduling with review queue
6. If not: adjust format before another 2-week test

### 5I. Content Compliance (Content Review Gate)

Every piece of social content must pass the Content Review Gate (Section 0C) before publishing:

- No unauthorized tax advice (education only -- Circular 230)
- No "you should" language for legal matters (UPL compliance)
- FTC disclosure on any partner/affiliate mentions
- "Free" claims are accurate and unconditional
- First 30 days: founder reviews EVERY post manually (no auto-publish)
- After 30 days: pre-approved templates can auto-publish; novel content still requires review

### 5J. Founder LLC Journey Content Series (NORTH STAR)

**The meta-narrative**: "I'm building a free LLC formation app while forming my own LLC. Here's every step, every cost, every frustration -- and why I'm building something better."

The founder is forming a California LLC RIGHT NOW. This is the exact journey LaunchFree users will go through. Every step becomes social content -- authentic, educational, and positions LaunchFree as the solution.

**LLC Formation Steps -> Content Hooks**:


| Step                     | What Happens                                                             | Content Hook (TikTok/IG/X)                                                                            | Emotion                     |
| ------------------------ | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- | --------------------------- |
| 1. Choose a name         | Search CA SOS business database, discover your name is taken, try 5 more | "I tried to name my company and California said no. 5 times."                                         | Frustration -> relatability |
| 2. File Articles of Org  | Fill out Form LLC-1 on CA SOS website, pay $70                           | "Starting an LLC costs $70 in California. Here's the 3-minute form nobody shows you."                 | Demystification             |
| 3. Wait for approval     | CA SOS processing time (can be weeks)                                    | "Day 1 vs Day 14 of waiting for California to approve my LLC..."                                      | Anticipation                |
| 4. Get an EIN            | IRS.gov, free, takes 5 minutes online                                    | "The IRS gave me a tax ID in 5 minutes. For free. Why does anyone pay $70 for this?"                  | Outrage at upsellers        |
| 5. Operating Agreement   | Write one (or use a template, or AI generates it)                        | "LegalZoom charges $99 for this document. I had AI write mine in 30 seconds."                         | Product demo moment         |
| 6. Registered Agent      | Set up RA service                                                        | "Your LLC needs a 'registered agent.' Here's what that actually means (and why it costs $49-249/yr)." | Education                   |
| 7. Statement of Info     | File LLC-12 within 90 days of formation                                  | "90 days after forming your LLC, California wants MORE paperwork. Here's what to do."                 | Compliance awareness        |
| 8. Business bank account | Apply at Mercury/Relay/local bank                                        | "I opened a business bank account in 10 minutes. From my phone."                                      | Partner demo moment         |
| 9. Franchise tax reality | Discover the $800/yr CA franchise tax                                    | "Nobody told me California charges $800/yr just to EXIST as an LLC. Here's the workaround."           | Shock -> education          |
| 10. First year exempt    | Discover first-year exemption                                            | "Plot twist: your first year is actually FREE. Here's the fine print."                                | Relief                      |
| 11. Compliance calendar  | Set up annual reminders                                                  | "The 5 dates every LLC owner needs to know. Miss one and your LLC gets dissolved."                    | Urgency                     |
| 12. DBA filing           | File "Doing Business As" for brand names                                 | "My LLC name isn't my brand name. Here's why you need a DBA (and what it costs)."                     | Practical                   |


**Content Format per Step** (each step produces 3-5 pieces):

1. **TikTok/Reel (primary)**: 30-60s screen recording of the actual process + voiceover. Real screens, real forms, real costs. Raw and authentic.
2. **X thread**: 5-7 tweet breakdown with screenshots. Educational, save-worthy.
3. **IG carousel**: Step-by-step visual guide (5-7 slides). Highly saveable, shareable.
4. **Blog/guide page** (SEO): Full written guide on launchfree.ai (e.g., "How to File Articles of Organization in California"). Each page targets "[state] LLC formation" keywords.
5. **Behind-the-scenes TikTok**: "Day X of building a free LLC formation app while forming my own LLC" (build-in-public narrative arc).

**Why This Goes Viral**:

- **Pain is universal**: Everyone forming an LLC hits the same confusion. This content validates their frustration.
- **Real receipts**: Showing actual forms, actual costs, actual timelines. Not hypothetical.
- **Outrage hooks**: "LegalZoom charges $249 for something that takes 3 minutes" triggers shares.
- **Build-in-public**: "I'm building the solution to the problem I'm showing you" is a compelling narrative arc.
- **Each step is searchable**: People Google "how to get an EIN" (110K monthly searches), "California LLC cost" (12K), "do I need a registered agent" (8K). This content ranks.

**Revenue Flywheel**:

```
Viral LLC content (TikTok/IG/X)
    |
    v
Traffic to launchfree.ai (SEO guides + social CTAs)
    |
    v
Users form LLCs via LaunchFree ($0 service fee)
    |
    v
Cross-sell: RA ($99/yr), banking (Mercury/Relay affiliate $50-100),
            payroll (Gusto $50-200), insurance (Next $30-75)
    |
    v
Partner revenue ($$$) -- this is the 77% revenue driver
    |
    v
Reinvest in more content + product
```

**Integration with 30-Day Calendar** (Section 5F): LLC journey steps 1-4 map to Week 1-2 founder content. Steps 5-8 map to Week 3. Steps 9-12 map to Week 4. Each step's TikTok/Reel is the "founder spotlight" content that runs alongside the automated faceless content pipeline.

**Cross-reference**: Phase 0.6 (Form LLC) in Section 7 -- every Phase 0 step becomes content. LaunchFree social hooks in Section 5E.

---

## 5K. User Acquisition Strategy (Stress Test Addition)

The plan projects 10K-30K FileFree filers and 2K-5K LaunchFree users but never modeled how they arrive. Social content is one channel, not the strategy. This section fills that gap.

### Channel-by-Channel Projections (Year 1)


| Channel                                   | Monthly Investment              | Time to Impact   | Year 1 Users (Est.) | Notes                                                                                                   |
| ----------------------------------------- | ------------------------------- | ---------------- | ------------------- | ------------------------------------------------------------------------------------------------------- |
| **Organic TikTok/Reels**                  | $15-17/mo (pipeline cost)       | 2-4 months       | 500-3,000           | Faceless + founder content. 90%+ of videos get <500 views; the bet is on the 1-2 that go viral.         |
| **SEO / Content**                         | $0 (AI-written, founder-edited) | 6-12 months      | 1,000-5,000         | Blog posts: "cheapest state for LLC", "free tax filing 2027", "LLC vs sole prop". Long tail, compounds. |
| **Product Hunt + HN launch**              | $0                              | Day 1 spike only | 500-2,000           | One-time spike. LaunchFree PH launch, FileFree PH launch. Plan for both.                                |
| **Reddit / personal finance communities** | $0 (time cost)                  | 1-3 months       | 200-1,000           | r/personalfinance, r/smallbusiness, r/tax. Authentic answers that mention product. Never spam.          |
| **TikTok Spark Ads**                      | $100-300/mo                     | Immediate        | 1,000-5,000         | Boost top-performing organic videos only. $0.05-0.10/click. Budget in FINANCIALS.md.                    |
| **Referral program**                      | $0-5/referral (tax credit)      | 3-6 months       | 500-2,000           | "Refer a friend, both get [benefit]". Implement in Phase 7.                                             |
| **Cross-sell (LaunchFree -> FileFree)**   | $0                              | Jan 2027         | 500-2,000           | Every LLC former needs to file taxes. Built-in pipeline.                                                |
| **TOTAL REALISTIC RANGE**                 |                                 |                  | **5,200-23,000**    |                                                                                                         |


### Customer Acquisition Cost (CAC) Model


| Segment                 | CAC              | Lifetime Value (LTV) | LTV:CAC  | Verdict                                                       |
| ----------------------- | ---------------- | -------------------- | -------- | ------------------------------------------------------------- |
| Organic (SEO + social)  | ~$0              | $15-50 (Year 1)      | Infinite | Build this first. It compounds.                               |
| Paid social (Spark Ads) | $0.50-2.00       | $15-50               | 7-100x   | Profitable from day 1 IF content converts. Test with $200/mo. |
| Product Hunt / HN       | ~$0              | $15-50               | Infinite | One-time, non-repeatable. Nice but not a strategy.            |
| Referral                | $5 (credit cost) | $15-50               | 3-10x    | Excellent unit economics. Build in Phase 7.                   |


### Pre-Launch Audience Building (Start NOW, Before Products Ship)


| Action                                                 | Owner          | Timeline           | Goal                                         |
| ------------------------------------------------------ | -------------- | ------------------ | -------------------------------------------- |
| Start LLC Journey content series (Section 5J)          | Founder 1      | March-April 2026   | 500+ followers before LaunchFree launch      |
| Publish 3 SEO blog posts on paperworklabs.com/blog     | Founder 1 + AI | April 2026         | Index in Google for long-tail LLC keywords   |
| Post in r/smallbusiness and r/Entrepreneur weekly      | Founder 1      | Ongoing            | Build credibility, understand user language  |
| Launch waitlist with referral incentive                | Founder 1      | Already live       | Grow to 500+ emails before LaunchFree launch |
| Submit to BetaList, Indie Hackers, Startup directories | Founder 1      | 1 month pre-launch | 200-500 signups from startup community       |


### Bootstrapped Growth Case Studies

**FreeTaxUSA**: Built to 10M+ filers with zero VC funding. Strategy: SEO-first (ranks #1 for "free tax filing"), word-of-mouth from happy users, price undercut (federal free, state $14.99). No paid social until 1M+ users. Lesson: product quality IS the marketing.

**Credit Karma**: Grew to 100M users pre-acquisition on free credit scores + SEO + word-of-mouth. Zero paid ads for first 3 years. Lesson: give away something valuable that competitors charge for, and users become evangelists.

**Our playbook**: Follow both patterns. Free filing IS the hook (like Credit Karma's free credit score). SEO compounds over time (like FreeTaxUSA's dominance). Social content builds brand recognition. Paid amplification ($100-300/mo max) only boosts proven organic winners.

### Brand Mission Alignment

Every piece of content should reinforce one of these mission pillars:

- **Accessibility**: "Taxes shouldn't cost $89" / "Your LLC shouldn't cost $500"
- **Transparency**: "No hidden fees, no bait-and-switch, no surprise renewals"
- **Empowerment**: "You don't need a CPA for a simple return" / "You don't need a lawyer to form an LLC"
- **AI as helper**: "AI does the work, you just confirm"

Content that doesn't tie back to a mission pillar gets killed. This is how brands build recognition -- relentless consistency, not volume.

### Viral Mechanics

- **Refund amount sharing**: "I just filed my taxes for free and I'm getting $X back" (shareable card with FileFree branding)
- **LLC formation celebration**: "I just started my business!" (shareable certificate with LaunchFree branding)
- **Comparison calculator**: "How much are you overpaying for tax prep?" (interactive widget, generates shareable result)
- **Referral loops**: Referrer and referee both get a benefit (e.g., priority support, Tax Optimization Plan discount)

### What's NOT in the Strategy (Honest Gaps)

- **Paid search (Google Ads)**: Too expensive for "LLC formation" ($15-30/click). Not viable until revenue covers it.
- **Influencer partnerships**: No budget and no traction to pitch. Revisit at 10K+ users.
- **Email list buying**: Never. Destroys trust and violates CAN-SPAM intent.
- **PR / press**: No story yet. Revisit after Product Hunt launch with traction data.

**Ad budget**: $100-300/mo max for TikTok Spark Ads + Meta boost, starting at LaunchFree launch. Only boost organic content that already performed well. This is NOT a paid-first strategy.

### 5L. Scale Growth Playbook: Path to 2M Users (Lessons from Taxu, TaxDown, Credit Karma)

The organic-first strategy (Section 5K) projects 5K-23K users in Year 1. To reach 2M+ users (Taxu-level scale), we need additional high-leverage growth channels. These lessons come from studying how Taxu.io reached 2M users, how TaxDown uses celebrity marketing and TikTok Spark Ads for seasonal surges, and how Credit Karma grew to 100M on free-product virality.

#### Channel 1: Tax Season Surge Marketing (TaxDown Playbook)

TaxDown runs aggressive paid social during tax season (Jan-April) and goes quiet the rest of the year. This is smart: 80% of filing volume happens in a 10-week window. Concentrate spend.

- **January-April**: 5x ad budget ($500-1,500/mo on TikTok Spark Ads + Meta). Boost only top 5% of organic content. Target: "free tax filing", "file taxes free", "TurboTax alternative".
- **Celebrity/creator partnerships**: At 25K+ users, engage 2-3 micro-influencers ($500-1,000 each) in personal finance / Gen Z space. NOT before product traction justifies the spend.
- **Seasonal urgency content**: "IRS deadline in X days", "Most people overpay for tax prep", countdown content that creates FOMO.
- **Expected impact**: 10K-50K users per tax season at $0.50-2.00 CAC (highly efficient for paid social during high-intent season).

#### Channel 2: B2B API Distribution (Taxu Playbook)

Taxu.io reached 2M users partly by offering their filing engine as an embeddable API for other platforms. This is a distribution multiplier.

- **Tax-as-a-Service API**: Expose FileFree's tax calculation + filing engine as an API for fintech apps, payroll companies, and banking apps that want to offer "file taxes" as a feature.
- **Pricing**: Per-return API fee ($5-15/return) or monthly access fee ($500-2,000/mo). White-label option available.
- **Target partners**: Payroll companies (Gusto, ADP), banking apps (Chime, Current), fintech platforms that want to add tax filing without building it.
- **Expected impact**: Each API partner brings their existing user base. 5 partners with 10K users each = 50K filings/year through our engine. We don't need to acquire those users -- they come through the partner.
- **Timeline**: Year 2 (after own MeF transmitter is proven in Season 1). API spec development starts Phase 8.

#### Channel 3: Community-Led Growth (Credit Karma + Reddit Playbook)

Credit Karma grew its first 1M users through organic community engagement: Reddit, personal finance forums, word-of-mouth. No paid ads for 3 years.

- **Reddit strategy**: Authentic, value-first answers in r/personalfinance, r/tax, r/smallbusiness, r/freelance. Never spam. Build credibility by answering questions before linking to product. "I built a free tax filing app" posts perform well on Reddit when the founder is genuinely helpful.
- **Discord / community**: Launch a "Tax Help" Discord server. Free community tax Q&A (educational, not advice). Cross-sell to FileFree for filing. Builds trust and organic referrals.
- **Indie Hackers / Build in Public**: Document the journey of building FileFree and LaunchFree. "1 founder + 44 AI agents building a fintech" is a compelling narrative that attracts early adopters and press.
- **Expected impact**: 1K-5K users from community in Year 1, compounding as reputation builds.

#### Channel 4: B2B CPA Outreach (Distill)

Distill (Section 1C) targets CPA firms directly. Each CPA firm processes 50-500+ returns/season. CPA adoption is a distribution multiplier for brand awareness.

- **LinkedIn + direct email**: Target independent CPAs and small firms (1-10 preparers). 75K+ CPA firms in the US.
- **CPA referral program**: CPAs who use Distill can refer their clients to consumer FileFree for personal filing. "Your CPA uses Distill" is a trust signal that converts.
- **State CPA society partnerships**: Sponsor or present at state CPA society events. Low cost, high-credibility distribution.
- **Expected impact**: 100-300 CPA firms in Year 1 -> each firm is a distribution channel for consumer product. 300 firms x 100 clients aware = 30K potential consumer users.

#### 2M User Acquisition Model (Year 1-5 Projection)

**Direct Users** (visit filefree.ai/launchfree.ai, eligible for marketplace, financial profiles, partner matching):

| Year | Organic + SEO | Paid Social | Community | CPA Channel (Distill referrals) | Cross-sell | Direct Total |
| ---- | ------------- | ----------- | --------- | ------------------------------- | ---------- | ------------ |
| Y1 | 5K-10K | 5K-15K | 1K-5K | 1K-3K | 1K-2K | 13K-35K |
| Y2 | 20K-50K | 30K-100K | 5K-15K | 5K-15K | 5K-10K | 65K-190K |
| Y3 | 50K-100K | 100K-300K | 20K-50K | 15K-40K | 20K-50K | 205K-540K |
| Y4 | 100K-200K | 200K-400K | 50K-100K | 30K-80K | 50K-100K | 430K-880K |
| Y5 | 200K-400K | 300K-500K | 100K-200K | 50K-150K | 100K-200K | 750K-1.45M |

**API Filing Volume** (Distill API — processed through partner platforms, per-return revenue only, no marketplace profiles):

| Year | Distill API Filing Volume | Per-Return Rev |
| ---- | ------------------------- | -------------- |
| Y1 | 0 | $0 |
| Y2 | 20K-50K | $100K-750K |
| Y3 | 100K-200K | $500K-3M |
| Y4 | 200K-500K | $1M-7.5M |
| Y5 | 300K-700K | $1.5M-10.5M |

**Why the split matters**: Direct users have financial profiles eligible for marketplace recommendations (valued at 8-15x revenue multiple). API filing volume generates per-return revenue only (valued at 3-5x revenue multiple). Conflating them inflates the user count and misrepresents the marketplace opportunity. Total "returns processed" = Direct + API, but marketplace valuation applies only to Direct users.

**Key insight**: Distill API distribution is the filing volume multiplier. Organic and paid social plateau at ~750K-1.45M direct users. API distribution through partner platforms provides the per-return revenue multiplier. This is exactly how Taxu reached scale -- they powered tax filing inside other apps.

#### 5M. Distill B2B Go-to-Market (Bootstrapped Playbook)

Distill's GTM is entirely bootstrapped -- no funding required. Consumer FileFree's social media presence generates brand awareness; Distill rides that momentum with a product-led B2B motion.

**Pre-Launch (Now - December 2026, $0 spend)**:

- **Engineering-as-marketing**: Build 3 free CPA-targeted Trinkets that rank for SEO and demonstrate tech quality: (1) W-2 OCR Tester -- CPAs upload a W-2, see extraction quality instantly, no signup, this IS the product demo; (2) Tax Bracket Calculator (Professional) -- multi-scenario, side-by-side comparison, SEO magnet; (3) Filing Deadline Tracker -- every state deadline in one dashboard, embeddable widget CPAs put on their own sites. Research shows free tools generate 60K+ page views in first week (Clearbit Logo API) and compound over years (HubSpot Website Grader: 65K monthly visits after 18 years).
- **LinkedIn content engine**: Founder posts 2-3x/week on CPA pain points, AI in tax prep, W-2 automation. Target: 500 CPA connections in 3 months. Each post ends with "DM me for early access."
- **Waitlist at distill.tax**: Collect email + firm size + current tax software (UltraTax/Drake/Lacerte/ProConnect). This data prioritizes export format development.

**Tax Season Launch (January - April 2027, $0-200/mo spend)**:

- **Free tier (Trojan horse)**: 10 returns/month free, no credit card. CPAs try it during the busiest season. If it works, they're hooked.
- **Founder-led sales (first 10-20 customers)**: Personally reach out to 50-100 independent CPAs via LinkedIn DMs (warm -- they've been consuming content for months), state CPA society directories (public member lists), r/taxpros subreddit, Accounting Twitter/X. The ask: "We built an AI tool that extracts W-2 data in seconds. Can I show you a 5-minute demo?" At $49-199/mo, 10-20 paying firms validates the product and hits $1K-3K MRR.
- **Product Hunt launch**: "AI Tax Extraction for CPAs" -- time for early January (tax season start = maximum relevance). Product Hunt drives 500-2K signups for well-positioned B2B tools.
- **Viral loop**: Every exported return includes "Extracted by Distill" metadata. CPAs who see it from other firms ask "what tool is this?"

**Post-Tax Season Growth (May 2027+, revenue-funded)**:

- **Content SEO (compounding)**: 2-4 articles/month targeting: "Best AI tax preparation software for CPAs 2027", "How to automate W-2 data entry", "UltraTax vs Drake vs Distill -- AI extraction comparison". These rank in 3-6 months and generate leads perpetually.
- **CPA community infiltration**: Sponsor local CPA society meetups ($100-300/event). Present at state CPA conferences (often free for vendors who speak on topics). Guest articles in Accounting Today and CPA Practice Advisor.
- **Referral program**: "Refer a CPA firm, both get one month free." CPAs talk constantly -- one happy customer = 3-5 referrals.
- **API self-serve (Distill API)**: Developer-facing docs + API keys + usage-based billing. Developers find us via GitHub (open-source SDKs), dev.to, HackerNews, "tax filing API" Google searches (high-intent, low competition).

**Revenue milestones (no funding required)**:

| Milestone | Timeline | Revenue | Channel |
| --------- | -------- | ------- | ------- |
| 10 CPA firms | Feb 2027 | $500-2K MRR | Founder-led sales + free tier conversion |
| 50 CPA firms | Apr 2027 | $2.5K-10K MRR | Product Hunt + content + referrals |
| 200 CPA firms | Jan 2028 (Season 2) | $10K-40K MRR | SEO + word-of-mouth + returning firms |
| API first customers | Q3 2027 | +$500-2K MRR | Self-serve developer signups |

**Why B2B works without funding**: Consumer products need millions of users to monetize (expensive). B2B SaaS needs 200 customers at $100/mo average = $20K MRR. Achievable with founder-led sales + content + referrals. No ads needed. The B2B arm can self-fund while consumer FileFree grows organically via socials.

---

## 6. Agent Architecture (Venture-Wide)

### 6A. The Problem: All Agents Are FileFree-Specific

All 12 Cursor personas and 6 n8n workflows were built for FileFree as a standalone product:

- `social.mdc` references @filefree handles, "Gen Z tax filing app"
- `brand.mdc` references filefree.ai domain, FileFree-specific colors
- `growth.mdc` references tax-specific SEO, TurboTax competition
- `partnerships.mdc` references HYSA referrals, tax partnerships only
- n8n workflows all output to FileFree-specific databases

Now that we're a venture with LaunchFree, Trinkets, and paperworklabs.com, the agent architecture needs to be **product-aware, not product-locked**.

### 6B. Three-Tier Persona Model

Agents are organized into three tiers. **All venture-level personas must be available everywhere** -- use `alwaysApply: true` in frontmatter. Product-level personas activate via globs when you open relevant files. n8n agents are always available (they run on Hetzner, triggered by webhooks or cron, accessible via Slack).

**Tier 1: Venture-Level Personas** (shared across all products, `alwaysApply: true`)


| #   | Persona         | File               | Specific Changes Needed                                                                                                                                               |
| --- | --------------- | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Staff Engineer  | `engineering.mdc`  | Add monorepo conventions (pnpm workspace, `packages/*` imports), multi-app patterns, `apis/` folder structure. Remove FileFree-only path references.                  |
| 2   | UX/UI Lead      | `ux.mdc`           | Add `packages/ui` shared design system reference, multi-brand theming (`[data-theme]` selectors), cross-product navigation patterns.                                  |
| 3   | Chief of Staff  | `strategy.mdc`     | Expand from FileFree context to full venture. Add LaunchFree + Trinkets product context, Google Drive HQ structure, venture KPIs.                                     |
| 4   | General Counsel | `legal.mdc`        | Add LLC formation compliance (UPL disclaimers for LaunchFree), RA legal requirements, FTC "free" guidance for both products. Add Content Review Gate checklist.       |
| 5   | CFO             | `cfo.mdc`          | Expand unit economics to both products + trinkets. Add shared infra cost allocation (Hetzner split), per-product revenue projections, RA margin analysis.             |
| 6   | QA Lead         | `qa.mdc`           | Add formation data validation rules, cross-product security (venture identity PII), state data pipeline validation. Expand PII definitions to include LLC owner data. |
| 7   | Partnership Dev | `partnerships.mdc` | Add LaunchFree partnerships (banking: Mercury/Relay, payroll: Gusto, RA providers: CorpNet, insurance: Next). Update pipeline tracking for both products.             |
| 8   | Workflows       | `workflows.mdc`    | Add LaunchFree-specific workflow templates (ship formation feature, state data update, compliance alert).                                                             |
| 9   | AI Ops Lead     | `agent-ops.mdc`    | Already venture-wide. Add reference to `docs/AI_MODEL_REGISTRY.md`.                                                                                                   |


**Tier 2: Product-Level Personas** (activated by glob patterns, product-specific knowledge)


| #   | Persona                     | File                                              | Globs                                                                      | Purpose                                                                         |
| --- | --------------------------- | ------------------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| 10  | Tax Domain Expert           | `tax-domain.mdc`                                  | `apps/filefree/`**, `apps/distill/**`, `apis/filefree/`**, `packages/tax-engine/**`, `packages/data/**/tax-*` | IRS rules, brackets, MeF schemas                                                |
| 11  | CPA / Tax Advisor           | `cpa.mdc`                                         | `apps/filefree/**`                                                         | Tax advisory content quality                                                    |
| 12  | FileFree Social             | `filefree-social.mdc` (rename from `social.mdc`)  | `apps/filefree/**/social/**`                                               | FileFree content: @filefree handles, tax hooks, TurboTax positioning            |
| 13  | FileFree Growth             | `filefree-growth.mdc` (extract from `growth.mdc`) | `apps/filefree/**`                                                         | Tax-specific SEO, TurboTax competition keywords                                 |
| 14  | FileFree Brand              | `filefree-brand.mdc` (extract from `brand.mdc`)   | `apps/filefree/**`                                                         | Violet-indigo palette, FileFree voice                                           |
| 15  | **Formation Domain Expert** | `formation-domain.mdc` (NEW)                      | `apps/launchfree/`**, `apis/launchfree/`**, `packages/data/**/formation-*` | State LLC rules, RA requirements, annual report deadlines, entity types         |
| 16  | **LaunchFree Social**       | `launchfree-social.mdc` (NEW)                     | `apps/launchfree/**/social/`**                                             | LaunchFree content: @launchfree handles, formation hooks, LegalZoom positioning |
| 17  | **LaunchFree Growth**       | `launchfree-growth.mdc` (NEW)                     | `apps/launchfree/`**                                                       | Formation-specific SEO, "free LLC" keywords, LegalZoom/ZenBusiness positioning  |
| 18  | **LaunchFree Brand**        | `launchfree-brand.mdc` (NEW)                      | `apps/launchfree/`**                                                       | Teal-cyan palette, LaunchFree voice                                             |
| 19  | **Studio**                  | `studio.mdc` (NEW)                                | `apps/studio/`**                                                           | paperworklabs.com company site + command center UX                              |


### 6C. Persona Split Specs

`**social.mdc` -> `filefree-social.mdc` + `launchfree-social.mdc`**:


| Attribute                       | filefree-social.mdc                                                           | launchfree-social.mdc                                                                 |
| ------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Handles                         | @filefree.tax (TikTok, IG), @filefreetax (X, YT)                             | @launchfree (TikTok, IG, X, YT)                                                       |
| Voice                           | Smart friend who makes taxes feel easy                                        | Smart friend who makes business formation feel easy                                   |
| Content pillars                 | Tax myths, W-2 explainers, refund tips, filing demos                          | LLC tips, state comparisons, compliance, RA explained                                 |
| Hook themes                     | Pain (TurboTax costs), curiosity (tax hacks), transformation (filed in 3 min) | Pain (LegalZoom costs), curiosity (LLC benefits), transformation (launched in 10 min) |
| Competitors to position against | TurboTax, H&R Block, FreeTaxUSA                                               | LegalZoom, ZenBusiness, GoDaddy, Northwest                                            |
| Compliance                      | Circular 230 (tax education only)                                             | UPL (formation services, not legal advice)                                            |
| Posting cadence                 | 7-10/week tax season, 2-3/week off-season                                     | 3-5/week consistent year-round                                                        |


`**brand.mdc` -> `filefree-brand.mdc` + `launchfree-brand.mdc`**:

- FileFree: violet-indigo palette (`from-violet-500 to-purple-600`), tax-anxiety-killing tone
- LaunchFree: teal-cyan palette (`from-teal-500 to-cyan-600`), entrepreneurial empowerment tone
- Shared: Inter + JetBrains Mono typography, dark mode default, same animation patterns

`**growth.mdc` -> `filefree-growth.mdc` + `launchfree-growth.mdc`**:

- FileFree: SEO targets "free tax filing", "file taxes online free", competitor comparison pages vs TurboTax
- LaunchFree: SEO targets "free LLC formation", "how to start an LLC", state-specific landing pages, competitor comparisons vs LegalZoom/ZenBusiness

### 6D. Current Agents (20 -- Already Built)

14 Cursor personas + 6 n8n workflows (12 original personas + EA Interactive + AI Ops Lead):


| #     | Agent                                                                                           | Type                     | Status                                                  |
| ----- | ----------------------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------- |
| 1-12  | Engineering, UX, Growth, Social, Strategy, Legal, CFO, QA, Tax Domain, CPA, Partnerships, Brand | Cursor personas (.mdc)   | Active (FileFree-specific, pending venture-wide update) |
| 13-18 | Social Content, Growth Content, Strategy Check-in, Partnership Outreach, CPA Review, QA Scanner | n8n autonomous workflows | Active (output to Notion, pending GDrive migration)     |


### 6E. New Agents to Build (12+)


| #   | Agent                         | Type                    | Trigger                                                                               | Purpose                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| --- | ----------------------------- | ----------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 19  | L1 Support (DocBot)           | n8n webhook             | User message                                                                          | Answer from knowledge base (60% resolution target)                                                                                                                                                                                                                                                                                                                                                                                                                          |
| 20  | L2 Support (OpsBot)           | n8n webhook             | DocBot escalation                                                                     | Execute actions: check status, resend email, reset password                                                                                                                                                                                                                                                                                                                                                                                                                 |
| 21  | State Data Validator          | n8n cron (daily/weekly) | Daily for volatile states (CA, NY, TX, FL, IL, WA, NJ, MA, GA, PA), weekly for others | Check state SOS websites for fee/rule changes. Flag stale data (>30 days) to Compliance Monitor.                                                                                                                                                                                                                                                                                                                                                                            |
| 22  | IRS Update Monitor            | n8n cron (October)      | Annual                                                                                | Parse new Revenue Procedure for bracket changes                                                                                                                                                                                                                                                                                                                                                                                                                             |
| 23  | Competitive Intel             | n8n cron (weekly)       | Mondays                                                                               | Monitor LegalZoom/ZenBusiness/TurboTax pricing + features                                                                                                                                                                                                                                                                                                                                                                                                                   |
| 24  | Analytics Reporter            | n8n cron (weekly)       | Sundays                                                                               | Pull PostHog data, generate weekly metrics report                                                                                                                                                                                                                                                                                                                                                                                                                           |
| 25  | Infra Health Monitor          | n8n cron (hourly)       | Continuous                                                                            | Check Render/Vercel/Hetzner status, alert on issues (see Section 7B)                                                                                                                                                                                                                                                                                                                                                                                                        |
| 26  | Affiliate Revenue Tracker     | n8n cron (daily)        | Daily                                                                                 | Check affiliate dashboards, report conversions                                                                                                                                                                                                                                                                                                                                                                                                                              |
| 27  | LaunchFree Social Bot         | n8n cron (daily)        | 8am                                                                                   | Draft LaunchFree social content for Postiz                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| 28  | LaunchFree Growth Bot         | n8n cron (weekly)       | Mondays                                                                               | Draft LaunchFree SEO articles                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 29  | LaunchFree Compliance Bot     | n8n cron (monthly)      | 1st                                                                                   | State filing deadline alerts for users                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| 30  | Knowledge Base Sync           | n8n cron (nightly)      | 2am                                                                                   | Sync Google Drive docs to support agent context                                                                                                                                                                                                                                                                                                                                                                                                                             |
| 31  | AI Ops Lead                   | Cursor persona (.mdc)   | On demand                                                                             | Model routing, cost tracking, persona audits                                                                                                                                                                                                                                                                                                                                                                                                                                |
| 32  | Executive Assistant (EA)      | Cursor persona + n8n    | Daily cron + on-demand                                                                | Daily briefing, weekly planning, decision tracking, financial tracking, doc maintenance. See Section 6J1.                                                                                                                                                                                                                                                                                                                                                                   |
| 33  | Compliance & Security Monitor | n8n cron (daily)        | 6am                                                                                   | Tracks: cyber insurance status, data breach plan currency, EFIN cert status, 50-state data freshness, legal doc expiry (ToS, privacy policy last-reviewed dates), **State Filing Engine health** (portal health status, filing failure rates, state-specific issues, stuck submissions). Outputs daily compliance status to Slack #compliance-alerts, filing engine alerts to #filing-engine, and weekly summary to Mission Control P4.4. Filing Engine Monitor is a function within Compliance Monitor (not a separate agent — keep agent count lean). |
| 34  | Partnership Intelligence      | n8n cron (weekly)       | Mondays                                                                               | Scans affiliate networks (Impact.com, CJ Affiliate, ShareASale, Partnerize) for new fintech programs. Compares commission rates across similar partners. Monitors existing affiliate performance (clicks, conversions, revenue). Tracks program changes (rate changes, terms, closures). **Monitors formation API partner landscape** (FileForms, CorpNet program changes, new entrants, pricing shifts). Generates weekly "Partnership Opportunities" report to Slack #partnerships. Generates compatibility scores based on user profile data. Supports Olga Sharma but works fully autonomously. |


### 6F. n8n Workflow Updates (Existing 6)


| #   | Workflow                     | Changes Needed                                                           |
| --- | ---------------------------- | ------------------------------------------------------------------------ |
| 1   | Social Content Generator     | Rename to `filefree-social-content`. Output to GDrive instead of Notion. |
| 2   | Growth Content Writer        | Rename to `filefree-growth-content`. Output to GDrive.                   |
| 3   | Weekly Strategy Check-in     | Expand to cover both products. Output to GDrive.                         |
| 4   | QA Security Scan             | Scan both APIs. Output to GitHub Issues (keep as-is).                    |
| 5   | Partnership Outreach Drafter | Add LaunchFree partners. Output to GDrive.                               |
| 6   | CPA Tax Review               | Keep FileFree-only. Output to GDrive.                                    |

**New n8n Workflows (planned):**

| #   | Workflow                       | Schedule       | Description                                                                                                          |
| --- | ------------------------------ | -------------- | -------------------------------------------------------------------------------------------------------------------- |
| 7   | `filing-engine-health`         | Hourly         | Health check of top 10 state portals. Posts failures to #filing-engine. Escalates to #ops-alerts if >2 portals down. |
| 8   | `compliance-deadline-check`    | Daily (6am)    | Check for upcoming formation compliance deadlines (annual reports, franchise tax). Alert at 60/30/7 days.            |


### 6G. n8n Workflow Dependency Graph

```
Knowledge Base Sync (nightly 2am)
    |
    v
L1 Support Bot <-- user webhook
    |
    v (escalation)
L2 Support Bot

Analytics Reporter (weekly)
    |
    v (feeds into)
Weekly Strategy Check-in

State Data Validator (monthly)
    |
    v (creates GitHub Issues for)
IRS Update Monitor (annual, October)

FileFree Social Content (daily 8am) --> Postiz queue
LaunchFree Social Bot (daily 8am)  --> Postiz queue
    |
    v (both feed analytics to)
Analytics Reporter

Competitive Intel (weekly) --> GDrive report
    |
    v (informs)
Growth Content Writer (weekly) --> GDrive draft

Infra Health Monitor (hourly) --> Slack #ops-alerts
Affiliate Revenue Tracker (daily) --> GDrive report
LaunchFree Compliance Bot (monthly) --> user emails
```

### 6H. AI Operations Lead (`agent-ops.mdc`)

**Authority**: Owns ALL model routing decisions across the venture. Engineering implements model assignments but does not choose them independently.

**Responsibilities**:

1. **Model Registry**: Maintain Section 0E and `docs/AI_MODEL_REGISTRY.md` as living documents. Update when new models release.
2. **Cost Monitoring**: Monthly API usage audit. Flag workflows exceeding expected cost by >50%.
3. **Persona Audit**: Quarterly review of all .mdc personas. Ensure system prompts are current and effective.
4. **New Model Evaluation**: When a new model drops, evaluate benchmarks + pricing vs current assignments. Generate swap recommendation within 48 hours.
5. **Workflow Optimization**: Identify tasks where a cheaper model could achieve the same quality.

### 6I. Company Org Chart: Agents as Employees

**Total: 24 Cursor personas + 20 n8n workflows = 44 agents** (15 Active, 10 Standby, 9 Planned). Hierarchical org chart under Founder as root. Key departments: Engineering (tax/formation domain + AI ops + QA), Product (UX), Growth (per-product social + content pipelines), Brand (per-product), Legal (content review gate + compliance bot), CFO (affiliate tracking), Partnerships (outreach + intelligence), CPA (tax review), Customer Success (L1/L2 support bots), Competitive Intel, Strategy, Workflows, Infra Health.

**Governance Protocol**: PROPOSE → ROUTE to affected agents → REVIEW → VERDICT (APPROVE/CONCERN/BLOCK) → RESOLVE. Founder is final arbiter. Used for: architecture, new forms, legal decisions, partner integrations.

**EA Split**: EA Interactive (ea.mdc, Cursor) handles decisions/queries. EA Ops Monitor (n8n cron) handles briefings. They do NOT overlap responsibilities.

**Full org chart, agent status table, governance protocol, overlap resolution**: [docs/archive/VMP-ARCHIVE.md](../archive/VMP-ARCHIVE.md) Section "6I Agent Org Chart"

### 6J. Agent Interaction Model

Three patterns: (1) **Cursor Personas** — activate via file globs or domain questions, real-time collaborators during coding/strategy; (2) **n8n Autonomous** — cron-triggered, work while you sleep (EA briefing 7am, social content 8am, infra/filing health hourly, compliance daily, strategy/intel weekly, state validator monthly); (3) **On-Demand n8n** — Slack slash commands for trinket discovery, support, competitive checks, EA queries. Daily founder time: ~15-20 minutes.

**Full interaction model with schedules and commands**: [docs/archive/VMP-ARCHIVE.md](../archive/VMP-ARCHIVE.md) Section "6J Agent Interaction Model"


### 6J1. Executive Assistant Agent (#32) -- Detail Spec

The EA is the founder's most frequently used agent. It bridges Cursor (interactive) and n8n (autonomous).

**Dual implementation**: `.cursor/rules/ea.mdc` (Cursor persona) + `venture-ea-daily` / `venture-ea-weekly` (n8n workflows)

**What makes the EA different from other agents**: It has write access to documentation. When the founder makes a decision in any conversation, the EA logs it. When a phase task completes, the EA updates `docs/TASKS.md`. When money is spent, the EA updates `docs/FINANCIALS.md`.

**Documents owned by EA**:


| Document                      | Update Frequency       | Trigger                              |
| ----------------------------- | ---------------------- | ------------------------------------ |
| `docs/KNOWLEDGE.md`           | Per conversation       | Founder makes a decision             |
| `docs/TASKS.md`               | Per task completion    | Phase milestone hit                  |
| `docs/FINANCIALS.md`          | Per expense            | Domain purchase, subscription change |
| `docs/VENTURE_MASTER_PLAN.md` | Strategic changes only | Major direction shift                |


### 6K. Autonomous Engineering Protocol

No agent is currently assigned to write production code for FileFree or LaunchFree. All engineering work happens in interactive Cursor sessions. Background agents can handle well-scoped, pattern-replicable tasks autonomously.

**Pattern**: Human writes the first implementation (e.g., first state tax module). Agent replicates the pattern for remaining items. Human reviews PR. Never auto-merge.

**Autonomous engineering tasks (suitable for background agents)**:


| Task                                                   | Agent Model   | Input                                         | Output                                 | Human Review |
| ------------------------------------------------------ | ------------- | --------------------------------------------- | -------------------------------------- | ------------ |
| State tax JSON configs (Tier 1 conforming, ~30 states) | Claude Sonnet | Template from first state + state tax docs    | `packages/data/tax/{state}.json`       | PR review    |
| State formation JSON (50 states)                       | Claude Sonnet | Template + SOS website data                   | `packages/data/formation/{state}.json` | PR review    |
| Shared UI components from designs                      | Claude Sonnet | Figma specs or component descriptions         | `packages/ui/components/*.tsx`         | PR review    |
| Test suites for tax calculations                       | Claude Sonnet | Tax calc implementation + IRS Pub 17 examples | `packages/tax-engine/__tests__/*.test.ts` | PR review    |
| MeF XML schema -> Zod types                            | Claude Sonnet | Downloaded IRS XML schemas                    | `packages/tax-engine/mef/schemas/*.ts`    | PR review    |
| API endpoint scaffolding                               | Claude Sonnet | OpenAPI spec or route descriptions            | `apis/*/routes/*.py`                   | PR review    |


**Key principle**: The agent IS the engineering team; the founder IS the tech lead who reviews. Agent writes code, creates PR. Human reviews and merges. Never auto-merge production code.

**Quality gates for sensitive domains**: Tax calculation and formation data PRs require 100% test coverage and validation against IRS Publication 17 worked examples before merge. FCRA-touching code (credit score integration) requires Legal persona review. These gates apply to both human and agent-generated PRs.

**Workflow**: Cursor Background Agents (already available) can run multi-file tasks, create PRs, run tests. Ideal for well-scoped tasks with clear specs and established patterns.

---

## 7. Execution Phases

### Phase 0: Infrastructure (Weeks 1-3, Realistic)

**Dependency chain**: P0.1 (DONE) -> P0.2, P0.3, P0.4, P0.5 (parallel) -> P0.6 (blocked on LLC name) -> P0.7 -> P0.8 (needs specimen, after launch) -> P0.9 (parallel with anything)

**Pre-code blockers (Section 0G)**: EFIN application, cyber insurance, LLC name decision, attorney consult, breach response plan. These run parallel to Phase 0 tasks below.


| Task                         | Owner     | Branch                   | Files/Specs                                                                                                                                                                                                                                        | Acceptance Criteria                                                                                                                                                                                | Depends On                               | Status      |
| ---------------------------- | --------- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- | ----------- |
| P0.1 Buy domains             | Founder 1 | N/A (no code)            | N/A                                                                                                                                                                                                                                                | launchfree.ai + filefree.ai registrar confirmed                                                                                                                                                    | None                                     | DONE        |
| P0.2 Migrate FileFree domain | Founder 1 | `chore/domain-migration` | `web/next.config.ts` (redirects), Vercel dashboard (custom domain), DNS provider (A/CNAME records)                                                                                                                                                 | filefree.ai serves the app. filefree.tax 301-redirects to filefree.ai. All existing links preserved. SSL cert issued.                                                                              | P0.1                                     | NOT STARTED |
| P0.3 Google Workspace        | Founder 1 | N/A (no code)            | Google Workspace Business Starter (1 seat, $6/mo). Primary: paperworklabs.com. Aliases: filefree.ai, launchfree.ai, distill.tax. See D76.                                                                                                          | Emails received at [hello@filefree.ai](mailto:hello@filefree.ai), [hello@launchfree.ai](mailto:hello@launchfree.ai). SPF/DKIM/DMARC configured for all domains.                                    | P0.1                                     | DONE        |
| P0.4 Google Drive HQ         | Founder 1 | N/A (no code)            | Create folder structure: `Paperwork Labs HQ/Operations/Daily Briefings/`, `Paperwork Labs HQ/Operations/Weekly Plans/`, `Paperwork Labs HQ/Trinkets/One-Pagers/`, `Paperwork Labs HQ/Trinkets/PRDs/`, `Paperwork Labs HQ/Intelligence/`. Add GDrive MCP server to `.cursor/mcp.json`. | GDrive accessible from Cursor via MCP. Folder structure matches EA spec in `ea.mdc`.                                                                                                               | P0.3                                     | NOT STARTED |
| P0.5 Secure social handles   | Founder 1 | N/A (no code)            | Register @launchfree on TikTok, Instagram, X, YouTube. Set profile pic to monogram, link to launchfree.ai.                                                                                                                                         | All 4 accounts created, profile pics set, bios written, URLs point to launchfree.ai.                                                                                                               | P0.1                                     | NOT STARTED |
| P0.6 Form LLC                | Founder 1 | N/A (no code)            | California SOS online filing. DBA filings at county clerk (FileFree, LaunchFree, Trinkets, Distill).                                                                                                                                                        | Articles of Organization filed with CA SOS. Confirmation number received. DBA filings submitted. EIN applied for on IRS.gov (same day as LLC confirmation). Bank account opened.                   | LLC name decided (Section 0G #4) -- DONE | NOT STARTED |
| P0.7 Migrate DNS subdomains  | Founder 1 | `chore/dns-migration`    | DNS provider records: ops.paperworklabs.com -> Hetzner (n8n), social.paperworklabs.com -> Hetzner (Postiz). Point paperworklabs.com -> Vercel (apps/studio). Remove old filefree.tax subdomains.                                                   | n8n accessible at ops.paperworklabs.com. Postiz accessible at social.paperworklabs.com. paperworklabs.com serves studio app. Old subdomains return 404 or redirect.                                | P0.2                                     | NOT STARTED |
| P0.8 File trademarks         | Founder 1 | N/A (no code)            | USPTO TEAS Plus application. FILEFREE: Class 036 + 042. LAUNCHFREE: Class 035 + 042. Supplemental Register.                                                                                                                                        | Applications filed. Serial numbers received. Docket dates noted in TASKS.md.                                                                                                                       | Product launch (needs specimen of use)   | DEFERRED    |
| P0.9 Legal compliance setup  | Founder 1 | `chore/legal-compliance` | Update `.cursor/rules/social.mdc`, `growth.mdc`, `brand.mdc` to include Content Review Gate checklist from Section 0C. Create/update `web/src/app/(legal)/privacy/page.tsx`, `web/src/app/(legal)/terms/page.tsx`.                                 | Every content-producing persona .mdc includes the Content Review Gate checklist verbatim. Privacy policy and ToS pages updated with cross-sell consent language from Section 0C Legal Risk Matrix. | None (can start immediately)             | NOT STARTED |


### Phase 1: Monorepo Restructure — COMPLETE

pnpm monorepo with 5 apps (filefree, launchfree, studio, trinkets, distill) + 2 APIs (filefree, launchfree) + 3 shared packages (ui, auth, analytics). All 11 tasks (P1.1-P1.11) done. Imports resolved, CI path-filtered, port assignments verified. See TASKS.md for remaining polish items.


### Phase 1.5: First Trinket + Agent Pipeline Test (Week 3-4, 3-5 days)


| Task                                      | Details                                                                                                                                      |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| P1.5.1 Build financial calculator trinket | Mortgage, compound interest, savings goal, budget planner. Client-side JS. Establishes the `apps/trinkets/` pattern.                         |
| P1.5.2 Create tool-layout component       | Shared layout: header, ad unit slots, SEO head, footer, internal links between tools                                                         |
| P1.5.3 Create trinket templates           | `docs/templates/trinket-one-pager.md` + `docs/templates/trinket-prd.md` -- templates the agent pipeline uses                                 |
| P1.5.4 Test Trinket Factory pipeline      | Run the 3-stage agent pipeline (GPT-5.4 Discovery -> Claude Sonnet PRD -> Claude Sonnet Build) on a second trinket idea to validate the flow |
| P1.5.5 Deploy to Vercel                   | SSG, AdSense placeholder, verify SEO (JSON-LD, sitemap, meta tags)                                                                           |


This phase tests the venture's agent infrastructure end-to-end while producing a real deployed product. The financial calculators are pre-decided; the agent pipeline validates a second trinket idea from market discovery.

### Phase 2: 50-State Data Infrastructure (Week 4-7)

This is not a coding task with a side of research. This is an AI-powered data pipeline that populates, validates, and keeps fresh ALL 50 states from day one. The marginal cost of state #11 through #50 is near zero when AI does the extraction. See Section 3B for the full architecture spec.


| Task                                    | Details                                                                                                                                      |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| P2.1 Create packages/data scaffold      | TypeScript types, Zod schemas (formation + tax), directory structure, state engine API. Also scaffold `packages/tax-engine/` (empty, interfaces only) and `packages/document-processing/` (empty, interfaces only) for future phases. |
| P2.2 Build Source Registry              | 50 state configs: SOS URL, DOR URL, Tax Foundation reference, aggregator URLs, scrape method per source                                      |
| P2.3 AI-extract 50-state tax data       | Scrape Tax Foundation 2026 table -> GPT-4o structured extraction -> 50 JSON files -> cross-validate against state DOR sites                  |
| P2.4 AI-extract 50-state formation data | Scrape aggregator tables (WorldPopReview, ChamberOfCommerce) -> GPT-4o extraction -> 50 JSON files -> cross-validate against state SOS sites |
| P2.5 Human review + approval            | Founder reviews AI extractions in batch (est. 4-6 hours total). Each state JSON gets `last_verified`, `sources[]`, `verified_by`             |
| P2.6 Build state engine                 | getStateFormationRules(), getStateTaxRules(), calculateStateTax(), getAllStates(), getStateFreshness()                                       |
| P2.7 Validation suite                   | Zod schemas + sanity checks + 100% test coverage + CI enforcement                                                                            |
| P2.8 n8n: Source Monitor workflow       | Weekly cron: scrape Tax Foundation + aggregator sites, compute content hashes, detect changes, alert on diffs                                |
| P2.9 n8n: Deep Validator workflow       | Monthly cron: scrape all 50 state SOS + DOR sites directly, AI cross-validate against our stored data, flag discrepancies                    |
| P2.10 n8n: Annual Update workflow       | October cron: triggered by IRS Revenue Procedure release, full federal + state refresh cycle                                                 |


### Phase 3: LaunchFree MVP (Week 6-10)


| Task                              | Details                                                          |
| --------------------------------- | ---------------------------------------------------------------- |
| P3.1 LaunchFree landing page      | Hero, how it works, state selector, pricing, trust badges        |
| P3.2 Formation wizard             | State selection -> name check -> details -> review -> submit     |
| P3.3 Articles of Organization PDF | @react-pdf/renderer, state-specific templates                    |
| P3.4 Backend: formation service   | Create formation, store state, generate PDF, track status        |
| P3.5 RA credit system             | $49/yr base, earn credits via partner actions (banking, payroll) |
| P3.6 Stripe integration           | RA subscription, one-time formation fees (for paid states)       |
| P3.7 LaunchFree dashboard         | User's LLC status, compliance checklist, RA status, next steps   |
| P3.8 Legal pages                  | Privacy policy, ToS for LaunchFree (adapt from FileFree)         |


**Phase 3.5 (post-LaunchFree MVP)**: Compliance-as-a-Service subscription ($49-99/yr). Add `compliance_calendar` table, extend 50-state JSON configs with annual report deadlines and franchise tax amounts, build email/push reminder engine via n8n workflow, and add compliance dashboard page in LaunchFree. See Section 1B.1 for full business case.

### Phase 4: Command Center (Week 8-14, parallel with Phase 3)

The command center is the control plane for the entire venture. It is what makes the "one human + 44 agents" model operationally viable. Every page is spec'd in detail in Section 3.

**Tier 1 — COMPLETE**: Studio landing page, admin auth, Mission Control dashboard, Agent Monitor, Infrastructure health, Docs viewer. All deployed at paperworklabs.com. P4.3 (Studio API) deferred.


**Tier 2 -- Build Next (enables growth operations):**


| Task                         | Page               | Data Sources                               | Complexity |
| ---------------------------- | ------------------ | ------------------------------------------ | ---------- |
| P4.7 Analytics               | `/admin/analytics` | PostHog API or embeds                      | Medium     |
| P4.8 Support inbox           | `/admin/support`   | Support bot PostgreSQL (Hetzner)           | Medium     |
| P4.9 Social media command    | `/admin/social`    | Postiz API                                 | Medium     |
| P4.10 State Data observatory | `/admin/data`      | packages/data JSON + n8n validator results | Low        |


**Tier 3 -- Build When Revenue Flows:**


| Task                       | Page               | Data Sources                                | Complexity |
| -------------------------- | ------------------ | ------------------------------------------- | ---------- |
| P4.11 Revenue intelligence | `/admin/revenue`   | Stripe API + affiliate dashboards           | Medium     |
| P4.12 Campaign control     | `/admin/campaigns` | Campaign tables in studio DB                | High       |
| P4.13 User intelligence    | `/admin/users`     | Venture identity DB + cross-product queries | High       |


### Phase 5: User Intelligence Platform (Week 10-12)


| Task                                  | Details                                                                                                                                                                                                                                                                                                    |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P5.1 Venture identity data model      | VentureIdentity, IdentityProduct, UserEvent, UserSegment, Campaign, CampaignEvent tables. **Also create marketplace tables (empty, schema-only)**: partner_products, partner_eligibility, fit_scores, partner_bids, recommendations, recommendation_outcomes. Tables exist from day 1 per strategic architecture (D66). |
| P5.2 Cross-product opt-in consent     | "I consent to [LLC Name] using my information across FileFree, LaunchFree, and related services to send me product updates and recommendations. I can unsubscribe from any product at any time." Unchecked default. Per-brand unsubscribe in email footer. See Section 0C Legal Risk Matrix for full spec. |
| P5.3 packages/intelligence engine     | Rules-based recommendation engine (Phase 1) with profile builder, partner matcher, and campaign triggers. See Section 4 for full spec.                                                                                                                                                                     |
| P5.4 packages/email templates         | React Email templates: onboarding series, lifecycle campaigns, partner offers (Legal reviewed)                                                                                                                                                                                                             |
| P5.5 LaunchFree onboarding emails     | 5-email welcome series via n8n + Gmail (with cross-product opt-in respect)                                                                                                                                                                                                                                 |
| P5.6 LaunchFree -> FileFree campaigns | Tax season blast, post-formation nudge (only for users who opted in)                                                                                                                                                                                                                                       |
| P5.7 User event tracking              | Emit UserEvents from both products on key milestones (formed LLC, filed taxes, clicked partner). PostHog event taxonomy per Section 4C.                                                                                                                                                                    |
| P5.8 Campaign analytics + admin       | PostHog events, UTM tracking, campaign performance in admin dashboard                                                                                                                                                                                                                                      |
| P5.9 Experimentation framework        | PostHog feature flags for A/B testing recommendation placements and partner ordering. FTC compliance constraints baked in. See Section 4K.                                                                                                                                                                 |
| P5.10 KPI dashboard setup             | PostHog dashboards for company KPIs: activation rate, completion rate, MAU, partner conversion rate. See Section 4L.                                                                                                                                                                                       |
| P5.11 Lifecycle campaign workflows    | n8n workflows for 7 trigger-based campaigns (post-filing refund, mid-year check-in, post-formation banking, credit score change, tax season return, annual report deadline, dormant re-engagement). See Section 4L.                                                                                        |
| P5.12 Partner auth scaffold           | API key + partner ID authentication for partner dashboard (Section 4N Stage 2+). Build routes at `/api/v1/partners/*`. Initially unused -- scaffold exists so partner auth is ready when first partner requests dashboard access. Includes: partner registration, API key generation, rate limiting.        |


### Phase 6: Agent Restructure + Social Pipeline (Week 10-14)


| Task                                        | Details                                                                                                    |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| P6.1 Update 9 venture-level personas        | engineering, strategy, legal, cfo, qa, partnerships, ux, workflows (update content for venture-wide scope) |
| P6.2 Split 3 personas into product-specific | social -> filefree-social + launchfree-social; brand -> split; growth -> split                             |
| P6.3 Create 6 new personas                  | formation-domain, launchfree-social, launchfree-growth, launchfree-brand, studio, agent-ops                |
| P6.4 Update 6 existing n8n workflows        | Rename, update outputs from Notion to GDrive                                                               |
| P6.5 Build faceless content pipeline        | n8n workflow: topics -> GPT script -> ElevenLabs -> video assembly -> Postiz                               |
| P6.6 Build 12 new n8n workflows             | Support bots, state validator, competitive intel, analytics, infra monitor, campaign engine                |
| P6.7 Migrate Notion to Google Drive         | Move docs, update n8n output nodes                                                                         |


### Phase 7: FileFree Season Prep (October 2026)


| Task                                  | Details                                                                                                                                            |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| P7.1 Resume FileFree Sprint 4         | All 50 state tax calcs (data already built in P2.3), PDF polish                                                                                    |
| P7.2 Column Tax integration           | SDK integration, sandbox testing                                                                                                                   |
| P7.3 TaxAudit partnership             | White-label audit shield integration (if Founder 2 closed deal)                                                                                    |
| P7.4 Refund Plan screen               | HYSA referrals, financial product recs, audit shield upsell, refund splitting UI (Form 8888), goal-based savings recommendations. See Section 1B.3 |
| P7.5 Transactional emails             | Welcome, filing confirmation, abandonment drip                                                                                                     |
| P7.6 FileFree -> LaunchFree campaigns | Post-filing cross-sell for users with biz income                                                                                                   |
| P7.7 Marketing page refresh           | Social proof, filing counter, comparison table                                                                                                     |
| P7.8 1099-NEC + Schedule C support    | Freelancer/gig income. 1099-NEC extraction via OCR pipeline, Schedule C business income/expenses                                                   |
| P7.9 Dependent support                | Dependent information capture, Child Tax Credit ($2,000/child), EITC calculations, HOH filing status                                               |
| P7.10 Schedule B (interest/dividends) | Interest and ordinary dividend income, auto-populate from 1099-INT/1099-DIV                                                                        |
| P7.11 Schedule 1 (additional income)  | Student loan interest, educator expenses, HSA deductions, IRA contributions                                                                        |
| P7.12 All 50 state return engines     | Data-driven state tax calculation engine. Each state defined in JSON (rates, brackets, credits, conformity). ALL 50 states from launch.            |
| P7.13 MeF schema acquisition          | Download ALL IRS + E-Standards XML schemas. Parse into Zod types (TS) and Pydantic models (Python). See Section 7D.                                |
| P7.14 MeF local validation engine     | Build XML generator + local schema validator. Generate all 13 IRS test scenarios. Iterate to 100% local pass rate. See Section 7D.                 |
| P7.15 State test return factory       | For each of 42 MeF states, generate test return with correct state schema. Validate ALL state attachments locally. See Section 7D.                 |
| P7.16 ATS submission                  | Submit all 13 federal scenarios (locally validated). Monitor acknowledgments. Fix and resubmit rejections. See Section 7D.                         |
| P7.17 Communication test              | Automated end-to-end transmission test with IRS. See Section 7D.                                                                                   |
| P7.18 Idempotency middleware          | FastAPI middleware + Redis backend. `X-Idempotency-Key` header on all filing/payment/submission endpoints. See Section 2B.1                        |
| P7.19 Circuit breaker wrappers        | `pybreaker` integration for Cloud Vision, OpenAI, IRS MeF, Column Tax, affiliate APIs. Degradation strategies per service. See Section 2B.2        |
| P7.20 Reconciliation pipeline         | Dual-path tax calculation verification. Nightly batch validation against IRS Pub 17 test vectors. See Section 2B.3                                 |
| P7.21 OpenTelemetry instrumentation   | Distributed tracing across OCR-to-filing pipeline. Grafana Cloud free tier. Filing Health dashboard. See Section 2B.4                              |
| P7.22 Load testing suite              | k6 scripts for 4 tax season scenarios. Monthly runs from October 2026. Performance budget enforcement. See Section 2B.5                            |


### Form Coverage Roadmap


| Milestone                      | Forms                                                                                                  | Notes                                                                        |
| ------------------------------ | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| **January 2027 launch**        | 1040 + Schedule 1 + Schedule B + Schedule C + 1099-NEC/INT/DIV + dependents + ALL 50 state returns     | Covers ~80% of US filers. Phase 7-8.                                         |
| **February 2027 (mid-season)** | Schedule A (itemized deductions) + Schedule D (capital gains basics)                                   | Covers homeowners + basic investors. Phase 8.                                |
| **Year 2 (2027-2028 season)**  | Schedule E (rental), Schedule SE (self-employment tax), multi-state, HSA (Form 8889), K-1 pass-through | Covers small landlords, full self-employed, health savings. Phase 10 (K-1). |
| **Year 2 (business filing)**   | Form 1065 (partnership/LLC), Form 1120-S (S-Corp), Schedule K-1 generation                             | Business returns. $49-99/return (consumer), included in Pro Firm. Phase 10. |
| **Year 3+**                    | Depreciation (Form 4562), AMT (Form 6251), brokerage import (CSV/API), foreign income (Form 2555)      | Edge cases, power users.                                                     |


**MeF ATS testing scope**: The October 2026 ATS testing must cover 1040 + Schedule 1 + B + C + state return XML schemas for ALL 50 states. Start XML generator development by June 2026.

### 7D. MeF Local Validation Engine (Zero-Risk ATS Strategy)

ATS testing is schema validation -- the IRS programmatically checks your XML output against published schemas. This is exactly what AI excels at. By building a local validation engine FIRST, we achieve near-100% first-submission pass rate to ATS.

**Key facts** (verified):

- IRS ATS requires ~13 test scenarios for Form 1040 (published as PDFs on irs.gov)
- ALL XML schemas are publicly downloadable from irs.gov/downloads/irs-schema
- State MeF schemas are published by E-Standards (statemef.com), the FTA-recognized body
- State returns piggyback on the federal submission -- you don't submit 50 separate state packages
- 42 states + DC participate in the 1040 MeF program. Only CA FTB and MA DOR run independent systems.

**Pipeline**:


| Step                          | Timeline       | Agent Work                                                                                                                                                              | Human Work                               |
| ----------------------------- | -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| P7.13 Schema acquisition      | June 2026      | Download ALL IRS + E-Standards XML schemas. Parse into Zod types (TS) and Pydantic models (Python). Build schema version tracker.                                       | None                                     |
| P7.14 Local validation engine | June-July 2026 | Build XML generator from tax calculation output. Build local schema validator. Generate all 13 IRS test scenarios programmatically. Iterate until 100% local pass rate. | Review 2-3 generated XML files           |
| P7.15 Test return factory     | August 2026    | For each of 42 MeF-participating states, generate a test return with correct state schema piggyback. Validate ALL state attachments locally. Generate coverage report.  | Review coverage report                   |
| P7.16 ATS submission          | October 2026   | Submit all 13 federal scenarios (already locally validated). Monitor acknowledgments. Auto-fix and resubmit any rejections.                                             | Contact e-Help Desk if non-schema issues |
| P7.17 Communication test      | November 2026  | Automated end-to-end transmission test.                                                                                                                                 | Verify acknowledgment                    |


**For CA FTB and MA DOR** (independent systems): Use Column Tax as e-file partner for these 2 states only in Year 1. Apply for their independent transmitter programs in Year 2.

**Residual risk**: Zero for schema-related failures. Only risk is IRS process delays (their systems being slow), mitigated by starting June not October.

### 7E. Tiered State Tax Engine Architecture

Federal tax is uniform. State tax is chaos. The engine uses three tiers to handle all 50 states efficiently:

**Tier 1 -- Conforming States (~30 states)**: Start from federal AGI or taxable income, apply state-specific rate brackets, standard deduction, and credits. Entirely data-driven via JSON config. Examples: Colorado (flat 4.4% of federal taxable income), Utah (flat 4.65%), Michigan (flat 4.25%).

**Tier 2 -- Semi-Conforming States (~12 states)**: Start from federal AGI but with state-specific modifications. JSON config + small modifier functions per state. Examples: Virginia (starts from federal AGI, subtracts VA-specific deductions, applies VA brackets), Georgia (adjusts for GA standard deduction amounts).

**Tier 3 -- Independent States (~5 states: CA, NJ, PA, MA, NH)**: Fully custom calculation modules per state. Agent generates initial module from state tax form instructions (publicly available PDFs). Human reviews tax logic. Example: California starts from federal AGI but has its own Schedule CA with ~40 modification items.

**No-income-tax states (7: AK, FL, NV, SD, TX, WA, WY)**: No state return needed. Config flag: `"hasIncomeTax": false`.

**Budget**: Tier 1 states take minutes each (config only). Tier 2 states take hours each. Tier 3 requires 2-3 days per state. Total extra budget: 2 weeks in Phase 7.

### Phase 8: FileFree Launch (January 2027)


| Task                            | Details                                                                                                                                               |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| P8.1 MeF transmitter            | Build XML generator, pass IRS ATS testing (October), communication test (November). Test schemas for 1040 + Schedules 1, B, C + all 50 state returns. |
| P8.2 E-file go-live             | Switch from Column Tax to own transmitter for supported forms                                                                                         |
| P8.3 Tax Optimization Plan      | Stripe, $29/yr, premium dashboard                                                                                                                     |
| P8.4 Product Hunt + HN launch   | Coordinate with filing season start                                                                                                                   |
| P8.5 Paid amplification         | TikTok Spark Ads + Meta boost on winning organic content                                                                                              |
| P8.6 Schedule A (itemized)      | Mid-season release (February 2027). Mortgage interest, SALT, charitable contributions                                                                 |
| P8.7 Schedule D (capital gains) | Mid-season release (February 2027). Basic stock sales, 1099-B import                                                                                  |
| P8.8 Refund Advance integration | If partner secured. Early refund access as acquisition tool                                                                                           |


### Phase 9: Distill -- Full B2B Compliance Platform (Summer 2026)

Leverages shared infrastructure from Phases 1-3 (OCR pipeline, tax engine, filing engine, 50-state data). ~80% shared tech. Distill is a separate B2B brand from FileFree (see Section 1C for rationale). Development runs in parallel with Phases 5-6, launching Summer 2026. AI-augmented development compresses the incremental B2B work (multi-tenant auth, API keys, billing, docs) into weeks, not quarters. See Section 1C for full product spec and Section 5M for bootstrapped GTM playbook.


| Task                            | Details                                                                                                                                                                            |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P9.1 Scaffold apps/distill      | Next.js app at `apps/distill/`. Package name `@venture/distill`. `[data-theme="distill"]` (own brand, dark professional theme). Landing at `/`, dashboard at `/dashboard`.             |
| P9.2 CPA firm onboarding flow   | Firm registration (name, firm size, tax software used), team invites, role management (admin/preparer/reviewer). Multi-tenant data model: `firms`, `firm_members`, `firm_clients`. |
| P9.3 Bulk document upload       | Drag-and-drop multiple W-2s/1099s per client. Queue through shared OCR pipeline (`apis/filefree/` with firm-scoped routes). Batch progress tracking with per-document status.      |
| P9.4 Professional dashboard     | Client list, per-client document status, extraction confidence scores, field-by-field review workflow, approval/correction interface.                                               |
| P9.5 Tax software export        | Generate import files for UltraTax (CSV), Drake (XML), ProConnect (CSV), Lacerte (CSV). Publicly documented formats. Per-client or batch export.                                  |
| P9.6 Stripe B2B billing         | Monthly subscription plans (Solo $49, Team $99, Firm $199). Seat-based billing, usage metering (returns/mo), annual discount (20%).                                               |
| P9.7 CPA-specific landing page  | `distill.tax` landing page. SEO targets: "AI tax preparation software for CPAs", "automated W-2 data entry". Comparison with MagneticTax and manual entry.                        |
| P9.8 CPA outreach campaign      | Target independent CPAs and small firms (1-10 preparers). LinkedIn + direct email campaign. Tax season urgency messaging. Product Hunt launch for B2B segment.                     |
| P9.9 Multi-tenant security audit | Pre-launch security audit: verify RLS policies prevent cross-firm data leakage, test firm-scoped middleware injection, penetration test B2B routes, validate audit log immutability. |
| P9.10 DPA template + onboarding | Data Processing Agreement template (attorney consult scope). Automated firm onboarding agreement flow. Covers: data processing scope, 24hr image retention, no cross-product data usage, CCPA/state privacy compliance. |
| P9.11 Audit trail implementation | Immutable audit log for all extractions, edits, exports, submissions. 7-year retention. CSV export for CPA compliance. Timestamped with user ID + firm ID.                         |


### Phase 10: Business Tax Filing (Year 2, 2027-2028 Season)

Business returns (1065, 1120-S) serve both consumer FileFree users with pass-through entities and Distill CPA firms. Priced at $49-99/return for consumer, included in Distill Firm plan.


| Task                                  | Details                                                                                                                                                                                |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P10.1 Form 1065 engine                | Partnership/multi-member LLC return. Schedule K-1 generation for each partner. Pass-through income/loss allocation.                                                                    |
| P10.2 Form 1120-S engine              | S-Corp return. Schedule K-1 generation. Reasonable compensation analysis (AI-assisted).                                                                                                |
| P10.3 Business expense categorization | AI-powered expense categorization from uploaded bank statements or manual entry. Map to Schedule C/1065/1120-S line items.                                                             |
| P10.4 K-1 import for personal returns | Recipients of K-1s (from client's own businesses or external) can import pass-through income into their 1040 via OCR or manual entry.                                                 |
| P10.5 MeF business return schemas     | Download IRS business return XML schemas. Extend MeF local validation engine (Section 7D) to cover 1065 and 1120-S.                                                                   |
| P10.6 Business filing pricing         | Stripe integration for business return fees: $49/return (1065), $99/return (1120-S). Free for Pro Firm plan subscribers. LaunchFree cross-sell: first business return free.            |
| P10.7 LaunchFree -> FileFree Business | Mandatory cross-sell path: every LaunchFree LLC former who selects "Partnership" or "S-Corp" tax election sees "File your business taxes with FileFree" at formation and at tax season. |


### Background Tasks (Continuous)


| Task                                                                          | Owner     | Deadline                   | Status      | Notes                                                                           |
| ----------------------------------------------------------------------------- | --------- | -------------------------- | ----------- | ------------------------------------------------------------------------------- |
| EFIN application (Form 8633)                                                  | Founder 1 | THIS WEEK                  | NOT STARTED | 45-day processing. Blocks entire MeF chain. See Section 0G.                     |
| Self-serve affiliate apps (Marcus, Wealthfront, Betterment via Impact.com/CJ) | Founder 1 | April 2026                 | NOT STARTED | Plan B revenue. Online forms, no calls needed. Do this regardless of Founder 2. |
| Cyber liability insurance ($1M E&O + cyber)                                   | Founder 1 | Before first SSN collected | NOT STARTED | $1,500-3,000/yr. Non-negotiable. See Section 0G.                                |
| Data breach response plan                                                     | Founder 1 | Before first SSN collected | NOT STARTED | 2-page doc from SANS/NIST templates. See Section 0G.                            |
| Startup attorney consult (1 hour)                                             | Founder 1 | Before Phase 3             | NOT STARTED | UPL + RA questions. ~$300-500. See Section 0G.                                  |
| Column Tax partnership                                                        | Founder 2 | June 2026                  | NOT STARTED | Book demo, negotiate sandbox access.                                            |
| TaxAudit/audit shield partnership                                             | Founder 2 | September 2026             | NOT STARTED | 3-6 month lead time, start Q2 2026.                                             |
| HYSA affiliate applications (banking partners)                                | Founder 2 | October 2026               | NOT STARTED | At least 1 banking partner for first tax season.                                |
| MeF certification prep                                                        | Founder 1 | Start June 2026            | NOT STARTED | XML generator -> ATS testing (October) -> Comms test (November).                |
| TikTok Spark Ads budget                                                       | Founder 1 | At LaunchFree launch       | NOT STARTED | $100-300/mo max. Boost proven organic winners only. See Section 5K.             |
| Pre-launch audience building                                                  | Founder 1 | Ongoing, start NOW         | NOT STARTED | SEO blog posts, Reddit, waitlist growth. See Section 5K.                        |


### Phase Timeline (AI-Augmented — Agents Are the Team)

One founder + AI agents (Cursor, n8n) shipping at the velocity of a full engineering team. Traditional dev estimates don't apply. Shared infrastructure (`packages/*`) is built once and consumed by all products — including Distill's B2B APIs.

| Phase | Target | Hard Deadline? | Rationale |
| --- | --- | --- | --- |
| Phase 0 (Infrastructure) | March 2026 | NO | LLC filing, EFIN (45-day processing), domains, legal. Non-code tasks. |
| Phase 1 (Monorepo) | April 2026 | NO | pnpm workspace restructure, shared packages, 5 apps scaffolded. Foundation for everything. |
| Phase 1.5 (First Trinket) | April 2026 | NO | Overlaps with late Phase 1. Agent pipeline test. |
| Phase 2 (50-State Data) | May 2026 | NO | AI extraction + human review. LaunchFree + Distill Compliance API depend on it. |
| Phase 3 (LaunchFree MVP) | June-July 2026 | NO | Formation wizard, PDF gen, State Filing Engine, Stripe, RA credits, dashboard. First revenue product. |
| Phase 4 (Command Center) | June 2026 | NO | Tier 1 during Phase 3. Daily ops pages. |
| Phase 5 (User Intelligence) | July 2026 | NO | Cross-product data model, consent, campaigns. |
| Phase 6 (Agent Restructure) | July 2026 | NO | Persona split, social pipeline, n8n workflows. |
| Phase 9 (Distill Full Platform) | July-August 2026 | NO | CPA SaaS + Formation API + Tax API + Compliance API. ~80% shared from Phases 1-3. Incremental: multi-tenant, API keys, billing, docs. |
| Phase 7 (FileFree Season Prep) | October 2026 | **YES** | IRS season doesn't move. MeF XML generator starts June. ATS testing October. |
| Phase 8 (FileFree Launch) | January 2027 | **YES** | Tax season. IRS accepts returns ~late January. |
| Phase 10 (Business Tax Filing) | 2027-2028 | NO | Forms 1065, 1120-S. Year 2 product. |

**Key insight**: Phase 9 (Distill) runs in parallel with Phases 5-6, not sequentially after Phase 8. The shared infrastructure from Phases 1-3 means Distill's incremental build is thin. Only two hard deadlines are external (IRS): MeF ATS testing (October 2026) and tax season start (January 2027). Everything else ships as fast as the agents can build it.

### Critical Path (Stress Test Addition)

```
LLC Name Decision (NOW) -> Phase 0.6 (file LLC) -> EIN -> Bank Account -> Stripe -> Trademarks
                                                                                 |
EFIN Application (NOW) -------- 45 days ---------> Software Dev ID -> ATS Testing (Oct 2026) -> MeF Launch (Jan 2027)
                                                                                 |
Phase 1 (Monorepo) -> Phase 2 (50-State) -> Phase 3 (LaunchFree) -> Phase 7 (FileFree Prep) -> Phase 8 (Launch)
```

**Three hard deadlines that cannot move**:

1. **EFIN approval**: Must apply NOW. 45-day processing means approval by May 2026 at earliest. Late application compresses the October ATS testing window.
2. **MeF ATS testing**: IRS opens ATS testing window each fall. Must have XML generator complete by June 2026 to test in October. Miss this and FileFree e-file delays to January 2028.
3. **Tax season**: IRS starts accepting returns late January. Product must be live by then.

### State Filing Engine Architecture

LaunchFree files your LLC with the state on your behalf. The user provides their information; we handle document preparation AND state submission. Nearly all 50 states (~48) have online filing portals. Only ~2 states (Maine and possibly 1 other) are truly mail-only. This was confirmed via research into SmartLegalForms' state-by-state filing database (March 2026). The original claim of "20-25 mail-only states" was factually incorrect.

**How competitors file (confirmed research, March 2026):** LegalZoom (NYSE: LZ), ZenBusiness, and Northwest all genuinely submit formation documents to the Secretary of State on behalf of customers -- at $0 service fee for basic tiers. They use manual staff entry into state portals (primary method), state API integrations where available, and mail for the handful of paper-only states. Revenue comes from RA ($199-249/yr), compliance upsells, and add-ons -- not from filing fees.

**Why not use a formation API partner?** White-label formation APIs exist (CorpNet API, FileForms API, SwyftFilings API). CorpNet offers 20-30% off retail ($99 Basic) = ~$69-79/filing wholesale (source: CorpNet partner FAQ). FileForms wholesale is estimated at $30-60/filing (source: FileForms ROI calculator). At $0 service fee, LaunchFree would absorb $50-80K/year in wholesale costs at 1K formations -- not viable on a $278/mo burn. Building our own State Filing Engine costs ~$0 marginal per filing (just compute time) after the upfront development investment.

**Three-Tier Filing Architecture:**


| Tier | Method | States | Implementation |
| ---- | ------ | ------ | -------------- |
| 1 | State APIs (where formal third-party filing APIs exist) | Delaware (ICIS PublicXMLService confirmed), others TBD | Direct REST/SOAP integration. Delaware requires DCIS ID, Registered Agent number, IP registration, sandbox testing. Gated credential = competitive moat. Same-day programmatic filing. |
| 2 | Portal automation (Playwright) | ~45 states with online filing portals | Headless browser automation. Per-state config: portal URL, form field mappings, fee schedule, confirmation flow. RA/agent filing paths bypass public CAPTCHAs (authorized agent access). Screenshot audit trail at every step. |
| 3 | Print-and-mail | ~2-3 states (Maine + any holdouts) | Generate completed PDF + cover letter. Automated mailing via print-and-mail API service (e.g., Lob). Tracking number provided to user. |


**Payment Orchestration:** User pays LaunchFree via Stripe checkout (state filing fee + $0 service fee). State Filing Engine pays the state during automated submission using Stripe Issuing virtual cards (programmatic card creation, pricing per Stripe's current schedule). Estimated blended marginal cost per filing: ~$0.25-0.50 (virtual card fees + CAPTCHA solving + compute -- actual costs to be validated during Phase 3 development). For high-volume states (DE, CA, FL, TX), apply for prepaid deposit accounts directly with the state for even lower cost and higher reliability.

**Bottleneck Analysis (ranked by severity):**

1. **Payment orchestration (CRITICAL):** Paying state fees during automated submission is the hardest part. States accept different payment methods (credit card, ACH, check, prepaid). Stripe Issuing solves this for credit card states. Prepaid deposit accounts for high-volume states.
2. **Portal fragility (HIGH):** State portals redesign without notice, breaking automation. Mitigations: multiple selector strategies per field (CSS > XPath > text > ARIA), daily automated health checks, volume-weighted maintenance (top 10 states = ~80% of filings), manual fallback SLA (staff submits within 4 hours, script fix within 48 hours).
3. **Anti-bot / CAPTCHA (MEDIUM):** Solved primarily by being the Registered Agent -- RA filing paths are authorized agent access, not anonymous public access. For states where we're not yet RA: CAPTCHA solving services (~$0.003/solve), rate-limited submissions (1-2 per state per hour).
4. **State-specific quirks (MEDIUM):** NY publication requirement, CA biennial Statement of Information within 90 days, some states require notarized articles. Each quirk = a handler in the per-state JSON config + compliance calendar trigger.
5. **Filing verification (MEDIUM):** Multi-channel: instant portal confirmation numbers, email parsing for state confirmations, periodic status polling, mail tracking for print-and-mail states.

**MVP rollout (Phase 3):** Top 10 states by formation volume (CA, TX, FL, DE, WY, NY, NV, IL, GA, WA) via portal automation + Delaware ICIS API. Manual founder submission for remaining 40 states (~3-4/day at 1K formations/year). Scale rollout: 30 states by Phase 3.5, full 50-state automation by Phase 5.

**Dual-use infrastructure:** The State Filing Engine powers both LaunchFree (consumer, $0) and the Distill Formation API (B2B, $20-40/filing target pricing). See Section 1C for the Distill umbrella brand architecture. This is the same pattern as FileFree + Distill Tax API sharing `packages/tax-engine/`.

### 7B. Alerting Strategy

The Infra Health Monitor (Agent #25) needs a clear alerting hierarchy:


| Severity | Condition                                                | Alert Channel                   | Response Time     |
| -------- | -------------------------------------------------------- | ------------------------------- | ----------------- |
| CRITICAL | Render/Vercel DOWN, API 5xx rate >5%                     | Slack #ops-alerts + Email + SMS | Immediate         |
| WARNING  | API response time >2s, error rate >1%, disk >80%         | Slack #ops-alerts + Email       | Within 1 hour     |
| INFO     | Deploy completed, cron job finished, daily health report | Slack #ops-alerts only          | Next business day |


**Alert routing**:

- All alerts go to Slack `#ops-alerts` channel (see Section 12 for full Slack hub architecture)
- CRITICAL also sends email to founder + SMS via Twilio ($0.0075/SMS, ~$2/month max)
- n8n handles all alert routing logic (Slack API nodes + Twilio API)

**Monitoring endpoints**:

- Render: `https://api.render.com/v1/services/{id}` (health status)
- Vercel: `https://api.vercel.com/v9/deployments` (deployment status)
- Hetzner: direct HTTP health check to n8n/Postiz endpoints
- Neon: connection test via studio API health endpoint
- Upstash: Redis PING via studio API health endpoint

### 7C. Trinkets Domain Decision

**Decision**: Use `tools.filefree.ai` subdomain. Do NOT buy individual domains per trinket.

**Rationale** (SEO research-backed):

- No domain purchase needed (we own filefree.ai)
- Easy DNS setup (CNAME to Vercel)
- Subdomain inherits some domain authority from filefree.ai (confirmed: subdirectories > subdomains > new domains for SEO authority)
- Individual exact-match domains (e.g., `freemortgagecalculator.com`) have been devalued by Google since 2012 EMD update
- New domains start at DA 0 -- won't outrank established tools (NerdWallet, Bankrate, Calculator.net) for years
- At Year 1 trinkets revenue of $50-300, buying 15+ domains at $10-15/yr each is negative ROI
- Cross-sell CTAs naturally funnel traffic from trinkets to FileFree/LaunchFree

**Graduation criteria**: If a single trinket exceeds 10K monthly visits, consider buying a standalone domain and 301-redirecting. This is a growth optimization, not a launch decision.

**URL structure**: Subdirectory-style paths on the subdomain for topical clustering: `tools.filefree.ai/calculators/mortgage`, `tools.filefree.ai/converters/pdf-to-word`. See Section 0F for full technical pattern.

**Vercel config**: Add `tools.filefree.ai` as a custom domain to the `apps/trinkets/` Vercel project.

---

## 8. Plan Hygiene

**Anti-Bloat Rules** (D52): (1) Collapse completed phase tables to one-line summaries. (2) Rotate KNOWLEDGE.md every 6 months, keep under 500 lines. (3) Archive superseded docs. (4) Master plan target: under 3,500 lines.

---

## 9. Self-Review Findings (Archived)

5 rounds of self-review (all personas) produced 30+ findings. All but 2 LOW findings are FIXED. Open items: F19 (CCPA "sale" analysis for Stage 3 aggregate data) and F24 (score existing partner hit list against 5-factor matrix when outreach begins).

**Full review findings**: [docs/archive/VMP-ARCHIVE.md](../archive/VMP-ARCHIVE.md) Sections 9 and 10

---

## 10. Key Decisions — All Decided

10 of 11 decisions resolved. Only open item: **#7 Trademark filing timing** (file post-launch with specimen vs intent-to-use now at $350/class extra). All other decisions logged in KNOWLEDGE.md (D38-D57).

---

## 12. Agent Communication Hub: Slack + Email Aliases

### Why Slack

The venture operates like a company with AI employees. Employees need a persistent communication channel that isn't just Cursor chat windows (which are ephemeral). Slack provides:

- Persistent message history (searchable, linkable)
- Channel-based organization (functional departments)
- Two-way agent interaction via n8n webhooks
- Mobile app for founder on-the-go checks
- Integrations ecosystem (GitHub, Vercel, Render, Google Drive notifications)

### Channel Structure


| Channel            | Purpose                                              | Who Posts                                   |
| ------------------ | ---------------------------------------------------- | ------------------------------------------- |
| #general           | Company-wide announcements, decisions                | Founder, EA                                 |
| #daily-briefing    | EA Ops Monitor daily summary (7am)                   | EA Ops Monitor (n8n)                        |
| #weekly-planning   | Weekly planning output (Sunday 6pm)                  | EA Ops Monitor (n8n)                        |
| #compliance-alerts | Compliance Monitor status updates                    | Compliance Monitor (n8n)                    |
| #ops-alerts        | Infrastructure health alerts (CRITICAL/WARNING/INFO) | Infra Health Monitor (n8n)                  |
| #social-content    | Social post drafts for review/approval               | Social Content Pipeline (n8n)               |
| #dev-feed          | GitHub PR notifications, Vercel deploys, CI results  | GitHub/Vercel integrations                  |
| #partnerships      | Partnership pipeline updates, outreach drafts        | Partnership Outreach (n8n)                  |
| #data-integrity    | State data validation results, stale data alerts     | State Data Validator (n8n)                  |
| #filing-engine     | State Filing Engine health, submission status, portal failures | Filing Engine Monitor (n8n)        |
| #revenue           | Affiliate conversions, Stripe events                 | Affiliate Tracker (n8n), Stripe integration |


### Two-Way Agent Interaction

**Founder -> Agent (Slack -> n8n)**:

- Founder posts in a channel with a command format (e.g., `/agent status`, `/agent brief me on partnerships`)
- n8n Slack trigger node picks up the message
- Routes to appropriate agent workflow
- Agent responds in-thread

**Agent -> Founder (n8n -> Slack)**:

- n8n workflows post to appropriate channels via Slack API
- Urgent items go to #ops-alerts (plus email/SMS for CRITICAL)
- Routine reports go to #daily-briefing

**Cursor -> Slack (Slack MCP)**:

- Use Slack MCP in Cursor to read/post messages from within the IDE
- EA persona can check Slack context before answering operational questions
- Decisions made in Cursor get logged to #general via EA

### Professional Email Aliases (Google Workspace)

Department-level email aliases on Google Workspace. All route to founder's inbox. Agents draft replies, founder approves and sends.


| Alias                                                       | Domain        | Purpose                                   |
| ----------------------------------------------------------- | ------------- | ----------------------------------------- |
| [hello@filefree.ai](mailto:hello@filefree.ai)               | filefree.ai   | General FileFree inquiries                |
| [support@filefree.ai](mailto:support@filefree.ai)           | filefree.ai   | FileFree user support                     |
| [legal@filefree.ai](mailto:legal@filefree.ai)               | filefree.ai   | Legal inquiries, DMCA, compliance         |
| [partnerships@filefree.ai](mailto:partnerships@filefree.ai) | filefree.ai   | Partnership inquiries (Founder 2 primary) |
| [hello@launchfree.ai](mailto:hello@launchfree.ai)           | launchfree.ai | General LaunchFree inquiries              |
| [support@launchfree.ai](mailto:support@launchfree.ai)       | launchfree.ai | LaunchFree user support                   |
| [hello@distill.tax](mailto:hello@distill.tax)               | distill.tax   | General Distill inquiries                 |
| [support@distill.tax](mailto:support@distill.tax)           | distill.tax   | Distill technical support                 |
| [api@distill.tax](mailto:api@distill.tax)                   | distill.tax   | API partner inquiries, developer support  |


**Note**: filefree.tax aliases (hello@, support@) retained as forwards to filefree.ai equivalents post-migration (P0.2).

**Outbound Email Flow**:

1. Agent (Partnership Outreach, Support Bot) drafts email in Google Docs or Slack thread
2. Founder reviews draft in Slack (#partnerships or #support)
3. Founder approves -> Agent sends via Gmail API (n8n Gmail node) from appropriate alias
4. Sent email logged in Slack thread for audit trail

**Setup**: Google Workspace active on paperworklabs.com (Business Starter, 1 seat, $6/mo — see D76). Alias domains: filefree.ai, launchfree.ai, distill.tax. Department aliases (hello@, support@, legal@, partnerships@, api@) configured on each domain, all routing to founder's inbox (sankalp@paperworklabs.com). Olga Sharma gets admin panel access via personal email in `ADMIN_EMAILS` env var — no second Workspace seat needed.

### Stress Test: Communication Overload

Risk: 10+ channels with multiple agents posting could overwhelm the founder.

Mitigations:

- **Notification tiers**: Only #ops-alerts and #compliance-alerts send push notifications. All other channels are check-when-ready.
- **Daily digest**: EA Ops Monitor's 7am #daily-briefing summarizes everything the founder needs to know. If nothing is on fire, the founder only reads this one channel.
- **Mute by default**: #dev-feed, #revenue, #data-integrity are muted. Founder checks manually or via weekly planning.
- **Escalation chain**: If an agent posts something that needs immediate founder attention, it goes to #ops-alerts with CRITICAL tag, plus email + SMS.

