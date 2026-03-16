# Paperwork Labs -- Product Requirements Document

**Version**: 7.0
**Last Updated**: 2026-03-16
**Status**: Venture-Level PRD (supersedes FileFree-only v6.0)

---

## 1. Venture Overview

**Entity**: Paperwork Labs LLC (California). DBA filings for "FileFree", "LaunchFree", "Trinkets", and "Distill".

**Domain**: paperworklabs.com (holding company and command center).

**Monthly burn (real)**: ~$278/mo. Breakdown: Hetzner $6 + Render x2 $14 + Google Workspace $6 + domains ~$20 + OpenAI ~$10 + ElevenLabs $5 + cyber insurance ~$150 (est.) + CA franchise tax ~$67 (amortized). See FINANCIALS.md for full breakdown.

**Founding team**: Founder 1 (Product/Engineering) builds all products, OCR pipeline, tax calculations, and infrastructure. Founder 2 (Partnerships/Revenue) sources and closes financial product partnerships -- the primary revenue engine. AI personas (44 agents) assist both co-founders across all products.

**AI model strategy**: 9 models across 7 roles with quality-first routing. See AI_MODEL_REGISTRY.md and VENTURE_MASTER_PLAN.md Section 0E for the authoritative routing registry.

For deep strategy, valuation scenarios, marketplace evolution, and agent architecture, see VENTURE_MASTER_PLAN.md (source of truth for all strategic decisions).

### Products

| Product | Domain | Description | Target Launch | Status |
|---|---|---|---|---|
| FileFree | filefree.ai | Free AI-powered tax filing. W2 photo to completed 1040 in minutes. Year-round AI tax advisor. Revenue: refund routing, financial referrals, audit shield, Tax Optimization Plan. | January 2027 | In development |
| LaunchFree | launchfree.ai | Free LLC formation service ($0 service fee; user pays state filing fees only). AI-powered 50-state comparison. Revenue: RA credits, banking/payroll/insurance referrals, compliance SaaS. | Summer 2026 | In development |
| Distill | distill.tax | B2B compliance automation platform. Umbrella brand for tax, formation, and compliance APIs + CPA SaaS dashboard. Four lines: Distill for CPAs (SaaS), Distill Tax API, Distill Formation API, Distill Compliance API. ~80% shared tech per vertical. | Summer 2026 | Planned |
| Trinkets | tools.filefree.ai | Collection of utility tools (financial calculators, converters, generators). Revenue: AdSense + cross-sell to main products. | Phase 1.5 | Planned |
| Studio / Command Center | paperworklabs.com | Venture command center, admin dashboard, agent monitor, docs viewer. Public portfolio page + authenticated `/admin/` panel. | Phase 4 | Planned |

---

## 2. Product 1: FileFree (filefree.ai)

### 2.1 Problem Statement

~166M individual tax returns are filed annually in the US. ~70% of filers have simple tax situations (W2 income, standard deduction), yet they pay $0-$170+ to TurboTax or spend hours at H&R Block for what should be a 5-minute process. The IRS killed its free Direct File program for 2026. TurboTax faces active lawsuits for selling user data and deceptive pricing. 67% of Gen Z are stressed about filing. 40% have cried over it. The system is broken, and the alternatives are disappearing.

But the bigger problem is upstream: filing your first tax return is the first real interaction most young Americans have with the financial system, and the experience is so traumatic that it creates lasting anxiety about all financial decisions. No one is building for this moment.

### 2.2 Solution

FileFree is a mobile-first web application that starts as free, AI-powered tax preparation -- snap a W2, get your completed return in minutes. But the real product is what comes next: a year-round AI tax advisor that helps Gen Z make smarter financial decisions, starting from the trust earned during that first filing.

**Phase 1 (2026):** Free tax prep -- W2 photo to completed 1040 PDF in under 5 minutes. Tiered OCR pipeline (GCP Cloud Vision + GPT). E-file via partner at cost while our own IRS transmitter is certified.

**Phase 2 (2027):** Free e-file via own IRS MeF transmitter (NORTH STAR) + Tax Optimization Plan ($29/yr) + financial product marketplace.

**Phase 3 (2028):** Embedded tax engine (B2B API) for fintechs, payroll providers, and neobanks.

### 2.3 Target User (MVP)

- Age 18-30 (Gen Z, especially first-time and early-career filers)
- Single filer OR Married filing jointly
- W2 income only (1-3 W2s)
- Standard deduction (no itemizing)
- No dependents (MVP), add dependents in v1.1
- No investment income, rental income, or self-employment (MVP)
- US resident, single state

### 2.4 Why This User -- The Data

- 67% of Gen Z report stress about filing taxes (vs 57% all Americans) -- Stagwell 2026
- 62% of Gen Z say tax season is their #1 financial stressor -- AOL/Yahoo Finance
- 52% fear making errors; only 33% feel confident filing correctly
- 45% say filing negatively impacts their mental health
- 55% consider filing taxes "one of the hardest parts of adulting"
- 44% have already used AI for tax help (vs 4% of Boomers) -- Stagwell 2026
- 70% would consider using AI-based tax prep -- Stagwell 2026
- 40% procrastinate until the last minute; 50%+ had unfiled returns 3 days after April 15
- 50% of Gen Z have faced IRS fees, penalties, or collections -- LendEDU
- 80% of tax software users stick with the same program year after year -- PCMag

That last stat is the business case: whoever captures a 22-year-old owns their tax relationship for a decade.

### 2.5 Competitive Landscape

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

### 2.6 The april Threat

april raised $78M ($38M Series B in July 2025). They are the first new company in 15+ years to achieve national e-file coverage in all 50 states. They're embedded in Chime, Gusto, and 30+ fintech platforms. They show users only 36 screens for federal + state combined. 60+ NPS.

**Why april doesn't kill us:** april is B2B2C -- they're an API that other companies embed. They don't have a consumer brand. They don't show up when someone Googles "file taxes free." We're B2C. Different distribution, different positioning. A user who opens the App Store or Google looking for "free tax filing" will never find april.

