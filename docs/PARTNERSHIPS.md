# FileFree Partnership Playbook

**For**: Partnerships Co-Founder (Founder 2)
**Last Updated**: 2026-03-09
**Companion docs**: PRD.md (Section 7: Revenue Model), STRATEGY_REPORT.md (Section 6: Team Structure)

This is your standalone reference document. Everything you need to operate is here — no need to read code, technical docs, or engineering specs.

---

## 1. Why Partnerships Are THE Business

FileFree is a free tax filing app. Filing is the acquisition channel — it earns user trust. The actual revenue comes from financial product partnerships at the **refund moment**: the instant a 22-year-old sees "$3,400 refund" on screen and decides what to do with it.

This is the Credit Karma playbook. Credit Karma was acquired by Intuit for $7.1B on the strength of financial product referrals alone. We have an advantage over Credit Karma: we have verified W-2 income, exact refund amount, filing status, and state — the most valuable targeting data in consumer finance.

### Your Impact, Quantified

| Scenario | Description | Revenue at 100K Users |
|---|---|---|
| A — No partnerships person | Affiliate-only, no direct deals, no lending | $438K |
| B — Partnerships in place | Direct deals, lending partner, optimized | $805K |
| **Delta** | **Your contribution** | **$367K** |

Partnership-dependent revenue (refund routing + financial referrals + refund advance) = **77% of Scenario B revenue**. The filing app is the engine. Partnerships are the fuel.

### Unit Economics

- Cost per user: $0.060 (OCR + AI + infrastructure)
- Scenario B ARPU: $8.05
- Gross margin: 99.3%
- 5-year LTV: $27.05 (80% annual retention, PCMag data)
- Max sustainable CAC: $9.02
- Fixed monthly infrastructure: $12.49/mo

---

## 2. Tiered Partnership Strategy (Marketplace-Aligned)

The partnership strategy aligns with the 4-stage Financial Marketplace Platform evolution (see Master Plan Section 4O). Each partnership tier maps to a marketplace stage. Partners naturally upgrade tiers as our user base grows and the platform becomes more valuable.

### Tier A — Self-Serve Affiliates (Stage 1: 0-5K users)

**What:** Apply to affiliate networks online. Standard programs -- fill out a form, describe your audience, get approved, receive tracking links.

**Payout:** $25-100 per funded account (standard affiliate rates).

**Partners:** Marcus, Wealthfront, Betterment, Fidelity, SoFi, Ally, Robinhood, Chime, Acorns via Impact.com/CJ Affiliate.

**Timeline:** Apply NOW, pre-product. Activate links when Refund Plan screen ships.

**Owner:** Either co-founder (online forms, 15-30 min each).

**Data flow:** One-way (we send users to partner, partner pays us). No data back from partner.

### Tier B — Managed Affiliates + Data Reciprocity (Stage 2: 5K-25K users)

**What:** Upgrade top-performing Tier A partners to managed relationships with tiered CPA and data sharing.

**Pitch:** "We're driving X funded accounts per month at Y% conversion rate -- 3x your network average. We want: (1) tiered CPA ($75 instead of $50), (2) you share approval rates and funded amounts back to us."

**Payout:** $75-200 per funded account (1.5-3x standard affiliate).

**Owner:** Founder 2 (negotiation). Founder 1 joins for technical data integration.

**Data flow:** Two-way. We send pre-qualified users. Partner shares back:
- Approval rate per segment (helps us compute real match quality)
- Average funded amount (helps us estimate LTV per recommendation)
- 30/60/90-day retention (helps us recommend products users actually keep)

**Why data reciprocity matters:** This data feeds back into the scoring model (Section 4E Layer 2), making recommendations better for ALL partners. Partners who share data get better-qualified leads. It's a flywheel.

### Tier C — API Partners (Stage 3: 25K-50K users)

**What:** Partners submit product details, eligibility criteria, and CPA bids via our Partner API. Self-serve onboarding portal.

