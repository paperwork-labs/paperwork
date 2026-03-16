# Paperwork Labs — Financial Tracker

**Maintained by**: Executive Assistant agent (`ea.mdc`)
**Last updated**: 2026-03-16

---

## One-Time Expenses

| Date | Item | Amount | Category | Notes |
|---|---|---|---|---|
| Mar 2026 | filefree.ai domain (2yr) | ~$220 | Domain | Purchased |
| Mar 2026 | launchfree.ai domain (2yr) | ~$220 | Domain | Purchased |
| Mar 2026 | paperworklabs.com domain | ~$12 | Domain | Purchased. Holding company site |
| TBD | California LLC filing fee (Paperwork Labs LLC) | $70 | Legal | |
| Mar 2026 | distill.tax domain | ~$8 | Domain | Purchased |
| TBD | DBA filings (x4: FileFree, LaunchFree, Trinkets, Distill) | ~$40-100 | Legal | ~$10-25 per name |
| TBD | Registered Agent (first year) | ~$49 | Legal | Annual, first year |
| TBD | USPTO trademark filing (FILEFREE + LAUNCHFREE) | ~$2,100 | Legal | Supplemental Register, Class 036+042 and 035+042 |
| TBD | FCRA compliance review (credit score integration) | ~$500-1,000 | Legal | Required before Phase 1.5 credit score soft pulls. See Master Plan Section 4M. |
| **TOTAL ONE-TIME** | | **~$3,201-$3,746** | | |

## Monthly Recurring

| Service | Cost | Category | Notes |
|---|---|---|---|
| Hetzner VPS (CX33) | $6/mo | Infrastructure | n8n + Postiz + Redis + PostgreSQL |
| Render (FileFree API) | $7/mo | Infrastructure | Starter plan, 512MB |
| Render (LaunchFree API) | $7/mo | Infrastructure | Starter plan (when launched) |
| Google Workspace (1 seat) | $6/mo | Operations | paperworklabs.com primary domain + alias domains (filefree.ai, launchfree.ai, distill.tax). See D76. |
| Domain renewals (avg) | ~$20/mo | Domain | Spread across year |
| OpenAI API (dev usage) | ~$10/mo | AI/ML | GPT-4o, GPT-4o-mini, DALL-E |
| ElevenLabs (voice clone) | $5/mo | Content | Starter plan. Apply for startup grant (33M chars free/12mo). |
| Cyber liability insurance (amortized) | ~$150/mo | Legal/Insurance | ~$1,800/yr for $1M E&O + cyber coverage. GET THIS BEFORE FIRST SSN. |
| CA franchise tax (amortized) | ~$67/mo | Legal | $800/yr minimum, due April 15 annually |
| **TOTAL MONTHLY (REAL)** | **~$278/mo** | | |

### At-Scale Variable Costs (not yet incurred)

| Service | Cost | Trigger |
|---|---|---|
| Stripe processing fees | 2.9% + $0.30/txn | First paid transaction |
| AI OCR at scale (Cloud Vision + GPT) | ~$0.005-0.02/doc | >1K OCR pages/mo |
| Social content pipeline (ElevenLabs + Hetzner FFmpeg) | ~$15-17/mo | Full video pipeline active |
| Partner wholesale costs (RA, audit shield) | Varies by partner | First partner deal closed |
| Vercel Pro | $20/mo | 5 apps in monorepo (filefree, distill, launchfree, studio, trinkets) — Hobby tier limits to 1 project per account |

### Free Tier Services (no cost until scale)

| Service | Free Tier Limit | Upgrade Trigger |
|---|---|---|
| Vercel (x5 apps) | Hobby tier (1 project) | Phase 1 monorepo deploys multiple apps — triggers Vercel Pro ($20/mo) |
| Neon PostgreSQL | 0.5 GB storage, 190 compute hours | 5K+ users |
| Upstash Redis | 500K commands/mo | 500K+ commands |
| GCP Cloud Vision | 1K pages/mo | 1K+ OCR pages/mo |
| PostHog | 1M events/mo | 1M+ events |
| Sentry | 5K errors/mo | 5K+ errors |
| Grafana Cloud | 50GB traces/mo, 50GB logs/mo, 10K metrics | Exceeds free limits (unlikely at MVP) |
| k6 Cloud | Local execution (unlimited) | Use k6 Cloud only if CI integration needed ($0 for local runs) |

## Runway

| Metric | Value |
|---|---|
| Total monthly burn (real) | ~$284/mo |
| Annual fixed costs | ~$3,408/yr ($284/mo x 12, includes amortized $800/yr CA franchise tax) |
| Cash invested to date | ~$452 (domains: filefree.ai, launchfree.ai, paperworklabs.com) |
| Planned one-time expenses | ~$3,201-$3,746 (LLC + trademarks + FCRA review) + ~$300-500 (attorney consult) + ~$1,800 (first year cyber insurance) = ~$5,301-$6,046 |
| Months of runway at $0 revenue | Indefinite (bootstrapped, costs covered by founder) |

