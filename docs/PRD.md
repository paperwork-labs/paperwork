---
doc_kind: spec
last_reviewed: 2026-04-24
version: "8.0"
---

# Paperwork Labs — Product Requirements Document

**Status**: Venture-level PRD

**Entity**: Paperwork Labs LLC (California). Products: FileFree, LaunchFree, Distill, Trinkets, Brain, Studio.
**Monthly burn**: ~$278/mo (see `docs/FINANCIALS.md:1` for breakdown).
**Team**: Founder 1 (Product/Engineering), Founder 2 (Partnerships/Revenue), 44 AI agent personas.

For full venture strategy, valuation, marketplace evolution, and agent architecture, see `docs/VENTURE_MASTER_PLAN.md:1`.
For AI model routing, see `docs/AI_MODEL_REGISTRY.md:1`.
For Brain technical architecture (60 design decisions, 228 findings), see `docs/BRAIN_ARCHITECTURE.md:1`.

## TL;DR

- **Build**: A linked portfolio — mobile-first free tax prep (`FileFree`), $0-fee LLC formation (`LaunchFree`), B2B compliance and APIs (`Distill`), utility calculators (`Trinkets`), the `Studio` command center, and the `Brain` life-intelligence layer — backed by shared packages in this monorepo.
- **Audience**: First-time and simple filers; new business owners; CPA firms and API integrators; internal operators; later, Brain consumers.
- **Non-obvious**: Consumer and B2B tax flows share `packages/tax-engine/package.json:1` and `packages/document-processing/package.json:1`; LaunchFree and Distill formation share `packages/filing-engine/src/index.ts:1`; sustainable free e-file for simple returns requires bringing an in-house IRS Modernized e-File (MeF) transmitter live (NORTH STAR), not relying on a partner in perpetuity.

| Product | Domain | Description | Launch | Status |
|---|---|---|---|---|
| FileFree | filefree.ai | Free AI tax filing | January 2027 | In development |
| LaunchFree | launchfree.ai | Free LLC formation | Summer 2026 | In development |
| Distill | distill.tax | B2B compliance APIs + CPA SaaS | Summer 2026 | Planned |
| Trinkets | tools.filefree.ai | Utility tools (calculators) | Phase 1.5 | Planned |
| Brain | brain.paperworklabs.com | AI life intelligence system | Phase 11 | Architecture complete |
| Studio | paperworklabs.com | Command center + portfolio | Phase 4 | Tier 1 complete |

---

## FileFree (filefree.ai)

### Problem

~166M individual tax returns are filed annually in the US. ~70% of filers have simple tax situations (W2 income, standard deduction), yet they pay $0-$170+ to TurboTax or spend hours at H&R Block for what should be a 5-minute process. <!-- STALE 2026-04-24: Re-verify IRS Direct File / free-filing story for 2026 filing season; agency programs change year to year --> TurboTax faces active lawsuits for selling user data and deceptive pricing. 67% of Gen Z are stressed about filing. 40% have cried over it. The system is broken, and the alternatives are disappearing.

Filing a first return is the first real interaction most young Americans have with the financial system; a bad experience creates lasting anxiety about money. No product owns that first filing moment.

### Users

- Age 18-30 (Gen Z, especially first-time and early-career filers)
- Single filer or married filing jointly
- W2 income only (1-3 W2s)
- Standard deduction (no itemizing)
- No dependents in MVP; dependents in v1.1
- No investment, rental, or self-employment income in MVP
- US resident, single state

**Research signal:** 67% of Gen Z stress about filing (vs 57% of all Americans); 62% call tax season the #1 financial stressor. 44% have used AI for tax help (vs 4% of Boomers); 70% would consider AI-based prep. 80% stick with the same program year after year — whoever captures a 22-year-old holds that relationship for ~10 years. 40% procrastinate until the deadline; 50%+ had unfiled returns three days after April 15.

### Scope

FileFree is a mobile-first web app: free, AI-powered tax prep — snap a W2, get a completed return in minutes. The year-round product is an AI tax advisor for Gen Z, built on trust from that first filing.

**Phase 1 (2026):** Free tax prep — W2 photo to completed 1040 PDF in under five minutes. Tiered OCR (GCP Cloud Vision + GPT). E-file through a partner at cost until the in-house IRS transmitter is certified.

**Phase 2 (2027):** Free e-file via the owned IRS MeF transmitter (NORTH STAR) + Tax Optimization Plan ($29/yr) + financial product marketplace.

**Phase 3 (2028):** Embedded tax engine (B2B API) for fintechs, payroll, and neobanks.

### Non-goals (MVP)

- Itemized deductions, Schedule C self-employment, and investment/rental income beyond the form roadmap
- Multi-state, dependents, and complex 1099s in the “later” tranche only — not first ship

### Success metric

**2026 (validation):** Email waitlist 500+ by April 15, 2,000+ by October 15. Beta users (full flow) 500 by October 15. Completion rate > 60% of starters. NPS > 50. Tax-receipt share rate > 15% of completers. 50+ testimonials.

**2027 (revenue):** 50,000 filers. 2,500 AI Advisory subs (5% conversion). 5,000 financial-product referrals (10% of filers). ARR $500K+.

**2028 (scale):** 500,000 filers. ARR $5M+. 5+ B2B API partners.

### Competitive landscape

**Market size:** US consumer tax prep ~$8.2B. Intuit (TurboTax) = $4.9B revenue, 60% market share.

**Filing volume:** 165.8M returns in 2025. 154.9M e-filed (93.4%). ~16.5M extension filers (10%). Average refund in 2026: $2,290 (up 10.9%).

