# Paperwork Labs — Founder Side Projects Evaluation

**Owner**: Strategy + CFO agents
**Last updated**: March 2026
**Purpose**: Evaluate founder's existing side projects for viability as Paperwork Labs products, trinkets, or shelved ideas.

**Status**: Items 5-9 have been formally integrated into the Venture Master Plan as core products/features with dedicated Phases. They are no longer "side projects." This document is retained as the evaluation record (market assessment, competitive landscape, GO/NO-GO rationale). For execution details, see their respective Phase sections in `docs/VENTURE_MASTER_PLAN.md`.

---

## Evaluation Criteria

| Factor | Weight | Description |
|---|---|---|
| Market size | 30% | TAM, competition, user demand signals |
| Alignment | 25% | Synergy with FileFree/LaunchFree ecosystem and brand |
| Effort to ship | 20% | Technical complexity, time to MVP, ongoing maintenance |
| Revenue potential | 15% | Monetization path, realistic Year 1 revenue |
| Differentiation | 10% | What makes this better than existing solutions |

---

## 1. Axiomfolio

**What it is**: Portfolio tracking/management tool

**Market Assessment**:
- Crowded market: Wealthfront, Personal Capital, Mint (now Credit Karma), Kubera, Empower
- Users expect brokerage integrations (Plaid, Yodlee) which are expensive ($0.10-0.50/connection/mo)
- Read-only portfolio tracking is a commodity; value is in advice/optimization

**Competitive Landscape**:
- Empower (Personal Capital): Free portfolio tracker, monetizes through wealth management advisory ($100K+ AUM)
- Kubera: $150/yr, targets HNWI, supports crypto + real estate + private equity
- Portfolio Visualizer: Free, power-user tools, ad-supported

**Alignment with Venture**: HIGH. Users who file taxes have financial data. Cross-sell from FileFree (post-filing: "Now track your investments year-round"). Could feed into Tax Optimization Plan ($29/yr) with capital gains/loss insights.

**Effort**: HIGH. Brokerage integrations are expensive and complex. Plaid investment tier costs significantly more than banking tier. Maintaining connections across brokerages is ongoing engineering burden.

**Revenue Path**: Subscription ($5-15/mo) or bundle with Tax Optimization Plan. Alternatively, free tier with premium insights.

**GO / NO-GO**: **DEFER to Year 2+**. High alignment but high effort. The integration costs (Plaid investment) make this non-viable pre-revenue. Revisit when FileFree has 10K+ users and Tax Optimization Plan revenue can fund Plaid costs. Could become a "premium" feature of Tax Optimization Plan rather than standalone product.

---

## 2. ReplyRunner

**What it is**: Automated email/message reply tool

**Market Assessment**:
- Growing market: AI email assistants are hot (Superhuman, Shortwave, Ellie.ai, Compose AI)
- Consumer email AI is a feature, not a product (Gmail, Outlook already have AI compose)
- B2B email automation has more legs (outbound sales, customer support)

**Competitive Landscape**:
- Superhuman: $25/mo, premium email with AI
- Shortwave: Free tier, AI-first email client
- Ellie.ai: $19/mo, AI email reply generator
- Gmail Smart Compose: Free, built into Gmail

**Alignment with Venture**: LOW. No natural cross-sell with FileFree or LaunchFree. Different user persona entirely.

**Effort**: MEDIUM. Core feature (AI reply generation) is straightforward with GPT API. But email integration (OAuth, thread parsing, send-on-behalf) is complex. Gmail API + Outlook Graph API both have approval processes.

**Revenue Path**: SaaS subscription ($10-25/mo). Crowded pricing tier.

**GO / NO-GO**: **NO-GO**. Low alignment with venture, crowded market with built-in competitors (Gmail, Outlook), and no clear differentiation. The AI reply space is becoming a commodity feature, not a standalone product.

---

## 3. Jointly

**What it is**: Joint finance management app for couples