## Revenue Projections (from Master Plan Section 1 — Stress Tested)

| Period | Pessimistic | Moderate | Aggressive |
|---|---|---|---|
| LaunchFree H2 2026 (incl. Compliance SaaS) | $7.9K | $34.5K | $114K |
| FileFree Jan-Apr 2027 | $7K | $29K | $150K |
| **Year 1 Total** | **$14.9K** | **$63.5K** | **$264K** |
| Year 2 (2028) | $75K | $300K | $750K |

Note: Year 1 increase driven by Compliance-as-a-Service recurring revenue ($49-99/yr per LLC). Year 2 reflects CaaS renewals + refund splitting affiliate revenue + quarterly estimator engagement uplift. See Master Plan Sections 1B.1-1B.3.

### Year 2-5 Marketplace Revenue (from Master Plan Section 4O)

| Year | Stage | Est. Users | ARPU | Marketplace Rev | Product Rev | Total Revenue |
|---|---|---|---|---|---|---|
| Y1 (2027) | Stage 1 | 2K-5K | $3-7 | $6K-35K | $15K-264K | **$21K-299K** |
| Y2 (2028) | Stage 1-2 | 10K-25K | $8-15 | $80K-375K | $75K-750K | **$155K-$1.1M** |
| Y3 (2029) | Stage 2-3 | 25K-50K | $15-35 | $375K-$1.75M | $300K-$1.5M | **$675K-$3.25M** |
| Y4 (2030) | Stage 3-4 | 50K-100K | $25-50 | $1.25M-$5M | $500K-$2M | **$1.75M-$7M** |
| Y5 (2031) | Stage 4 | 100K-200K | $35-80 | $3.5M-$16M | $1M-$4M | **$4.5M-$20M** |

Key inflection: Year 3 is where marketplace revenue overtakes product revenue. See Master Plan Section 4O for stage gates and competitive moat analysis.

### Distill B2B SaaS Revenue (CPA SaaS — launching Summer 2026)

| Year | CPA Firms | Avg Plan | Monthly Rev | Annual Rev |
|---|---|---|---|---|
| H2 2026 (launch) | 5-20 | $49-79/mo | $245-1.6K | **$1.5K-9.5K** |
| Y1 (2027) | 30-100 | $79-99/mo | $2.4K-9.9K | **$28K-119K** |
| Y2 (2028) | 100-300 | $99-129/mo | $9.9K-38.7K | **$119K-464K** |
| Y3 (2029) | 300-600 | $119-149/mo | $35.7K-89.4K | **$428K-$1.07M** |
| Y4 (2030) | 600-1,000 | $139-169/mo | $83.4K-169K | **$1M-$2M** |
| Y5 (2031) | 1,000-2,000 | $149-179/mo | $149K-358K | **$1.8M-$4.3M** |

This is immediate, predictable SaaS revenue -- not marketplace ARPU that requires consumer scale. Revenue starts the moment a CPA firm signs up. ~80% tech overlap with consumer FileFree means near-zero marginal infrastructure cost.

**Annual billing discount impact**: Distill offers 20% annual billing discount (Solo $39/mo, Team $79/mo, Firm $159/mo). If 50% of firms choose annual, effective monthly revenue drops ~10% from the table above. However, annual billing improves cash flow predictability and reduces churn.

### Distill API Revenue (Formation + Tax + Compliance APIs — launching Summer 2026)

| Year | API Filings/Calls | Avg Revenue/Unit | Annual Rev |
|---|---|---|---|
| H2 2026 (launch) | 50-200 filings | $30/filing avg | **$1.5K-6K** |
| Y1 (2027) | 500-2K filings | $30/filing avg | **$15K-60K** |
| Y2 (2028) | 2K-5K filings | $30/filing avg | **$60K-150K** |
| Y3 (2029) | 5K-15K filings | $25/filing (volume discounts) | **$125K-375K** |

Note: $20-40/filing is target pricing, undercutting incumbent API providers. Marginal cost estimated at ~$0.25-0.50/filing (actual costs to be validated). Gross margin target: 90%+. Tax API and Compliance API add incremental per-call revenue not included above.

### Business Tax Filing Revenue (from Master Plan Phase 10)

| Year | Business Returns | Avg Fee | Annual Rev |
|---|---|---|---|
| Y2 (2028) | 200-500 | $65 | **$13K-33K** |
| Y3 (2029) | 500-2,000 | $70 | **$35K-140K** |
| Y4 (2030) | 2,000-5,000 | $75 | **$150K-375K** |
| Y5 (2031) | 5,000-15,000 | $75 | **$375K-$1.1M** |

Business returns (Form 1065, 1120-S) are NOT free. Priced at $49/return (1065) and $99/return (1120-S). Free for Distill Firm subscribers. LaunchFree cross-sell: first business return free for LLC formers who selected partnership/S-Corp tax election.

### B2B Tax-as-a-Service API Revenue (from Master Plan Section 5L, Year 2+)