**What we can learn from april:** Their 36-screen flow proves "ask only what's needed" works. Their success validates the market. Their embedded model is our Phase 3 -- we should build toward B2B API as a revenue diversification play.

**E-file note:** We're building our own IRS MeF transmitter (NORTH STAR). Column Tax is our interim e-file partner (October 2026) at cost-passthrough while we complete IRS certification.

### 2.7 Honest Moat Assessment

**What is NOT a moat (but IS a differentiator):**

- Emotional design / anxiety-focused UX -- any well-funded competitor can hire good designers. This buys 6-12 months, not permanent advantage.
- Speed -- april already does 36 screens. Speed is compressible. But incumbents can't strip down without losing revenue from complex filers.
- "Privacy-first" claims -- any startup can say this. Proving it requires time and track record.

**What IS defensible:**

**Moat 1: First-Filer Lock-In (STRUCTURAL)**
80% annual retention means whoever captures a 22-year-old filing their first return owns that customer for ~10 years. With ~4M Americans turning 22 each year, the first-filer market is ~4M/year. If we capture 5% of first-time filers, that's 200K users/year with 80% retention -- compounding to 670K active users by year 5 without any other acquisition.

**Moat 2: Trust-to-Advisory Pipeline (RELATIONSHIP)**
Free filing earns trust. Trust enables financial advisory. Advisory creates ongoing relationship (monthly engagement) that is 10x stickier than annual filing. Once a user relies on FileFree for "should I open a Roth IRA?" and "how much should I put in my 401k?", they're not switching for a $5/year savings on filing.

**Moat 3: Network Effects via Social Proof (DISTRIBUTION)**
Tax filing is social -- "who do you use?" is a common question. The viral tax receipt card, referral system, and TikTok/Instagram content create compounding distribution. If 15% of users share their card and 5% of viewers convert, each user generates 0.0075 new users. At 100K users, that's 750 organic acquisitions per cycle -- growing exponentially.

**Moat 4: Data Compound Interest (LONG-TERM)**
Each year of filing data makes the AI advisor smarter: "You made $12K more than last year -- here's how to adjust your W-4 withholding so you're not giving the IRS an interest-free loan." Multi-year data is something new competitors can never have for existing users.

**Moat 5: Proprietary OCR Intelligence Layer (COST STRUCTURE)**
The moat isn't the OCR engine itself -- it's the post-processing intelligence layer on top. Our pipeline: GCP Cloud Vision for text extraction + local SSN isolation (regex, never sent to AI) + GPT-4o-mini structured field mapping + GPT-4o vision fallback for edge cases. Cost: ~$0.004/doc vs competitors' $0.30+ (GCP Document AI W-2 Parser). This 75x cost advantage means we can offer truly free filing at any scale.

### 2.8 User Flow (MVP)

#### Screen 0: Try Without Signing Up (Growth Unlock)

- User can snap/upload a W2 photo WITHOUT creating an account
- Show the OCR extraction magic (fields filling in one by one)
- Gate: "Create a free account to save your return and finish filing"
- This reduces the trust barrier to zero and creates shareable "wow" moments
- Anonymous session data converts to user account on sign-up

#### Screen 1: Landing / Login

- Hero: anxiety-focused copy, not feature-focused
- Primary CTA: "Snap Your W2 -- See It In Action" (try-before-signup)
- Secondary CTA: "Sign In" for returning users
- Social proof: filing counter, testimonials, trust badges
- Comparison section: FileFree vs TurboTax vs FreeTaxUSA
- FAQ section targeting Gen Z concerns ("Is this really free?", "Is my data safe?", "What's the catch?")
- Dedicated /pricing page linked from nav: explicit free-forever guarantee for core filing
- Auth: Google OAuth + Apple Sign-In, optional email/password fallback
- Mobile-optimized, dark theme with gradient accents

#### Screen 2: Document Capture -- W2

- Full-screen camera interface with W2 bounding box overlay
- Guide text: "Position your W2 within the frame"
- Manual capture button (auto-capture is stretch goal)
- Immediate quality check: blur detection, lighting check
- If quality fails: "That's a bit blurry. Try again with more light."
- Upload from photo library as alternative
- Multiple W2 support ("Add another W2" after first)

#### Screen 3: Document Capture -- Driver's License

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

#### Screen 6: Your Return Summary (THE MONEY SCREEN)

- Animated refund reveal (count-up) or calm owed display
- Breakdown: Gross Income, Standard Deduction, Taxable Income, Federal Tax, Already Paid, Refund/Owed
- Charts: "Where Your Taxes Go" pie chart, "Your Refund vs Average" bar chart
- AI Insights: plain-English explanation + personalized tips (streaming, typewriter effect)
- Tax receipt viral card: shareable graphic with filing time, opt-in refund amount, FileFree branding
- CTAs: "Download Your Completed Return (PDF)", "Add State Filing -- Free"

#### Screen 7: Download & Next Steps (MVP -- no e-file yet)

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

### 2.9 E-File Strategy

#### NORTH STAR: Own IRS MeF Transmitter (January 2027)

The #1 long-term strategic priority. Owning our e-file infrastructure means $0/return cost, full control, and no third-party dependencies. This is what makes "free forever" permanently sustainable.

**IRS Certification Timeline (hard calendar constraints):**

1. **March 2026 (NOW):** Apply for EFIN (Form 8633). Requirements: PTIN, IRS e-Services account, ID.me verification, fingerprinting. 45-day processing. Approval expected ~late April.
2. **May 2026:** EFIN approved. Apply for e-Services MeF system access (1-2 weeks).
3. **May-September 2026:** Build MeF XML generator from TaxCalculation data model (IRS Publication 4164 specification). Map all 1040 fields to MeF XML schema. 4-8 weeks focused engineering.
4. **October 2026:** IRS Assurance Testing System (ATS) opens. Submit 12 mandatory test scenarios. This is the hard constraint -- ATS opens once per year in October.
5. **November 2026:** Complete communication test with IRS MeF production system.
6. **January 2027:** Production go-live. Free e-file for all users. Deprecate Column Tax for simple returns.