**Pitch:** "Join our financial marketplace. Submit your product details via API. Bid on access to pre-qualified user segments. Get real-time conversion analytics."

**Payout:** Auction-based CPA ($100-200+ for premium segments) + optional platform access fee.

**Owner:** Founder 2 (relationship + negotiation). Partner API built by Founder 1.

**Data flow:** Bidirectional + programmatic. Partners submit eligibility criteria and bids via API. They receive anonymized segment data and real-time conversion funnels.

### Tier D — Marketplace Participants (Stage 4: 50K+ users)

**What:** Partners upload eligibility models, run segment simulations, and optimize in real-time via the marketplace console.

**Payout:** CPA auction + monthly platform access fee ($500-2,000/mo).

**Owner:** Self-serve. Founder 2 manages strategic relationships only.

**Data flow:** Full marketplace integration. Partners run models against anonymized profiles. Real-time bidding and optimization.

### Strategic Partner Scoring Matrix

Evaluate every potential partner on 5 dimensions before pursuing:

| Factor | Weight | Description | Stage 1 Focus |
|---|---|---|---|
| Revenue per conversion | 30% | CPA/CPS amount per funded account | Prioritize highest-paying affiliates |
| Data reciprocity potential | 25% | Will they share approval rates, funded amounts, retention data back? | Ask upfront, even if they can't share yet |
| User trust alignment | 20% | Does this product genuinely help our users? Would we recommend it to a friend? | Hard filter -- reject anything predatory |
| Integration complexity | 15% | Affiliate link (trivial) vs API (medium) vs custom build (high) | Stage 1 = affiliate links only |
| Exclusivity value | 10% | Would featuring this partner exclusively give competitive advantage? | Never grant category exclusivity |

**Exclusivity strategy**: Never grant category exclusivity (e.g., "only HYSA partner"). Competition between partners drives CPA bids up at Stage 3+. DO offer "featured partner" placement for a premium -- higher bid = top position, but competitors still visible below.

### Data Reciprocity Agreements (Stage 2+ Upgrade Path)

When upgrading a partner from Tier A to Tier B, negotiate for them to share:

1. **Approval rates per segment**: "Of the users we sent with credit scores 700-749, how many were approved?" This feeds directly into Fit Score accuracy.
2. **Average funded amounts**: "What's the average deposit for users referred by us vs. other channels?" This helps us estimate LTV per recommendation.
3. **30/60/90-day retention**: "What % of our referrals are still active after 90 days?" This helps us recommend products users actually keep -- not just products that convert.
4. **Reason for rejection** (anonymized): "Were rejections due to credit score, income, state, or other?" This immediately improves our eligibility filtering.

This data is the secret weapon. Partners who share data get better-qualified leads, which increases their conversion rate, which makes them more willing to pay premium CPA, which increases our revenue. The flywheel accelerates.

**Technical mechanism by stage**:
- **Stage 2 (Tier B)**: Monthly CSV email. Partner sends a spreadsheet with referral_id, approval_status, funded_amount, and retention_status (30/60/90 day). We provide a CSV template. Simple, low-friction, no integration work for the partner.
- **Stage 3 (Tier C)**: Webhook callback. Partner sends a POST to our `/api/v1/partners/outcomes` endpoint with referral_id, event_type (approved/rejected/funded/churned), and optional metadata. Real-time data flow enables immediate scoring model updates.
- **Stage 4 (Tier D)**: Real-time API. Full bidirectional API. Partner queries our segments, we query their outcomes. Batch and streaming modes.

---

## 3. Partnership Hit List

### Tier 1: HYSA Partners (Primary Revenue — apply NOW)

**1. Marcus by Goldman Sachs**
- **Product:** High-yield savings account (5%+ APY)
- **Affiliate program:** Via Impact network. Public referral program pays $50-100/funded account.
- **Application URL:** Search "Marcus" on impact.com after creating a publisher account
- **Direct partnership potential:** HIGH — Marcus actively partners with fintech apps for referral volume
- **Revenue estimate (100K users):** 8% attach rate x $75 avg = $600K
- **Competitive intel:** Partners with Credit Karma, NerdWallet, Bankrate
- **Status:** Not Started