**Market Assessment**:
- Underserved niche: most finance apps are single-user. Couples need shared visibility without shared accounts.
- Honeydue (acquired by Zeta) was the closest competitor, pivoted to banking. Zeta is a joint banking product.
- Real pain point: 36% of couples argue about money. Financial transparency reduces conflict.

**Competitive Landscape**:
- Zeta: Joint banking + budgeting, $0 (bank product)
- Honeydue: Acquired, product sunsetted
- Copilot Money: $10/mo, single-user focused, no joint features
- YNAB: $99/yr, budgeting-focused, no joint-specific features

**Alignment with Venture**: MEDIUM-HIGH. FileFree users who are married/filing jointly have a natural cross-sell path. "You just filed your taxes together -- now manage your money together." Could integrate with Tax Optimization Plan for household-level tax insights.

**Effort**: MEDIUM-HIGH. Needs Plaid banking connections (expensive at scale), real-time transaction sync, and a delicate UX around financial transparency (what to share, what to keep private).

**Revenue Path**: Freemium ($0 basic, $8/mo premium with insights). Or bundle into household Tax Optimization Plan.

**GO / NO-GO**: **DEFER to Year 2+**. Good market fit and decent venture alignment, but the Plaid dependency and UX complexity make this a Year 2+ product. Could be reimagined as a feature within FileFree's post-filing experience rather than a standalone app. The "Jointly" brand name may conflict with "filing jointly" in tax context -- evaluate naming if pursued.

---

## 4. FittingRoom

**What it is**: Virtual try-on / fashion tech tool

**Market Assessment**:
- Hot AR/AI space but dominated by massive players (Snap, Meta, Google) with billions in R&D
- Virtual try-on requires computer vision, 3D modeling, or AR SDK integration
- B2C fashion tech has high churn and low willingness to pay

**Competitive Landscape**:
- Google Virtual Try-On: Free, built into Search
- Snap AR: Free, integrated into Snapchat
- Stitch Fix: Uses AI for styling, but it's a retail business
- Various startups (Zeekit, acquired by Walmart): B2B solutions for retailers

**Alignment with Venture**: ZERO. No connection to financial services, tax, LLC, or any venture product.

**Effort**: VERY HIGH. Computer vision / AR is specialized engineering. Not in our skill set or tech stack.

**Revenue Path**: B2B licensing to retailers (long sales cycle) or consumer subscription (low WTP).

**GO / NO-GO**: **NO-GO**. Zero alignment, very high technical complexity, dominated by Big Tech players. This is a completely different business and should remain a personal interest project if desired, not a venture product.

---

## 5. Compliance-as-a-Service (LaunchFree Add-On)

**What it is**: Ongoing LLC compliance management -- annual report reminders, franchise tax calculations, state deadline tracking, pre-filled renewal forms. Subscription add-on to LaunchFree.

**Market Assessment**:
- Every LLC needs ongoing compliance. Annual reports, franchise taxes, and state renewals are mandatory and confusing.
- 4.4M new business applications filed in 2023 (Census Bureau). ~70% are LLCs.
- Compliance failures lead to administrative dissolution -- a genuine pain point with real financial consequences.

**Competitive Landscape**:
- LegalZoom: $299/yr compliance package (bundled with RA)
- ZenBusiness: $199/yr Pro plan includes compliance alerts
- Northwest: $225/yr (includes RA + compliance)
- Incfile: $149/yr compliance package
- None offer a standalone compliance-only tier below $149/yr

**Alignment with Venture**: VERY HIGH. LaunchFree already captures all formation data (state, entity type, formation date, RA). Compliance data is a JSON config extension of existing 50-state data in `packages/data`. Zero new infrastructure -- it's calendar math + state fee lookups + email reminders.

**Effort**: LOW. State deadline configs extend existing JSON data. Reminder engine uses existing n8n pipeline. Dashboard is one new page in LaunchFree. Estimated: 1-2 weeks of development (Phase 3.5).

**Revenue Path**: $49-99/yr subscription per LLC. At 10% attach rate on 2K formations = $10K-20K/yr. Recurring revenue that compounds -- unlike one-time affiliate commissions. Scales linearly with LaunchFree growth.