#### Interim: Column Tax SDK (October - December 2026)

- Integrate Column Tax web SDK into post-summary flow
- Transparent cost-passthrough: user pays exactly what we pay Column Tax (no markup). Target: negotiate to $10-15/return.
- Free PDF download always available as alternative
- User-facing messaging: "We're going through the rigorous IRS e-file certification process, which completes this fall. Until then, you can download your return for free, or e-file through our certified partner at cost. Once we're IRS-certified, e-file will be free forever."

#### MVP (Now - September 2026)

- No e-file. Generate 1040 PDF with step-by-step mailing instructions.
- Include IRS Free File guidance where applicable.
- Messaging: "E-file coming October 2026. Download your completed return now."

### 2.10 Form Coverage Roadmap

| Milestone | Forms | Notes |
|---|---|---|
| **January 2027 launch** | 1040 + Schedule 1 + Schedule B + Schedule C + 1099-NEC/INT/DIV + dependents + ALL 50 state returns | Covers ~80% of US filers |
| **February 2027 (mid-season)** | Schedule A (itemized deductions) + Schedule D (capital gains basics) | Covers homeowners + basic investors |
| **Year 2 (2027-2028 season)** | Schedule E (rental), Schedule SE (self-employment tax), multi-state, HSA (Form 8889), K-1 pass-through | Covers small landlords, full self-employed, health savings |
| **Year 2 (business filing)** | Form 1065 (partnership/LLC), Form 1120-S (S-Corp), Schedule K-1 generation | Business returns. $49-99/return (consumer), included in Pro Firm |
| **Year 3+** | Depreciation (Form 4562), AMT (Form 6251), brokerage import (CSV/API), foreign income (Form 2555) | Edge cases, power users |

### 2.11 Success Metrics

**2026 (Validation):**

- Email waitlist: 500+ by April 15, 2,000+ by October 15
- Beta users (complete full flow): 500 by October 15
- Completion rate: > 60% of users who start filing complete it
- NPS: > 50
- Share rate (tax receipt card): > 15% of completers
- Testimonials collected: 50+

**2027 (Revenue):**

- Total filers: 50,000
- AI Advisory subscribers: 2,500 (5% conversion)
- Financial product referrals: 5,000 (10% of filers)
- ARR: $500K+

**2028 (Scale):**

- Total filers: 500,000
- ARR: $5M+
- B2B API partners: 5+

---

## 3. Product 2: LaunchFree (launchfree.ai)

### 3.1 Problem Statement

There are ~4.4M new business formations in the US per year. Entrepreneurs pay $39-$500+ in service fees to companies like LegalZoom ($149-$299), ZenBusiness ($0 base + $199-$349/yr upsell), and Northwest ($39) for what is fundamentally a simple government form. Worse, these companies bury state filing fees in the total, upsell aggressively on EIN filing ($70-$150 for something that takes 5 minutes free on IRS.gov), and charge $99-$299 for operating agreement templates. No competitor helps users choose which state to form in based on their actual situation.

### 3.2 Solution

LaunchFree is a free LLC formation service. $0 service fee -- the user pays only what their state charges, disclosed upfront before they start. AI-powered 50-state comparison helps users pick the cheapest, best-fit state for their business.

**What's actually free (our service -- $0 forever):**

- LLC formation filing (document preparation + state submission via Filing Engine): $0
- Operating agreement template (state-specific, attorney-reviewed): $0
- EIN filing walkthrough: $0
- Compliance calendar + reminders: $0
- 50-state comparison AI guide: $0

**What's NOT free (government fees -- clearly disclosed upfront):**

- State filing fee: $35-$500 (depends on state)
- We help users find the cheapest legitimate option for their situation

**Revenue**: RA credits, banking/payroll/insurance referrals, Compliance-as-a-Service ($49-99/yr).

### 3.3 50-State AI Comparison (The Differentiator)

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

**Data accuracy standard:** Every fee, deadline, and requirement shows its source ("CA SOS, last verified 2026-03-01"). User confirmation step before any filing action. Automated freshness checks via n8n daily (volatile states) and weekly (all others). See VENTURE_MASTER_PLAN.md Section 3B for full pipeline architecture.

### 3.4 State Filing Engine

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

**Dual-use:** The State Filing Engine powers both LaunchFree (consumer, $0) and the Distill Formation API (B2B, $20-40/filing target pricing). Code lives in `packages/filing-engine/`, shared by both products.

### 3.5 What's Free vs What's Not

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

### 3.6 RA Credit System

**Base RA price**: $49/yr. Users earn credits to reduce or eliminate the cost by completing partner actions:

- Open a business bank account (Mercury, Relay): earn $25 credit
- Set up payroll (Gusto): earn $25 credit
- Get business insurance (Next): earn $15 credit

**Pricing language**: "RA starting at $49/yr. Earn credits to reduce your cost." NEVER say "Free RA."

### 3.7 Compliance-as-a-Service ($49-99/yr add-on, Phase 3.5)

After LLC formation, ongoing compliance management -- annual report reminders, franchise tax calculations, state deadline tracking, pre-filled renewal forms.

LaunchFree already captures all state-specific formation data in the 50-state JSON configs. Compliance deadlines and annual report requirements are a natural extension of the same data set. Zero new infrastructure -- it's calendar math + state fee lookups + email reminders via n8n.

| Metric | Conservative | Moderate | Aggressive |
|---|---|---|---|
| LaunchFree formations (Year 1) | 1,000 | 2,000 | 5,000 |
| Compliance attach rate | 8% | 12% | 18% |
| Price | $49/yr | $79/yr | $99/yr |
| Annual recurring revenue | $3,920 | $18,960 | $89,100 |

**Competitive positioning**: "You formed for free. Now stay compliant for $49/yr. LegalZoom charges $299."

### 3.8 Competitive Landscape