**2. Wealthfront**
- **Product:** HYSA (5%+ APY) + automated investing
- **Affiliate program:** Via Impact network. $50-150/funded account depending on product.
- **Application URL:** Search "Wealthfront" on impact.com
- **Direct partnership potential:** HIGH — startup-friendly, strong affiliate program
- **Revenue estimate (100K users):** 4% attach rate x $100 avg = $400K
- **Competitive intel:** Partners with NerdWallet, The Points Guy, fintech apps
- **Status:** Not Started

**3. Betterment**
- **Product:** Automated investing + HYSA
- **Affiliate program:** Via CJ Affiliate. $50-150/funded account.
- **Application URL:** Search "Betterment" on cj.com
- **Direct partnership potential:** MEDIUM — they're selective but open to fintech partners
- **Revenue estimate (100K users):** 3% attach rate x $100 avg = $300K
- **Competitive intel:** Partners with NerdWallet, various personal finance sites
- **Status:** Not Started

**4. Fidelity**
- **Product:** IRA/brokerage accounts, HYSA
- **Affiliate program:** In-house program. $50-100/funded account.
- **Application URL:** Search for "Fidelity affiliate program" — apply directly
- **Direct partnership potential:** MEDIUM — large institution, slower to move but high payout
- **Revenue estimate (100K users):** 2% attach rate x $75 avg = $150K
- **Status:** Not Started

### Tier 2: E-File Partner (Critical for October 2026)

**5. Column Tax**
- **Product:** E-file SDK — lets us submit tax returns to the IRS
- **Affiliate program:** N/A — this is a B2B SDK integration
- **Pricing:** Public rate ~$25/return (WorkMoney pricing). Our target: negotiate to $10-15/return.
- **Action required:** Book demo call at columntax.com/contact-us
- **What to negotiate:** Per-return pricing (volume discount), white-labeling options, sandbox access timeline
- **Timeline:** Need sandbox access by June 2026 for October launch
- **Your role:** Book the call, negotiate pricing. Founder 1 joins for technical SDK questions.
- **Status:** Not Started

### Tier 3: Refund Advance Partners (requires e-file, Sprint 4+)

**6. Refundo**
- **Product:** Refund advance — users get their refund in 24 hours instead of 21 days
- **Model:** 0% APR to user. Lender profits on float + interchange. We earn $3-5/advance.
- **Outreach required:** YES — email/call to establish partnership
- **Revenue estimate (100K users):** 12% attach rate x $4 avg = $48K
- **Status:** Not Started (wait until e-file is close to live)

**7. Green Dot / Republic Bank**
- **Product:** Alternative refund advance / prepaid card refund deposit
- **Model:** Similar to Refundo. Rev share on advance fees.
- **Outreach required:** YES
- **Status:** Not Started

### Tier 4: Adjacent Financial Products (Phase 3+)

**8. Lemonade**
- **Product:** Renters insurance
- **Affiliate program:** Standard affiliate, $30-50/referral
- **Why it fits:** Gen Z renters who just filed taxes = high intent for adulting products
- **Status:** Not Started

**9. Discover or Capital One (Secured Credit Card)**
- **Product:** Secured credit card for first-time credit builders
- **Affiliate program:** Standard card affiliate, $50-100/approval
- **Why it fits:** First-time filers are often also first-time credit builders
- **Status:** Not Started

**10. YNAB or Budgeting App**
- **Product:** Cross-referral partnership (we refer users to them, they refer users to us)
- **Model:** Mutual referral, no cash exchange initially
- **Why it fits:** Post-filing is the moment people think "I should be better with money"
- **Status:** Not Started

---

## 4. Outreach Templates

### Template A: Affiliate Network Application Cover Note

Use when affiliate networks ask "Describe your audience and how you plan to promote our product."