**Differentiation**: We undercut competitors by 3-6x ($49 vs $199-299) because our marginal cost is near zero. No humans involved -- fully automated reminders and form generation. The competitive moat is the combination of free formation + cheap compliance: "You formed for free. Now stay compliant for $49/yr."

**GO / NO-GO**: **GO -- Phase 3.5** (post-LaunchFree MVP). Low effort, high alignment, recurring revenue, clear competitive advantage. This is the first true SaaS revenue stream for the venture.

---

## 6. Quarterly Tax Estimator (FileFree / Trinket)

**What it is**: Estimated quarterly tax calculator for 1099/freelance workers (IRS Form 1040-ES). Input: YTD income + expenses. Output: recommended quarterly payment, next deadline, payment voucher PDF.

**Market Assessment**:
- 59M Americans freelance (Upwork 2023). All with 1099 income need to pay estimated quarterly taxes or face IRS underpayment penalties.
- "Quarterly tax calculator" has ~12K monthly searches with moderate competition.
- Existing tools (TurboTax, QuickBooks) require accounts and are bloated. No clean, free, fast option exists.

**Competitive Landscape**:
- TurboTax TaxCaster: Free but requires Intuit account, bloated UX, no prior-year auto-population
- QuickBooks Self-Employed: $15/mo, overkill for just quarterly estimates
- IRS Form 1040-ES worksheet: PDF, manual math, zero guidance
- Various simple web calculators: no personalization, no voucher generation

**Alignment with Venture**: VERY HIGH. FileFree already has a tax calculation engine. Quarterly estimates are a simplified version of the annual calculation (safe harbor rule). Prior-year filing data auto-populates for returning users -- a moat no competitor can match.

**Effort**: LOW-MEDIUM. Basic Trinket version (manual input): 3-5 days. Full FileFree feature (auto-populated from prior return): 1-2 weeks in Phase 7. Reuses existing tax engine.

**Revenue Path**: Free (acquisition + retention). Indirect monetization: (1) Tax Optimization Plan upsell at $29/yr, (2) 4x/year re-engagement increases affiliate conversion 3x vs one-time filers, (3) SEO traffic acquisition at near-zero CAC.

**Differentiation**: The only quarterly estimator that auto-populates from your actual prior-year tax return. "Based on your 2026 return, your Q1 2027 estimated payment is $1,847." No manual entry. No guessing.

**GO / NO-GO**: **GO -- Phase 1.5 (Trinket) + Phase 7 (FileFree feature)**. Ship basic version as a Trinket for SEO immediately. Upgrade to auto-populated FileFree feature during Season Prep. Near-zero incremental effort, high engagement value.

---

## 7. Refund Splitting + Goal-Based Savings (FileFree)

**What it is**: At refund time, let users split their refund across multiple accounts (checking, HYSA, IRA). Uses IRS Form 8888 which already supports direct deposit to up to 3 accounts.

**Market Assessment**:
- Average federal tax refund: $3,167 (IRS 2024 data). 77% of filers receive a refund.
- Refund moment is the highest-intent financial moment of the year -- users are primed to make financial decisions.
- Behavioral economics: refunds feel like "found money," making users more willing to save/invest.

**Competitive Landscape**:
- TurboTax: Offers refund splitting but buries it in settings. No goal-based framing.
- H&R Block: Similar -- available but not promoted.
- Credit Karma: No refund splitting (they do tax filing but focus on credit products).
- No free filing product makes refund splitting the centerpiece of the post-filing experience.

**Alignment with Venture**: VERY HIGH. We already generate the 1040 PDF. Form 8888 is a trivial addition (3 routing numbers + amounts). The intelligence layer knows the user's financial profile, enabling personalized goal recommendations. Each split to an affiliate account = $25-75 commission.

**Effort**: LOW. Form 8888 PDF generation: 1 day. Refund splitting UI: 2-3 days. Goal templates + recommendations: 2-3 days. Total: ~1 week as part of P7.4 Refund Plan screen.