| Service | Service Fee | Upsells | State Fee Transparency | State Comparison |
|---|---|---|---|---|
| LegalZoom | $0-$299 | Heavy ($199 RA, $159 operating agreement, $159 EIN) | Buried in total | No |
| ZenBusiness | $0 | Heavy ($199/yr Pro, $349/yr Premium) | Shown separately | No |
| Northwest | $39 | Moderate ($125/yr RA included Y1) | Shown separately | No |
| Incfile | $0 | Heavy ($149-$349 bundles) | Shown separately | No |
| Cairn (withcairn.com) | Free guide, $14.99 docs | Limited | Shown | Guide only, not full service |
| **LaunchFree** | **$0** | **None (revenue from partner referrals)** | **Upfront, before you start** | **Yes (AI-powered, all 50 states)** |

### 3.9 Success Metrics

**H2 2026 (Launch):**

- Formations: 1,000-5,000
- RA credit purchases: 1-3% of formations
- Compliance SaaS attach rate: 8-18%
- Revenue: $7.9K-$114K

**Year 2 (2027-2028):**

- Formations: 5,000-15,000
- Cross-sell to FileFree: 5-8% of formers file taxes via FileFree
- Compliance SaaS renewals: 70%+ retention

---

## 4. Product 3: Distill (distill.tax) -- B2B Compliance Automation Platform

### 4.1 What It Is

Distill is the B2B umbrella brand for all compliance automation products. It started as a CPA tax automation SaaS, but the same infrastructure pattern applies to every compliance vertical: tax extraction, LLC formation, and ongoing entity compliance. "Distill" = extract the pure essence from complex government paperwork.

**Why a separate brand**: The word "Free" in "FileFree" creates cognitive dissonance for B2B buyers paying $199/mo. "Distill" = extract pure essence from raw material, fits naturally under Paperwork Labs (distilling paperwork).

**Why one B2B brand (not separate brands per vertical):** Companies like Stripe (Payments, Atlas, Issuing, Identity), Twilio (SMS, Voice, Email), and Plaid (Auth, Identity, Transactions, Income) use one brand for multiple API products. Developers hate juggling multiple platforms -- one login, one API key, one billing relationship. Cross-sell is frictionless. At 2 founders, the single-brand model is correct.

**Why this exists**: MagneticTax (YC S25) raised venture capital to build exactly the CPA tax extraction product. We build the identical OCR/extraction pipeline for consumer FileFree anyway. The B2B product is ~20% incremental engineering. It is the fastest path to predictable revenue because CPAs pay monthly SaaS fees from day 1.

### 4.2 Four Product Lines

1. **Distill for CPAs** (SaaS dashboard at distill.tax, Phase 9): Upload client W-2s/1099s in bulk, auto-extract fields, review in professional dashboard, export to UltraTax (CSV), Drake (XML), ProConnect (CSV), Lacerte (CSV). Shares `packages/tax-engine/` and `packages/document-processing/`.

2. **Distill Tax API** (api.distill.tax/tax, Summer 2026): Headless Tax-as-a-Service for fintech apps, payroll companies, banking apps. Per-return pricing ($5-15/return). Calculation-only at launch; e-file endpoint activates January 2027 when MeF transmitter ships. Shares `packages/tax-engine/`.

3. **Distill Formation API** (api.distill.tax/formation, Summer 2026): LLC formation as a service for CPAs, law firms, HR platforms, banking apps, accounting software. Per-filing pricing ($20-40/filing target, undercutting incumbent API providers). Powered by the same State Filing Engine as LaunchFree (`packages/filing-engine/`).

4. **Distill Compliance API** (api.distill.tax/compliance, Summer 2026): State compliance calendars, deadline tracking, annual report reminders, automated alerts. Natural extension of the `packages/data/` 50-state configs. Advanced operations (amendments, foreign qualifications, dissolutions) expand in Year 2-3.

The CPA SaaS is a UI product. The APIs are headless engines. All share core infrastructure (`packages/tax-engine/`, `packages/filing-engine/`, `packages/data/`) but are distinct products with distinct pricing.

### 4.3 Tech Overlap (~80% Shared Per Vertical)

**Shared:**

- OCR pipeline (Cloud Vision + GPT tiered extraction) -- shared with FileFree
- W-2/1099 field extraction + Pydantic schemas -- shared with FileFree
- Tax calculation engine (50-state) -- shared with FileFree
- State Filing Engine (portal automation, state APIs) -- shared with LaunchFree
- 50-state data layer (`packages/data/`) -- shared with FileFree + LaunchFree
- Document storage (GCP Cloud Storage, 24hr lifecycle) -- shared
- SSN isolation (regex extraction, never sent to LLMs) -- shared

**B2B-specific delta (~2-3 weeks engineering):**

- Multi-tenant team management (firm -> preparers -> clients)
- Bulk document upload (drag-and-drop multiple documents, queue through shared OCR pipeline, batch progress tracking)
- Professional dashboard (client list, per-client document status, extraction confidence, review workflow)
- Tax software export: CSV/XML import files for UltraTax, Drake, ProConnect, Lacerte
- Stripe B2B billing with seat-based plans and usage metering

### 4.4 Pricing

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

### 4.5 Multi-Tenant Data Isolation

All Distill API routes use firm-scoped middleware that injects `firm_id` from auth token into every database query. Row-level security (RLS) on PostgreSQL enforced via `SET app.current_firm_id` + RLS policies. No query can return data from a different firm. CPA firm A's client data must never leak to CPA firm B. Security audit required before Distill launch (P9.9).

### 4.6 DPA Requirement

Consumer FileFree users consent directly. Distill is different: the CPA firm is our customer, but the individuals whose W-2s are uploaded are NOT our direct users. We process their PII on behalf of the CPA firm.

CPA firms must sign a Data Processing Agreement (DPA) covering:

- What data we process
- How long we retain it (24hr for images per existing policy)
- That we do not use client data for consumer product matching
- CCPA/state privacy law compliance

DPA template needed before Distill launch (attorney consult scope item, P9.10).

### 4.7 Audit Trail

