# Founder Side Projects Evaluation

**Owner**: Strategy + CFO agents
**Last updated**: March 2026
**Purpose**: Evaluate founder's existing side projects for viability as venture products, trinkets, or shelved ideas.

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

## Summary

| Project | Verdict | Timing | Notes |
|---|---|---|---|
| Axiomfolio | DEFER | Year 2+ | High alignment but needs Plaid investment. Revisit as Tax Optimization Plan premium feature. |
| ReplyRunner | NO-GO | N/A | Low alignment, commodity market, no differentiation. |
| Jointly | DEFER | Year 2+ | Good alignment, underserved market, but Plaid + UX complexity. Explore as FileFree household feature. |
| FittingRoom | NO-GO | N/A | Zero alignment, very high complexity, Big Tech competitors. |

**Recommendation**: Focus entirely on FileFree + LaunchFree + Trinkets for Year 1. Axiomfolio and Jointly become Year 2+ candidates once the core venture has revenue and user traction to justify Plaid costs and expanded product surface area.