> FileFree (filefree.tax) is a free, AI-powered tax filing app built for Gen Z (ages 18-30). After users complete their tax return and see their refund amount, we present personalized financial product recommendations on our "Refund Plan" screen — the highest-intent financial decision moment of their year.
>
> Our users have verified W-2 income, exact refund amounts, filing status, and state residency — the most valuable targeting data in consumer finance. We recommend products that genuinely help our users (high-yield savings for their refund, IRA accounts for first-time investors) with clear disclosures.
>
> We project [X] users in our first year with [Y]% recommendation engagement rates based on comparable fintech apps.

### Template B: Column Tax Demo Request

> Subject: FileFree — Column Tax SDK Demo Request
>
> Hi Column Tax team,
>
> I'm the partnerships lead at FileFree (filefree.tax), a free AI-powered tax filing app for Gen Z. We're building our own IRS MeF transmitter (target: January 2027) but need an interim e-file solution for October 2026.
>
> We'd love to explore the Column Tax SDK for our use case:
> - Simple W-2 filers (single, MFJ, standard deduction)
> - Pre-filled data from our OCR pipeline (all fields mapped before handoff)
> - White-labeled integration within our app
> - Projected volume: 2K-5K returns in first season, scaling to 30K+
>
> Could we book a 30-minute demo to discuss SDK capabilities, pricing, and sandbox access?
>
> Best,
> [Name]
> FileFree — filefree.tax

### Template C: Direct Partnership Upgrade (Phase 3)

> Subject: FileFree x [Partner] — Direct Partnership Discussion
>
> Hi [Name],
>
> I'm reaching out from FileFree, a free tax filing app for Gen Z. We've been driving [X] funded [product] accounts per month through your affiliate program with a [Y]% conversion rate — well above the network average.
>
> Given our growing volume and aligned audience (18-30, first-time filers seeing their refund for the first time), I'd love to explore a direct partnership. Specifically:
>
> - Higher per-account payouts reflecting our conversion quality
> - Co-marketing opportunities (we can feature you as a recommended partner)
> - API integration for a seamless user experience
> - Dedicated account management
>
> Would you be open to a 20-minute call to discuss? Happy to share our conversion data and user demographics.
>
> Best,
> [Name]
> FileFree — filefree.tax

### Template D: Refund Advance Partner Intro

> Subject: Refund Advance Partnership — FileFree
>
> Hi [Name],
>
> FileFree is a free tax filing app for Gen Z with [X] users and IRS e-file capability. We'd like to offer our users refund advances through your platform.
>
> Our user profile: 18-30, W-2 income, average refund ~$3,400, 91% receive refunds. 21% of Gen Z rely on their refund for rent and groceries — speed matters to our audience.
>
> We're looking for:
> - 0% APR advance (lender profits on float/interchange)
> - Seamless API integration within our filing flow
> - Rev share model ($3-5/advance)
>
> Would you be open to discussing a partnership?
>
> Best,
> [Name]
> FileFree — filefree.tax

### Template E: Follow-Up (1 week, no response)

> Subject: Re: [Original Subject]
>
> Hi [Name],
>
> Following up on my note from last week. I know inboxes get busy — just wanted to make sure this didn't get buried.
>
> Happy to work around your schedule for a quick call, or if there's a better contact for partnership discussions, I'm glad to be redirected.
>
> Best,
> [Name]

### Template F: Tier B Upgrade -- Tiered CPA + Data Reciprocity (Stage 2, 5K+ users)