Every extraction, edit, export, and submission is timestamped with user ID and firm ID. Immutable audit log retained for 7 years (IRS record retention requirement). Exportable as CSV for CPA firm compliance needs. This is a differentiation feature -- CPAs face IRS audits and need proof of every step.

### 4.8 Competitive Positioning vs MagneticTax

- MagneticTax is VC-funded (YC S25) with dedicated burn. We're bootstrapped with consumer filing as the primary product -- the B2B arm is marginal cost.
- MagneticTax only does 1040 data entry. Distill inherits our full form coverage (1040 + Schedules 1, A, B, C, D + 1099-NEC/INT/DIV + 50-state returns) and expands as consumer FileFree adds forms.
- MagneticTax has no consumer product, no financial marketplace, no cross-product data moat.

**Distribution**: Target independent CPAs and small firms (1-10 preparers). 75,000+ CPA firms in the US. Tax season creates natural urgency. Off-season demand: extensions, amendments, prior-year returns, quarterly estimates. See VENTURE_MASTER_PLAN.md Section 5M for bootstrapped B2B GTM playbook.

### 4.9 Success Metrics

| Milestone | Timeline | Revenue | Channel |
|---|---|---|---|
| 10 CPA firms | Feb 2027 | $500-2K MRR | Founder-led sales + free tier conversion |
| 50 CPA firms | Apr 2027 | $2.5K-10K MRR | Product Hunt + content + referrals |
| 200 CPA firms | Jan 2028 | $10K-40K MRR | SEO + word-of-mouth + returning firms |
| API first customers | Q3 2027 | +$500-2K MRR | Self-serve developer signups |

---

## 5. Product 4: Trinkets (tools.filefree.ai)

### 5.1 Overview

Trinkets is a collection of simple, client-side utility tools (financial calculators, converters, generators) that serve three purposes:

1. **Test the agent infrastructure** -- the Trinket Factory pipeline validates our end-to-end agent workflow (Discovery -> PRD -> Build)
2. **Build shared libraries** -- the first trinket establishes reusable patterns (`packages/tool-template`)
3. **Passive revenue** (bonus) -- AdSense monetization, cross-sell to FileFree/LaunchFree

All processing is browser-based (pdf-lib, heic2any, browser-image-compression, qrcode.js). Zero server cost. Zero backend. No auth required. Cross-sell CTAs funnel traffic to FileFree/LaunchFree.

### 5.2 Trinket Factory Agent Pipeline (3-Stage)

Instead of manually picking tools, the agent infrastructure discovers, specs, and builds them:

**Stage 1: DISCOVERY (GPT-5.4)**
Computer-use: browse competitor sites, analyze UX/pricing/SEO. + Gemini Flash for SEO keyword analysis. Output: 1-pager from template (`docs/templates/trinket-one-pager.md`). Human reviews, approves/rejects.

**Stage 2: SPEC (Claude Sonnet)**
Takes approved 1-pager as input. Writes precise PRD from template (`docs/templates/trinket-prd.md`). Human reviews, approves/rejects.

**Stage 3: BUILD (Claude Sonnet)**
Takes approved PRD + established pattern from first trinket. Generates code, creates PR for human review. 79.6% SWE-bench = best code quality.

### 5.3 Domain Strategy

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

### 5.4 First Trinket: Financial Calculators

Pre-decided idea (agent validates, not selects). Includes:

- Mortgage calculator
- Compound interest calculator
- Savings goal calculator
- Budget planner

All client-side JavaScript. Zero API costs, zero server costs. Aligns with FileFree's financial brand (cross-sell opportunity). Hosted on Vercel free tier as `apps/trinkets/` in the monorepo.

### 5.5 Revenue Projections

| Period | Revenue | Notes |
|---|---|---|
| Year 1 | $50-300 | New domain, minimal traffic. SEO takes 6-12 months. |
| Year 2 | $5K-20K | Long-tail SEO begins compounding. Cross-sell conversions. |
| Year 3+ | $20K-100K | SEO compounds. Portfolio of 15+ tools. |

**Market context**: iLovePDF (216M monthly visits, ~$4M/yr), SmallPDF (61M monthly visits, ~$11M/yr), PDF2Go (5-12M monthly visits, ~$670K/yr). These are established players with 10+ year head starts. Revenue projections are conservative.

---

## 6. Product 5: Studio / Command Center (paperworklabs.com)

### 6.1 Purpose

The command center is the control plane for the entire venture. It is what makes the "one human + AI agents" model operationally viable. Clean, minimal holding company portfolio page at `/` (public), plus authenticated `/admin/` panel for operations, and public `/docs/*` viewer for company documents.

### 6.2 Three-Tier Page Hierarchy

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
| State Data Observatory | `/admin/data` | 50-state freshness indicators, last verified dates, change history | `packages/data/` JSON + n8n validator |

**Tier 3 -- Build When Revenue Flows:**

| Page | Route | Purpose | Data Sources |
|---|---|---|---|
| Revenue Intelligence | `/admin/revenue` | Stripe revenue by product/stream, affiliate revenue, MRR/churn/ARPU, spend overview | Stripe API + affiliate dashboards |
| Campaign Control | `/admin/campaigns` | Create/manage cross-sell campaigns, targeting, performance | Campaign tables in studio DB |
| User Intelligence | `/admin/users` | Venture identity browser, segments, cross-product journey visualization | Venture identity DB |

### 6.3 Docs Viewer (public, /docs/*)

- Renders company docs from the git repo as clean, readable HTML pages
- Pages: Master Plan, Financials, Knowledge Base, Tasks, AI Model Registry
- Uses `react-markdown` or `next-mdx-remote` to render markdown fetched from GitHub API
- Clean typography, table styling, anchor links for section navigation
- Responsive and mobile-friendly -- designed for non-technical readers (founder shares `paperworklabs.com/docs/financials` with wife)
- No GitHub account needed to read
- Cached with React Query (staleTime: 5 min)
- Table of contents sidebar generated from markdown headings

---

## 7. Revenue Model