**Revenue Path**: Each split destination to an affiliate account (HYSA, IRA) is a conversion. At 5% adoption on 10K filers, 60% affiliate rate, $50 avg commission = $15K. At scale (30K filers, 8% adoption): $126K.

**Differentiation**: We make refund splitting the star of the post-filing experience, not a buried setting. Personalized goal recommendations based on the user's actual tax data and financial profile. "You're 24 with no retirement savings -- a Roth IRA with your $1,200 split will be worth ~$15,000 by retirement."

**GO / NO-GO**: **GO -- Phase 7 (P7.4 expansion)**. Trivial implementation effort, significant revenue upside, and it transforms the post-filing experience from "you're done" to "let's make your money work."

---

## 8. Business Tax Filing (FileFree + LaunchFree Synergy)

**What it is**: Business return preparation for Forms 1065 (partnership/multi-member LLC) and 1120-S (S-Corp). Includes Schedule K-1 generation for pass-through income allocation to partners/shareholders.

**Market Assessment**:
- 3.5M+ partnership returns and 5M+ S-Corp returns filed annually (IRS SOI data).
- Every LaunchFree LLC former who selects "partnership" or "S-Corp" tax election MUST file a business return -- this is mandatory compliance, not optional.
- Business tax prep starts at $219 (TurboTax Business), $85+ (H&R Block Business), $10-29/mo (Taxu.io). No free options exist.

**Competitive Landscape**:
- TurboTax Business: $219/return. Desktop-only. Established but expensive and dated.
- Taxu.io: $10-29/mo business tier. 2M+ users. Closest competitor -- they charge for business features we could undercut.
- X.TAX: $95-159/return. AI-powered but not free, not integrated with formation.
- No competitor combines free LLC formation + business tax filing in a single flow.

**Alignment with Venture**: VERY HIGH. This is a mandatory cross-sell from LaunchFree. Users who form an LLC through LaunchFree and select partnership or S-Corp election are legally required to file a business return. "You formed your LLC with LaunchFree for free. Now file your business taxes with FileFree." The data flows naturally -- formation data pre-fills the business return.

**Effort**: HIGH. Business returns are significantly more complex than personal returns. Schedule K-1 generation requires partner allocation logic. MeF business return schemas are separate from 1040 schemas. Estimated: 4-6 weeks of engineering (Phase 10, Year 2).

**Revenue Path**: $49/return (1065), $99/return (1120-S). Free for Distill Firm plan subscribers. LaunchFree cross-sell: first business return free.

| Scenario | Returns | Avg Fee | Annual Rev |
|---|---|---|---|
| Conservative (Y2) | 200 | $65 | $13K |
| Moderate (Y2) | 500 | $70 | $35K |
| Aggressive (Y2) | 2,000 | $75 | $150K |

**Differentiation**: Only platform that combines free LLC formation + free personal filing + paid business filing. LaunchFree formation data pre-fills the business return. K-1s flow directly into partners' personal FileFree returns.

**GO / NO-GO**: **GO -- Phase 10 (Year 2, 2027-2028 season)**. High alignment, mandatory demand from LaunchFree users, significant revenue at scale. High effort justified by the synergy multiplier and the absence of free alternatives. The tax engine infrastructure from Phase 7 handles most of the heavy lifting; business-specific logic (K-1 allocation, partnership accounting) is the primary delta.

---

## 9. Distill -- B2B Tax Automation Platform (distill.tax)

**What it is**: Separate B2B brand from FileFree. Two product lines: **Distill for CPAs** (SaaS dashboard for CPA firms — upload client W-2s/1099s in bulk, auto-extract fields via shared OCR pipeline, export to professional tax software) and **Distill API** (headless Tax-as-a-Service + Formation API + Compliance API, Summer 2026). Built under Paperwork Labs venture umbrella.

