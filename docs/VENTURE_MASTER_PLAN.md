> **Source of truth**: This file (`docs/VENTURE_MASTER_PLAN.md`) is the authoritative copy. The `.cursor/plans/` copy may be stale. All edits should happen here and be committed to git.

# Venture Master Plan v1

**Date**: March 12, 2026 | **Supersedes**: All prior strategy plans including deep_research_tightening (5 plans archived)

---

## 0. Venture Overview

**Model**: One human + AI agent workforce + partnerships co-founder (2-3 hrs/wk)

**Products**:

- **LaunchFree** (launchfree.ai) -- Free LLC formation service ($0 service fee; user pays state filing fees only, disclosed upfront). AI-powered 50-state comparison helps users pick the cheapest, best-fit state. Revenue: RA credits, banking/payroll/insurance referrals. Launches Summer 2026.
- **FileFree** (filefree.ai) -- Free tax filing. Revenue: refund routing, financial referrals, audit shield, Tax Opt Plan. Launches January 2027.
- **Trinkets** (tools.filefree.ai) -- Collection of simple utility tools (financial calculators, converters, generators). Revenue: AdSense + cross-sell to main products. Complexity: LOW. Built as `apps/trinkets/` in monorepo. See Section 0F.

**HQ**: sankalpsharma.com -- Venture command center, admin dashboard, agent monitor, cross-sell campaigns.

**Entity**: Single California LLC with DBA for each brand. Name TBD (founder researching -- see Section 0B). California chosen over Wyoming because founder is a CA resident (see Section 0B for full comparison). See Section 0B for naming research and legal structure.

**Trademark status**: "FILEFREE" and "LAUNCHFREE" to be filed on USPTO Supplemental Register. See Section 0C for full trademark and legal risk framework.

**Domains purchased**: filefree.ai, launchfree.ai (March 2026). Existing: filefree.tax, sankalpsharma.com.

**AI Model Strategy**: 9 models across 7 roles. See Section 0E for authoritative routing registry (owned by AI Ops Lead persona).

**Monthly burn**: ~$46/mo (Hetzner $6 + Render x2 $14 + Google Workspace $6 + domains ~$20 + OpenAI ~$10). Vercel/Neon/Upstash all free tier.

---

## 0B. LLC Naming: Research-Backed Decision

### The Question

Should the parent LLC be "Sharma Ventures LLC" (personal) or a branded name?

### Research Findings

**Against personal names in holding companies:**