### 7.1 FileFree Revenue Streams

**The Core Insight:** Free tax filing is the acquisition channel, not the product. The monetization event is the refund moment -- the instant a 22-year-old sees "$3,400 refund" on screen is the highest-intent financial decision moment of their year. This is the Credit Karma playbook ($8.1B acquisition by Intuit).

**Free Forever (Acquisition Layer):**

- Federal tax preparation -- free
- State tax preparation (all 50 income-tax states) -- free
- All filing statuses, up to 3 W2s -- free
- AI-powered OCR + plain-English explanation -- free
- 1040 PDF download -- free
- E-file via own MeF transmitter (January 2027+) -- free
- E-file via Column Tax (October-December 2026) -- at cost (passthrough, ~$10-15, no markup)

**Stream 1: Refund Routing to Partner Accounts ($50-100/funded account)**

After calculating the refund, show a "Refund Plan" screen with IRS Form 8888 split options. HYSA partners pay $50-100 per funded account. Investment account partners pay $50-150.

Projected conversion: 8-12% of users with refunds. At $75 avg = $4.00-6.00/user.

**Stream 2: Financial Product Referrals ($50-200/referral)**

Post-filing recommendations based on user's actual tax data. HYSA: $50-100/referral. Roth IRA: $50-150. Credit cards: $50-100/approval. Renters insurance: $30-50.

Projected conversion: 2-4% effective referral rate. At $75 avg = $1.50-3.00/user.

**Stream 3: Refund Advance ($3-5/advance revenue share)**

Partner with a fintech lender. $0 cost to user, 0% APR. We earn $3-5 per advance. Requires e-file capability (October 2026+).

Projected conversion: 10-15% at $3-5 = $0.30-0.75/user.

**Stream 4: Audit Shield ($19-29/year)**

AI-assisted audit response prep + $1M coverage via insurance partner (TaxAudit/Protection Plus). Our cost: ~$10/return wholesale. Our price: $19-24. Margin: 47-58%.

Projected conversion: 2-4% at $19-29 = $0.38-1.16/user.

**Stream 5: Tax Optimization Plan ($29/year, annual)**

Annual one-time purchase at filing time. W-4 adjustment calculator, IRA contribution optimizer, year-over-year comparison, quarterly estimate reminders, priority support.

Projected conversion: 2-5% at $29 = $0.58-1.45/user.

**Stream 6: Complex Filing ($39 one-time, Phase 2+)**

1099 income, itemized deductions, investment income, multi-state. Core simple filing stays free forever.

Projected conversion: 1-5% at $39 = $0.39-1.95/user.

**Stream 7: B2B Embedded Tax API (Phase 3, 2028+)**

License our OCR + calculation + MeF submission engine to fintechs. API pricing $5-25 per return (volume-tiered).

**Three Revenue Scenarios at 100K Users:**

| Scenario | Blended ARPU | Annual Revenue |
|---|---|---|
| A -- Conservative (referrals only) | $4.38 | $438K |
| B -- Moderate (partnerships in place) | $8.05 | $805K |
| C -- Aggressive (full stack + B2B) | $13.31 | $1.331M + $200K B2B |

### 7.2 LaunchFree Revenue Streams

| Stream | Pessimistic | Moderate | Aggressive |
|---|---|---|---|
| RA credits (1-3% buy) | $1K | $5K | $7K |
| Banking referrals (2-5%) | $2K | $7.5K | $12.5K |
| Payroll referrals (0.5-1%) | $1K | $3K | $5K |
| Compliance SaaS (8-18%) | $3.9K | $19K | $89K |
| **H2 2026 Total** | **$7.9K** | **$34.5K** | **$114K** |

### 7.3 Distill Revenue (SaaS Subscriptions)

| Year | CPA Firms | Avg Plan | Monthly Rev | Annual Rev |
|---|---|---|---|---|
| Y1 (2027) | 30-100 | $79-99/mo | $2.4K-9.9K | $28K-119K |
| Y2 (2028) | 100-300 | $99-129/mo | $9.9K-38.7K | $119K-464K |
| Y3 (2029) | 300-600 | $119-149/mo | $35.7K-89.4K | $428K-$1.07M |

### 7.4 Combined Year 1 Projections

| Scenario | LaunchFree (H2 2026) | FileFree (Jan-Apr 2027) | **Total** |
|---|---|---|---|
| **Pessimistic** | $7.9K | $7K | **$14.9K** |
| Moderate | $34.5K | $29K | **$63.5K** |
| Aggressive | $114K | $150K | **$264K** |

**Why the pessimistic scenario matters**: It models 5K filers, 1K formations, bottom-tier attach rates, and self-serve affiliates only (no Founder 2 deals closed). At $14.9K Year 1 revenue, the venture survives ($278/mo burn) but takes longer to reach meaningful revenue. The compliance SaaS revenue is recurring and compounds year over year.

### 7.5 Unit Economics

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

### 7.6 Plan B: Zero Partnerships Closed

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

### 7.7 Partnership Milestones

| Milestone | Owner | Deadline | Consequence If Missed |
|---|---|---|---|
| Submit self-serve affiliate apps (Betterment, Wealthfront, SoFi) | Founder 1 | April 2026 | Delays referral revenue by 1-2 weeks |
| Book Column Tax demo call | Founder 2 | May 2026 | No interim e-file for October extension season |
| Column Tax sandbox access | Founder 2 | June 2026 | Cannot test e-file integration; fallback = PDF only |
| RA wholesale partner signed (CorpNet or equivalent) | Founder 2 | July 2026 | Launch LaunchFree without RA service |
| TaxAudit/audit shield partnership | Founder 2 | September 2026 | Launch FileFree without audit shield |
| At least 1 banking partner confirmed | Either | October 2026 | Refund routing not available for first tax season |

See PARTNERSHIPS.md for the complete playbook including partner hit list, outreach templates, and partnership lifecycle.

---

## 8. Architecture

### 8.1 Monorepo Structure (pnpm workspaces)

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

### 8.2 Tech Stack

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