| Year | API Partners | Avg Returns/Partner | Per-Return Fee | Annual Rev |
|---|---|---|---|---|
| Y2 (2028) | 2-5 | 5K-10K | $8 | **$80K-400K** |
| Y3 (2029) | 5-15 | 10K-30K | $7 | **$350K-$3.2M** |
| Y4 (2030) | 15-30 | 20K-50K | $6 | **$1.8M-$9M** |
| Y5 (2031) | 30-50 | 30K-80K | $5.50 | **$5M-$22M** |

API distribution is the 2M-user unlock. Per-return pricing decreases at volume (volume discounts). This revenue stream is speculative until own MeF transmitter is proven (January 2027).

### Combined Revenue Summary (All Streams)

| Year | Consumer Product | Marketplace | B2B Pro SaaS | Biz Tax Filing | API Distribution | **Total** |
|---|---|---|---|---|---|---|
| Y1 | $15K-264K | $6K-35K | $28K-119K | $0 | $0 | **$49K-418K** |
| Y2 | $75K-750K | $80K-375K | $119K-464K | $13K-33K | $80K-400K | **$367K-$2M** |
| Y3 | $300K-$1.5M | $375K-$1.75M | $428K-$1.07M | $35K-140K | $350K-$3.2M | **$1.5M-$7.7M** |
| Y4 | $500K-$2M | $1.25M-$5M | $1M-$2M | $150K-375K | $1.8M-$9M | **$4.7M-$18.4M** |
| Y5 | $1M-$4M | $3.5M-$16M | $1.8M-$4.3M | $375K-$1.1M | $5M-$22M | **$11.7M-$47.4M** |

**Revenue diversification**: By Year 3, no single revenue stream exceeds 50% of total revenue. This de-risks the business -- marketplace dependency is balanced by SaaS, API, and product revenue.

### Valuation Trajectory (from Master Plan Section 0D)

| Year | Revenue (mod) | Multiple | Valuation (mod) | Stage |
|---|---|---|---|---|
| Y1 | $63.5K | 3-5x | $190K-317K | Stage 1 |
| Y2 | $300K | 5-8x | $1.5M-$2.4M | Stage 2 |
| Y3 | $1.5M | 6-10x | $9M-$15M | Stage 3 |
| Y4 | $3.5M | 8-12x | $28M-$42M | Stage 3-4 |
| Y5 | $10M | 10-15x | $100M-$150M | Stage 4 |

**Plan B (zero partnerships)**: $6.5K-37K Year 1 from Tax Optimization Plan direct sales + AdSense + self-serve affiliates (Betterment, SoFi, Wealthfront, Ally, Robinhood, Chime, Acorns -- all self-serve applications). Survivable at $284/mo burn.

## Monthly Actuals

Track ALL venture expenses by category. EA agent logs expenses as they occur. CFO agent analyzes monthly trends.

### March 2026

| Category | Item | Amount | Notes |
|---|---|---|---|
| **Domain** | filefree.ai (2yr) | $220 | Purchased |
| **Domain** | launchfree.ai (2yr) | $220 | Purchased |
| **SaaS** | Cursor (IDE) | TBD | Track monthly subscription cost |
| **AI/ML** | OpenAI API usage | TBD | Track from platform.openai.com/usage |
| **AI/ML** | Anthropic API usage | TBD | Track from console.anthropic.com |
| **Infra** | Hetzner VPS | $6 | |
| **Infra** | Render (FileFree API) | $7 | |
| **Ops** | Google Workspace | $6 | 1 seat (Business Starter), paperworklabs.com primary. Olga admin via ADMIN_EMAILS env var. |
| **TOTAL** | | TBD | Fill in at month end |

### Categories

| Category | What Goes Here | Who Logs | Who Analyzes |
|---|---|---|---|
| Infra | Hosting, servers, databases, Redis, CDN | EA | CFO |
| AI/ML | API costs (OpenAI, Anthropic, Google Cloud Vision, ElevenLabs) | EA | AI Ops Lead |
| Domain | Domain registrations, renewals | EA | CFO |
| SaaS | Developer tools (Cursor, GitHub, Postiz, Sentry, PostHog) | EA | CFO |
| Legal | LLC fees, trademarks, attorney consults, insurance | EA | Legal + CFO |
| Marketing | Paid ads (Spark Ads, Meta boost), content production | EA | Growth |
| Content | Voiceover, video production, stock assets | EA | Growth |

*Copy the March template each month. Track everything. No expense is too small to log.*

## Expense Log (Chronological)

Track all purchases here as they happen. EA agent updates this section.

| Date | Description | Amount | Category | Receipt/Reference |
|---|---|---|---|---|
| Mar 2026 | filefree.ai domain registration (2yr) | ~$220 | Domain | Registrar confirmation |
| Mar 2026 | launchfree.ai domain registration (2yr) | ~$220 | Domain | Registrar confirmation |
| Mar 2026 | paperworklabs.com domain registration | ~$12 | Domain | Holding company domain. Registrar confirmation |

---

*This document is the single source of truth for venture finances. Updated by the Executive Assistant agent after every expense. Monthly summaries generated in weekly planning output.*