> Subject: FileFree x [Partner] — Tiered Partnership Upgrade
>
> Hi [Name],
>
> Quick update on our partnership performance: FileFree has driven [X] funded [product] accounts through your affiliate program in [timeframe], with a [Y]% conversion rate — [Z]x your network average.
>
> We'd like to discuss upgrading to a direct, tiered relationship:
>
> 1. **Tiered CPA**: $[amount] per funded account (reflecting our conversion quality)
> 2. **Data sharing**: We'd love to receive anonymized approval rates and funded amounts for our referrals. This helps us send you even better-qualified leads — a win-win.
> 3. **Featured placement**: Priority position on our Refund Plan screen for your product category
>
> Our users have verified W-2 income, credit scores, and detailed financial profiles. We can segment and pre-qualify traffic in ways affiliate networks can't.
>
> 20-minute call to discuss?
>
> Best,
> [Name]
> FileFree — filefree.ai

### Template G: Tier C -- Partner API Introduction (Stage 3, 25K+ users)

> Subject: Join FileFree's Financial Marketplace — Partner API Access
>
> Hi [Name],
>
> FileFree is opening our partner API to select financial product providers. We have [X]K active users with verified income data, credit scores, and detailed financial profiles — the richest per-user dataset in consumer fintech.
>
> What the Partner API offers:
>
> - Submit your product details and eligibility criteria programmatically
> - Receive anonymized segment data ("X,000 users match your criteria")
> - Set CPA bids to compete for top placement in personalized recommendations
> - Real-time conversion analytics dashboard
>
> Our users see products ranked by "Fit Score" — a personalized match score based on their actual financial profile. Partners on our API see 2-3x higher conversion rates vs. standard affiliate channels because every impression is pre-qualified.
>
> Interested in early access? Happy to walk you through the platform.
>
> Best,
> [Name]
> FileFree — filefree.ai

### Template H: Tier D -- Marketplace Invitation (Stage 4, 50K+ users)

> Subject: FileFree Financial Marketplace — Premium Partner Invitation
>
> Hi [Name],
>
> FileFree's financial marketplace now serves [X]K+ users with the deepest per-user financial profiles in consumer fintech: verified income, credit scores, filing status, business ownership data, and behavioral signals from year-round engagement.
>
> We're inviting select partners to our premium marketplace tier:
>
> - Upload your eligibility models to our secure sandbox — see exactly which users match
> - Run segment simulations before committing budget
> - Real-time bidding on premium segments (high-income, good credit, refund in hand)
> - Full conversion funnel analytics with partner-level A/B testing
>
> Current marketplace partners see [Y]% conversion rates on matched recommendations — [Z]x industry average.
>
> Would love to set up a demo of the marketplace console.
>
> Best,
> [Name]
> FileFree — filefree.ai

---

## 5. Your Weekly Cadence (2-3 Hours Total)

### Monday — Pipeline Review (30 min)
- Check Notion Partnership Pipeline for status updates
- Review any AI-drafted outreach emails in your queue
- Approve and send outreach (personalize if needed)
- Flag any partners that need product/engineering input

### Wednesday — Calls & Meetings (60 min)
- AI preps call briefs the night before (deal summary + agenda + key questions)
- Take 1-2 partnership calls
- After each call: update Notion with notes, next steps, and status change

### Friday — Status Update (30 min)
- Update Notion pipeline statuses
- Review any incoming partnership responses
- Flag anything for the Monday pipeline review
- If no active outreach: review hit list for next targets

---

## 6. What You Do NOT Need to Worry About

These are Founder 1's domain. Don't spend your limited hours on them:

- **Product development** — app features, UI/UX, bug fixes
- **Code and infrastructure** — servers, databases, deployments
- **Tax calculations** — brackets, deductions, IRS rules
- **OCR pipeline** — document scanning, AI field extraction
- **Security architecture** — encryption, SSN handling, PII compliance
- **Social media content** — TikTok, Instagram, content calendar
- **EFIN application** — IRS certification process
- **Day-to-day product decisions** — feature prioritization, sprint planning

**Your sole focus:** Getting financial product partnerships signed, activated, and optimized so that when users see their refund amount, we have the right products to recommend.

---

## 7. Partnership Lifecycle

How a deal goes from idea to revenue, and who owns each stage:

```
Stage              Owner           AI Persona Does
─────────────────────────────────────────────────────
Research           AI              Research partner programs, pricing, contacts, competitive intel
Application        AI / You        Draft application cover note, you submit
Outreach           AI / You        Draft outreach email, you personalize and send
Meeting            You             AI preps call brief with agenda, questions, negotiation points
Negotiation        You             AI summarizes terms, flags risks, drafts counterproposals
Signed             You             AI reviews agreement, you sign
Integration        Founder 1       Engineering builds the product integration
Activate           Both            Links go live, both monitor initial performance
Optimize           Both            Track conversion, A/B test placement, adjust recommendations
Revenue            Both            Monitor payouts, reconcile monthly, report to pipeline
```

---

## 8. Key Dates & Milestones (Marketplace-Aligned)

| Date | Milestone | Marketplace Stage | Your Action |
|---|---|---|---|
| March 2026 | Sprint 0 | Pre-Stage 1 | Submit Tier A affiliate applications (Marcus, Wealthfront, Betterment, Fidelity, SoFi). Book Column Tax demo. |
| June 2026 | Column Tax sandbox | Pre-Stage 1 | Confirm pricing locked. Ensure sandbox access. |
| September 2026 | Refund Plan screen built | Pre-Stage 1 | Review partner placement. Confirm affiliate links. Test tracking. |
| October 2026 | E-file goes live | Pre-Stage 1 | Begin refund advance outreach (Refundo, Green Dot). |
| January 2027 | First tax season | Stage 1 begins | Monitor conversion rates per partner per segment. Collect baseline data. |
| April 2027 | Post-season review | Stage 1 | Analyze: which partners converted best? For which segments? Build the Tier B upgrade pitch. |
| Mid-2027 | 5K+ users | Stage 1 -> 2 gate | Initiate Tier B upgrade negotiations with top 3 partners. Pitch tiered CPA + data reciprocity. |
| Late 2027 | 10K+ users | Stage 2 | Score partner roster with Strategic Partner Matrix. Identify Tier C candidates. |
| Early 2028 | 25K+ users | Stage 2 -> 3 gate | Launch Partner API. Begin Tier C onboarding. Send Template G to prospects. |
| Mid-2028 | 50K+ users | Stage 3 -> 4 gate | Launch marketplace console. Invite premium partners. Send Template H. |

---

## 9. How to Use the AI Partnerships Persona

In Cursor, when you need partnership support, invoke the partnerships.mdc persona by referencing it in your prompt. It can:

- **Draft an outreach email:** "Draft an outreach email to Wealthfront's affiliate team introducing FileFree."
- **Prep a call:** "Prepare a call brief for our Column Tax demo on Wednesday."
- **Research a partner:** "Research Lemonade's affiliate program — pricing, terms, application process."
- **Generate a pipeline update:** "Generate a weekly pipeline status summary from the current hit list."
- **Review terms:** "Review these partnership terms and flag anything non-standard."

Every output is designed to be actionable in 5-10 minutes. If something needs heavy editing, the persona isn't doing its job.

---

## Appendix: Glossary

| Term | Meaning |
|---|---|
| Affiliate network | Platform (Impact, CJ Affiliate) that connects publishers (us) with advertisers (Marcus, etc.). Handles tracking, attribution, payouts. |
| Publisher | Us — the company that refers users to a partner's product |
| Funded account | A user who opens AND deposits money into a partner account. This is what triggers the payout. |
| Attach rate | % of our users who take the recommended action (open a HYSA, buy audit shield, etc.) |
| ARPU | Average Revenue Per User — total revenue divided by total users |
| Rev share | Revenue sharing — we get a cut of revenue the partner earns from our referral |
| Form 8888 | IRS form that lets filers split their refund into up to 3 bank accounts. This is the mechanism for refund routing. |
| Refund Plan screen | The screen users see after their refund is calculated. This is where partner recommendations appear. |
| MeF transmitter | IRS system for electronic tax filing. We're building our own (target: January 2027). |
| Column Tax | Our interim e-file partner until our own transmitter is certified. |