| Competitor | Federal | State | W2 OCR | Speed | Revenue Model | Threat to FileFree |
|---|---|---|---|---|---|---|
| TurboTax | "Free" (upsells) | $39.99+ | Yes | 30+ min | Upsells + data | LOW (trust collapse, can't simplify without killing revenue) |
| H&R Block | "Free" (upsells) | $37+ | Yes | 30+ min | Upsells + pro services | LOW (same structural problem) |
| FreeTaxUSA | Free (all complexity) | $15.99 | Yes (unreliable) | 20-40 min | State filing fees | MODERATE (free federal for ALL complexity, 3.2% market share, $35.7M rev) |
| Cash App Taxes | Free | Free | No | 15-30 min | Cross-sell to Cash App ecosystem | HIGH (truly free, but requires Cash App account) |
| april | Embedded | Embedded | Yes | 36 screens | B2B API fees | CRITICAL (see below) |
| Taxu.io | Free basic + $10-29/mo biz | Included | Yes | Fast | Personal + business tiers | MEDIUM-HIGH (2M+ users, charges for business features) |
| NerdWallet | Free (Column Tax) | Free | Yes | Varies | Content/affiliate | MEDIUM (Column Tax white-label, not proprietary) |
| TaxSlayer | Free (Simply Free) | $24.95+ | Limited | 20+ min | Paid tiers | LOW-MEDIUM (free tier limited to simple returns) |
| **FileFree** | **Free** | **Free** | **Yes (AI)** | **2-5 min** | **Advisory + referrals** | -- |

### The april threat

april ($78M raised) is B2B2C -- embedded in Chime, Gusto, 30+ fintechs. They don't have a consumer brand; we're B2C. Users Googling "file taxes free" never find april. We're building our own IRS MeF transmitter (NORTH STAR). Column Tax is interim e-file partner (October 2026) at cost-passthrough.

### Moat assessment

Full competitive analysis in `docs/VENTURE_MASTER_PLAN.md:1` Section 4O.

### User flow (MVP)

**Key points:** Anonymous W2 try-before-signup (Screen 0) reduces friction. Capture and confirm documents (W2, optional DL) before filing details and the refund/owed summary. MVP ends at PDF + mail instructions; e-file and dashboard are phased.

#### Screen 0: Try without signing up (growth unlock)

- User can snap/upload a W2 photo WITHOUT creating an account
- Show the OCR extraction magic (fields filling in one by one)
- Gate: "Create a free account to save your return and finish filing"
- This reduces the trust barrier to zero and creates shareable "wow" moments
- Anonymous session data converts to user account on sign-up

#### Screen 1: Landing and login

- Hero: anxiety-focused copy, not feature-focused
- Primary CTA: "Snap Your W2 -- See It In Action" (try-before-signup)
- Secondary CTA: "Sign In" for returning users
- Social proof: filing counter, testimonials, trust badges
- Comparison section: FileFree vs TurboTax vs FreeTaxUSA
- FAQ section targeting Gen Z concerns ("Is this really free?", "Is my data safe?", "What's the catch?")
- Dedicated /pricing page linked from nav: explicit free-forever guarantee for core filing
- Auth: Google OAuth + Apple Sign-In, optional email/password fallback
- Mobile-optimized, dark theme with gradient accents

#### Screen 2: Document capture (W-2)

- Full-screen camera interface with W2 bounding box overlay
- Guide text: "Position your W2 within the frame"
- Manual capture button (auto-capture is stretch goal)
- Immediate quality check: blur detection, lighting check
- If quality fails: "That's a bit blurry. Try again with more light."
- Upload from photo library as alternative
- Multiple W2 support ("Add another W2" after first)

#### Screen 3: Document capture (driver's license)

- Same camera interface, DL-shaped bounding box
- Skippable: "Enter your info manually instead" link
- Front of DL only (MVP)
- Extract: Full name, address, DOB

#### Screen 4: Confirm Extracted Data

- Clean, editable form with extracted data
- Confidence indicators: green (>95%), yellow (80-95% -- "please verify"), red (<80% -- empty, user types in)
- Manual entry fallback: if OCR fails, same form layout with all fields empty and W2 box-number labels
- "Everything look right?" CTA at bottom

#### Screen 5: Filing Details

- Filing status selector (Single, MFJ, MFS, HoH) -- large tappable cards
- Standard deduction auto-selected (shows amount)
- Dependents: greyed out with "Coming Soon" badge (MVP)
- Only what's legally required -- minimal

#### Screen 6: Return summary

- Animated refund reveal (count-up) or calm owed display
- Breakdown: Gross Income, Standard Deduction, Taxable Income, Federal Tax, Already Paid, Refund/Owed
- Charts: "Where Your Taxes Go" pie chart, "Your Refund vs Average" bar chart
- AI Insights: plain-English explanation + personalized tips (streaming, typewriter effect)
- Tax receipt viral card: shareable graphic with filing time, opt-in refund amount, FileFree branding
- CTAs: "Download Your Completed Return (PDF)", "Add State Filing -- Free"

#### Screen 7: Download and next steps (MVP, no e-file)

- Completed 1040 PDF download
- Step-by-step submission instructions (IRS Free File or mail)
- "E-file coming January 2027 -- we'll notify you"
- AI Advisor teaser: "Want to keep more of your money next year? Get personalized tax-saving tips year-round." -> email capture for AI advisory waitlist
- Upsell: "Protect yourself with Audit Shield -- $29/year"

#### Screen 8: Dashboard (Post-Filing)

- Filing status card with return summary
- Download return PDF
- "File State Return" CTA
- AI Advisor card: monthly tax tip, "Your tax-saving opportunities" (preview of premium)
- Referral card: "Know someone who needs to file? Share FileFree"

### E-file strategy

**Key points:** NORTH STAR is an in-house MeF transmitter (not permanent Column Tax margin). Interim: partner e-file at pass-through. MVP: PDF + mail. Calendar dates in the numbered list need rolling updates each season.

#### NORTH STAR: Own IRS MeF transmitter (January 2027)

The #1 long-term strategic priority. Owning our e-file infrastructure means $0/return cost, full control, and no third-party dependencies. This is what makes "free forever" permanently sustainable.

**IRS Certification Timeline (hard calendar constraints):**

1. **March 2026:** Apply for EFIN (Form 8633). Requirements: PTIN, IRS e-Services account, ID.me verification, fingerprinting. 45-day processing. <!-- STALE 2026-04-24: EFIN approval window vs. today; update when application status is known -->
2. **May 2026:** EFIN approved. Apply for e-Services MeF system access (1-2 weeks).
3. **May-September 2026:** Build MeF XML generator from TaxCalculation data model (IRS Publication 4164 specification). Map all 1040 fields to MeF XML schema. 4-8 weeks focused engineering.
4. **October 2026:** IRS Assurance Testing System (ATS) opens. Submit 12 mandatory test scenarios. This is the hard constraint -- ATS opens once per year in October.
5. **November 2026:** Complete communication test with IRS MeF production system.
6. **January 2027:** Production go-live. Free e-file for all users. Deprecate Column Tax for simple returns.

#### Interim: Column Tax SDK (October–December 2026)

- Integrate Column Tax web SDK into post-summary flow
- Transparent cost-passthrough: user pays exactly what we pay Column Tax (no markup). Target: negotiate to $10-15/return.
- Free PDF download always available as alternative
- User-facing messaging: "We're going through the rigorous IRS e-file certification process, which completes this fall. Until then, you can download your return for free, or e-file through our certified partner at cost. Once we're IRS-certified, e-file will be free forever."

#### MVP (pre–October 2026)

- No e-file. Generate 1040 PDF with step-by-step mailing instructions.
- Include IRS Free File guidance where applicable.
- Messaging: "E-file coming October 2026. Download your completed return now."

### Form coverage roadmap

| Milestone | Forms | Notes |
|---|---|---|
| **January 2027 launch** | 1040 + Schedule 1 + Schedule B + Schedule C + 1099-NEC/INT/DIV + dependents + ALL 50 state returns | Covers ~80% of US filers |
| **February 2027 (mid-season)** | Schedule A (itemized deductions) + Schedule D (capital gains basics) | Covers homeowners + basic investors |
| **Year 2 (2027-2028 season)** | Schedule E (rental), Schedule SE (self-employment tax), multi-state, HSA (Form 8889), K-1 pass-through | Covers small landlords, full self-employed, health savings |
| **Year 2 (business filing)** | Form 1065 (partnership/LLC), Form 1120-S (S-Corp), Schedule K-1 generation | Business returns. $49-99/return (consumer), included in Pro Firm |

---

## LaunchFree (launchfree.ai)

### Problem

There are ~4.4M new business formations in the US per year. Entrepreneurs pay $39-$500+ in service fees to companies like LegalZoom ($149-$299), ZenBusiness ($0 base + $199-$349/yr upsell), and Northwest ($39) for what is fundamentally a simple government form. Worse, these companies bury state filing fees in the total, upsell aggressively on EIN filing ($70-$150 for something that takes 5 minutes free on IRS.gov), and charge $99-$299 for operating agreement templates. No incumbent optimizes for “which state should I form in given my situation.”

### Users

- US residents forming a new LLC (side projects and main businesses)
- Price-sensitive; need state fees and ongoing costs shown before commitment
- _TODO: tighten ICP (e.g. solo vs. multi-member) from GTM research_

### Scope

LaunchFree is a free LLC formation service. $0 service fee — the user pays only what their state charges, disclosed upfront. AI-driven 50-state comparison helps pick the lowest-cost, best-fit state.

**Service at $0:** LLC formation (prep + state submission via Filing Engine in `packages/filing-engine/src/index.ts:1`), state-specific operating agreement template, EIN walkthrough, compliance calendar and reminders, 50-state comparison guide.

**Not covered by us (government and third parties):** State filing fee ($35–$500 by state). We surface the cheapest legitimate path for the user’s case.

**Revenue:** RA credits, banking/payroll/insurance referrals, Compliance-as-a-Service ($49–99/yr).

### Non-goals

- Licensed legal advice or custom operating-agreement drafting — templates plus plain-language explanation only
- Full 50-state unattended automation on day one — see MVP rollout and manual fallbacks
- Hiding or blending state fees into “free” — FTC-safe copy and fee disclosure in the same view as any “$0” claim

### Success metric

**H2 2026 (Launch):**

- Formations: 1,000-5,000
- RA credit purchases: 1-3% of formations
- Compliance SaaS attach rate: 8-18%
- Revenue: $7.9K-$114K

**Year 2 (2027-2028):**

- Formations: 5,000-15,000
- Cross-sell to FileFree: 5-8% of formers file taxes via FileFree
- Compliance SaaS renewals: 70%+ retention

### 50-state comparison

No competitor helps users choose which state to form in based on their actual situation. LaunchFree's AI comparison guide analyzes filing fees, annual costs, franchise tax, privacy protections, processing speed, and entity types across all 50 states. The user inputs their home state, business type, and priorities; the AI presents a ranked recommendation with full cost breakdowns.

**Cheapest states to form (marketing content):**

| State | Filing Fee | Annual Cost | Notes |
|---|---|---|---|
| Montana | $35 | $20/yr | Cheapest filing in the US |
| Kentucky | $40 | $15/yr | Low ongoing costs |
| Arkansas | $45 | $150/yr | Higher annual |
| Colorado | $50 | $10/yr | Very low annual |
| Arizona | $50 | $0/yr (no annual report) | No ongoing state cost |
| Michigan | $50 | $25/yr | Moderate |

**Data accuracy standard:** Every fee, deadline, and requirement shows its source (e.g. "CA SOS, last verified 2026-03-01"). User confirmation before any filing action. Automated freshness checks in n8n: daily in volatile states, weekly for all others. See `docs/VENTURE_MASTER_PLAN.md:1` Section 3B.

### State filing engine

LaunchFree files your LLC with the state on your behalf. The user provides their information; we handle document preparation AND state submission. Nearly all 50 states (~48) have online filing portals. Only ~2 states (Maine and possibly 1 other) are truly mail-only. Source: SmartLegalForms state-by-state filing database (March 2026).

**Three-Tier Filing Architecture:**

| Tier | Method | States | Implementation |
|---|---|---|---|
| 1 | State APIs | Delaware (ICIS PublicXMLService confirmed), others TBD | Direct REST/SOAP integration. Delaware requires DCIS ID, RA number, IP registration, sandbox testing. Gated credential = competitive moat. Same-day programmatic filing. |
| 2 | Portal automation (Playwright) | ~45 states with online portals | Headless browser automation. Per-state config: portal URL, form field mappings, fee schedule, confirmation flow. RA/agent filing paths bypass CAPTCHAs (authorized agent access). Screenshot audit trail. |
| 3 | Print-and-mail | ~2-3 states (Maine + holdouts) | Generate completed PDF + cover letter. Automated mailing via print-and-mail API service (e.g., Lob). Tracking number provided to user. |

**Payment Orchestration:** Stripe Issuing virtual cards for programmatic state fee payment (pricing per Stripe's current schedule). Estimated blended marginal cost: ~$0.25-0.50/filing (virtual card fees + CAPTCHA solving + compute -- actual costs to be validated during Phase 3 development).

**Bottleneck Summary:**

1. Payment orchestration (CRITICAL) -- different states accept different payment methods
2. Portal fragility (HIGH) -- state sites redesign without notice; daily health checks + manual fallback SLA
3. Anti-bot / CAPTCHA (MEDIUM) -- solved by RA authorized agent access
4. State-specific quirks (MEDIUM) -- per-state config handles edge cases
5. Filing verification (MEDIUM) -- multi-channel confirmation

**MVP rollout:** Top 10 states (CA, TX, FL, DE, WY, NY, NV, IL, GA, WA) via portal automation + Delaware ICIS API. Manual founder submission for remaining 40 states at low volume. Full 50-state automation by Phase 5.

**Dual-use:** The State Filing Engine powers both LaunchFree (consumer, $0) and the Distill Formation API (B2B, $20-40/filing target pricing). Code lives in `packages/filing-engine/src/index.ts:1` (orchestrator and handlers).

### Free vs. paid

| Item | Cost | Who Pays |
|---|---|---|
| LLC formation prep (Articles of Organization) | $0 | LaunchFree covers |
| Operating agreement template | $0 | LaunchFree covers |
| EIN filing walkthrough | $0 | LaunchFree covers |
| 50-state AI comparison | $0 | LaunchFree covers |
| Compliance calendar + reminders | $0 | LaunchFree covers |
| State filing fee | $35-$500 | User pays state |
| Registered agent (annual) | $49/yr base | User pays (earn credits to reduce) |
| Compliance-as-a-Service (optional) | $49-99/yr | User pays (optional add-on) |

**FTC "Free" compliance**: NEVER use "Free LLC" as a standalone headline. Always: "Free LLC Formation Service" or "$0 Service Fee." State filing fees must appear in the same visual field as any "free" claim.

### RA credit system

**Base RA price**: $49/yr. Users earn credits to reduce or eliminate the cost by completing partner actions:

- Open a business bank account (Mercury, Relay): earn $25 credit
- Set up payroll (Gusto): earn $25 credit
- Get business insurance (Next): earn $15 credit

**Pricing language**: "RA starting at $49/yr. Earn credits to reduce your cost." NEVER say "Free RA."

### Compliance-as-a-Service (Phase 3.5, $49–99/yr)

After LLC formation, ongoing compliance management -- annual report reminders, franchise tax calculations, state deadline tracking, pre-filled renewal forms.

LaunchFree already captures all state-specific formation data in the 50-state JSON configs (`packages/data/package.json:1` workspace). Compliance deadlines and annual report requirements extend the same data: calendar rules, state fee lookups, and n8n-driven email reminders.

| Metric | Conservative | Moderate | Aggressive |
|---|---|---|---|
| LaunchFree formations (Year 1) | 1,000 | 2,000 | 5,000 |
| Compliance attach rate | 8% | 12% | 18% |
| Price | $49/yr | $79/yr | $99/yr |
| Annual recurring revenue | $3,920 | $18,960 | $89,100 |

**Competitive positioning**: "You formed for free. Now stay compliant for $49/yr. LegalZoom charges $299."

### LaunchFree competitive landscape

| Service | Service Fee | Upsells | State Fee Transparency | State Comparison |
|---|---|---|---|---|
| LegalZoom | $0-$299 | Heavy ($199 RA, $159 operating agreement, $159 EIN) | Buried in total | No |
| ZenBusiness | $0 | Heavy ($199/yr Pro, $349/yr Premium) | Shown separately | No |
| Northwest | $39 | Moderate ($125/yr RA included Y1) | Shown separately | No |
| Incfile | $0 | Heavy ($149-$349 bundles) | Shown separately | No |
| Cairn (withcairn.com) | Free guide, $14.99 docs | Limited | Shown | Guide only, not full service |
| **LaunchFree** | **$0** | **None (revenue from partner referrals)** | **Upfront, before you start** | **Yes (AI-powered, all 50 states)** |

---

## Distill (distill.tax)

### Problem

B2B buyers need tax extraction, formation, and entity compliance without the “free consumer” story of `FileFree`. A separate B2B brand (Stripe/Plaid style) keeps one login, one API key, and clean cross-sell. Incumbent CPA extraction plays exist (e.g. MagneticTax, YC S25); we ship on top of the same OCR and engines built for consumer — Distill is mostly incremental on shared packages.

### Users

- CPA firms and small professional shops (1–10 preparers) using Distill for CPAs
- Fintech, payroll, HR, and banking integrators for Tax, Formation, and Compliance APIs
- _TODO: add firm-size bands and support expectations when sales playbook lands_

### Scope

**Brand:** “Distill” = extract the essential data from government paperwork. Covers tax extraction, LLC formation, ongoing compliance.

**Product lines:** (1) **Distill for CPAs** (dashboard at distill.tax, Phase 9): bulk W-2/1099 upload, review UI, export to UltraTax/Drake/ProConnect/Lacerte — uses `packages/tax-engine/package.json:1` and `packages/document-processing/package.json:1`. (2) **Distill Tax API** (api.distill.tax/tax): per-return ($5–15); calc-only at first; e-file when MeF ships — `packages/tax-engine/package.json:1`. (3) **Distill Formation API** (api.distill.tax/formation): $20–40/filing target; same State Filing Engine as LaunchFree — `packages/filing-engine/src/index.ts:1`. (4) **Distill Compliance API** (api.distill.tax/compliance): deadlines and alerts from `packages/data/package.json:1` configs. Advanced entity ops (amendments, FQ, dissolution) in later years.

The CPA product is a UI surface; the APIs are headless. Shared core, distinct pricing.

### Non-goals

- Reusing the FileFree brand or “free” consumer positioning for B2B contracts
- _TODO: explicit list of API surfaces not in Summer 2026 cut (if any)_
- _TODO: partner SLAs and data residency when enterprise deals start_

### Success metric

| Milestone | Timeline | Revenue | Channel |
|---|---|---|---|
| 10 CPA firms | Feb 2027 | $500-2K MRR | Founder-led sales + free tier conversion |
| 50 CPA firms | Apr 2027 | $2.5K-10K MRR | Product Hunt + content + referrals |
| 200 CPA firms | Jan 2028 | $10K-40K MRR | SEO + word-of-mouth + returning firms |
| API first customers | Q3 2027 | +$500-2K MRR | Self-serve developer signups |

### Shared technology (B2B vs. consumer)

**Shared:**

- OCR pipeline (Cloud Vision + GPT tiered extraction) -- shared with FileFree
- W-2/1099 field extraction + Pydantic schemas -- shared with FileFree
- Tax calculation engine (50-state) -- shared with FileFree
- State Filing Engine (portal automation, state APIs) -- shared with LaunchFree
- 50-state data layer (`packages/data/package.json:1` workspace) — shared with FileFree + LaunchFree
- Document storage (GCP Cloud Storage, 24hr lifecycle) -- shared
- SSN isolation (regex extraction, never sent to LLMs) -- shared

**B2B-specific delta (~2-3 weeks engineering):**

- Multi-tenant team management (firm -> preparers -> clients)
- Bulk document upload (drag-and-drop multiple documents, queue through shared OCR pipeline, batch progress tracking)
- Professional dashboard (client list, per-client document status, extraction confidence, review workflow)
- Tax software export: CSV/XML import files for UltraTax, Drake, ProConnect, Lacerte
- Stripe B2B billing with seat-based plans and usage metering

### Distill pricing

| Plan | Price | Preparers | Returns/mo | API Access |
|---|---|---|---|---|
| Solo | $49/mo | 1 | 50 | No |
| Team | $99/mo | 3 | 200 | No |
| Firm | $199/mo | Unlimited | 500+ | Yes |

Annual billing discount: 20% (Solo $39/mo, Team $79/mo, Firm $159/mo).

**Revenue projections (CPA SaaS -- Summer 2026 launch):**

| Scenario | CPA Firms | Avg Plan | Monthly Rev | Annual Rev |
|---|---|---|---|---|
| Conservative | 30 | $79/mo | $2,370 | $28K |
| Moderate | 100 | $99/mo | $9,900 | $119K |
| Aggressive | 300 | $129/mo | $38,700 | $464K |

**Distill Formation API revenue projections (launching Summer 2026):**

| Scenario | Year 1 (H2 2026 - H1 2027) | Year 2 (2027-2028) | Basis |
|---|---|---|---|
| Conservative | $15K | $150K | 500 API filings @ $30 avg |
| Moderate | $36K | $360K | 1.2K API filings @ $30 avg |
| Aggressive | $60K | $600K | 2K API filings @ $30 avg |

Note: $20-40/filing is target pricing, undercutting incumbent API providers. Marginal cost estimated at ~$0.25-0.50/filing. Gross margin target: 90%+.

### Multi-tenant data isolation

All Distill API routes use firm-scoped middleware that injects `firm_id` from auth token into every database query. Row-level security (RLS) on PostgreSQL enforced via `SET app.current_firm_id` + RLS policies. No query can return data from a different firm. CPA firm A's client data must never leak to CPA firm B. Security audit required before Distill launch (P9.9).

### DPA requirement

Consumer FileFree users consent directly. Distill is different: the CPA firm is our customer, but the individuals whose W-2s are uploaded are NOT our direct users. We process their PII on behalf of the CPA firm.

CPA firms must sign a Data Processing Agreement (DPA) covering:

- What data we process
- How long we retain it (24hr for images per existing policy)
- That we do not use client data for consumer product matching
- CCPA/state privacy law compliance

DPA template needed before Distill launch (attorney consult scope item, P9.10).

### Audit trail

Every extraction, edit, export, and submission is timestamped with user ID and firm ID. Immutable audit log retained for 7 years (IRS record retention requirement). Exportable as CSV for CPA firm compliance needs. This is a differentiation feature -- CPAs face IRS audits and need proof of every step.

### Competitive positioning (vs. MagneticTax)

- MagneticTax is VC-funded (YC S25) with dedicated burn. We are bootstrapped; consumer filing is the primary product and B2B is marginal cost.
- MagneticTax only does 1040 data entry. Distill inherits full form coverage (1040 + Schedules 1, A, B, C, D + 1099-NEC/INT/DIV + 50-state returns) and expands as FileFree adds forms.
- MagneticTax has no consumer product, no financial marketplace, no cross-product data moat.

**Distribution:** Target independent CPAs and small firms (1–10 preparers). 75,000+ CPA firms in the US. Tax season creates urgency. Off-season: extensions, amendments, prior-year, quarterly estimates. See `docs/VENTURE_MASTER_PLAN.md:1` Section 5M.

---

## Trinkets (tools.filefree.ai)

### Trinkets overview

Trinkets is a collection of simple, client-side utility tools (financial calculators, converters, generators) that serve three purposes:

1. **Test the agent infrastructure** -- the Trinket Factory pipeline validates our end-to-end agent workflow (Discovery -> PRD -> Build)
2. **Build shared libraries** — the first trinket documents reusable UI/logic patterns in-app <!-- STALE 2026-04-24: `packages/tool-template` path not in repo; align with `apps/trinkets/package.json:1` or add package -->
3. **Passive revenue** (bonus) -- AdSense monetization, cross-sell to FileFree/LaunchFree

All processing is browser-based (pdf-lib, heic2any, browser-image-compression, qrcode.js). Zero server cost. Zero backend. No auth required. Cross-sell CTAs funnel traffic to FileFree/LaunchFree.

### Trinket Factory pipeline

Instead of manually picking tools, the agent infrastructure discovers, specs, and builds them:

**Stage 1: DISCOVERY (GPT-5.4)**
Computer-use: browse competitor sites, analyze UX/pricing/SEO. + Gemini Flash for SEO keyword analysis. Output: 1-pager from `docs/templates/trinket-one-pager.md:1`. Human reviews, approves/rejects.

**Stage 2: SPEC (Claude Sonnet)**
Takes approved 1-pager as input. Writes precise PRD from `docs/templates/trinket-prd.md:1`. Human reviews, approves/rejects.

**Stage 3: BUILD (Claude Sonnet)**
Takes approved PRD + established pattern from first trinket. Generates code, creates PR for human review. 79.6% SWE-bench = best code quality.

### Trinkets domain and URLs

Stay on `tools.filefree.ai` subdomain. Do NOT buy individual domains per trinket.

**Rationale:**

- No domain purchase needed (we own filefree.ai)
- Subdomain inherits some authority from parent domain
- Individual domains start at DA 0 and cost $10-15/yr each
- At Year 1 trinkets revenue of $50-300, buying 15+ domains is negative ROI

**URL structure**: Use subdirectory-style paths for topical clustering:

- `tools.filefree.ai/calculators/mortgage`
- `tools.filefree.ai/calculators/compound-interest`
- `tools.filefree.ai/converters/pdf-to-word` (future)

**Graduation criteria**: If a single trinket exceeds 10K monthly visits, consider buying a standalone domain and 301-redirecting.

### First trinket: financial calculators

Pre-decided idea (agent validates, not selects). Includes:

- Mortgage calculator
- Compound interest calculator
- Savings goal calculator
- Budget planner

All client-side JavaScript. Zero API costs, zero server costs. Aligns with FileFree for cross-sell. Hosted on Vercel (app root `apps/trinkets/package.json:1`).

### Trinkets revenue outlook

| Period | Revenue | Notes |
|---|---|---|
| Year 1 | $50-300 | New domain, minimal traffic. SEO takes 6-12 months. |
| Year 2 | $5K-20K | Long-tail SEO begins compounding. Cross-sell conversions. |

**Market context**: iLovePDF (216M monthly visits, ~$4M/yr), SmallPDF (61M monthly visits, ~$11M/yr), PDF2Go (5-12M monthly visits, ~$670K/yr). These are established players with 10+ year head starts. Revenue projections are conservative.

---

## Studio (paperworklabs.com)

### Command center role

The command center is the control plane for the venture: it makes a small team plus agents workable day to day. Public `/`: minimal portfolio. Protected `/admin/*`: operations. Public `/docs/*`: readable company documentation. API aggregation and caching live in `apps/studio/src/lib/command-center.ts:2` (`cached`).

### Admin page tiers

**Tier 1 -- Build First (enables daily operations):**

| Page | Route | Purpose | Data Sources |
|---|---|---|---|
| Company Landing | `/` (public) | Portfolio page: company name, one-liner, product cards, team section, legal footer | Static |
| Admin Auth | `/admin/*` (protected) | Google OAuth, admin email allowlist gate | `ADMIN_EMAILS` env var |
| Mission Control | `/admin` | Activity feed (live terminal-style log), summary cards, quick links | n8n + Render + Vercel + Hetzner + Stripe + PostHog APIs |
| Agent Monitor | `/admin/agents` | n8n workflow status, execution history, failure alerts | n8n API |
| Infrastructure Health | `/admin/infrastructure` | Render, Vercel, Hetzner, Neon, Upstash status and resource usage | Provider APIs |

**Tier 2 -- Build Next (enables growth operations):**

| Page | Route | Purpose | Data Sources |
|---|---|---|---|
| Analytics | `/admin/analytics` | PostHog dashboard embeds, key metrics, per-product breakdown | PostHog API |
| Support Inbox | `/admin/support` | All support conversations, AI response drafts, human overrides | PostgreSQL (Hetzner) |
| Social Media Command | `/admin/social` | Scheduled posts, approve/reject drafts, performance metrics | Postiz API |
| State Data Observatory | `/admin/data` | 50-state freshness indicators, last verified dates, change history | `packages/data/package.json:1` workspace JSON + n8n validator |

**Tier 3 -- Build When Revenue Flows:**

| Page | Route | Purpose | Data Sources |
|---|---|---|---|
| Revenue Intelligence | `/admin/revenue` | Stripe revenue by product/stream, affiliate revenue, MRR/churn/ARPU, spend overview | Stripe API + affiliate dashboards |
| Campaign Control | `/admin/campaigns` | Create/manage cross-sell campaigns, targeting, performance | Campaign tables in studio DB |
| User Intelligence | `/admin/users` | Venture identity browser, segments, cross-product journey visualization | Venture identity DB |

### Public docs viewer (`/docs/*`)

- Renders company docs from the git repo as clean, readable HTML pages
- Pages: Master Plan, Financials, Knowledge Base, Tasks, AI Model Registry
- Uses `react-markdown` or `next-mdx-remote` to render markdown fetched from GitHub API
- Clean typography, table styling, anchor links for section navigation
- Responsive and mobile-friendly -- designed for non-technical readers (founder shares `paperworklabs.com/docs/financials` with wife)
- No GitHub account needed to read
- Cached with React Query (staleTime: 5 min)
- Table of contents sidebar generated from markdown headings

---

## Brain (brain.paperworklabs.com)

**Technical spec** (canonical): `docs/BRAIN_ARCHITECTURE.md:1` <!-- STALE 2026-04-24: “lines / decisions / findings” marketing counts drift as the spec grows — confirm in doc, not in PRD -->

### Problem

Consumer products (FileFree, LaunchFree, Distill) stay narrow; a durable company needs a **memory** layer and proactive surface that is not a one-off tax or LLC flow. The Brain is that umbrella: one user model that improves across time.

### Users

- **Phase 11-alpha:** Two founders, internal
- **Phase 11-beta:** Early consumers willing to connect accounts for proactive value
- **Phase 11-full:** Mainstream consumers, couples/family circles, mobile
- _TODO: segment assumptions for Brain GTM (see BRAIN spec)_

### Scope

- Channel-agnostic “life intelligence”: finances, routine, travel, health-adjacent signals where users opt in
- “Skills” for FileFree, LaunchFree, and Distill sit inside the Brain mental model, not the other way around
- Proactive delivery as primary; chat is secondary; memory and the Brain Fill narrative as retention levers
- _TODO: pin scope to a concrete v1 feature list in `docs/BRAIN_ARCHITECTURE.md:1`_

### Non-goals

- A generic chatbot with no memory guarantee
- Registered investment or tax advice; regulated outputs stay in product-specific guardrails
- _TODO: fill from BRAIN legal/compliance section when locked_

### Success metric

_TODO: pull North Star + retention + Brain Fill metrics from `docs/BRAIN_ARCHITECTURE.md:1` into a single table here._

### Strategic anchors (design record)

- **D49 — Memory moat:** Accumulated life context is the switching cost; by ~day 90 the system should infer broad lifestyle class without a quiz
- **D51 — Brain Fill meter:** A visible, gamified progress construct for data completeness
- **D52 — Tiered email processing:** Inexpensive entry path; “we never read your emails” metadata tier
- **D58 — Life intelligence:** Intentional parity of ambition across life domains, not only finance
- **D60 — Proactive-primary:** Pushes to users from multiple channels; chat stays capped (100 msg/mo on free in current pricing)
- **D59 — Revenue model:** Subscription + referrals + lifestyle commerce at scale (see master plan, not re-derived here)

### Phased delivery

- **11-alpha (internal):** Copilot for founders; Slack; venture context
- **11-beta (consumer foundation):** Google OAuth, Gmail/Calendar/Maps signals, Brain Fill v1, proactive nudges
- **11-full (product):** Expo app, Plaid, circles, generative UI, referral loop

### Brain pricing (policy)

| Tier | Price Y1 | Price Y2+ | Limits | Memory |
|------|---------|----------|--------|--------|
| Free | $0 | $0 | 100 msg/mo, 2 connections | 1 year |
| Personal | $29/yr | $49/yr | Unlimited msg, 10 connections | 5 years |
| Together | $49/yr | $79/yr | Couples + Circle | Lifetime |
| Family | $79/yr | $129/yr | Up to 5 + kid profiles | Lifetime |

### Brain competitive positioning (consumer)

Origin ($15/mo) does finance only. Brain does finance + lifestyle + email + calendar + location + couples. Origin has 2 of 7 capabilities. Brain has all 7, starting at $0. brain.ai ($51.5M raised) went horizontal with no moat; we go vertical-first with genuine switching cost.

---

## Revenue model

Full revenue model: `docs/VENTURE_MASTER_PLAN.md:1` Section 1.

### FileFree revenue

Free filing = acquisition; refund moment = monetization. Streams: refund routing ($50-100/funded), referrals ($50-200), Audit Shield ($19-29/yr), Tax Optimization Plan ($29/yr).

### LaunchFree revenue

RA credits, banking/payroll referrals, Compliance SaaS ($49-99/yr). H2 2026: $7.9K–$114K range by scenario.

### Distill revenue

CPA SaaS ($49–199/mo tiers), Formation API ($20-40/filing). Y1: $28K–119K; Y2: $119K–464K.

### Combined year 1 projections

| Scenario | LaunchFree (H2 2026) | FileFree (Jan-Apr 2027) | **Total** |
|---|---|---|---|
| **Pessimistic** | $7.9K | $7K | **$14.9K** |
| Moderate | $34.5K | $29K | **$63.5K** |
| Aggressive | $114K | $150K | **$264K** |

**Why the pessimistic scenario matters**: It models 5K filers, 1K formations, bottom-tier attach rates, and self-serve affiliates only (no Founder 2 deals closed). At $14.9K Year 1 revenue, the venture survives ($278/mo burn) but takes longer to reach meaningful revenue. The compliance SaaS revenue is recurring and compounds year over year.

### Unit economics

**Cost per user (verified, v6.0 -- Cloud Vision + GPT pipeline):**

| Component | Cost | Source |
|---|---|---|
| GCP Cloud Vision OCR | $0.002 | $0.0015/page, first 1K pages/mo free |
| GPT-4o-mini field mapping (structured) | $0.001 | ~1500 tokens structured output per doc |
| GPT-4o vision fallback (~10% of docs) | $0.002 | $0.02/doc x 10% escalation rate |
| GPT-4o insights generation | $0.040 | $2.50/M input, ~3K in + 2K out |
| GCP Cloud Storage (24 hours) | $0.001 | Negligible |
| Vercel Hobby (amortized) | $0.000 | $0/mo (free tier) |
| Render Starter (amortized) | $0.004 | $7/mo / 2000 users |
| **Total per user** | **$0.050** | |

**Blended ARPU (Scenario B, moderate):** $8.05
**Gross margin:** 99.3%
**LTV (5-year, 80% retention):** $8.05 x 3.36 = $27.05
**Maximum sustainable CAC:** $27.05 / 3 = $9.02

Version history: v1.0 was $3.30/user (AWS Textract). v6.0 is $0.050/user (Cloud Vision + Render Starter) -- a 66x cost reduction through architectural decisions.

### Plan B: zero partnerships closed

If Founder 2 closes no deals, most fintech affiliate programs are self-serve (apply online, no calls):

| Program | Platform | Commission |
|---|---|---|
| Betterment (HYSA/investing) | Impact.com | $25-$1,250 per referral |
| SoFi (banking/investing) | Impact.com | $50-$100 per funded account |
| Wealthfront (HYSA/investing) | Direct | $30-$75 per funded account |
| Ally Bank (HYSA/savings) | CJ Affiliate | $5-$12 per signup |
| Robinhood (investing) | Impact.com | $5-$20 per funded account |
| Chime (banking) | CJ Affiliate | $10-$50 per direct deposit |
| Acorns (micro-investing) | CJ Affiliate | $5-$10 per signup |

**Plan B Year 1 revenue: $6.5K-37K.** Survivable at $278/mo burn. Founder 2 raises the ceiling (premium partnership terms, co-marketing deals), but does NOT set the floor.

### Partnership milestones

| Milestone | Owner | Deadline | Consequence If Missed |
|---|---|---|---|
| Submit self-serve affiliate apps (Betterment, Wealthfront, SoFi) | Founder 1 | April 2026 | Delays referral revenue by 1-2 weeks |
| Book Column Tax demo call | Founder 2 | May 2026 | No interim e-file for October extension season |
| Column Tax sandbox access | Founder 2 | June 2026 | Cannot test e-file integration; fallback = PDF only |
| RA wholesale partner signed (CorpNet or equivalent) | Founder 2 | July 2026 | Launch LaunchFree without RA service |
| TaxAudit/audit shield partnership | Founder 2 | September 2026 | Launch FileFree without audit shield |
| At least 1 banking partner confirmed | Either | October 2026 | Refund routing not available for first tax season |

See `docs/PARTNERSHIPS.md:1` for the complete playbook including partner hit list, outreach templates, and partnership lifecycle.

---

## Architecture

### Monorepo structure (pnpm workspaces)

```
venture/
  apps/
    filefree/            (filefree.ai -- Next.js, consumer tax filing)
    distill/             (distill.tax -- Next.js, B2B compliance automation, Phase 9)
    launchfree/          (launchfree.ai -- Next.js, LLC formation)
    studio/              (paperworklabs.com -- Next.js, command center + portfolio)
    trinkets/            (tools.filefree.ai -- Next.js SSG, utility tools)
  packages/
    ui/                  (22 shadcn components + 4 brand themes + chat widget)
    auth/                (shared auth: hooks, middleware, session)
    analytics/           (PostHog + attribution + PII scrubbing)
    data/                (50-state formation + tax JSON configs, Zod schemas, state engine)
    tax-engine/          (tax calculation, form generators, MeF XML schemas, reconciliation)
    document-processing/ (OCR pipeline client, field extraction schemas, bulk upload queue)
    filing-engine/       (State Filing Engine: portal automation, state APIs, Stripe Issuing)
    intelligence/        (financial profile, recommendations, experimentation, campaigns)
    email/               (shared email templates, React Email)
  apis/
    filefree/            (Python/FastAPI -- consumer + Distill B2B routes)
    launchfree/          (Python/FastAPI -- formation service)
    studio/              (Python/FastAPI -- command center aggregator)
  infra/
    compose.dev.yaml
    hetzner/
    env.dev.example
  docs/
    VENTURE_MASTER_PLAN.md
    PRD.md (this document)
    TASKS.md
    FINANCIALS.md
    PARTNERSHIPS.md
    AI_MODEL_REGISTRY.md
    KNOWLEDGE.md
    templates/
  pnpm-workspace.yaml
  package.json
  Makefile
  render.yaml
```

### Technology stack

**Frontend:**

- Next.js 14+ (App Router), TypeScript (strict mode)
- shadcn/ui (Radix primitives + Tailwind -- copy-paste, we own the code)
- Tailwind CSS 4+, Framer Motion
- Vercel AI SDK (`ai` + `@ai-sdk/react`) for streaming AI insights
- Recharts, Lucide React, React Hook Form + Zod
- @tanstack/react-query (server state), Zustand (minimal client state)
- @react-pdf/renderer (1040 PDF generation)

**Backend:**

- FastAPI (Python 3.11+), SQLAlchemy 2.0 (async), asyncpg
- PostgreSQL 15+ (Neon serverless), Redis (Upstash serverless)
- Alembic (migrations), Pydantic v2 (schemas)
- FastAPI BackgroundTasks (MVP), Celery with Redis broker (at scale)

**AI/ML Pipeline -- Tiered OCR:**

1. Preprocessing (Pillow): auto-rotate EXIF, contrast normalization, resize
2. Text Extraction (GCP Cloud Vision `DOCUMENT_TEXT_DETECTION`): $0.0015/page, 1K free/mo
3. SSN Isolation (local regex): SSN extracted via `\d{3}-?\d{2}-?\d{4}` ON OUR SERVER. NEVER sent to OpenAI. Masked with XXX-XX-XXXX in all downstream LLM calls.
4. Field Mapping -- Primary (GPT-4o-mini structured output): ~$0.001/doc
5. Field Mapping -- Fallback (GPT-4o vision): for <85% confidence, ~$0.02/doc
6. Post-validation: SSN format, EIN format, wage amounts numeric, cross-field consistency
7. Manual entry fallback: if both paths produce low-confidence results

**ALL monetary values in the tax engine are stored as integers (cents). No floats. Ever.**

### Federated identity

Each product owns its own user table in its own database. The venture layer adds SSO and cross-product intelligence on top, but is removable without breaking either product.

```
PRODUCT DATABASES (independent, can be separated):

  filefree DB:
    users: id, email, name, password_hash, ...filefree-specific fields...
           venture_identity_id (OPTIONAL, nullable FK)

  launchfree DB:
    users: id, email, name, password_hash, ...launchfree-specific fields...
           venture_identity_id (OPTIONAL, nullable FK)

VENTURE DATABASE (studio, never sold):

  venture_identities: id, email, name, created_at
  identity_products: venture_identity_id, product, product_user_id, first_used
  user_events: id, venture_identity_id, event_type, product, metadata, timestamp
  user_segments: venture_identity_id, segment, computed_at
```

If FileFree is acquired: remove the `venture_identity_id` column. FileFree still works independently.

### Authentication architecture

**Portfolio SSO (target — Clerk satellite topology):**

- **Primary Clerk host:** `accounts.paperworklabs.com` — Frontend API + embedded sign-in/sign-up (`apps/accounts/`, Track H4). See [`docs/infra/CLERK_SATELLITE_TOPOLOGY.md`](../docs/infra/CLERK_SATELLITE_TOPOLOGY.md).
- **Satellites:** `filefree.ai`, `launchfree.ai`, `distill.tax`, `tools.filefree.ai` (Trinkets), the public AxiomFolio Next.js hostname, and Studio on `paperworklabs.com` share one **production** Clerk instance; each satellite domain is registered in the Clerk Dashboard and configured in app code (`isSatellite`, `NEXT_PUBLIC_CLERK_DOMAIN`, primary `signInUrl` / `signUpUrl` pointing at `accounts.paperworklabs.com`).
- **Cross-brand behavior:** Apex brand domains sync sessions with the primary via Clerk’s satellite handoff (not a single shared cookie across unrelated domains). `paperworklabs.com` subdomains follow Clerk’s normal cross-subdomain session rules once DNS and allowlists are set.
- **Venture layer:** Per-product databases and `venture_identity_id` (above) remain the data model for cross-product intelligence; Clerk supplies the shared interactive login layer on top.

**User Auth (FileFree, LaunchFree, Distill, Trinkets, AxiomFolio Next):**

- Providers: Google OAuth + Apple Sign-In (cover 95%+ of users). Optional email/password fallback. Configured on the **converged** Clerk production instance.
- Implementation: `@clerk/nextjs` per app today; shared patterns may consolidate in `packages/auth` (Track C). Legacy FileFree / AxiomFolio session paths coexist during migration — see per-app [`docs/infra/CLERK_*.md`](../docs/infra/CLERK_FILEFREE.md) runbooks.

**Admin Auth (paperworklabs.com + admin panels):**

- Clerk + allowlist: middleware checks authenticated identity and `ADMIN_EMAILS` (and related operator gates) as documented in [`docs/infra/CLERK_STUDIO.md`](../docs/infra/CLERK_STUDIO.md).

**Trinkets (`tools.filefree.ai`):**

- Clerk satellite for interactive SSO where needed; the surface remains mostly public utilities. Cross-sell CTAs may deep-link into FileFree/LaunchFree.

### Brand architecture

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

HOLDING COMPANY:
  paperworklabs.com ... Corporate site, portfolio, command center
```

Consumer brands attract users with free products. Revenue comes from upsells and referrals. Distill monetizes the same infrastructure as B2B APIs and SaaS. Paperwork Labs ties it all together as the infrastructure company. This follows the Stripe model (one B2B brand, multiple product lines) rather than the Intuit model (separate brands per vertical).

### Brand palettes

**FileFree** (Tax / Trust / Calm): Violet-Indigo
- Primary: `#4F46E5` (Indigo 600)
- Gradient: `#8B5CF6` -> `#9333EA` (Violet 500 -> Purple 600)
- Background: `#020817` (Slate 950)

**LaunchFree** (Business Formation / Energy / Action): Teal-Cyan
- Primary: `#0D9488` (Teal 600)
- Gradient: `#14B8A6` -> `#06B6D4` (Teal 400 -> Cyan 500)
- Background: `#0A0F1A` (deep navy)

**Studio/Command Center** (Internal / Data / Ops): Zinc-Neutral
- Primary: `#71717A` (Zinc 500)
- Background: `#09090B` (Zinc 950)

**Distill** (B2B / Professional / Precision): Deep Blue-Slate
- Primary: `#2563EB` (Blue 600)
- Gradient: `#3B82F6` -> `#1E40AF` (Blue 500 -> Blue 800)
- Background: `#0F172A` (Slate 900)

**Trinkets / Tools** (Utility / Approachable / Helpful): Amber-Orange
- Primary: `#F59E0B` (Amber 500)
- Gradient: `#F59E0B` -> `#EA580C` (Amber 500 -> Orange 600)
- Background: `#0C0A09` (Stone 950)

**All products:** Inter + JetBrains Mono typography. Dark mode by default.

Implementation: CSS `[data-theme]` selectors in `packages/ui/src/themes.css:10` (FileFree theme block). Each app sets its theme on `<body data-theme="...">`.

### Infrastructure

| Service | Provider | Cost | Purpose |
|---|---|---|---|
| Frontend (5 apps) | Vercel | Free (Hobby) -> $20/mo (Pro at 5 apps) | Next.js hosting |
| Backend (FileFree API) | Render | $7/mo (Starter, 512MB) | FastAPI |
| Backend (LaunchFree API) | Render | $7/mo (Starter) | FastAPI |
| Database | Neon | Free tier (0.5 GB, 190 compute hrs) | PostgreSQL |
| Sessions | Upstash | Free tier (500K commands/mo) | Redis |
| File Storage | GCP Cloud Storage | Negligible | Encrypted, 24hr auto-delete |
| OCR | GCP Cloud Vision | 1K free pages/mo, then $0.0015/page | Text extraction |
| Automation | Hetzner CX33 | $6/mo | n8n + Postiz + Redis + PostgreSQL |
| Payment Orchestration | Stripe Issuing | Per Stripe schedule | Virtual cards for state filing fee payment |
| Portal Automation | Render (or dedicated worker) | $7/mo | Playwright workers for state portal automation |
| DNS/Domains | Various | ~$20/mo amortized | filefree.ai, launchfree.ai, distill.tax, paperworklabs.com |

**Port Map (Local Development):**

| Service | Port |
|---|---|
| apps/filefree | 3001 |
| apps/launchfree | 3002 |
| apps/trinkets | 3003 |
| apps/studio | 3004 |
| apps/distill | 3005 |
| apis/filefree | 8001 |
| apis/launchfree | 8002 |
| apis/studio | 8003 |
| PostgreSQL | 5432 |
| Redis | 6379 |

### Production reliability

**Idempotency Keys:** Every state-changing financial operation requires a client-generated idempotency key. Backend stores key + result in Redis (TTL 24hr). Prevents double-submits during tax deadline surge. Pattern: `X-Idempotency-Key` header on all `POST`/`PUT` to `/api/v1/filings/*`, `/api/v1/payments/*`, `/api/v1/submissions/*`.

**Circuit Breakers:** Every external service call wrapped in `pybreaker`. Degradation per service:

| Service | Degradation When Open |
|---|---|
| Cloud Vision OCR | Queue image in Redis, return "processing" status, retry via background task |
| OpenAI GPT | Fall back to rule-based field mapping (regex + position heuristics) |
| IRS MeF Transmitter | Queue submission in PostgreSQL, show "Submitted, awaiting IRS confirmation" |
| Column Tax API | Fall back to PDF download |
| Affiliate Tracking | Log event locally, reconcile later |

**Tax Calculation Reconciliation:** Dual-path verification for every return. Path A (forward calculation) vs Path B (reverse from refund). If delta exceeds $1 tolerance, flag for manual review. Nightly batch re-runs all day's calculations.

**Observability:** OpenTelemetry SDK + Grafana Cloud free tier (50GB traces/mo). Distributed tracing across the full OCR-to-filing pipeline. Alerting: p99 > 60s, error rate > 1%, reconciliation failure > 0.1%.

**Load Testing:** k6 scripts for 4 tax season scenarios (steady state, deadline surge, OCR bottleneck, soak test). Performance budget: p95 < 30s, p99 < 60s, zero data loss, error rate < 0.1% at 10x load.

---

## Data models

### FileFree models

**Key points:** `User` and `Filing` anchor the core flow; `Document` and `TaxProfile` hold encrypted PII; `TaxCalculation` stores cent-based money fields; `Submission` and `Waitlist` cover MeF and acquisition.

**User:**
- id: UUID
- email: string (unique, indexed)
- password_hash: string
- full_name_encrypted: string
- referral_code: string (unique)
- referred_by: FK -> User (nullable)
- role: enum (user, admin)
- advisor_tier: enum (free, premium) -- default: free
- venture_identity_id: UUID (nullable FK)
- created_at, updated_at: timestamp

**Filing:**
- id: UUID
- user_id: FK -> User
- tax_year: integer
- filing_status: enum (single, married_joint, married_separate, head_of_household)
- status: enum (draft, documents_uploaded, data_confirmed, calculated, review, submitted, accepted, rejected)
- created_at, updated_at, submitted_at: timestamp

**Document:**
- id: UUID
- filing_id: FK -> Filing
- document_type: enum (w2, drivers_license, 1099_misc, 1099_nec, 1099_int, 1099_div)
- storage_key: string (encrypted)
- extraction_status: enum (pending, processing, completed, failed)
- extraction_data: JSONB (encrypted)
- confidence_scores: JSONB
- created_at, processed_at: timestamp

**TaxProfile:**
- id: UUID
- filing_id: FK -> Filing (unique)
- ssn_encrypted, full_name_encrypted, address_encrypted, date_of_birth_encrypted: string/JSONB
- total_wages, total_federal_withheld, total_state_withheld: integer (cents)
- state: string
- created_at: timestamp

**TaxCalculation:**
- id: UUID
- filing_id: FK -> Filing (unique)
- adjusted_gross_income, standard_deduction, taxable_income, federal_tax, state_tax, total_withheld, refund_amount, owed_amount: integer (cents)
- ai_insights: JSONB
- calculated_at: timestamp

**Submission:**
- id: UUID
- filing_id: FK -> Filing (unique)
- transmitter_partner: string
- submission_id_external: string
- irs_status: enum (submitted, accepted, rejected)
- rejection_codes: JSONB (nullable)
- submitted_at, status_updated_at: timestamp

**Waitlist:**
- id: UUID
- email: string (unique)
- source: string (landing, referral, social)
- created_at: timestamp

### LaunchFree models

**Formation:**
- id: UUID
- user_id: FK -> User
- state_code: string (2-char)
- entity_type: enum (llc, corporation, nonprofit)
- entity_name: string
- filing_method: enum (api, portal, mail)
- status: enum (draft, documents_prepared, submitting, submitted, confirmed, approved, rejected, failed)
- total_cost_cents: integer
- created_at, updated_at, submitted_at: timestamp

**StateConfig:**
- state_code: string (primary key)
- state_name: string
- formation_data: JSONB (from per-state files such as `packages/data/src/formation/CA.json:1`)
- tax_data: JSONB (from per-year/state files such as `packages/data/src/tax/2026/CA.json:1`)
- last_verified: date
- last_verified_source: string

**FilingSubmission:**
- id: UUID
- formation_id: FK -> Formation
- state_code: string (2-char)
- tier: enum (api, portal, mail)
- status: enum (pending, submitting, submitted, confirmed, failed)
- filing_number: string (nullable, from state confirmation)
- submitted_at: timestamp (nullable)
- confirmed_at: timestamp (nullable)
- screenshots: JSONB (array of screenshot URLs for portal automation audit trail)
- error_log: text (nullable)
- retry_count: integer (default 0)
- created_at, updated_at: timestamp

**StatePortalConfig:**
- state_code: string (primary key)
- portal_url: string
- filing_method_tier: enum (api, portal, mail)
- field_mappings: JSONB (per-state form field selectors + mapping)
- fee_schedule: JSONB (entity type -> fee amount)
- captcha_type: string (nullable -- none, recaptcha, hcaptcha, custom)
- ra_login_path: string (nullable -- RA-specific filing portal URL)
- last_health_check: timestamp
- health_status: enum (healthy, degraded, down)

**ComplianceCalendar:**
- id: UUID
- formation_id: FK -> Formation
- state_code: string
- requirement_type: enum (annual_report, franchise_tax, statement_of_info)
- due_date: date
- status: enum (upcoming, reminded, completed, overdue)
- reminder_sent_at: timestamp (nullable)

### Distill models

**Firm:**
- id: UUID
- name: string
- tax_software: enum (ultratax, drake, proconnect, lacerte, other)
- stripe_customer_id: string
- plan: enum (solo, team, firm)
- created_at: timestamp

**FirmMember:**
- id: UUID
- firm_id: FK -> Firm
- email: string
- role: enum (admin, preparer, reviewer)
- created_at: timestamp

**FirmClient:**
- id: UUID
- firm_id: FK -> Firm
- name_encrypted: string
- ssn_encrypted: string
- status: enum (active, archived)
- created_at: timestamp

**AuditLog:**
- id: UUID
- firm_id: FK -> Firm
- user_id: FK -> FirmMember
- action: enum (extraction, edit, export, submission)
- entity_type: string
- entity_id: UUID
- details: JSONB
- timestamp: timestamp (immutable, 7yr retention)

### Venture identity

**VentureIdentity:**
- id: UUID
- email: string (unique)
- name: string
- created_at: timestamp

**IdentityProduct:**
- venture_identity_id: FK -> VentureIdentity
- product: enum (filefree, launchfree, trinkets, distill)
- product_user_id: UUID
- first_used: timestamp

**UserEvent:**
- id: UUID
- venture_identity_id: FK -> VentureIdentity
- event_type: string (from event taxonomy — see `docs/VENTURE_MASTER_PLAN.md:1` Section 4C)
- product: enum
- metadata: JSONB
- timestamp: timestamp (immutable, append-only)

**UserSegment:**
- venture_identity_id: FK -> VentureIdentity
- segment: string
- computed_at: timestamp

### Marketplace tables

**PartnerProduct:**
- id: UUID
- partner_id, partner_name: string
- product_type: enum (hysa, ira, credit_card, loan, insurance, payroll)
- product_name: string
- affiliate_network: enum (impact, cj, direct, api)
- affiliate_link: string
- commission_type: enum (cpa, cps, rev_share)
- commission_amount_cents: integer
- min_credit_score, max_credit_score: integer (nullable)
- min_income_cents: integer (nullable)
- states_available: string[] (nullable = all states)
- status: enum (active, paused, archived)
- cpa_bid_cents: integer (nullable, Stage 3+)
- created_at, updated_at: timestamp

**FitScore:**
- id: UUID
- venture_identity_id: FK -> VentureIdentity
- partner_product_id: FK -> PartnerProduct
- score: integer (0-100)
- score_version: integer
- scoring_method: enum (static, rules, bandit, ml)
- factors_json: JSONB (field NAMES + weights only, NEVER raw values)
- computed_at: timestamp

**Recommendation:**
- id: UUID
- venture_identity_id: FK -> VentureIdentity
- partner_product_id: FK -> PartnerProduct
- fit_score: integer
- rank_position: integer
- placement: enum (refund_plan, dashboard, email, in_app)
- scoring_method: string
- status: enum (shown, clicked, converted, dismissed)
- created_at: timestamp

**RecommendationOutcome:**
- id: UUID
- recommendation_id: FK -> Recommendation
- outcome_type: enum (click, signup, funded, retained_30d)
- revenue_cents: integer
- partner_reported_approval: boolean (nullable, Stage 2+)
- partner_reported_funded_amount_cents: integer (nullable, Stage 2+)
- timestamp: timestamp

### Campaign engine

**Campaign:**
- id: UUID
- name: string
- segment_target: string
- message_template: string
- channel: enum (email, in_app_notification, in_app_card)
- status: enum (draft, active, paused, completed)
- schedule: JSONB
- created_at: timestamp

**CampaignEvent:**
- id: UUID
- campaign_id: FK -> Campaign
- venture_identity_id: FK -> VentureIdentity
- event_type: enum (sent, opened, clicked, converted, unsubscribed)
- timestamp: timestamp

---

## API design

### FileFree API

All endpoints return `{ success: boolean, data: T, error?: string }`. Auth via HTTP-only secure cookies with SameSite=Lax + CSRF tokens. API prefix: `/api/v1/`.

**Auth:**
- `POST /api/v1/auth/register` -- hCaptcha verified
- `POST /api/v1/auth/login` -- set session cookie
- `POST /api/v1/auth/logout` -- clear session
- `GET /api/v1/auth/me` -- current user
- `DELETE /api/v1/auth/account` -- delete all data (CCPA cascade)

**Filings:**
- `POST /api/v1/filings` -- create
- `GET /api/v1/filings` -- list
- `GET /api/v1/filings/{id}` -- detail
- `PATCH /api/v1/filings/{id}` -- update

**Documents:**
- `POST /api/v1/documents/upload` -- authenticated upload
- `GET /api/v1/documents/{id}/status` -- poll extraction
- `GET /api/v1/documents/{id}/data` -- extraction data
- `PATCH /api/v1/documents/{id}/data` -- user corrections
- `POST /api/v1/documents/demo-upload` -- anonymous try-before-signup (rate limited)

**Tax:**
- `GET /api/v1/filings/{id}/profile` -- tax profile
- `PUT /api/v1/filings/{id}/profile` -- update profile
- `POST /api/v1/filings/{id}/calculate` -- trigger calculation
- `GET /api/v1/filings/{id}/calculation` -- results
- `GET /api/v1/filings/{id}/pdf` -- download 1040 PDF

**Waitlist:**
- `POST /api/v1/waitlist` -- join waitlist

**Submission (October 2026+):**
- `POST /api/v1/filings/{id}/submit` -- e-file via partner
- `GET /api/v1/filings/{id}/submission` -- status

**Rate Limits:** 5 req/min auth, 20 req/min upload, 5 uploads/day/user.

### LaunchFree API

**Formations:**
- `POST /api/v1/formations` -- create formation
- `GET /api/v1/formations` -- list user's formations
- `GET /api/v1/formations/{id}` -- formation detail
- `PATCH /api/v1/formations/{id}` -- update formation
- `POST /api/v1/formations/{id}/generate-pdf` -- generate Articles of Organization PDF

**States:**
- `GET /api/v1/states` -- all states summary (fees, turnaround, entity types)
- `GET /api/v1/states/{code}` -- single state detail
- `GET /api/v1/states/{code}/name-check?name={query}` -- name availability check
- `POST /api/v1/states/compare` -- AI-powered multi-state comparison

**Compliance:**
- `GET /api/v1/compliance/{formation_id}` -- compliance calendar
- `POST /api/v1/compliance/{formation_id}/mark-complete` -- mark requirement complete
- `GET /api/v1/compliance/upcoming` -- upcoming deadlines across all formations

**Filing Engine (State Submission):**
- `POST /api/v1/formations/{id}/submit` -- trigger state filing via Filing Engine
- `GET /api/v1/formations/{id}/submission-status` -- check filing submission status
- `GET /api/v1/states/{code}/portal-health` -- state portal health check

### Distill API (`/api/v1/pro/*`)

All routes use firm-scoped middleware. `firm_id` injected from auth token.

- `POST /api/v1/pro/firms` -- register firm
- `POST /api/v1/pro/firms/{id}/members` -- invite team member
- `POST /api/v1/pro/clients` -- add client
- `GET /api/v1/pro/clients` -- list firm clients
- `POST /api/v1/pro/documents/bulk-upload` -- bulk document upload
- `GET /api/v1/pro/documents/{id}/extraction` -- extraction data
- `PATCH /api/v1/pro/documents/{id}/extraction` -- preparer corrections
- `POST /api/v1/pro/export/{format}` -- export to UltraTax/Drake/ProConnect/Lacerte
- `GET /api/v1/pro/audit-log` -- immutable audit trail

**Formation API (Summer 2026):**
- `POST /api/v1/pro/formations` -- create + submit formation (B2B)
- `GET /api/v1/pro/formations/{id}` -- check formation status
- `GET /api/v1/pro/states` -- available states, fees, and processing times

**Partner API (Stage 3+):**
- `POST /api/v1/partners/products` -- submit product parameters
- `PUT /api/v1/partners/products/{id}/eligibility` -- set eligibility criteria
- `POST /api/v1/partners/bids` -- set CPA bids per segment
- `GET /api/v1/partners/segments` -- anonymized aggregate segment data
- `GET /api/v1/partners/funnel` -- partner conversion funnel

### Studio API

Aggregator backend for admin dashboard. All routes protected by admin allowlist.

- `GET /api/v1/admin/overview` -- summary cards (users, revenue, agents, uptime)
- `GET /api/v1/admin/agents` -- n8n workflow statuses
- `GET /api/v1/admin/infrastructure` -- provider health checks
- `GET /api/v1/admin/analytics` -- PostHog data proxy
- `GET /api/v1/admin/revenue` -- Stripe + affiliate revenue
- `GET /api/v1/admin/users` -- venture identity browser
- `POST /api/v1/admin/campaigns` -- create campaign
- `GET /api/v1/admin/compliance` -- compliance status indicators

---

## Legal and compliance

### Entity structure

**Now (pre-revenue):** Single California LLC (Paperwork Labs LLC) + DBA filings for "FileFree", "LaunchFree", and "Trinkets".

- California filing: $70
- DBA filing: ~$10-25 per name
- Franchise tax: $0 first year (exempt for new LLCs), $800/yr after
- RA: ~$49/yr
- Total year 1: ~$119-145

**At $50K+ combined revenue:** Convert to holding company structure. Parent LLC (Paperwork Labs LLC) stays as-is. Create FileFree LLC and LaunchFree LLC as subsidiaries with own bank accounts, EINs, and liability shields.

### Trademark framework

"FILEFREE" and "LAUNCHFREE" to be filed on USPTO Supplemental Register. Both marks are treated as **descriptive** in counsel’s current view, so Principal Register registration is difficult without five years of substantially exclusive commercial use.

| Mark | Classes | Register | Cost | Timeline |
|---|---|---|---|---|
| FILEFREE (stylized wordmark) | Class 036 (Financial), Class 042 (SaaS) | Supplemental | $350 x 2 = $700 | File after product launch (need specimen) |
| LAUNCHFREE (stylized wordmark) | Class 035 (Business formation), Class 042 (SaaS) | Supplemental | $350 x 2 = $700 | File after product launch |
| FILEFREE (logo/design mark) | Class 036, Class 042 | Supplemental | $350 x 2 = $700 | File with wordmark |
| **Total** | | | **~$2,100** | All within 90 days of launch |

**CRITICAL**: filefree.com is owned by Intuit (confirmed via WHOIS, registered since 1999 via MarkMonitor). NEVER reference filefree.com anywhere, ever.

### FTC “free” compliance

Our service IS actually free for ALL users. This is our strongest legal position.

"Filing is free. 100% of filers. 100% of the time. No income limits. No complexity limits for supported forms. No asterisks. No small print."

The moment we add a condition that makes filing not-free for some users, we are exposed to the exact FTC action that hit Intuit.

**LaunchFree "Free" rules:**
- NEVER use "Free LLC" as a standalone headline. Always: "Free LLC Formation Service" or "$0 Service Fee."
- State filing fees must appear in the same visual field as any "free" claim.
- RA credits: NEVER say "Free RA." Always: "RA starting at $49/yr. Earn credits to reduce your cost."

### Circular 230

We provide TAX EDUCATION, not TAX ADVICE. This distinction is legally critical.

Every screen, email, social post, or AI response that discusses tax topics must include: "This is general tax information, not tax advice. For advice specific to your situation, consult a qualified tax professional."

NEVER say "you should" + tax action. ALWAYS say "many filers in your situation" or "the standard deduction is typically..."

### UPL compliance

We provide BUSINESS FORMATION SERVICES, not LEGAL ADVICE.

NEVER say "you should form in Delaware" or "you need an operating agreement." ALWAYS say "many entrepreneurs choose Delaware because..." or "operating agreements are commonly used to..."

**Operating agreement model**: LaunchFree provides state-specific operating agreement TEMPLATES (pre-written by a licensed attorney, stored as PDFs). AI EXPLAINS clauses but does NOT select, modify, or draft clause language. Marketing: "Operating agreement template included" not "AI-generated operating agreement."

### Cross-sell consent (3-tier)

**Tier 1 -- Cross-Product Data Use:**
- Opt-in checkbox (unchecked by default) on every signup form
- "I consent to [LLC Name] using my information across FileFree, LaunchFree, and related services to send me product updates and recommendations. I can unsubscribe from any product at any time."
- Enables: cross-product email campaigns, segment identification, unified profile

**Tier 2 -- Personalized Product Matching:**
- Opt-in on Refund Plan screen AND user profile/settings page
- "Use my financial profile to show me personalized product recommendations from our partners"
- Users who consent see Fit Scores and matched products (marketplace experience)
- Users who don't consent see generic product listings (static affiliate links)
- Single consent covers all matching methods: rules-based, bandit, ML, partner-submitted models

**Tier 3 -- Anonymized Insights (Stage 3+):**
- Opt-in during credit score check or profile completion
- "Include my anonymized data in aggregate insights shared with financial product partners"
- No PII ever shared. Partners see only aggregate counts, demographics, predicted conversion rates

**Additional controls:**
- Global Privacy Control (GPC) signal detection: treat as opt-out for Tier 2 and Tier 3
- "Do Not Sell or Share My Personal Information" link in footer (preemptive CCPA)
- Per-product unsubscribe in email footer
- Consent audit trail: timestamp, IP, consent text version, consent tier stored per user

### PII data lifecycle (CCPA-first)

| Data Element | Product | Sensitivity | Storage | Encryption | Retention |
|---|---|---|---|---|---|
| SSN | FileFree | Critical | Neon DB (encrypted column) | AES-256, separate key | 7 years (IRS statute) |
| W-2 images | FileFree | Critical | GCP Cloud Storage | At-rest encryption | 24 hours (auto-delete) |
| Name, email, address | All | High | Neon DB | At-rest encryption | Until deletion request |
| Filing status, income | FileFree | High | Neon DB | At-rest encryption | 7 years |
| LLC owner info | LaunchFree | High | Neon DB | At-rest encryption | Indefinite (ongoing records) |
| Credit score | Future (Phase 1.5) | High | Neon DB (encrypted column) | AES-256, separate key | 2 years |
| Event/behavioral data | All | Low | PostHog + Neon | Standard | 3 years (anonymize after) |

**Deletion cascade** (account deletion endpoint available from day one):

1. Neon DB: soft-delete user, hard-delete PII after 30-day grace period
2. GCP Cloud Storage: delete remaining W-2 images
3. Upstash Redis: clear all session data
4. Venture identity: remove cross-product links
5. Credit score provider: request deletion via reseller API (if opted in)
6. PostHog: delete user profile (events retained anonymized)
7. Confirmation email sent to user
8. 30-day response window (CCPA requirement)

### Legal protection checklist

| Item | Status | Deadline | Notes |
|---|---|---|---|
| E&O + Cyber liability insurance ($1M) | NOT DONE | Before first SSN | $1,500-3,000/yr. Non-negotiable. |
| Data breach response plan (SANS template) | NOT DONE | Before first SSN | 2-page doc: discovery, containment, notification, remediation |
| Terms of Service (attorney-reviewed) | NOT DONE | Before launch | Limitation of liability, arbitration, data accuracy disclaimer |
| Privacy Policy (CCPA + state laws) | NOT DONE | Before launch | Data collection, retention, sharing, deletion rights |
| Tax filing disclaimer (Circular 230) | NOT DONE | Before launch | On every screen that touches tax data |
| LLC formation disclaimer (UPL) | NOT DONE | Before launch | On every LaunchFree page |
| Startup attorney consultation | NOT DONE | Before Phase 3 | 1 hour, ~$300-500. Key: UPL for AI formation guidance, RA liability |

**Our approach**: Follow FreeTaxUSA model for tax (accuracy guarantee capped at $10K, covers OUR calculation errors only). Follow LegalZoom model for LLC (templates, not drafting). Get E&O insurance before collecting any data.

---

## Content and distribution

**SEO:** FileFree: "how to file taxes for free", "first time filing taxes", "tax refund calculator" — 3-5 guides at launch, FAQ schema, "First Time Filing" hub. LaunchFree: "free LLC formation", "cheapest state for LLC", 50 state landing pages.

**Social:** TikTok + IG Reels + YouTube Shorts + X. Faceless AI content daily + weekly founder video. 7-10 posts/week tax season (FileFree), 3-5/week year-round (LaunchFree). n8n pipeline: trend research → script/image/voice → Postiz → founder review (5 min/day). ~$3/mo for 30 videos.

**Paid ($200-500/mo tax season):** TikTok Spark Ads primary, Meta Boost secondary. Only boost organically validated posts. Kill: TikTok CPC >$0.50, Meta CPC >$1.00. Off-season: $0.

**Viral loops:** Tax receipt card (FileFree, 15% share target), LLC celebration certificate (LaunchFree), referral program, try-before-signup, comparison calculator (Trinket).

**Content Review Gate (mandatory):** Circular 230, UPL, FTC, CAN-SPAM, brand verification. First 30 days: manual review. After: pre-approved templates can auto-publish.

---

## Program timeline

| Phase | Description | Target | Hard? |
|---|---|---|---|
| 0 | Infrastructure (domains, LLC, EFIN, legal) | Mar 2026 | — |
| 1 | Monorepo Restructure (pnpm, 5 apps, shared packages) | Apr 2026 | — |
| 1.5 | First Trinket + Agent Pipeline Test | Apr 2026 | — |
| 2 | 50-State Data Infrastructure | May 2026 | — |
| 3 | LaunchFree MVP (Filing Engine, Stripe, RA) | Jun-Jul 2026 | — |
| 4 | Command Center (Tier 1) | Jun 2026 | — |
| 5-6 | User Intelligence + Agent Restructure | Jul 2026 | — |
| 9 | Distill B2B Platform (parallel) | Jul-Aug 2026 | — |
| 7 | FileFree Season Prep (MeF XML, forms) | Oct 2026 | **YES** (IRS ATS) |
| 8 | FileFree Launch | Jan 2027 | **YES** (tax season) |
| 10 | Business Tax Filing (1065, 1120-S, K-1) | 2027-2028 | — |

**Critical path:** EFIN (first step) → ~45 days → ATS Oct 2026 → MeF Jan 2027. Phase 0→1→2→3→9 (parallel)→7→8.

**Hard deadlines:** Submit EFIN application as early as the calendar allows; MeF XML by Jun 2026 for Oct ATS; product live by late Jan 2027. Full phase details: `docs/VENTURE_MASTER_PLAN.md:1`. <!-- STALE 2026-04-24: EFIN/ATS dates are calendar-sensitive; re-read each quarter -->

---

## Related documents

- Strategy, valuation, marketplace, agent architecture: `docs/VENTURE_MASTER_PLAN.md:1`
- Product tasks and sprints: `docs/TASKS.md:1`
- Burn and revenue actuals: `docs/FINANCIALS.md:1`
- Partnership playbook: `docs/PARTNERSHIPS.md:1`
- Model routing: `docs/AI_MODEL_REGISTRY.md:1`
- Decisions and org memory: `docs/KNOWLEDGE.md:1`