- Investors perceive branded names as more scalable and strategic ([source: TechBullion](https://techbullion.com/how-business-naming-affects-investor-perception-and-market-value/))
- Personal-name LLCs signal "small operation" and give no indication of what the business does ([source: TaxSharkInc](https://taxsharkinc.com/can-you-make-your-name-an-llc/))
- Harder to sell or bring in investors -- the brand is tied to one person
- Privacy: your full legal name is now on every state filing, partnership agreement, and public record

**For personal names:**

- Simple, authentic, no naming research needed
- Common pattern for personal brand ventures (think: "Bezos Expeditions", "Thiel Capital")
- BUT those are billionaire investment vehicles, not product companies

**Real examples of multi-product tech holding companies:**

- Oktopii (creative tech holding)
- Upsilon Holdings (AI product studio)
- Rexmore (AI-native holding company)
- Q6 Technology Holdings (multi-product AI)
- None of them use founder names.

### Naming Criteria for Our LLC

1. **Abstract/brandable** -- no one needs to know or care what the parent LLC is called
2. **Not confusable** with any product name (not "FreeSoft LLC" or "FileLaunch LLC")
3. **Short** -- you'll type this on contracts, bank forms, invoices
4. **Available** in California (check: bizfileonline.sos.ca.gov)
5. **Domain not needed** -- this entity never faces the public. `sankalpsharma.com` is the public HQ.
6. **Neutral** enough to hold future products beyond tax/formation

### Status: NAME TBD (Founder Researching Separately)

The founder's almost-three-year-old daughter's favorite word is "toast," inspiring toast-themed name exploration. Multiple rounds of research have narrowed the field. Key findings that ruled out options:

**Toast Inc conflict**: Toast Inc (NYSE: TOST, $25B market cap) owns 28 USPTO trademarks including "TOAST" (Class 009). They sued "Toast Labs, Inc." in January 2016 (SDNY, Case 1:16-cv-00168), dismissed March 2016 (likely settlement). Any "Toast [X]" name carries medium-to-high risk of cease & desist.

**"Butters" slang**: "Butterside Labs" was a leading candidate until research revealed "butters" is British slang for "ugly/unattractive" ([Cambridge Dictionary](https://dictionary.cambridge.org/dictionary/english/butters)). Low risk for a holding company but unnecessary baggage.

**Names still under consideration** (no existing companies found for any):


| Name               | Vibe                                             | Risk     |
| ------------------ | ------------------------------------------------ | -------- |
| **Toastworks LLC** | Toast + "we build things." No slang issue.       | Very Low |
| **Halftoast LLC**  | Playful, "work in progress" energy.              | Very Low |
| **Crisp Labs LLC** | Toast gets crisp. "Crisp" = clean/sharp in tech. | Very Low |


**Key decision**: The holding company does NOT need a matching domain. Products have their own domains. The LLC name appears only on legal docs, privacy policies, bank accounts, and tax returns. Never customer-facing.

Founder is exploring additional options via separate brainstorming session. Name will be confirmed before LLC filing (Phase 0.6).

### Structure (Confirmed -- California LLC)

**Why California, not Wyoming (DECIDED March 2026)**:

The original plan recommended Wyoming. After analysis, California is the clear choice for a CA-resident founder:

| Factor | Wyoming | California |
|---|---|---|
| Filing fee | $100 | $70 |
| Annual report | $60/yr | $0 (no annual report required) |
| Franchise tax | $0 (but CA charges you anyway since founder is CA resident) | $800/yr (first year exempt for new LLCs) |
| RA cost | $25-29/yr | $49-125/yr |
| Privacy | Excellent (no owner disclosure) | Poor (public disclosure required) |
| Foreign registration in CA | Required (~$70 extra) | Not needed |
| Asset protection | Strong (charging order protection for single-member) | Weak |
| **Year 1 total** | **~$1,094** (with CA foreign reg + franchise tax) | **~$119** (first year franchise exempt) |
| **Year 2+ total** | **~$985/yr** | **~$849/yr** |

**Bottom line**: Wyoming's $0 income tax doesn't help a CA resident -- California taxes all your income regardless of where the LLC is formed. Wyoming would require foreign LLC registration in CA ($70), double RA fees, and double compliance. The only real Wyoming advantages (privacy, charging order protection) don't justify ~$975/yr extra pre-revenue.

**Revisit trigger**: When revenue exceeds $250K and asset protection justifies dual-state cost, consider Wyoming holding company with CA subsidiary.

**Now (pre-revenue):** Single California LLC + DBA filings for "FileFree", "LaunchFree", and "Trinkets"

- California filing: $70
- DBA filing: ~$10-25 per name
- Franchise tax: $0 first year (exempt for new LLCs), $800/yr after
- RA: ~$49/yr
- Total year 1: ~$119-145

**At $50K+ combined revenue:** Convert to holding company structure

- Parent LLC ([TBD] or chosen name) stays as-is
- Create FileFree LLC (subsidiary)
- Create LaunchFree LLC (subsidiary)
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
| FILEFREE (logo/design mark)    | Class 036, Class 042                                      | Supplemental Register | $350 x 2 = $700 | File with wordmark, separate application         |
| Total                          |                                                           |                       | ~$2,100         | All within 90 days of launch                     |


After 5 years of commercial use: petition to move to Principal Register with evidence of acquired distinctiveness (user counts, media coverage, brand recognition surveys).

### STRICT LEGAL GUIDELINES (All Personas Must Follow)

**Brand Name Rules:**

1. ALWAYS write "FileFree" (one word, two capital F's). NEVER "File Free", "file free", "Filefree", "FILE FREE", "File-Free"
2. ALWAYS write "LaunchFree" (one word, L and F capitalized). NEVER "Launch Free", "launch free", "Launchfree"
3. When used in a sentence, the brand name is a PROPER NOUN: "FileFree helps you file taxes" (not "file free with FileFree")
4. NEVER use "file free" as a verb phrase in marketing copy. Say "file your taxes for free" or "file at zero cost" -- keep the brand name and the concept separate
5. Domain references: always `filefree.tax` or `filefree.ai` -- NEVER reference `filefree.com` anywhere, ever

**FTC "Free" Compliance Rules:**

1. Our service IS actually free for ALL users. This is our strongest legal position. The moment we add a condition that makes filing not-free for some users, we are exposed to the EXACT FTC action that hit Intuit
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

1. Opt-in checkbox (unchecked by default) on every signup form: "I'd like to hear about other [LLC Name] products"
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

---

## 0D. Valuation Estimate (Realistic)

### Comparable Companies


| Company              | Revenue       | Valuation                             | Multiple      | Model                                     | Notes                                   |
| -------------------- | ------------- | ------------------------------------- | ------------- | ----------------------------------------- | --------------------------------------- |
| Credit Karma         | ~$1B (2019)   | $7.1B (2020 acq)                      | 7.1x revenue  | Free credit scores, referral monetization | Closest model comp to FileFree          |
| LegalZoom            | $751M LTM     | $994M EV (2026)                       | 1.3x revenue  | LLC formation + compliance, $79-299/pkg   | Public, mature, compressed multiple     |
| ZenBusiness          | Est. $200M+   | $1B+ (last raise)                     | ~5x revenue   | LLC formation, $0-349/pkg                 | VC-backed                               |
| Formation Nation     | Est. $20-30M  | $49M cash + $15M earnout + $50M stock | ~3-4x revenue | LLC formation (Inc Authority brand)       | Acquired by LegalZoom Feb 2025          |
| FreeTaxUSA (TaxHawk) | Est. $50-100M | Private (est. $200-500M)              | ~4-5x est.    | Free federal, $15 state                   | Bootstrapped since 2001, ~150 employees |


### Our Venture Valuation Scenarios

**Valuation Method**: EV/Revenue multiple. For bootstrapped fintech with AI, current market range is 4-8x revenue for growth-stage, 2-4x for early-stage ([source: Finro, WindsorDrake Q1 2026](https://www.finrofca.com/news/fintech-valuation-mid-2025)).

**Scenario A: Conservative (Year 2, Combined ~$100K revenue)**

- Multiple: 3-5x (early-stage bootstrapped)
- Valuation: $300K-500K
- Context: Pre-traction, product live but small user base

**Scenario B: Moderate (Year 3, Combined ~$500K revenue, 50K+ users)**

- Multiple: 5-8x (growth-stage fintech with AI + cross-sell)
- Valuation: $2.5M-4M
- Context: Proven unit economics, two products cross-selling, 50K+ combined users

**Scenario C: Aggressive (Year 4-5, Combined ~$2M revenue, 200K+ users)**

- Multiple: 6-10x (scaled fintech platform)
- Valuation: $12M-20M
- Context: MeF transmitter live ($0/return moat), 50-state coverage, proven referral revenue
- Acquisition interest from: LegalZoom (cross-sell), Intuit (competitive threat removal), fintech aggregators

**Scenario D: Home Run (Year 5+, Combined ~$5M+ revenue, 500K+ users)**

- Multiple: 8-12x (if "AI financial advisor" narrative takes hold)
- Valuation: $40M-60M
- Context: Credit Karma playbook proven at smaller scale, AI advisory relationship established
- This requires: partnership revenue firing on all cylinders, advisory product retention, brand trust at scale

**The Formation Nation Acquisition is the most relevant comp**: LegalZoom paid ~$115M total (cash + stock + earnout) for a business formation company. If LaunchFree reaches ~$5-10M revenue with a free acquisition channel and cross-sell to FileFree, a similar acquisition outcome ($50-100M) is realistic in the 5-7 year timeframe.

**What makes our valuation story unique**: Two products with shared infrastructure and cross-sell moat. Each product individually is worth 3-5x revenue. Together with cross-sell data and AI advisory relationship, the portfolio premium could push multiples to 8-12x. This is the Credit Karma playbook: the platform IS the data, and the data compounds with every user.

---

## 0E. AI Model Routing Strategy (Authoritative -- Owned by AI Ops Lead)

**Last reviewed**: March 12, 2026 | **Next review**: April 12, 2026

### Routing Principle

Use the cheapest model that can do the job accurately. Escalate only when the task demands it. The AI Ops Lead persona (`agent-ops.mdc`) owns this registry and all model routing decisions. Engineering implements but does not choose models.

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


| Workflow                   | Model            | Tier | Why                                           | ~Cost/Run |
| -------------------------- | ---------------- | ---- | --------------------------------------------- | --------- |
| State data structuring     | GPT-4o-mini      | 1    | Cheapest Zod schema mapping                   | $0.001    |
| State data deep validation | Gemini 2.5 Pro   | 2    | 1M context, #1 Arena, 50% cheaper than Sonnet | $0.01     |
| State fee lookups          | Gemini 2.5 Flash | 1.5  | Simple lookup, 90% cheaper than Sonnet        | $0.001    |
| Formation guidance AI      | Claude Sonnet    | 2A   | UPL compliance, cautious framing              | $0.01     |
| Operating agreement gen    | Claude Sonnet    | 2A   | Legal document, precision matters             | $0.03     |


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


**Cross-Sell & Marketing**


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
apps/trinkets/                  (Next.js SSG, Vercel free)
  src/app/
    mortgage-calculator/page.tsx
    compound-interest/page.tsx
    savings-goal/page.tsx
    budget-planner/page.tsx
  src/components/
    tool-layout.tsx              (shared: header, ad slots, footer)
    seo-head.tsx                 (per-tool JSON-LD, meta tags)
    ad-unit.tsx                  (Google AdSense)
```

All processing is browser-based (pdf-lib, heic2any, browser-image-compression, qrcode.js). Zero server cost. Zero backend needed.

### Build Timing

Phase 1.5: After monorepo restructure (Phase 1), before 50-state data pipeline (Phase 2). Time budget: 3-5 days. Then hands-off for 6 months while building main products. Check traffic at Month 6.

---

## 1. Revenue Model (Corrected)

### Timeline

- **H2 2026**: LaunchFree earns revenue (6 months post-launch)
- **Jan-Apr 2027**: FileFree first tax season (4 months, NOT a full year)
- **2028**: Cross-sell kicks in, at-scale attach rates

### FileFree First Tax Season (Jan-Apr 2027)


| Stream                | First-Season Attach Rate | Rev Per | 10K Filers | 20K Filers | 30K Filers |
| --------------------- | ------------------------ | ------- | ---------- | ---------- | ---------- |
| Refund routing HYSA   | 4%                       | $50     | $20K       | $40K       | $60K       |
| Financial referrals   | 1.5%                     | $75     | $11K       | $22.5K     | $34K       |
| Audit Shield          | 5% (if partner ready)    | $20     | $10K       | $20K       | $30K       |
| Tax Optimization Plan | 2%                       | $29     | $5.8K      | $11.6K     | $17.4K     |
| Refund advance        | 0% (not ready Y1)        | --      | $0         | $0         | $0         |
| **TOTAL**             |                          |         | **$47K**   | **$94K**   | **$141K**  |


### LaunchFree H2 2026 (~6 months)


| Stream                     | Volume  | Rev Per | Total        |
| -------------------------- | ------- | ------- | ------------ |
| RA credits (3% buy $49/yr) | 60-150  | $49     | $3K-7K       |
| Banking referrals (5%)     | 100-250 | $50     | $5K-12.5K    |
| Payroll referrals (1%)     | 20-50   | $100    | $2K-5K       |
| **TOTAL**                  |         |         | **$10K-25K** |


### Combined


| Scenario     | LaunchFree (H2 2026) | FileFree (Jan-Apr 2027) | **Total** |
| ------------ | -------------------- | ----------------------- | --------- |
| Conservative | $10K                 | $47K                    | **$57K**  |
| Moderate     | $18K                 | $94K                    | **$112K** |
| Aggressive   | $25K                 | $141K                   | **$166K** |


**Year 2 (2028)**: $300K-600K (80% retention + growth + at-scale attach rates + cross-sell)

### LaunchFree "Free" Framing (Honest, Defensible)

**What's actually free (our service -- $0 forever)**:

- LLC formation filing (prep + submit): $0
- Operating agreement (AI-generated, state-specific): $0
- EIN filing walkthrough: $0
- Compliance calendar + reminders: $0
- 50-state comparison AI guide (compares filing fees, annual costs, franchise tax, privacy, speed): $0

**What's NOT free (government fees -- clearly disclosed upfront)**:

- State filing fee: $35-$500 (depends on state)
- We help users find the cheapest legitimate option for their situation

**Cheapest states to form** (marketing content):

| State | Filing Fee | Annual Cost | Notes |
|---|---|---|---|
| Montana | $35 | $20/yr | Cheapest filing in the US |
| Kentucky | $40 | $15/yr | Low ongoing costs |
| Arkansas | $45 | $150/yr | Higher annual |
| Colorado | $50 | $10/yr | Very low annual |
| Arizona | $50 | $0/yr (no annual report) | No ongoing state cost |
| Michigan | $50 | $25/yr | Moderate |

**Framing language** (use across all marketing):

> "LaunchFree handles the paperwork for $0. You only pay what your state charges -- and we'll help you pick the most affordable one."

**The differentiator**: Competitors (LegalZoom $149+, ZenBusiness $0+$199 upsells, Northwest $39) either charge service fees, bury state fees in the total, or upsell aggressively. LaunchFree's AI state comparison guide is unique -- no competitor helps you choose which state to form in based on your actual situation (home state, business type, budget, privacy needs). This is the moat.

**Competitive comparison**:

| Service | Service Fee | Upsells | State Fee Transparency | State Comparison |
|---|---|---|---|---|
| LegalZoom | $0-$299 | Heavy ($199 RA, $159 operating agreement, $159 EIN) | Buried in total | No |
| ZenBusiness | $0 | Heavy ($199/yr Pro, $349/yr Premium) | Shown separately | No |
| Northwest | $39 | Moderate ($125/yr RA included Y1) | Shown separately | No |
| Incfile | $0 | Heavy ($149-$349 bundles) | Shown separately | No |
| **LaunchFree** | **$0** | **None (revenue from partner referrals)** | **Upfront, before you start** | **Yes (AI-powered, all 50 states)** |

### Audit Shield Economics

- **What**: Prepaid IRS audit representation via Enrolled Agent/CPA. Covers defense costs (up to $1M), not taxes owed. 3-year federal coverage.
- **White-label partner**: TaxAudit / Protection Plus (same provider FreeTaxUSA, TaxAct, TurboTax use)
- **Our cost**: $10/return (firm-level wholesale)
- **Our price**: $19-24 (match FreeTaxUSA as low-cost leader)
- **Margin**: $9-14/sale (47-58% gross margin)
- **Attachment rate**: 5-8% first season, 10-15% at scale
- **Action**: Add TaxAudit partnership to Founder 2 pipeline (3-6 month lead time)

---

## 2. Architecture

### Monorepo (pnpm workspaces, no Turborepo)

```
venture/
  apps/
    filefree/            (filefree.ai -- Next.js, existing code from web/)
    launchfree/          (launchfree.ai -- Next.js, scaffolded)
    studio/              (sankalpsharma.com -- Next.js, COMMAND CENTER)
    trinkets/            (utility tools -- Next.js SSG, Vercel free, Phase 1.5)
  packages/
    ui/                  (22 shadcn components + theme + chat widget)
    auth/                (shared auth: hooks, middleware, session)
    analytics/           (PostHog + attribution + PII scrubbing)
    data/                (50-state formation + tax data + engine)
    cross-sell/          (recommendation engine, campaign triggers)
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

**How SSO works**: User signs up on FileFree -> FileFree creates its local user -> event fires to studio -> studio creates/updates venture_identity -> if user later signs up on LaunchFree with same email -> LaunchFree creates its local user, sends event -> studio links both product accounts to one venture_identity.

**If FileFree is acquired**: Remove the `venture_identity_id` column. FileFree still works independently. The buyer gets a complete product with its own user system.

### Cursor Workspace Scoping

The monorepo supports focused AI context by opening specific directories as Cursor workspaces:

- **Working on LaunchFree frontend**: Open `apps/launchfree/` as workspace root
- **Working on FileFree frontend**: Open `apps/filefree/` as workspace root
- **Working on shared packages**: Open `packages/` as workspace root
- **Working on infrastructure or cross-cutting**: Open repo root `venture/`

Each `apps/` and `apis/` directory can have its own `.cursor/rules/` with product-specific personas.

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

| Service | Port | Notes |
|---|---|---|
| **Frontends** | | |
| apps/filefree | 3001 | Next.js `--port 3001` |
| apps/launchfree | 3002 | Next.js `--port 3002` |
| apps/trinkets | 3003 | Next.js `--port 3003` |
| apps/studio | 3004 | Next.js `--port 3004` |
| **Backends** | | |
| apis/filefree | 8001 | uvicorn `--port 8001` |
| apis/launchfree | 8002 | uvicorn `--port 8002` |
| apis/studio | 8003 | uvicorn `--port 8003` |
| **Infrastructure** | | |
| PostgreSQL | 5432 | Default (shared, schema-isolated) |
| Redis | 6379 | Default (shared, key-prefixed) |

**Environment variables per app**: Each frontend sets `NEXT_PUBLIC_API_URL=http://localhost:800X` matching its backend.

**Dev commands** (root `package.json` scripts via pnpm):

| Command | What It Starts | Use Case |
|---|---|---|
| `pnpm dev:filefree` | 3001 + 8001 | Working on FileFree |
| `pnpm dev:launchfree` | 3002 + 8002 | Working on LaunchFree |
| `pnpm dev:trinkets` | 3003 (no backend) | Working on Trinkets (client-side only) |
| `pnpm dev:studio` | 3004 + 8003 | Working on Studio |
| `pnpm dev:all` | All ports | Cross-product testing |

Each dev command uses `concurrently` to start both frontend and backend. Trinkets has no backend (all client-side processing). `pnpm dev:all` starts everything for integration testing.

---

## 3. sankalpsharma.com: The Command Center (Detailed Spec)

The command center is the control plane for the entire venture. It is what makes the "one human + AI agents" model operationally viable. 13 admin pages organized in 3 tiers based on operational priority.

### Tier 1 -- Build First (enables daily operations)

**P4.1 Studio Landing Page** (`/` -- public)

- Hero: Name, one-liner ("I build AI-powered tools that make adulting free"), photo/avatar
- Portfolio: Cards linking to LaunchFree and FileFree with descriptions
- Footer: social links, email
- Data source: Static

**P4.2 Admin Auth** (`/admin/`* -- protected)

- Hardcoded admin email check (no role system needed for one human)
- Auth via shared `packages/auth/`

**P4.3 Studio-API Scaffold** (Backend)

- FastAPI on Hetzner CX33 (shared with n8n, Postiz)
- Aggregator backend: pulls data from all external APIs (Render, Vercel, n8n, PostHog, Stripe)
- PostgreSQL for venture_identities, user_events, campaigns

**P4.4 Mission Control Dashboard** (`/admin`)

- Activity feed: live terminal-style log of all agent actions (monospace, auto-scroll, new entries from top)
- Summary cards: total users, revenue this month, active agents, uptime
- Quick links to each product's admin
- Data sources: n8n executions, Render health, Vercel deployments, PostHog events, Stripe revenue

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

**P4.11 Revenue Intelligence** (`/admin/revenue`)

- Stripe revenue by product, stream, time period
- Affiliate revenue from partner dashboards
- MRR, churn, ARPU calculations
- Data source: Stripe API + affiliate dashboard APIs

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

### UX Guidelines (Admin)

- Use shadcn Table components for all list views. No custom data grid libraries.
- Use Recharts (already in stack) for trend charts. Keep to 3 chart types: line, bar, pie.
- No animations or transitions in admin pages. Instant renders.
- Every page loads in <1 second. React Query with aggressive caching (staleTime: 60s for most data, 5s for health checks).
- Activity Feed is the most important UX element -- feels like a live terminal.
- Mobile responsive is nice-to-have, not required.

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
// packages/data/sources/registry.ts
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
// packages/data/engine/index.ts
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

### 4B. Data Model

```
venture_identities: id, email, name, created_at
identity_products: venture_identity_id, product, product_user_id, first_used
user_events: id, venture_identity_id, event_type, product, metadata, timestamp
user_segments: venture_identity_id, segment, computed_at
user_financial_profile: venture_identity_id, income_bracket, filing_status, has_biz_income,
                        state, refund_amount_bracket, partner_interests[], updated_at
campaigns: id, name, segment_target, message_template, channel, status, schedule
campaign_events: id, campaign_id, venture_identity_id, event_type, timestamp
recommendations: id, venture_identity_id, partner_product, score, status, created_at
recommendation_outcomes: id, recommendation_id, outcome_type, revenue_cents, timestamp
```

### 4C. Event Taxonomy (Exhaustive)

Every user action that has intelligence value is captured as a UserEvent. Events are immutable (append-only log).

```
ACQUISITION EVENTS:
  signup                    -- product, source (organic/referral/paid/social), utm_params
  signup_source_attributed  -- final attribution after dedup
  referral_click            -- referrer_id, referred_product

FILEFREE EVENTS:
  w2_uploaded               -- document_id, upload_method (camera/file)
  w2_ocr_completed          -- document_id, confidence_score, field_count
  w2_manual_edit            -- document_id, field_name (signals OCR quality)
  filing_started            -- filing_id, filing_status_type
  filing_completed          -- filing_id, refund_or_owed, amount_cents
  refund_routing_selected   -- routing_type (direct_deposit/hysa/ira)
  pdf_downloaded            -- filing_id
  efile_submitted           -- filing_id, transmitter (column_tax/own_mef)
  efile_accepted            -- filing_id, acceptance_date
  partner_cta_viewed        -- partner_id, placement (refund_plan/dashboard/email)
  partner_cta_clicked       -- partner_id, placement
  partner_signup_completed  -- partner_id, estimated_revenue_cents
  tax_opt_plan_purchased    -- plan_tier, amount_cents
  tax_opt_plan_cancelled    -- plan_tier, reason

LAUNCHFREE EVENTS:
  state_selected            -- state_code, is_home_state
  name_search_started       -- query_text
  name_available            -- query_text, state_code
  formation_started         -- formation_id, state_code, entity_type
  formation_completed       -- formation_id, total_cost_cents
  ra_purchased              -- formation_id, ra_provider, annual_cost_cents
  ra_credit_earned          -- credit_type, amount_cents
  operating_agreement_generated -- formation_id
  ein_filing_started        -- formation_id
  compliance_calendar_viewed -- formation_id
  banking_cta_clicked       -- partner_id (Mercury, Relay, etc.)
  payroll_cta_clicked       -- partner_id (Gusto, etc.)
  insurance_cta_clicked     -- partner_id

TRINKETS EVENTS:
  tool_used                 -- tool_slug, input_params_hash (no PII)
  tool_result_viewed        -- tool_slug, time_on_page_ms
  cross_sell_cta_clicked    -- tool_slug, target_product

CROSS-PRODUCT EVENTS:
  cross_product_opt_in      -- source_product, consent_timestamp
  cross_product_opt_out     -- source_product
  email_sent                -- campaign_id, template_id
  email_opened              -- campaign_id
  email_clicked             -- campaign_id, link_id
  email_unsubscribed        -- campaign_id
  in_app_notification_shown -- notification_id
  in_app_notification_clicked -- notification_id
```

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


**Year 2 expansion (basic ML with enough data)**:

- Propensity scoring: predict likelihood of cross-product adoption
- Churn prediction: identify users likely to abandon before they do
- Partner match scoring: rank partner products by predicted conversion per user profile

**Year 3 (predictive, proactive)**:

- "Based on your tax profile, you could save $X by forming an LLC before year-end"
- "Users with your income and filing status typically benefit from a HYSA. Here's why."
- Seasonal predictions: anticipate tax season behavior based on prior year patterns

### 4E. Recommendation Engine Logic

The engine is a rules-based pipeline: `(segment + milestone + timing + consent) -> action`.

```
RULE 1: Post-Filing LLC Cross-Sell
  IF segment = "filed_taxes_no_llc"
     AND income > 50000
     AND has_1099_income = true
     AND days_since_filing > 14
     AND cross_product_opted_in = true
  THEN action: send_email
       template: "biz_income_llc_nudge"
       delay: 72h after filing completion
       expected_conversion: 3-5%
       estimated_revenue: $0 (free formation) but enables RA + partner revenue

RULE 2: Refund HYSA Recommendation
  IF event = "filing_completed"
     AND refund_amount > 50000 (cents = $500)
     AND refund_routing != "hysa"
  THEN action: show_in_app_recommendation
       template: "refund_hysa_card"
       placement: refund_plan_screen
       delay: immediate (show during filing flow)
       expected_conversion: 8-12%
       estimated_revenue: $25-50 per signup (HYSA affiliate)

RULE 3: Post-Formation Tax Cross-Sell (Seasonal)
  IF segment = "has_llc_no_taxes"
     AND month IN [11, 12, 1, 2, 3]
     AND cross_product_opted_in = true
  THEN action: send_email
       template: "llc_tax_season_nudge"
       delay: January 15 (filing season start)
       expected_conversion: 5-8%

RULE 4: Abandoned Formation Recovery
  IF event = "formation_started"
     AND no "formation_completed" within 48h
  THEN action: send_email
       template: "formation_almost_done"
       delay: 48h after start
       followup: 7 days later if still incomplete
       expected_conversion: 15-25%

RULE 5: RA Credit Upsell
  IF event = "ra_purchased"
     AND ra_credits_earned = 0
     AND days_since_ra_purchase > 7
  THEN action: send_email
       template: "earn_ra_credits"
       delay: 7 days
       expected_conversion: 10-15%
```

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


### 4H. Cross-Product Consent

- Opt-in checkbox (unchecked by default) on every signup form
- Consent stored per user, per product, with timestamp
- Cross-product emails only sent to users who explicitly opted in
- Single unsubscribe covers all brands (same legal entity)
- Consent audit trail maintained for CCPA/GDPR compliance
- Re-consent required if privacy policy materially changes

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

| Step | What Happens | Content Hook (TikTok/IG/X) | Emotion |
|---|---|---|---|
| 1. Choose a name | Search CA SOS business database, discover your name is taken, try 5 more | "I tried to name my company and California said no. 5 times." | Frustration -> relatability |
| 2. File Articles of Org | Fill out Form LLC-1 on CA SOS website, pay $70 | "Starting an LLC costs $70 in California. Here's the 3-minute form nobody shows you." | Demystification |
| 3. Wait for approval | CA SOS processing time (can be weeks) | "Day 1 vs Day 14 of waiting for California to approve my LLC..." | Anticipation |
| 4. Get an EIN | IRS.gov, free, takes 5 minutes online | "The IRS gave me a tax ID in 5 minutes. For free. Why does anyone pay $70 for this?" | Outrage at upsellers |
| 5. Operating Agreement | Write one (or use a template, or AI generates it) | "LegalZoom charges $99 for this document. I had AI write mine in 30 seconds." | Product demo moment |
| 6. Registered Agent | Set up RA service | "Your LLC needs a 'registered agent.' Here's what that actually means (and why it costs $49-249/yr)." | Education |
| 7. Statement of Info | File LLC-12 within 90 days of formation | "90 days after forming your LLC, California wants MORE paperwork. Here's what to do." | Compliance awareness |
| 8. Business bank account | Apply at Mercury/Relay/local bank | "I opened a business bank account in 10 minutes. From my phone." | Partner demo moment |
| 9. Franchise tax reality | Discover the $800/yr CA franchise tax | "Nobody told me California charges $800/yr just to EXIST as an LLC. Here's the workaround." | Shock -> education |
| 10. First year exempt | Discover first-year exemption | "Plot twist: your first year is actually FREE. Here's the fine print." | Relief |
| 11. Compliance calendar | Set up annual reminders | "The 5 dates every LLC owner needs to know. Miss one and your LLC gets dissolved." | Urgency |
| 12. DBA filing | File "Doing Business As" for brand names | "My LLC name isn't my brand name. Here's why you need a DBA (and what it costs)." | Practical |

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

## 6. Agent Architecture (Venture-Wide)

### 6A. The Problem: All Agents Are FileFree-Specific

All 12 Cursor personas and 6 n8n workflows were built for FileFree as a standalone product:

- `social.mdc` references @filefree handles, "Gen Z tax filing app"
- `brand.mdc` references filefree.tax domain, FileFree-specific colors
- `growth.mdc` references tax-specific SEO, TurboTax competition
- `partnerships.mdc` references HYSA referrals, tax partnerships only
- n8n workflows all output to FileFree-specific databases

Now that we're a venture with LaunchFree, Trinkets, and sankalpsharma.com, the agent architecture needs to be **product-aware, not product-locked**.

### 6B. Three-Tier Persona Model

Agents are organized into three tiers:

**Tier 1: Venture-Level Personas** (shared across all products, `alwaysApply` or broad globs)


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
| 10  | Tax Domain Expert           | `tax-domain.mdc`                                  | `apps/filefree/`**, `apis/filefree/**`, `packages/data/**/tax-*`           | IRS rules, brackets, MeF schemas                                                |
| 11  | CPA / Tax Advisor           | `cpa.mdc`                                         | `apps/filefree/**`                                                         | Tax advisory content quality                                                    |
| 12  | FileFree Social             | `filefree-social.mdc` (rename from `social.mdc`)  | `apps/filefree/**/social/**`                                               | FileFree content: @filefree handles, tax hooks, TurboTax positioning            |
| 13  | FileFree Growth             | `filefree-growth.mdc` (extract from `growth.mdc`) | `apps/filefree/**`                                                         | Tax-specific SEO, TurboTax competition keywords                                 |
| 14  | FileFree Brand              | `filefree-brand.mdc` (extract from `brand.mdc`)   | `apps/filefree/**`                                                         | Violet-indigo palette, FileFree voice                                           |
| 15  | **Formation Domain Expert** | `formation-domain.mdc` (NEW)                      | `apps/launchfree/`**, `apis/launchfree/**`, `packages/data/**/formation-*` | State LLC rules, RA requirements, annual report deadlines, entity types         |
| 16  | **LaunchFree Social**       | `launchfree-social.mdc` (NEW)                     | `apps/launchfree/**/social/`**                                             | LaunchFree content: @launchfree handles, formation hooks, LegalZoom positioning |
| 17  | **LaunchFree Growth**       | `launchfree-growth.mdc` (NEW)                     | `apps/launchfree/`**                                                       | Formation-specific SEO, "free LLC" keywords, LegalZoom/ZenBusiness positioning  |
| 18  | **LaunchFree Brand**        | `launchfree-brand.mdc` (NEW)                      | `apps/launchfree/`**                                                       | Teal-cyan palette, LaunchFree voice                                             |
| 19  | **Studio**                  | `studio.mdc` (NEW)                                | `apps/studio/`**                                                           | sankalpsharma.com portfolio/venture site, command center UX                     |


### 6C. Persona Split Specs

`**social.mdc` -> `filefree-social.mdc` + `launchfree-social.mdc**`:


| Attribute                       | filefree-social.mdc                                                           | launchfree-social.mdc                                                                 |
| ------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Handles                         | @filefree.tax, @filefreetax                                                   | @launchfree (TikTok, IG, X, YT)                                                       |
| Voice                           | Smart friend who makes taxes feel easy                                        | Smart friend who makes business formation feel easy                                   |
| Content pillars                 | Tax myths, W-2 explainers, refund tips, filing demos                          | LLC tips, state comparisons, compliance, RA explained                                 |
| Hook themes                     | Pain (TurboTax costs), curiosity (tax hacks), transformation (filed in 3 min) | Pain (LegalZoom costs), curiosity (LLC benefits), transformation (launched in 10 min) |
| Competitors to position against | TurboTax, H&R Block, FreeTaxUSA                                               | LegalZoom, ZenBusiness, GoDaddy, Northwest                                            |
| Compliance                      | Circular 230 (tax education only)                                             | UPL (formation services, not legal advice)                                            |
| Posting cadence                 | 7-10/week tax season, 2-3/week off-season                                     | 3-5/week consistent year-round                                                        |


`**brand.mdc` -> `filefree-brand.mdc` + `launchfree-brand.mdc**`:

- FileFree: violet-indigo palette (`from-violet-500 to-purple-600`), tax-anxiety-killing tone
- LaunchFree: teal-cyan palette (`from-teal-500 to-cyan-600`), entrepreneurial empowerment tone
- Shared: Inter + JetBrains Mono typography, dark mode default, same animation patterns

`**growth.mdc` -> `filefree-growth.mdc` + `launchfree-growth.mdc**`:

- FileFree: SEO targets "free tax filing", "file taxes online free", competitor comparison pages vs TurboTax
- LaunchFree: SEO targets "free LLC formation", "how to start an LLC", state-specific landing pages, competitor comparisons vs LegalZoom/ZenBusiness

### 6D. Current Agents (18 -- Already Built)

12 Cursor personas + 6 n8n workflows:


| #     | Agent                                                                                           | Type                     | Status                                                  |
| ----- | ----------------------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------- |
| 1-12  | Engineering, UX, Growth, Social, Strategy, Legal, CFO, QA, Tax Domain, CPA, Partnerships, Brand | Cursor personas (.mdc)   | Active (FileFree-specific, pending venture-wide update) |
| 13-18 | Social Content, Growth Content, Strategy Check-in, Partnership Outreach, CPA Review, QA Scanner | n8n autonomous workflows | Active (output to Notion, pending GDrive migration)     |


### 6E. New Agents to Build (12+)


| #   | Agent                     | Type                  | Trigger           | Purpose                                                              |
| --- | ------------------------- | --------------------- | ----------------- | -------------------------------------------------------------------- |
| 19  | L1 Support (DocBot)       | n8n webhook           | User message      | Answer from knowledge base (60% resolution target)                   |
| 20  | L2 Support (OpsBot)       | n8n webhook           | DocBot escalation | Execute actions: check status, resend email, reset password          |
| 21  | State Data Validator      | n8n cron (monthly)    | 1st of month      | Check 50 state websites for fee/rule changes                         |
| 22  | IRS Update Monitor        | n8n cron (October)    | Annual            | Parse new Revenue Procedure for bracket changes                      |
| 23  | Competitive Intel         | n8n cron (weekly)     | Mondays           | Monitor LegalZoom/ZenBusiness/TurboTax pricing + features            |
| 24  | Analytics Reporter        | n8n cron (weekly)     | Sundays           | Pull PostHog data, generate weekly metrics report                    |
| 25  | Infra Health Monitor      | n8n cron (hourly)     | Continuous        | Check Render/Vercel/Hetzner status, alert on issues (see Section 7B) |
| 26  | Affiliate Revenue Tracker | n8n cron (daily)      | Daily             | Check affiliate dashboards, report conversions                       |
| 27  | LaunchFree Social Bot     | n8n cron (daily)      | 8am               | Draft LaunchFree social content for Postiz                           |
| 28  | LaunchFree Growth Bot     | n8n cron (weekly)     | Mondays           | Draft LaunchFree SEO articles                                        |
| 29  | LaunchFree Compliance Bot | n8n cron (monthly)    | 1st               | State filing deadline alerts for users                               |
| 30  | Knowledge Base Sync       | n8n cron (nightly)    | 2am               | Sync Google Drive docs to support agent context                      |
| 31  | AI Ops Lead               | Cursor persona (.mdc) | On demand         | Model routing, cost tracking, persona audits                         |
| 32  | Executive Assistant (EA)  | Cursor persona + n8n  | Daily cron + on-demand | Daily briefing, weekly planning, decision tracking, financial tracking, doc maintenance. See Section 6J1. |


### 6F. n8n Workflow Updates (Existing 6)


| #   | Workflow                     | Changes Needed                                                           |
| --- | ---------------------------- | ------------------------------------------------------------------------ |
| 1   | Social Content Generator     | Rename to `filefree-social-content`. Output to GDrive instead of Notion. |
| 2   | Growth Content Writer        | Rename to `filefree-growth-content`. Output to GDrive.                   |
| 3   | Weekly Strategy Check-in     | Expand to cover both products. Output to GDrive.                         |
| 4   | QA Security Scan             | Scan both APIs. Output to GitHub Issues (keep as-is).                    |
| 5   | Partnership Outreach Drafter | Add LaunchFree partners. Output to GDrive.                               |
| 6   | CPA Tax Review               | Keep FileFree-only. Output to GDrive.                                    |


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

Infra Health Monitor (hourly) --> email/Discord alerts
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

### 6I. Three-Layer Architecture

```
Layer 1: STRATEGY (Human)
  Founder -- decisions, code, legal filings
  Co-founder -- partnership relationships

Layer 2: EXECUTION (AI Agents)
  Cursor Personas (14 venture + 10 product = 24 total)
    -- code, strategy, legal, growth, brand, ops, domain expertise, EA
  n8n Autonomous (19 workflows)
    -- social, support, monitors, content, compliance, ops, EA daily/weekly

Layer 3: INFRASTRUCTURE
  Hetzner VPS (n8n, Postiz) | Vercel x4 (sites) | Render x2 (APIs)
  Google Workspace | OpenAI + Anthropic + Google APIs
```

**Total agent count post-restructure**: 24 Cursor personas + 19 n8n workflows = **43 agents** (up from 18)

### 6J. Agent Interaction Model

The founder needs a clear mental model for how to communicate with the AI workforce. Three interaction patterns:

**Pattern 1: CURSOR PERSONAS (interactive -- they join your conversation)**

How: Open a file matching a persona's glob pattern, or explicitly invoke by asking a relevant question.

| Action | What Happens |
|---|---|
| Open `apps/filefree/...` | Engineering + FileFree product personas activate |
| Ask "review this for legal compliance" | `legal.mdc` activates |
| Ask "what should I work on today?" | `ea.mdc` activates |
| Ask "is this model the right choice?" | `agent-ops.mdc` activates |
| Ask "log this decision: we chose California LLC" | `ea.mdc` logs to `docs/KNOWLEDGE.md` |

When: During coding/strategy sessions in Cursor IDE. These are your real-time collaborators.

**Pattern 2: N8N AUTONOMOUS WORKFLOWS (they work while you sleep)**

How: Run on cron schedules or webhook triggers. No founder action needed.

| Time | Workflow | Output Location | Founder Action |
|---|---|---|---|
| 2am daily | Knowledge Base Sync | Internal DB | None (background) |
| 7am daily | EA Daily Briefing | GDrive + Discord `#ops-alerts` | Read (5 min) |
| 8am daily | Social Content (FileFree + LaunchFree) | Postiz queue | Review/approve (5 min) |
| Hourly | Infra Health Monitor | Discord `#ops-alerts` (only on issues) | Act if alerted |
| Daily | Affiliate Revenue Tracker | GDrive report | Check weekly |
| Sunday 6pm | EA Weekly Planning | GDrive | Review and adjust (10 min) |
| Mondays | Competitive Intel + Growth Content | GDrive | Review at leisure |
| Monthly 1st | State Data Validator + Compliance Bot | GitHub Issues + user emails | Review issues |

Daily founder time: ~15-20 minutes reviewing agent outputs. Mostly reading briefings and approving social content.

**Pattern 3: ON-DEMAND N8N WORKFLOWS (you trigger them)**

How: n8n webhook URL, Discord slash command, or direct n8n execution.

| Command | What Runs | Output |
|---|---|---|
| `/trinket-discover [keyword]` | Market Discovery Agent: researches keyword, finds competitors, sizes opportunity | 1-pager in GDrive |
| `/support [user question]` | L1 DocBot: answers from knowledge base | Discord response |
| `/competitive-check` | Competitive Intel: immediate scan of competitor pricing/features | GDrive report |
| `/ea [question]` | EA agent: ad-hoc operational query | Discord response |

### 6J1. Executive Assistant Agent (#32) -- Detail Spec

The EA is the founder's most frequently used agent. It bridges Cursor (interactive) and n8n (autonomous).

**Dual implementation**: `.cursor/rules/ea.mdc` (Cursor persona) + `venture-ea-daily` / `venture-ea-weekly` (n8n workflows)

**What makes the EA different from other agents**: It has write access to documentation. When the founder makes a decision in any conversation, the EA logs it. When a phase task completes, the EA updates `docs/TASKS.md`. When money is spent, the EA updates `docs/FINANCIALS.md`.

**Documents owned by EA**:

| Document | Update Frequency | Trigger |
|---|---|---|
| `docs/KNOWLEDGE.md` | Per conversation | Founder makes a decision |
| `docs/TASKS.md` | Per task completion | Phase milestone hit |
| `docs/FINANCIALS.md` | Per expense | Domain purchase, subscription change |
| `docs/VENTURE_MASTER_PLAN.md` | Strategic changes only | Major direction shift |

---

## 7. Execution Phases

### Phase 0: Infrastructure (This Week)


| Task                         | Owner     | Details                                                                                                        |
| ---------------------------- | --------- | -------------------------------------------------------------------------------------------------------------- |
| P0.1 Buy domains             | Founder 1 | launchfree.ai + filefree.ai PURCHASED (March 2026). Consider launchfree.llc.                                   |
| P0.2 Migrate FileFree domain | Founder 1 | filefree.tax -> filefree.ai (Vercel, DNS, 301s)                                                                |
| P0.3 Google Workspace        | Founder 1 | Set up on sankalpsharma.com, add secondary domains, create aliases                                             |
| P0.4 Google Drive HQ         | Founder 1 | Create Venture HQ folder structure, add GDrive MCP to Cursor                                                   |
| P0.5 Secure social handles   | Founder 1 | @launchfree on TikTok, IG, X, YouTube                                                                          |
| P0.6 Form LLC                | Founder 1 | California LLC (name TBD -- founder deciding, see Section 0B). File DBAs for "FileFree", "LaunchFree", "Trinkets". See Section 0B for CA vs WY analysis. |
| P0.7 Migrate DNS subdomains  | Founder 1 | ops/social.sankalpsharma.com -> Hetzner (replace filefree.tax subdomains)                                      |
| P0.8 File trademarks         | Founder 1 | FILEFREE + LAUNCHFREE on USPTO Supplemental Register, Class 036+042 and Class 035+042 (~$2,100)                |
| P0.9 Legal compliance setup  | Founder 1 | Add Content Review Gate checklist to all persona .mdc files. Update privacy/terms per Section 0C.              |


### Phase 1: Monorepo Restructure (Week 2-3)


| Task                             | Details                                                                                                                                                                                                                      |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1.1 Init pnpm workspace         | Create root package.json, pnpm-workspace.yaml                                                                                                                                                                                |
| P1.2 Extract packages/ui         | Move 22 shadcn components + utils.ts + motion.ts. Add multi-brand theme system (Section 2 palettes): `themes.css` with `[data-theme]` selectors for filefree (violet-indigo), launchfree (teal-cyan), studio (zinc-neutral), trinkets (amber-orange) -- 4 themes |
| P1.3 Extract packages/auth       | Move use-auth, use-idle-timeout, api.ts, session-timeout-dialog                                                                                                                                                              |
| P1.4 Extract packages/analytics  | Move posthog.ts, attribution.ts, posthog-provider, providers                                                                                                                                                                 |
| P1.5 Move web/ -> apps/filefree/ | Update all imports to @venture/* packages                                                                                                                                                                                    |
| P1.6 Move api/ -> apis/filefree/ | Update paths in compose, render.yaml, Makefile                                                                                                                                                                               |
| P1.7 Scaffold apps/launchfree/   | Copy filefree structure, strip product-specific pages                                                                                                                                                                        |
| P1.8 Scaffold apis/launchfree/   | Copy base patterns (auth, repo, response envelope, config)                                                                                                                                                                   |
| P1.9 Scaffold apps/studio/       | Next.js app for sankalpsharma.com                                                                                                                                                                                            |
| P1.9b Scaffold apps/trinkets/    | Next.js SSG app, Vercel free tier, AdSense placeholder, tool-layout component                                                                                                                                                |
| P1.10 Update infra               | compose.dev.yaml, render.yaml, Makefile, CI for monorepo                                                                                                                                                                     |
| P1.11 Verify                     | `pnpm dev:filefree`, `pnpm dev:launchfree`, `pnpm dev:studio`, `pnpm dev:trinkets` all work                                                                                                                                  |


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
| P2.1 Create packages/data scaffold      | TypeScript types, Zod schemas (formation + tax), directory structure, state engine API                                                       |
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


### Phase 4: Command Center (Week 8-14, parallel with Phase 3)

The command center is the control plane for the entire venture. It is what makes the "one human + 37 agents" model operationally viable. Every page is spec'd in detail in Section 3.

**Tier 1 -- Build First (enables daily operations):**


| Task                           | Page                    | Data Sources                                            | Complexity |
| ------------------------------ | ----------------------- | ------------------------------------------------------- | ---------- |
| P4.1 Studio landing page       | `/` public              | Static                                                  | Low        |
| P4.2 Admin auth                | `/admin/`*              | Hardcoded admin email check                             | Low        |
| P4.3 Studio API scaffold       | Backend                 | FastAPI + Redis on Hetzner                              | Medium     |
| P4.4 Mission Control dashboard | `/admin`                | n8n + Render + Vercel + Hetzner + Stripe + PostHog APIs | High       |
| P4.5 Agent Monitor             | `/admin/agents`         | n8n API (workflows + executions)                        | Medium     |
| P4.6 Infrastructure health     | `/admin/infrastructure` | Render + Vercel + Hetzner + Neon + Upstash APIs         | Medium     |


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


| Task                                  | Details                                                                                         |
| ------------------------------------- | ----------------------------------------------------------------------------------------------- |
| P5.1 Venture identity data model      | VentureIdentity, IdentityProduct, UserEvent, UserSegment, Campaign, CampaignEvent tables        |
| P5.2 Cross-product opt-in consent     | "Receive recommendations from our other tools" checkbox (CAN-SPAM compliant, unchecked default) |
| P5.3 packages/cross-sell engine       | Rules-based recommendation engine: segments + milestones + timing -> action                     |
| P5.4 packages/email templates         | React Email templates: onboarding series + cross-sell + partner offers (Legal reviewed)         |
| P5.5 LaunchFree onboarding emails     | 5-email welcome series via n8n + Gmail (with cross-product opt-in respect)                      |
| P5.6 LaunchFree -> FileFree campaigns | Tax season blast, post-formation nudge (only for users who opted in)                            |
| P5.7 User event tracking              | Emit UserEvents from both products on key milestones (formed LLC, filed taxes, clicked partner) |
| P5.8 Campaign analytics + admin       | PostHog events, UTM tracking, campaign performance in admin dashboard                           |


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


| Task                                  | Details                                                         |
| ------------------------------------- | --------------------------------------------------------------- |
| P7.1 Resume FileFree Sprint 4         | All 50 state tax calcs (data already built in P2.3), PDF polish |
| P7.2 Column Tax integration           | SDK integration, sandbox testing                                |
| P7.3 TaxAudit partnership             | White-label audit shield integration (if Founder 2 closed deal) |
| P7.4 Refund Plan screen               | HYSA referrals, financial product recs, audit shield upsell     |
| P7.5 Transactional emails             | Welcome, filing confirmation, abandonment drip                  |
| P7.6 FileFree -> LaunchFree campaigns | Post-filing cross-sell for users with biz income                |
| P7.7 Marketing page refresh           | Social proof, filing counter, comparison table                  |


### Phase 8: FileFree Launch (January 2027)


| Task                          | Details                                                                            |
| ----------------------------- | ---------------------------------------------------------------------------------- |
| P8.1 MeF transmitter          | Build XML generator, pass IRS ATS testing (October), communication test (November) |
| P8.2 E-file go-live           | Switch from Column Tax to own transmitter for simple returns                       |
| P8.3 Tax Optimization Plan    | Stripe, $29/yr, premium dashboard                                                  |
| P8.4 Product Hunt + HN launch | Coordinate with filing season start                                                |
| P8.5 Paid amplification       | TikTok Spark Ads + Meta boost on winning organic content                           |


### Background Tasks (Continuous)


| Task                                 | Owner     | Timeline                                               |
| ------------------------------------ | --------- | ------------------------------------------------------ |
| EFIN application (Form 8633)         | Founder 1 | Apply NOW, 45-day processing                           |
| Column Tax partnership               | Founder 2 | Book demo, negotiate by June 2026                      |
| TaxAudit/Protection Plus partnership | Founder 2 | 3-6 month lead time, start Q2 2026                     |
| HYSA affiliate applications          | Founder 2 | Marcus, Wealthfront via Impact. Self-serve, apply now. |
| MeF certification prep               | Founder 1 | Start XML generator June, ATS testing October          |


### Phase Timeline Reality Check

The 8-phase plan spans infrastructure (now) through FileFree launch (January 2027). This is ambitious for one founder doing all engineering.

**Realistic adjustments**:

- Phases 0-1 (Infra + Monorepo): 3-4 weeks (not 2-3). Monorepo restructure is fiddly.
- Phase 1.5 (First Trinket): Can overlap with late Phase 1. +1 week buffer.
- Phase 2 (50-State Data): 3-4 weeks. AI extraction is fast but human review is the bottleneck.
- Phases 3-6 are NOT sequential -- they can run in parallel tracks:
  - **Track A** (product): Phase 3 LaunchFree MVP
  - **Track B** (operations): Phase 4 Command Center (Tier 1 only)
  - **Track C** (agents): Phase 6 Agent Restructure
  - Phase 5 (User Intelligence) requires both products to exist, so it follows Phase 3.
- October 2026 is a hard deadline for FileFree tax season prep (Phase 7).

**Buffer**: Add 2-week buffer between Phase 2 completion and October 2026. If behind schedule, Phase 4 Tier 2-3 and Phase 6 social pipeline are the first to defer.

### 7B. Alerting Strategy

The Infra Health Monitor (Agent #25) needs a clear alerting hierarchy:


| Severity | Condition                                                | Alert Channel                          | Response Time     |
| -------- | -------------------------------------------------------- | -------------------------------------- | ----------------- |
| CRITICAL | Render/Vercel DOWN, API 5xx rate >5%                     | Email + Discord webhook + SMS (Twilio) | Immediate         |
| WARNING  | API response time >2s, error rate >1%, disk >80%         | Email + Discord webhook                | Within 1 hour     |
| INFO     | Deploy completed, cron job finished, daily health report | Discord webhook only                   | Next business day |


**Alert routing**:

- All alerts go to a `#ops-alerts` Discord channel on the venture Discord server
- CRITICAL also sends email to founder + SMS via Twilio ($0.0075/SMS, ~$2/month max)
- n8n handles all alert routing logic (HTTP Request nodes to Discord webhook + Twilio API)

**Monitoring endpoints**:

- Render: `https://api.render.com/v1/services/{id}` (health status)
- Vercel: `https://api.vercel.com/v9/deployments` (deployment status)
- Hetzner: direct HTTP health check to n8n/Postiz endpoints
- Neon: connection test via studio API health endpoint
- Upstash: Redis PING via studio API health endpoint

### 7C. Trinkets Domain Decision

**Decision**: Use `tools.filefree.ai` subdomain.

**Rationale**:

- No domain purchase needed (we own filefree.ai)
- Easy DNS setup (CNAME to Vercel)
- Clear brand connection (FileFree family)
- SEO benefit: subdomain inherits some domain authority from filefree.ai
- Can be separated to standalone domain later if trinkets grow significantly
- Cross-sell CTA naturally points back to filefree.ai

**Vercel config**: Add `tools.filefree.ai` as a custom domain to the `apps/trinkets/` Vercel project.

---

## 8. Plan Hygiene

### Plans to Archive (Superseded by This Document)

These plans from the venture strategy conversations are fully superseded:

1. `venture_master_strategy_ceeba1fd.plan.md`
2. `definitive_execution_plan_d3b7c878.plan.md`
3. `consolidated_strategic_review_11e18e9f.plan.md`
4. `revenue_social_agents_review_2da9fa89.plan.md`
5. `adjacent_business_opportunities_6683a5fc.plan.md`
6. `bizfree_stress_test_deep_a5395931.plan.md`
7. `bizfree_credit_model_review_46727fa1.plan.md`
8. `bizfree_naming_strategy_5fb6b573.plan.md`
9. `naming_strategy_deep_dive_ddcb53aa.plan.md`
10. `company_structure_deep_dive_f2e01bce.plan.md`
11. `adulting_os_strategic_master_plan_1a3a9b0d.plan.md` (+ duplicate `_262c0a19`)
12. `support_automation_strategy_3ed0ae08.plan.md` (+ duplicate `_590011fb`)
13. `deep_research_tightening_cc2f702c.plan.md`
14. `utility_tool_empire_strategy_383c8c1f.plan.md` (+ `_37aa2741`)
15. `naming_ra_trinkets_updates_ef9d6883.plan.md`

### Plan Ordering Rule

Create a Cursor rule (`.cursor/rules/plans.mdc`) that enforces:

- **One master plan per venture decision cycle** (this document is v1)
- Plans are prefixed with version and date: "Venture Master Plan v1 (2026-03-11)"
- Sub-plans for specific coding tasks reference the master plan section
- When a plan is superseded, move it to `.cursor/plans/archive/` (create dir)
- Never create a plan without checking if an existing one covers the scope

### docs/TASKS.md Update

When execution begins, the Phase 0-8 tasks above get merged into `docs/TASKS.md` as new sprints, replacing the current Sprint 4+ sections with the corrected venture-wide roadmap. The existing Sprint 0-3 (completed work) stays as historical record.

---

## 9. McKinsey Self-Review: All Personas Critique This Plan

Each persona reviewed the plan from their perspective. Findings grouped by severity. Detailed research for each finding is in the `deep_research_tightening` plan (archived but retained as reference).

### CRITICAL Findings

**F1. Scope Risk: 13 Admin Pages + 3 Products (CFO + Strategy)**

The command center has 13 admin pages across 3 tiers. Combined with LaunchFree MVP + FileFree resume + social pipeline, this is a large scope for a single founder.

**MITIGATION**: Build all 13 pages but in 3 tiers (Tier 1 with MVP, Tier 2 post-launch, Tier 3 with revenue). Managed via tiering, no scope cut.

**F2. CAN-SPAM + Company Structure (Legal + CPA)**

CAN-SPAM is opt-OUT (not opt-IN) for same-entity commercial emails. Since we're a single LLC with DBAs, cross-brand emails are technically from one sender. However, state privacy laws (CCPA) and trust best practices demand explicit opt-in.

**DECISION**: Single LLC + DBAs. Opt-in checkbox exceeds CAN-SPAM (opt-out law) but satisfies state privacy laws and builds trust. See Section 0B-0C.

### HIGH Findings

**F3. Social Content Pipeline Validation (Growth)**

DIY n8n pipeline at $0.10/video. Build pipeline first, validate with actual output for 2 weeks. No deferral -- the pipeline IS the test. See Section 5 for full spec.

**F4. 50-State Data Pipeline: All 50, Day One (Engineering + Tax Domain)**

The "research mountain" concern assumed manual research (30-60 min/state = 25-50 hours). With the AI-powered pipeline described in Section 3B:

- GPT does the extraction from structured web tables (~5 min/state AI time)
- Human reviews in batch (4-6 hours total for all 50 states)
- Three n8n monitoring workflows keep data fresh perpetually

**DECISION**: All 50 states, day one. The pipeline spec (Section 3B) guarantees this.

**F6. Brand Palettes for Each Product (UX + Brand)**

Multi-brand design systems use CSS variable theming with `[data-theme]` selectors. FileFree: violet-indigo. LaunchFree: teal-cyan. Studio: zinc-neutral. Implementation via `packages/ui/themes.css`. Split complementary color theory for family cohesion.

---

### MEDIUM Findings

**F7. RA Legal + Trademark Risk (Legal -- CRITICAL RESEARCH)**

### RA Service Requirements (Expanded)

Being a Registered Agent is NOT "vibe codeable." Research confirms ([howtostartabusiness.org](https://www.howtostartabusiness.org/registered-agent/requirements/)):

- **All 50 states**: physical street address (no PO box), available during business hours, 18+
- **Delaware**: commercial RAs must obtain state certificate
- **Nevada**: commercial RAs must be licensed
- **California**: 60-day resignation notice required
- **Alaska**: prohibits non-corporate LLCs from serving as RA
- Failure to forward legal documents = **default judgment** against user's LLC. This is liability we do NOT want.

### RA Pricing Reality (Corrected)

**For our own Wyoming LLC**: $25-29/yr (Wyoming-specific budget providers like wyomingllc.info at $25/yr or Rocky Mountain RA at $29/yr).

**For LaunchFree users (all 50 states)**: Wholesale volume pricing from CorpNet:


| Volume (active users) | Our Cost/User/Yr | What We Charge         | Margin |
| --------------------- | ---------------- | ---------------------- | ------ |
| 0-19 users            | ~$149/yr         | $149/yr (pass-through) | $0     |
| 20-50 users           | $119/yr          | $119-149/yr            | $0-30  |
| 51-150 users          | $99/yr           | $99-119/yr             | $0-20  |
| 151-500 users         | $89/yr           | $99/yr                 | $10    |
| 501-1,000 users       | $59/yr           | $79/yr                 | $20    |
| 1,001+ users          | $49/yr           | $49-79/yr              | $0-30  |


**GoDaddy "Free LLC" -- Competitive Analysis**: GoDaddy (via LegalZoom partnership) offers $0 service fee for LLC formation. But users still pay state fees ($100-800) + RA (~$150/yr) + upsells (operating agreement, EIN filing). ZenBusiness similarly baits at $99/yr RA, renews at $199/yr. LegalZoom charges $249/yr for RA.

**LaunchFree's REAL Competitive Moat** (it's NOT just "free filing" -- everyone does that now):

1. **No bait-and-switch**: Transparent pricing, no surprise renewals ($99/yr flat vs ZenBusiness $199 renewal)
2. **AI-powered guidance**: GPT-powered wizard in plain English, generates operating agreement, walks through EIN
3. **RA credit system**: Earn credits through referrals/activity, reduce cost toward $0 (at scale when wholesale hits $49)
4. **Cross-sell trust**: "You already trust us with your taxes. Now launch your business."
5. **All 50 state data, AI-maintained**: Formation requirements, fees, pros/cons -- updated by AI agents, not stale blog posts
6. **Compliance calendar**: Automated reminders for annual reports, franchise taxes, RA renewals (competitors charge $100+/yr for this)

**RECOMMENDATION (phased)**:

- **Phase 1 (0-500 users)**: Partner RA at wholesale. Charge $99/yr (transparent, cheaper than ZenBusiness $199 and LegalZoom $299). Position as "no surprise renewals."
- **Phase 2 (500+ users)**: Drop to $79/yr as volume pricing kicks in. Introduce credit system.
- **Phase 3 (1,000+ users)**: Drop to $49/yr or offer free RA with financial product partnerships. DIY RA only at this scale.

DIY RA deferred indefinitely. Requires:

- Physical addresses in all 50 states (~$2,500-5,000/yr via virtual offices)
- E&O insurance for RA liability
- State-by-state commercial RA registration where required
- Compliance staff or very robust automation

### Trademark Risk: filefree.com Is Intuit's (CONFIRMED)

See Section 0C for the full analysis. Summary:

- filefree.com owned by Intuit since 1999 (WHOIS confirmed: MarkMonitor registrar)
- "FileFree" is descriptive in the tax space -- harder to register BUT harder for Intuit to enforce
- File on **USPTO Supplemental Register** ($700 per mark, 2 classes each)
- After 5 years of commercial use, petition for Principal Register
- NEVER reference filefree.com anywhere. We operate on filefree.tax / filefree.ai.
- FTC "free" compliance: our service IS free, no conditions, no asterisks -- this is our strongest legal position

### Strict Legal Guidelines

Section 0C contains the complete compliance framework that ALL personas, agents, social content, emails, and marketing must follow. Key rules:

1. Brand names always as proper nouns (FileFree, LaunchFree -- exact casing)
2. Never use "file free" as a verb phrase in marketing (say "file your taxes for free")
3. Circular 230 disclaimer on all tax content
4. UPL disclaimer on all legal/formation content
5. FTC affiliate disclosure on all partner recommendations
6. Content Review Gate checklist before ANY publishing

---

**F8. Cross-Sell Compliance: Four Regulatory Frameworks (CPA + Legal -- Holistic)**

Cross-sell messages touch FOUR regulatory frameworks simultaneously:

**1. CAN-SPAM** (email): Unsubscribe, physical address, honest subjects. Penalty: $51,744/email.
**2. FTC "Free" Guide** (advertising): Service must actually be free with no hidden conditions. RA credits must disclose base $49/yr price. Penalty: FTC enforcement.
**3. IRS Circular 230** (tax advice): EDUCATION only, never specific advice. "Many filers..." not "You should..."
**4. State UPL laws** (legal advice): Formation SERVICES not legal advice. "Many choose Delaware because..." not "You should form in Delaware."

### Message Framework

- BAD: "You should form an LLC to protect yourself" (legal advice -- UPL violation)
- GOOD: "Many sole proprietors choose to form an LLC for liability protection. Here's how it works." (education)
- BAD: "Your LLC needs to file taxes" (directive -- Circular 230 risk)
- GOOD: "LLC owners typically need to file business taxes. FileFree makes it free." (informational)
- BAD: "Free RA service!" (misleading -- base price is $49/yr)
- GOOD: "RA service starting at $49/yr. Earn credits to reduce or eliminate the cost." (transparent)

### Every User-Facing Message Must Pass the Content Review Gate (Section 0C)

This includes: emails, social posts, in-app notifications, AI-generated tips, push notifications, landing page copy, and partner recommendation pages. No exceptions. The checklist is in Section 0C and must be built into every content persona's system prompt.

---

**F9. Admin Dashboard UX: Functional Over Beautiful (UX)**

The command center is internal tooling, not a customer-facing product. The UX bar is different: speed to insight over visual polish.

**RECOMMENDATION**:

- Use shadcn Table components for all list views (agents, campaigns, state data, users). No custom data grid libraries.
- Use Recharts (already in stack) for trend charts. Keep to 3 chart types: line, bar, pie.
- No animations or transitions in admin pages. Instant renders.
- Every page should load in <1 second. React Query with aggressive caching (staleTime: 60s for most data, 5s for health checks).
- The Activity Feed on Mission Control is the most important UX element -- it should feel like a live terminal. Monospace font, new entries slide in from top, auto-scroll.
- Mobile responsive is nice-to-have, not required. The founder will use this on a laptop, not a phone.

---

### LOW Findings

**F10. Social Media Content Quality Review (QA)**

Tax/finance content has regulatory requirements (IRS Circular 230 disclaimers, FTC disclosures for referrals). A fully automated pipeline with 5-min human review risks publishing non-compliant content.

**RECOMMENDATION**: For the first 30 days, founder reviews EVERY post before publishing (not just 5 min glance). After 30 days, establish a "pre-approved template" system where the n8n pipeline can only generate content from approved template structures. Novel content still requires manual review.

---

**F11. Monorepo CI: Path-Filtered Builds (Engineering -- Detailed Spec)**

pnpm workspaces without Turborepo means CI runs ALL tests on every PR by default. With 3 apps + 3 APIs + shared packages, this becomes 10+ minutes.

**SOLUTION**: `dorny/paths-filter@v3` ([source: oneuptime.com](https://oneuptime.com/blog/post/2025-12-20-monorepo-path-filters-github-actions/view)) -- the industry standard for monorepo CI:

```yaml
jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      filefree: ${{ steps.filter.outputs.filefree }}
      launchfree: ${{ steps.filter.outputs.launchfree }}
      shared: ${{ steps.filter.outputs.shared }}
    steps:
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            filefree:
              - 'apps/filefree/**'
            launchfree:
              - 'apps/launchfree/**'
            shared:
              - 'packages/**'
              - 'pnpm-lock.yaml'

  filefree-ci:
    needs: detect-changes
    if: needs.detect-changes.outputs.filefree == 'true' ||
        needs.detect-changes.outputs.shared == 'true'
    # lint + test + build for filefree only
```

Key rules:

- Shared `packages/**` changes trigger ALL downstream apps
- `pnpm-lock.yaml` changes trigger everything (dependency change)
- Docs-only changes trigger nothing (`paths-ignore: ['**/*.md', 'docs/**']`)
- Gitleaks runs on EVERY PR regardless (security is non-optional)
- Expected CI: 2-3 min per affected app vs 10+ min for everything

This is the same selective-build behavior Turborepo provides, without adding Turborepo to the stack.

---

**F12. ElevenLabs Voice Clone Quality (Growth)**

Voice clones require the founder to record 30+ minutes of clean audio for a quality clone. If the clone sounds robotic, it undermines the "human" trust signal the voice is supposed to provide.

**RECOMMENDATION**: Before committing to ElevenLabs ($22/mo), test with their free tier (10K characters). Record 3 sample videos with the cloned voice. If quality is insufficient, use a stock AI voice instead of a clone -- it sets a different expectation ("this is AI content") rather than an uncanny "is this real?" reaction.

---

### Summary of Revisions Based on Self-Review


| #   | Finding                      | Severity | Action                                                                                                                    | Impact on Plan                              |
| --- | ---------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| F1  | Scope risk                   | CRITICAL | Build all 13 admin pages in 3 tiers (Tier 1 with MVP, Tier 2 post-launch, Tier 3 with revenue)                            | Managed via tiering, no scope cut           |
| F2  | CAN-SPAM + company structure | CRITICAL | Single LLC + DBAs. Opt-in checkbox exceeds CAN-SPAM (opt-out law) but satisfies state privacy laws                        | Section 0B-0C added. Privacy policy updated |
| F3  | Social content pipeline      | HIGH     | DIY n8n pipeline ($0.10/video). Build pipeline first, validate with actual output for 2 weeks                             | No deferral -- pipeline IS the test         |
| F4  | 50-state data pipeline       | RESOLVED | All 50 states day one via AI extraction from structured sources (Section 3B). ~6 hrs human review                         | No scope reduction. Full coverage.          |
| F5  | Founder 2 bandwidth          | RESOLVED | Scale with traction. Zero work needed until products have live users.                                                     | Acknowledged as pre-product stage           |
| F6  | studio + brand palettes      | HIGH     | Hetzner-hosted studio. Multi-brand CSS variable theming (violet/teal/zinc/amber -- 4 products)                            | Section 2 palettes added to P1.2            |
| F7  | RA legal + trademark risk    | CRITICAL | Partner RA for v1. filefree.com is Intuit's (confirmed). File Supplemental Register. Full legal guidelines in Section 0C. | New Section 0C added. Strict brand rules.   |
| F8  | Cross-sell compliance        | HIGH     | 4 regulatory frameworks (CAN-SPAM, FTC Free, Circular 230, UPL). Content Review Gate checklist mandatory.                 | Section 0C contains master checklist        |
| F9  | Admin UX approach            | MEDIUM   | Functional over beautiful: shadcn tables, Recharts, no animations                                                         | UX guideline, no scope change               |
| F10 | Content compliance           | LOW      | 30-day manual review period                                                                                               | Delays full automation by 30 days           |
| F11 | CI path filters              | MEDIUM   | `dorny/paths-filter@v3`. Shared pkg changes trigger all apps. 2-3 min per app vs 10+ min total.                           | Detailed YAML spec in F11                   |
| F12 | Voice clone quality          | LOW      | Test ElevenLabs free tier (10K chars) before committing. Startup grants program: 12mo free with 33M chars.                | Apply for ElevenLabs startup grant          |


---

## 10. Key Decisions Still Needed (Founder Input Required)

1. **LLC Name**: TBD. Founder brainstorming separately. Toast-themed names under consideration (see Section 0B). Must confirm before Phase 0.6.
2. ~~**RA Strategy**~~: DECIDED -- Partner RA with wholesale volume pricing. $99/yr initial, drop with scale. See revised F7.
3. ~~**Phase 4 Scope**~~: DECIDED -- Full 13-page command center in 3 tiers. See Section 3.
4. ~~**Social Content Validation**~~: DECIDED -- Build pipeline first, validate with actual output for 2 weeks. See F3.
5. ~~**Founder 2 Priority**~~: DECIDED -- Scale with traction. Zero work needed pre-product. See F5.
6. ~~**Domain purchases**~~: DECIDED -- launchfree.ai + filefree.ai PURCHASED (March 2026, ~$440 for 2-year reg).
7. **Trademark filing timing**: File immediately after product launch (need specimen of use) or file intent-to-use now ($350 extra per class)?
8. ~~**AI Model Routing**~~: DECIDED -- 9-model strategy. See Section 0E. Owned by AI Ops Lead persona.
9. ~~**Trinkets product line**~~: DECIDED -- Phase 1.5, financial calculators first, then agent pipeline validates subsequent ideas. See Section 0F.
10. ~~**Trinkets domain**~~: DECIDED -- `tools.filefree.ai` subdomain. No purchase needed, inherits domain authority, easy DNS. See Section 7C.
11. ~~**LLC State**~~: DECIDED -- **California LLC** (March 2026). Founder is a CA resident; Wyoming would require foreign registration, double RA, and CA franchise tax anyway. CA year 1: ~$119 vs WY year 1: ~$1,094. See Section 0B for full comparison. Revisit Wyoming when revenue >$250K and asset protection justifies dual-state cost.

---

## 11. Realistic Valuation Estimate

See Section 0D for the full analysis with comparable companies. Summary:


| Timeframe          | Revenue         | Users | Multiple | Valuation Range |
| ------------------ | --------------- | ----- | -------- | --------------- |
| Year 2 (2027)      | ~$100K combined | 30K+  | 3-5x     | $300K-500K      |
| Year 3 (2028)      | ~$500K combined | 50K+  | 5-8x     | $2.5M-4M        |
| Year 4-5 (2029-30) | ~$2M combined   | 200K+ | 6-10x    | $12M-20M        |
| Home run (2031+)   | ~$5M+ combined  | 500K+ | 8-12x    | $40M-60M        |


Most relevant comp: LegalZoom paid ~$115M for Formation Nation (business formation brand). Credit Karma acquired for $7.1B at 7.1x revenue. Our cross-sell moat (tax filing + LLC formation) creates a portfolio premium neither comp had.