**Why a separate brand**: "Free" in "FileFree" creates cognitive dissonance for B2B buyers paying $199/mo. Tax industry standard is separate brands (Intuit: TurboTax vs ProConnect/Lacerte). "Distill" = extract pure essence from raw material, perfect metaphor for OCR-to-structured-data.

**Market Assessment**:
- 75,000+ CPA firms in the US. ~250,000 active CPAs.
- MagneticTax (YC S25) raised venture capital for exactly this use case -- validates market demand.
- CPAs spend 2-6 hours per client on manual data entry during tax season. AI automation is a clear value proposition.
- Tax season creates natural urgency (January-April) with off-season demand for extensions and amendments.

**Competitive Landscape**:
- MagneticTax: YC S25 batch, B2B AI tax prep for CPAs. Pre-revenue, VC-funded. 1040 data entry automation.
- SurePrep (Thomson Reuters): Established, $3,000-5,000+/yr. Enterprise-focused, not for small firms.
- Gruntworx: Document processing for CPAs. $4-8/document. Established but not AI-native.

**Alignment with Venture**: VERY HIGH. ~80% tech overlap with consumer FileFree. Same OCR pipeline, same field extraction, same tax calc engine. The B2B product is a different frontend on the same backend. CPA firms become a distribution channel for consumer FileFree (CPA referrals). Bidirectional flywheel: Distill CPA -> consumer FileFree -> Distill.

**Effort**: LOW-MEDIUM. ~2-3 weeks of incremental engineering on top of Phase 7 infrastructure. Delta: multi-tenant team management (RLS + firm-scoped middleware), bulk document upload, tax software export formats, Stripe B2B billing, audit trail logging (7yr retention), DPA onboarding flow.

**Revenue Path**: Pure SaaS, monthly subscriptions.

| Plan | Price | Preparers | Returns/mo |
|---|---|---|---|
| Solo | $49/mo | 1 | 50 |
| Team | $99/mo | 3 | 200 |
| Firm | $199/mo | Unlimited | 500+ |

Annual billing discount: 20% (Solo $39/mo, Team $79/mo, Firm $159/mo).

**Differentiation**: We build the OCR/extraction pipeline for consumer filing anyway -- B2B is marginal cost. MagneticTax is VC-funded with dedicated burn for one product. We're bootstrapped with consumer filing as the primary product and B2B as an incremental revenue arm with near-zero additional infrastructure cost. Distill's audit trail logging and CPA-optimized workflows differentiate from raw API competitors.

**GO / NO-GO**: **GO -- Phase 9 (Summer 2026)**. Very high alignment, low incremental effort (~80% shared infrastructure), immediate SaaS revenue, market validated by MagneticTax YC funding. This is the fastest path to predictable revenue in the venture. See Section 5M in master plan for bootstrapped B2B GTM playbook.

---

## Summary

### Integrated into Venture Master Plan (no longer side projects)

| Project | Phase | Master Plan Section | Pricing |
|---|---|---|---|
| Compliance SaaS | Phase 3.5 | Section 1B (LaunchFree) | $49-99/yr |
| Quarterly Estimator | Phase 1.5 + 7 | Section 0F (Trinkets) + Section 1A | Free |
| Refund Splitting | Phase 7 (P7.4) | Section 1A (FileFree) | Free (affiliate rev) |
| Business Tax Filing | Phase 10 (Year 2) | Section 1A + Phase 10 | $49-99/return |
| Distill (B2B Compliance Platform) | Phase 9 (Summer 2026) | Section 1C + Section 5M | $49-199/mo SaaS + API revenue |

### Shelved

| Project | Verdict | Notes |
|---|---|---|
| Axiomfolio | DEFER (Year 2+) | High alignment but needs Plaid investment. Revisit as Tax Optimization Plan premium feature. |
| Jointly | DEFER (Year 2+) | Good alignment, underserved market, but Plaid + UX complexity. Explore as FileFree household feature. |
| ReplyRunner | NO-GO | Low alignment, commodity market, no differentiation. |
| FittingRoom | NO-GO | Zero alignment, very high complexity, Big Tech competitors. |