### 8.3 Federated Identity

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

### 8.4 Auth Architecture

**User Auth (FileFree, LaunchFree):**

- Providers: Google OAuth + Apple Sign-In (cover 95%+ of users). Optional email/password fallback.
- Implementation: `packages/auth/` using Auth.js v5 (NextAuth), shared across all Next.js apps.
- SSO across subdomains: Cookie domain set to `.filefree.ai`. LaunchFree on `launchfree.ai` (different domain) links via venture identity system (email match).

**Admin Auth (paperworklabs.com + admin panels):**

- Same Google OAuth flow. Middleware checks if authenticated email is in `ADMIN_EMAILS` env var allowlist.
- No separate admin login page. Same SSO, authorization check on top.

**Trinkets Auth:** None. Public utility tools. Cross-sell CTAs link to FileFree/LaunchFree.

### 8.5 Brand Architecture

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

### 8.6 Brand Palettes

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

Implementation: CSS `[data-theme]` selectors in `packages/ui/themes.css`. Each app sets its theme via `<body data-theme="trinkets">`.

### 8.7 Infrastructure

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

### 8.8 Production Reliability

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

## 9. Data Models

### 9.1 FileFree Models

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

### 9.2 LaunchFree Models

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
- formation_data: JSONB (from `packages/data/states/formation/`)
- tax_data: JSONB (from `packages/data/states/tax/`)
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

### 9.3 Distill Models

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

### 9.4 Venture Identity

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
- event_type: string (from event taxonomy -- see VENTURE_MASTER_PLAN.md Section 4C)
- product: enum
- metadata: JSONB
- timestamp: timestamp (immutable, append-only)

**UserSegment:**
- venture_identity_id: FK -> VentureIdentity
- segment: string
- computed_at: timestamp

### 9.5 Marketplace Tables

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

### 9.6 Campaign Engine

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

## 10. API Design

### 10.1 FileFree API

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

### 10.2 LaunchFree API

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

### 10.3 Distill API (/api/v1/pro/*)

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

### 10.4 Studio API

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

## 11. Legal and Compliance

### 11.1 Entity Structure

**Now (pre-revenue):** Single California LLC (Paperwork Labs LLC) + DBA filings for "FileFree", "LaunchFree", and "Trinkets".

- California filing: $70
- DBA filing: ~$10-25 per name
- Franchise tax: $0 first year (exempt for new LLCs), $800/yr after
- RA: ~$49/yr
- Total year 1: ~$119-145

**At $50K+ combined revenue:** Convert to holding company structure. Parent LLC (Paperwork Labs LLC) stays as-is. Create FileFree LLC and LaunchFree LLC as subsidiaries with own bank accounts, EINs, and liability shields.

### 11.2 Trademark Framework

"FILEFREE" and "LAUNCHFREE" to be filed on USPTO Supplemental Register. Both marks are likely descriptive, making Principal Register registration difficult without 5 years of substantially exclusive commercial use.

| Mark | Classes | Register | Cost | Timeline |
|---|---|---|---|---|
| FILEFREE (stylized wordmark) | Class 036 (Financial), Class 042 (SaaS) | Supplemental | $350 x 2 = $700 | File after product launch (need specimen) |
| LAUNCHFREE (stylized wordmark) | Class 035 (Business formation), Class 042 (SaaS) | Supplemental | $350 x 2 = $700 | File after product launch |
| FILEFREE (logo/design mark) | Class 036, Class 042 | Supplemental | $350 x 2 = $700 | File with wordmark |
| **Total** | | | **~$2,100** | All within 90 days of launch |

**CRITICAL**: filefree.com is owned by Intuit (confirmed via WHOIS, registered since 1999 via MarkMonitor). NEVER reference filefree.com anywhere, ever.

### 11.3 FTC "Free" Compliance

Our service IS actually free for ALL users. This is our strongest legal position.

"Filing is free. 100% of filers. 100% of the time. No income limits. No complexity limits for supported forms. No asterisks. No small print."

The moment we add a condition that makes filing not-free for some users, we are exposed to the exact FTC action that hit Intuit.

**LaunchFree "Free" rules:**
- NEVER use "Free LLC" as a standalone headline. Always: "Free LLC Formation Service" or "$0 Service Fee."
- State filing fees must appear in the same visual field as any "free" claim.
- RA credits: NEVER say "Free RA." Always: "RA starting at $49/yr. Earn credits to reduce your cost."

### 11.4 Circular 230

We provide TAX EDUCATION, not TAX ADVICE. This distinction is legally critical.

Every screen, email, social post, or AI response that discusses tax topics must include: "This is general tax information, not tax advice. For advice specific to your situation, consult a qualified tax professional."

NEVER say "you should" + tax action. ALWAYS say "many filers in your situation" or "the standard deduction is typically..."

### 11.5 UPL Compliance

We provide BUSINESS FORMATION SERVICES, not LEGAL ADVICE.

NEVER say "you should form in Delaware" or "you need an operating agreement." ALWAYS say "many entrepreneurs choose Delaware because..." or "operating agreements are commonly used to..."

**Operating agreement model**: LaunchFree provides state-specific operating agreement TEMPLATES (pre-written by a licensed attorney, stored as PDFs). AI EXPLAINS clauses but does NOT select, modify, or draft clause language. Marketing: "Operating agreement template included" not "AI-generated operating agreement."

### 11.6 Cross-Sell Consent (3-Tier Architecture)

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

### 11.7 PII Data Lifecycle (CCPA-First)

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

### 11.8 Legal Protection Checklist

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

## 12. Content and Distribution Strategy

### 12.1 SEO

**FileFree targets:**
- "how to file taxes for free", "what is a W2", "standard deduction 2025"
- "first time filing taxes", "tax refund calculator"
- 3-5 genuinely helpful guides at launch, add 2/month
- FAQ schema markup for featured snippets
- "First Time Filing" hub page -- beachhead keyword cluster

**LaunchFree targets:**
- "free LLC formation", "how to start an LLC", "cheapest state for LLC"
- State-specific landing pages for all 50 states
- "LLC vs sole proprietorship", "do I need a registered agent"

### 12.2 Social Media

**Strategy**: Faceless AI-generated content (daily, zero founder time) + weekly founder-face video (10 min).

- TikTok (primary) + Instagram Reels + YouTube Shorts + X
- 7-10 posts/week during tax season, 2-3/week off-season (FileFree)
- 3-5 posts/week consistent year-round (LaunchFree)
- 5 content pillars: tax myths busted, "I filed in X minutes" reactions, W-2 explainers, money tips for Gen Z, founder journey (build-in-public)

**Pipeline cost**: ~$3/month for 30 videos (GPT-4o script $0.01 + DALL-E 3 image $0.04 + ElevenLabs voice $0.05 = ~$0.10/video). n8n orchestrates the pipeline: trend research -> script generation -> image/voice generation -> FFmpeg assembly -> Postiz queue -> founder review (5 min/day).

### 12.3 Paid Amplification ($200-500/mo tax season)

- **TikTok Spark Ads** (primary, $3-10 CPM): Boost organic posts with >1K views. Intermittent 3-5 day bursts at $20-50/day.
- **Meta/Instagram Boost** (secondary, $8-12 CPM): Boost top Reels. Better targeting for retargeting.
- **Key rule**: Never create ad-first content. Only boost posts the algorithm already validated organically.
- **Kill criteria**: TikTok CPC > $0.50 after $20 spend = stop. Meta CPC > $1.00 after $15 spend = stop.
- Off-season (May+): $0 paid. Organic only.

### 12.4 Viral Loops

**Tax receipt card (FileFree):** Shareable filing summary with filing time, opt-in refund amount, FileFree branding. Target: 15% share rate. Formats: IG Story (1080x1920), X (1200x675), square (1080x1080).

**LLC formation celebration (LaunchFree):** "I just started my business!" shareable certificate with LaunchFree branding.

**Referral program:** "Share FileFree" from dashboard, track with unique codes + UTM. Both referrer and referee get benefit (priority support, Tax Optimization Plan discount).

**Try-before-signup:** The demo IS the marketing. Users snap a W2 without signing up, see the OCR magic, share the "wow" moment.

**Comparison calculator (Trinket):** "How much are you overpaying for tax prep?" Interactive widget that generates a shareable result.

### 12.5 Autonomous Content (n8n workflows)

- **Daily**: Auto-draft 3 posts from trending topics via OpenAI + persona prompts -> queue in Postiz as drafts -> founder reviews/approves (5 min)
- **Weekly**: Pull Postiz analytics -> OpenAI generates growth report -> email summary
- **Monthly**: Pull infrastructure costs -> OpenAI checks vs budget -> alert if overspending

Content Review Gate (mandatory): Every piece of content passes Circular 230 compliance, UPL compliance, FTC disclosure, CAN-SPAM compliance, and brand name verification before publishing. First 30 days: founder reviews every post manually. After 30 days: pre-approved templates can auto-publish.

---

## 13. Realistic Timeline

| Phase | Description | Target | Hard Deadline? |
|---|---|---|---|
| Phase 0 | Infrastructure (domains, LLC, EFIN, legal) | March 2026 | NO |
| Phase 1 | Monorepo Restructure (pnpm workspaces, 5 apps, shared packages) | April 2026 | NO |
| Phase 1.5 | First Trinket + Agent Pipeline Test | April 2026 | NO |
| Phase 2 | 50-State Data Infrastructure (AI extraction, validation, n8n monitoring) | May 2026 | NO |
| Phase 3 | LaunchFree MVP (formation wizard, State Filing Engine, Stripe, RA credits) | June-July 2026 | NO |
| Phase 4 | Command Center (Tier 1 daily ops pages) | June 2026 | NO |
| Phase 5 | User Intelligence Platform (venture identity, campaigns, marketplace) | July 2026 | NO |
| Phase 6 | Agent Restructure + Social Pipeline (persona splits, n8n workflows) | July 2026 | NO |
| Phase 9 | Distill Full B2B Platform (CPA SaaS + Formation API + Tax API + Compliance API) | July-August 2026 | NO |
| Phase 7 | FileFree Season Prep (50-state tax calcs, MeF XML, forms, reliability) | October 2026 | **YES** -- IRS |
| Phase 8 | FileFree Launch (MeF go-live, Tax Opt Plan, marketing) | January 2027 | **YES** -- IRS |
| Phase 10 | Business Tax Filing (1065, 1120-S, K-1 generation) | 2027-2028 | NO |

Phase 9 (Distill) runs in parallel with Phases 5-6 — shared infrastructure from Phases 1-3 means the incremental B2B work is thin.

**Critical Path:**

```
EFIN Application (NOW) ---- 45 days ----> Software Dev ID -> ATS Testing (Oct 2026) -> MeF Launch (Jan 2027)

Phase 0 -> Phase 1 -> Phase 2 -> Phase 3 (LaunchFree + Filing Engine) -> Phase 9 (Distill APIs, parallel) -> Phase 7 (FileFree Prep) -> Phase 8 (Launch)
```

**Three hard deadlines that cannot move:**

1. **EFIN approval**: Must apply NOW. 45-day processing. Late application compresses the October ATS testing window.
2. **MeF ATS testing**: IRS opens ATS testing window each fall. Must have XML generator complete by June 2026 to test in October. Miss this and FileFree e-file delays to January 2028.
3. **Tax season**: IRS starts accepting returns late January 2027. Product must be live.

---

**Cross-References:**

- Strategic depth, valuation scenarios, marketplace evolution, agent architecture: VENTURE_MASTER_PLAN.md
- Product-specific development tasks and sprint planning: TASKS.md
- Financial tracking, burn rate, revenue actuals: FINANCIALS.md
- Partnership playbook, outreach templates, pipeline: PARTNERSHIPS.md
- AI model routing registry: AI_MODEL_REGISTRY.md
- Organizational memory, decisions log: KNOWLEDGE.md
