# AxiomFolio Platform McKinsey Review — 2026 Q2

**Status**: ACTIVE — strategic direction doc. Not a plan; the plan is [MASTER_PLAN_2026.md](MASTER_PLAN_2026.md). The 15-wave roadmap in Chapter 11 is the unit of execution.
**Created**: 2026-04-22
**Decision log**: [D144](../KNOWLEDGE.md) — 14 platform commitments.
**Companions**: [BROKER_COVERAGE_TRACKER.md](BROKER_COVERAGE_TRACKER.md) · [PORTFOLIO_SYNC_COMPLETENESS_2026Q2.md](PORTFOLIO_SYNC_COMPLETENESS_2026Q2.md) · [GAPS_2026Q2.md](GAPS_2026Q2.md) · [UX_AUDIT_2026Q2.md](UX_AUDIT_2026Q2.md).

---

## Table of contents

- Chapter 1 — Who we serve, what we serve
- Chapter 1.5 — Revenue engine, unit economics, founder dogfood
- Chapter 1.6 — Founder pain-points as the retail moat spine
- Chapter 1.7 — The tax-alpha moat layer (HNW retention)
- Chapter 1.8 — Medallion architecture + data warehouse discipline
- Chapter 2 — State-of-the-union audit
- Chapter 3 — User journeys
- Chapter 4 — Pricing audit + feature-to-tier remap
- Chapter 5 — Marketing narrative: two funnels
- Chapter 6 — Trading OS deep dive
- Chapter 7 — Broker-for-trading matrix (summary; detail in companion)
- Chapter 8 — Portfolio sync completeness (summary; detail in companion)
- Chapter 9 — Backtest reality check
- Chapter 10 — Marketing channels + per-channel CAC
- Chapter 11 — Execution roadmap: 15 waves
- Chapter 12 — Risks, reversibility, decision boundaries
- Chapter 13 — D144 commitments (summary)

---

## Chapter 1 — Who we serve, what we serve

### Three pillars, one product

AxiomFolio is a quantitative portfolio intelligence platform organized around three pillars that are deliberately decoupled at the code layer but stitched at the UX layer:

1. **Portfolio** — read-only broker sync (positions, trades, tax lots, options, balances, dividends). Snowball Analytics parity is the table stakes; no-custody multi-broker aggregation is the structural edge. Today IBKR (FlexQuery + Gateway), Schwab (OAuth), TastyTrade (SDK); bronze layer scaffolds for E*TRADE, Tradier, Coinbase.
2. **Intelligence** — daily OHLCV → indicator engine (SMA150-anchored 10-sub-stage classifier, RSI, ATR, ADX, MACD, TD Sequential) → `MarketSnapshot` (latest) + `MarketSnapshotHistory` (daily ledger). Market Regime Engine R1–R5 gates order flow. This is the analytical core.
3. **Strategy** — rule evaluator, backtester, signal generator, `OrderManager` → `RiskGate` → `BrokerRouter`. The single execution path. Exit cascade + circuit breaker + kill switch form the safety envelope.

The pillars are listed in dependency order (Portfolio feeds Intelligence feeds Strategy) but the **product** cuts across them: a Trade Card is Portfolio context + Intelligence signal + Strategy pre-staged order wrapped in one UI surface.

### Personas

We serve five personas across a coarse monetization ladder. Every feature must land in at least one persona's journey; features that don't are "nice to have" and belong on the cutting-room floor.

**P1 — Self-directed long-term investor (Free or Pro).** Holds $50k–$500k across one or two brokers, rebalances 2–4× per year, checks quarterly, wants gorgeous charts + dividend calendar + drawdown viz. Snowball Analytics is their current tool of record; they don't want signals, they want clarity. Funnel entry is `data.snowball_viz` which is free forever. Conversion hook: `chart.trade_annotations` (Pro) when they start asking "did I buy at a good spot?"

**P2a — Discretionary swing trader (Pro).** Trades 5–20 positions, weekly cadence, holds 2–8 weeks. Reads hedge fund research, watches Twitter/X, manually decides position size. Wants: validated picks (so they don't miss what the smart money already saw), stage chart annotations (so the chart speaks the Weinstein dialect they trade in), one-click-execute-to-broker. Conversion hook: a pick published at 07:15 ET that their favorite trader also tweeted at 07:22.

**P2b — Systematic swing trader (Pro+).** Same trade frequency as P2a but wants the rule set codified. Backtests ideas, wants walk-forward and Monte Carlo, wants to paper-validate before pushing live, wants the exit cascade to handle stops so they don't fat-finger. Conversion hook: `execution.tax_aware_exit` + `execution.rebalance` + the strategy lifecycle (Draft → Backtest → Shadow → PaperValidate → LivePull → LivePush).

**P3 — HNW individual tax-optimized operator (Quant Desk; the canonical persona per [D118](../KNOWLEDGE.md)).** Holds $500k–$5M across multiple brokers and account types (taxable + IRA + HSA, sometimes trust + 401k). Trades actively in one sleeve and holds long-term in another. The platform's canonical P3 is **the founder himself**: IBKR taxable + Schwab HSA, dual-from-day-one dogfooding. Their problems are not "what to buy" — their problems are "how do I exit a 200% gainer without realizing a short-term capital gain" and "how do I harvest a loss without tripping wash-sale across three accounts". Conversion hook: the FileFree year-end export that shows the dollar amount saved this year.

**P4 — RIA / small family office (Enterprise; future).** Manages $10M–$100M across 5–50 client households. Same tax problems as P3 but multiplied; needs SSO + audit log export + white-label. v1 scope lists this tier but does not prioritize; Enterprise is contract-billed ([`backend/services/billing/tier_catalog.py:186`](../../backend/services/billing/tier_catalog.py)).

### The P3 clarification that reshapes this review

P3 matters disproportionately because:

- Founder **is** P3 and dogfoods with **real capital**: IBKR equity $1.47M (peak $1.85M, trough $750k), Schwab HSA $33k.
- Every P3 feature can be validated against the founder's lived experience before marketing it. This is the tightest product-market-fit loop available to us.
- P3's LTV is 5–7× P2b's (Chapter 1.5). Losing P3 to Parametric, Canvas, or Wealthfront Premier is a 5–7× revenue leak per user.
- The tax-alpha layer that retains P3 (Chapter 1.7) is also what beats the incumbents; the retail-discipline layer (Chapter 1.6) is parity with Trade Ideas / TrendSpider / Composer, not moat.

The two-layer moat is therefore: **retail-discipline anchors acquisition + activation (Chapter 1.6); HNW tax-alpha anchors retention + LTV + defensibility (Chapter 1.7).** Both are dogfooded by the same person.

---

## Chapter 1.5 — Revenue engine, unit economics, founder dogfood

### Two revenue axes

**Axis 1 — Stripe MRR.** Paid subscribers on Free / Pro / Pro+ / Quant Desk / Enterprise. Pricing locked per [`backend/services/billing/tier_catalog.py`](../../backend/services/billing/tier_catalog.py): $0 / $29 / $79 / $299 / custom. Annual SKUs at 2-months-free: $0 / $290 / $790 / $2,990 / custom.

**Axis 2 — Founder P&L leverage.** Founder trades his own capital using the platform he is building. A feature that locks in $50k of profit on the IBKR sleeve or saves $30k in tax is, from the founder's point of view, a $50k/$30k release of engineering capital. Axis 2 credibility is also the single highest-conversion marketing asset (see Chapter 5 and Chapter 10: `/public/founder-portfolio`).

These axes are not independent — Axis 2 feeds Axis 1 via the redemption-arc marketing narrative, and Axis 1 feeds Axis 2 via the feature pipeline the founder gets to dogfood first.

### Founder capital (pinned from 2026-04-22 clarifications)

The three clarifications pinned by the founder 2026-04-22 (used throughout this doc, never re-asked):

- **IBKR (taxable)**: equity $1.42M, current ~$1.47M. Margin **currently used** $1.67M — not available buying power. Gross long ≈ $3.14M. Leverage ~2.13× on current equity. Peak equity $1.85M, trough $750k, current $1.47M. This is the **"$1.85M → $750k → $1.47M redemption arc"** that anchors Chapter 1.6 and Chapter 5.
- **Schwab HSA (tax-advantaged)**: $33k equity, **no options trading enabled** (equities only). Target $100k is a +200% stretch goal; realistic over 2–3 years on HSA-contribution-driven growth plus modest returns.
- **IBKR target $2.5M in the next 8–12 weeks**, with the founder's own stated thesis: *"got lots of speculative shit; one melt-up this summer could help exit."* This is **not a compounding target** — it is an **unwind-the-speculative-sleeve goal**. The Active/Conviction sleeve system ([G18](GAPS_2026Q2.md), [D135](../KNOWLEDGE.md)) is precisely the mechanical tool that makes this target achievable without emotional bleed.

### Per-persona revenue contribution (steady-state 12mo)

| Persona | Tier | Stripe ARR/user | Retention assumptions | Conversion funnel |
|---------|------|-----------------|----------------------|-------------------|
| P1 (occasional rebalancer) | Free → Pro | $0 → $290/yr | Free retains on charts alone; 3–5% Free→Pro on trade annotations | Snowball migration, word-of-mouth |
| P2a (discretionary swing) | Pro | $290/yr | Monthly churn 4% (picks are sticky when validator is trusted) | Trade Cards + validator trust |
| P2b (systematic) | Pro+ | $790/yr | Monthly churn 3% (switching cost: encoded strategies) | Pro-to-Pro+ on backtest need |
| P3 (HNW operator) | Quant Desk | $2,990/yr base, **$14k–$25k blended** | Monthly churn 1.3% (high switching cost via encoded TaxProfile + G16 ledger + G20 elections); YTD savings visible in FileFree 1.1.0 export | Founder-story content + tax-calculator lead magnet |
| P4 (RIA / family office) | Enterprise | $20k–$60k/yr | Contract term 12mo+; churn near-zero in year 1 after onboarding | Direct sales; year 2 scope |

**The Quant Desk LTV lift.** Chapter 1.7 walks the math; the short version: the tax-alpha stack at Quant Desk produces $10k–$75k/yr in verifiable tax savings for a $500k–$5M operator. A user who sees that number at 1099-time will not churn over a $299/mo bill. Retention rises from an assumed 2%/mo to 1.3%/mo; LTV lifts from $3,588/yr nominal to a blended $14k–$25k once we factor (a) higher retention, (b) annual tier upgrade cadence (Pro+ → Quant Desk as portfolio crosses $500k), (c) concierge / directed-indexing take-rate on partner referrals (Wave 3.7 Option A).

### The founder-dogfood flywheel

```
Axis 2 wins (e.g. $50k locked in via G16 HIFO exit)
   → Axis 2 Twitter thread with screenshots
   → lead magnet signup on /tax-calculator (P3 prospects)
   → Quant Desk trial signup
   → P3 stays → Axis 1 MRR
   → Axis 1 MRR funds next feature
   → founder dogfoods next feature
   → more Axis 2 wins
```

The flywheel breaks if any link breaks: the feature has to ship, the founder has to dogfood honestly, the public has to be able to verify. Which is why Wave 10 (dogfood amplification) is listed alongside Wave 1 (safety) as a tier-zero priority — a platform with a muted founder story is worth a fraction of one with a public one.

---

## Chapter 1.6 — Founder pain-points as the retail moat spine

The founder's lived trading experience, expressed as specific pain points, is the product spec for the retail-discipline layer. Every Chapter 1.6 pain point maps to a concrete platform feature and a wave in Chapter 11.

| Pain point (founder lived experience) | Platform feature that closes it | Wave | Tier gate |
|---------------------------------------|--------------------------------|------|-----------|
| "I held through a 60% drawdown because I kept adding on the way down" ($1.85M → $750k) | Circuit breaker + per-position hard stop + kill switch reachable from every page + portfolio-heat gauge (Principle #3) | W1 | Free (safety is never a paywall) |
| "I can't close when I'm winning; I watch gains evaporate" ([D26](../KNOWLEDGE.md), `incident R32`) | Trim signals + adaptive trailing stops + G16 winner-exit advisor with tax-aware lot selection + peak-signal alerts | W3.5, W3.6 | Pro+ (`execution.tax_aware_exit`) |
| "I size positions emotionally and concentrate on my favorites" | Position sizer based on ATR + equity + stage, hard-capped at `MAX_SINGLE_POSITION_PCT`; portfolio-heat gauge blocks new entries above 6% | W1, W2 | Pro+ (`execution.rebalance`) |
| "I chase stocks after the move; I don't wait for setups" | Stage-gate (no new entries above Stage 2A late); Market Regime gate (no longs in R4/R5); Trade Card only renders when all gates pass | W2, W6 | Pro (`strategy.position_health_audit`) |
| "I revenge trade after losses; I open dumb positions at EOD" | Circuit breaker trips on (N losses in day, drawdown threshold, after-hours new-entry lock); kill switch one-click from top nav | W1 | Free |
| "I don't document why I took the trade so I can't learn" | R-multiple ledger auto-written per entry with regime + stage + pick source + rationale; post-trade review UI | W2.5, W4 | Pro (`brain.trade_decision_explainer` Pro+ for full NL) |
| "I miss validator posts in the chaos of email + Twitter + Discord" | Validator queue auto-ingested (Twisted Slice); picks land in-app with pre-staged order + stop + size | W2, W6 | Pro (`picks.read`) |
| "I can't review my year in January when 1099s arrive" | Trading Year-in-Review + FileFree 1.1.0 export with lot-selection audit trail | W3.7, W9 | Pro+ (YIR), Quant Desk (FileFree full) |

The moat claim: **no competitor closes all eight of these.** Trade Ideas / TrendSpider / MarketSmith do the chart-annotation and stage-gate layer. Composer / StocksToBuyNow do the picks layer. None do the full-loop safety + discipline-bounded sizing + tax-aware exit + auto-journal + review. The moat is the integration, not any one feature.

---

## Chapter 1.7 — The tax-alpha moat layer (HNW retention)

### Thesis

AxiomFolio's defensible moat against well-funded incumbents (Trade Ideas, TrendSpider, Composer, Snowball Analytics, Wealthfront Premier, Betterment Premium, Parametric, Canvas, Frec) is **not the retail-discipline layer** — that is table stakes and any of them can copy it on a 6–12 month timeline. The real moat is a **tax-alpha stack for HNW operators** that:

1. **Undercuts AUM-fee incumbents by 3–10× on fees** at the $500k–$5M portfolio band. Parametric Custom charges 35–60 bps ($1,750–$30,000/yr on $500k–$5M); Canvas / Wealthfront Premier charge 25–40 bps; AxiomFolio Quant Desk is a flat $2,990/yr.
2. **Offers a structurally superior multi-broker no-custody posture** incumbents cannot match without becoming a custodian (licensing + capital + multi-year build).
3. **Is dogfooded by the founder** against his own IBKR + HSA accounts, which no competitor can match on product-market-fit velocity.

### The full 9-alternative stack

G20 in [`GAPS_2026Q2.md`](GAPS_2026Q2.md) defines the HNW tax-deferral surface. The review expands it into a 9-alternative evaluator with dollar math, ranked by estimated tax alpha for a $1.5M founder-equivalent book:

| # | Alternative | What it does | Who owns it today | AxiomFolio's role |
|---|-------------|--------------|-------------------|-------------------|
| 1 | **HIFO / tax-lot-optimized exit** | Pick the lot with the highest basis (or the specific lot matching a loss offset) when closing | G16 `TaxLotSelector` (partial, [D133](../KNOWLEDGE.md)) | Full — wire into `OrderManager` sell path, W3.6 |
| 2 | **Loss harvest with wash-sale guard** | Realize losses to offset gains without triggering IRS Rev. Rul. 2008-5 wash-sale; cross-broker aware | Partial | Full — cross-broker wash-sale watcher across IBKR + Schwab + TT, W3.7 |
| 3 | **SBLOC (Securities-Based Line of Credit)** | Borrow against portfolio at 1–3% over SOFR instead of realizing gains | Pointer only | Educational + calculator + broker integration pointer (IBKR LoanEdge available) |
| 4 | **Protective put** | Buy downside insurance to lock gains without selling | Partial (options surface) | Full evaluator with dollar math + break-even viz, W3.7 |
| 5 | **Collar** | Protective put + covered call to fund the put; defines exit band | None | Full evaluator + strategy template, W3.7 |
| 6 | **Covered call (income + partial hedge)** | Write calls above current price for premium; caps upside but improves cost basis | Partial (options surface) | Full evaluator + tax-lot-aware strike selection, W3.7 |
| 7 | **Exchange fund / long-term deferred** | Contribute appreciated stock to a Section 351 exchange fund for diversification without realization | None | Partner referrals + eligibility calculator + disclaimer, W3.7 Option A |
| 8 | **Direct indexing (tax-loss harvesting at scale)** | Own the index constituents directly; harvest individual-name losses while holding the index | None | W3.8 conditional build (partner-first W3.7 Option A; own SMA engine only on Month-6 gate) |
| 9 | **Qualified Opportunity Zone / Charitable Remainder Trust** | Defer long-term gains via QOZ reinvestment; avoid gains on charitable transfer | None | Educational + partner pointer, W3.7 |

### G20 tier-gating conflict — resolution

[`GAPS_2026Q2.md:1141`](GAPS_2026Q2.md) currently places the full G20 engine at Pro+ ($948/yr). The economic value is $10k–$75k/yr for a $500k–$5M operator — a 10–80× value-to-price ratio that strands the Quant Desk moat and leaves substantial revenue on the table.

**Resolution for this review** (flagged as D144 commitment and requires `GAPS_2026Q2.md` amendment):

| Capability | GAPS spec today | Resolution | Rationale |
|------------|-----------------|------------|-----------|
| Basic HIFO + loss-harvest advisor | Pro+ | Pro+ (unchanged) | These are mechanical selectors; table stakes for active traders |
| SBLOC / protective put / covered call education + pointer | Pro+ | Pro+ (unchanged) | Awareness content, no automation |
| Full `DeferralAlternativesEngine.evaluate()` with dollar math, ranked alternatives, year-end optimization | Pro+ | **Quant Desk** | Decision support that replaces a $5k–$25k CPA engagement; priced accordingly |
| Cross-broker wash-sale ledger | Pro+ | **Quant Desk** | Requires multi-account aggregation + IRS Rev. Rul. 2008-5 logic; defensible engineering |
| Direct-indexing SMA engine / partner concierge | (absent) | **Quant Desk** | $500k-minimum partners; fits Quant Desk persona exactly |
| FileFree 1.1.0 enriched export (G16 audit + G20 elections + wash-flags + sleeves) | (absent) | **Quant Desk** | Annual-visibility proof of tax alpha; retention anchor |
| Concierge (1 quarterly call with a CPA or CFP reviewing the YTD tax surface) | (absent) | **Quant Desk add-on or bundled** | Lowers activation friction for P3 prospects |

### Direct indexing — build-vs-partner-vs-hybrid

At the **$2M+ portfolio level** (founder-cited), direct indexing becomes economically viable: a 25–50 bp tax-alpha yield on a $2M book is $5k–$10k/yr harvested loss, which is real money even after platform fees. Three options:

**Option A — Advisor / partner referrals (default, Wave 3.7).** Ship within 1–2 weeks of engineering scope. Zero data or trading cost. Low legal risk. Revenue model: 10–20% partner-referral cut. Partners: Cache, Aperture, Canvas, Frec, Parametric. Ranked inside the app by minimum investment / fee / lockup / specific-index-availability. Output: a ranked recommendation inside the Quant Desk dashboard with a "refer out" button.

**Option B — Own SMA engine (Wave 3.8 conditional).** Build `DirectIndexingEngine` that harvests losses on individual holdings inside a tracked index. Requires: cost-basis data quality (Wave 8 must ship first), tax-lot optimizer (G16 W3.6 must ship first), order-generation flow (already exists), **RIA registration or counsel sign-off** on "user-selects-index, platform-routes-orders" posture (3–6mo lead time if RIA; $25–50k/yr ongoing compliance).

**Month-6 gate conditions (all three must hold to proceed with Option B):**
1. ≥20 Quant Desk subscribers with ≥$500k portfolios in signup funnel (demand signal).
2. Outside RIA counsel approves the "user-selects-index" posture, OR founder elects to register AxiomFolio as an RIA (decision tree: founder-only RIA → lighter Form ADV; multi-advisor RIA → heavier filing).
3. ≥30% of Wave 3.7 Option A partner referrals convert to partner signups within 6 months (validates market demand within the platform).

**Option C — Hybrid (recommended default).** Option A ships Wave 3.7. Month 6, evaluate the three gates. If all pass, build Option B as Wave 3.8. If any fail, Option A is sufficient moat — partner referrals with a 10–20% cut on a 25 bp partner fee is already $1k–$5k/yr/customer of passive revenue. Option B is optional upside, not existential.

### Competitive anchoring

At the $500k–$5M band, AxiomFolio Quant Desk ($2,990/yr flat) competes with:

| Competitor | Fee structure | $1M portfolio annual | $2.5M portfolio annual | Custody? | Multi-broker? |
|------------|---------------|---------------------|------------------------|----------|---------------|
| **Wealthfront Premier** | 0.25% AUM | $2,500 | $6,250 | Yes (Wealthfront Brokerage) | No |
| **Betterment Premium** | 0.40% AUM | $4,000 | $10,000 | Yes | No |
| **Parametric Custom** | 35–60 bp AUM | $3,500–$6,000 | $8,750–$15,000 | Yes (SMA) | No |
| **Canvas (O'Shaughnessy)** | 35 bp AUM | $3,500 | $8,750 | Yes (SMA) | No |
| **Frec** | 10 bp (direct indexing) | $1,000 | $2,500 | Yes | No |
| **AxiomFolio Quant Desk** | $2,990/yr flat | $2,990 | $2,990 | **No (user keeps broker)** | **Yes (IBKR + Schwab + TT + more)** |

AxiomFolio beats AUM-fee providers at the crossover around $1M; at $5M, AxiomFolio is 3–10× cheaper. Frec is the closest price competitor but is custody-locked and single-index. The **no-custody multi-broker posture is the structural moat** — not matchable without incumbents becoming custodians, which is a multi-year regulatory + capital build.

### FileFree 1.1.0 — schema expansion

FileFree integration is already live at schema 1.0.0 per [D89](../KNOWLEDGE.md), [D99](../KNOWLEDGE.md), [D100](../KNOWLEDGE.md), PR #332. The integration is **exclusively via the Paperwork Labs Brain webhook** — AxiomFolio never imports FileFree code and vice versa. Schema 1.1.0 bump is a Wave 3.7 ship that adds:

| Section | Source | Use for CPA / preparer |
|---------|--------|----------------------|
| `realized_events[].lot_selection_method` + `selected_lot_ids` + `wash_sale_override_accepted` | G16 `TaxLotSelector` | Explain exactly which lot was sold and why, for every disposition |
| `deferral_elections[]` | G20 decisions | Show which alternatives were considered + elected + deferred-amount |
| `cross_broker_wash_flags[]` | G20 cross-broker wash-sale watcher | IRS Rev. Rul. 2008-5 evidence for CPA audit defense |
| `lot.sleeve_type` | G18 sleeve tagging ([D135](../KNOWLEDGE.md)) | Distinguish active-trading lots from conviction holds in the year-end narrative |
| `sma_harvest_events[]` (conditional) | W3.8 direct-indexing SMA engine | Only populated if W3.8 ships; absent otherwise |

Implementation: bump `SCHEMA_VERSION` in [`backend/api/routes/portfolio/tax_export.py`](../../backend/api/routes/portfolio/tax_export.py); update Pydantic models in [`backend/services/tax/filefree_exporter.py`](../../backend/services/tax/filefree_exporter.py); add unit tests round-tripping a 2025-style trade log through the new fields; Brain webhook endpoint contract unchanged (HMAC-signed, idempotent).

---

## Chapter 1.8 — Medallion architecture + data warehouse discipline

### Thesis

The platform's long-term defensibility isn't just the moat layers above (discipline + tax-alpha) — it's that **everything above rests on a data warehouse we own end-to-end**. Competitors that rely on aggregators (Plaid, Yodlee) or rehost broker data in their custodial shell don't have a reproducible, append-only ledger of every broker fact and every derived signal. We do, and we should treat that as a first-class asset. The medallion pattern ([D127](../KNOWLEDGE.md), 2026-04-22) is the **layout contract** that keeps this asset coherent as the platform grows.

### The three layers (formalized per D127)

```
┌─────────────────────────────────────────────────────────────────────┐
│  GOLD   backend/services/gold/                                       │
│         App-facing signals, strategies, picks, advisors              │
│         Consumers: frontend pages, Brain chat, OrderManager          │
│         Purity rule: reads silver + gold; writes gold only           │
│         ▲ examples: gold/peak_signal_engine.py (D133)                │
│         ▲          gold/deferral_alternatives_engine.py (W3.7)       │
│         ▲          gold/direct_indexing_engine.py (W3.8 conditional) │
│         ▲          gold/candidate_generator.py                       │
│         ▲          gold/pick_quality_scorer.py (G7)                  │
├─────────────────────────────────────────────────────────────────────┤
│  SILVER backend/services/silver/  (grandfathered today: market/,    │
│                                      portfolio/, tax/)               │
│         Enriched, deterministic analytics on bronze data             │
│         Consumers: gold layer, API routes for read endpoints         │
│         Purity rule: reads bronze + silver; writes silver only       │
│         ▲ examples: silver/indicator_engine.py (SMA150-anchored)     │
│         ▲          silver/regime_engine.py (R1–R5)                   │
│         ▲          silver/stage_classifier.py (10 sub-stages)        │
│         ▲          silver/tax_lot_selector.py (G16)                  │
│         ▲          silver/cost_basis_resolver.py (W8 ACATS)          │
├─────────────────────────────────────────────────────────────────────┤
│  BRONZE backend/services/bronze/<broker>/                            │
│         Raw broker + market-data ingestion, idempotent writes        │
│         Consumers: silver layer + reconciliation jobs                │
│         Purity rule: reads external APIs only; writes bronze only    │
│         ▲ examples: bronze/etrade/sync_service.py (D130)             │
│         ▲          bronze/tradier/sync_service.py (D132)             │
│         ▲          bronze/coinbase/sync_service.py                   │
│         ▲          bronze/ibkr/* (grandfathered from portfolio/)     │
│         ▲          bronze/schwab/* (grandfathered from portfolio/)   │
│         ▲          bronze/tastytrade/* (grandfathered)               │
│         ▲          bronze/market_data/* (OHLCV providers)            │
└─────────────────────────────────────────────────────────────────────┘
```

Purity is enforced by convention + code review, not by tooling today. Wave 16 adds a lint rule.

### The data warehouse (what we actually have)

Tables, organized by layer. The point is that this is **already a data warehouse** — we just haven't been treating it as one in the UX or in the docs.

**Bronze tables (raw, broker-authoritative):**
- `position` — broker-reported positions. Immutable per sync snapshot.
- `tax_lot` — per-lot cost basis + acquisition date. Post-W8 includes `cost_basis_source` enum.
- `trade` — historical order fills; sourced from FlexQuery / Schwab transactions / TastyTrade SDK.
- `transaction` — dividends, fees, interest, transfers, corporate actions.
- `price_data` — daily OHLCV from the market data provider chain.
- `broker_connection`, `broker_account`, `broker_oauth_connection` — credentialing.

**Silver tables (enriched, deterministic):**
- `market_snapshot` — latest indicator state per symbol (RSI, ATR, MACD, ADX, stage, regime context).
- `market_snapshot_history` — **daily append-only ledger** of the above. This is the most valuable table we own; it's the longitudinal record of every symbol's stage and indicator state.
- `market_regime` — R1–R5 scored daily.
- `position_health` — D119-style discipline scores per open position.
- `option_tax_lot` — FIFO-matched option lot identities ([D140](../KNOWLEDGE.md)).

**Gold tables (signals, strategies, picks):**
- `candidate` — daily candidates generated per strategy.
- `pick` — validator-approved or platform-generated picks with lifecycle state.
- `strategy`, `strategy_run` — rule sets + execution history.
- `backtest_run` — simulated equity curve + per-bar state (Wave 4 adds full time-series persistence).
- `order`, `order_lifecycle_event` — live execution records.
- `audit_event` — cross-cutting lineage trail.

Everything above participates in **user-scoped multi-tenancy** ([D88](../KNOWLEDGE.md) and D144 iron law): every table that holds user data has a `user_id` FK and every query filters by it.

### Five warehouse disciplines we commit to

1. **Append-only ledgers for immutable history.** `market_snapshot_history`, `trade`, `transaction`, `audit_event`, `order_lifecycle_event`. Never `UPDATE` or `DELETE`; only `INSERT`. Enforced via PR-time checklist (and Wave 16 lint rule).
2. **Idempotent bronze writes.** Every bronze sync uses natural-key upserts (not `INSERT ... ON CONFLICT DO NOTHING`) so re-running yesterday's sync is a no-op rather than a duplication source. Existing pattern per [D130](../KNOWLEDGE.md) E*TRADE + [D132](../KNOWLEDGE.md) Tradier; codify as a `bronze.upsert_batch()` helper in Wave 16.
3. **Deterministic silver transforms.** Any silver calculation must be reproducible from bronze + the deployed code SHA. No silver output ever depends on "when the job ran." Enforce via `compute_full_indicator_series()` ([D5](../KNOWLEDGE.md)) being the single entry point for indicator math, and Wave 16 adds a parity test: same bronze input + same SHA ⇒ bit-identical silver output.
4. **Schema additive, never subtractive.** All migrations add columns or tables. Column removals happen only via `deprecated_` rename + N-release grace period. Iron law per [D144](../KNOWLEDGE.md) reversibility policy.
5. **Counter-based success auditing.** Every per-row loop emits `written / skipped / errors` counters with `assert sum == total` per `.cursor/rules/no-silent-fallback.mdc`. The [R40](../KNOWLEDGE.md) Redis-lock silent no-op incident is the canonical example of why this matters: silent failure at the warehouse layer corrupts downstream for months.

### What D127 already promises; what it leaves open

**D127 promises** (already locked as convention):
- New modules land in `backend/services/<layer>/` from day one.
- Existing trees (`market/`, `portfolio/`, `picks/`, `tax/`) are grandfathered with docstring tags.
- Physical moves happen in deliberate follow-up PRs.

**D127 leaves open** (resolved here as D145):
- When and in what order to physically relocate the grandfathered code.
- How we surface warehouse queries to operator / power-user layers (today nothing surfaces; the warehouse is invisible product value).
- Whether silver ever becomes a materialized view layer (PostgreSQL MV or a pushed export to ClickHouse / DuckDB for analytical queries).
- How plugin SDK (Quant Desk) authors access silver + gold without tripping user-tenancy.

### The Wave 16 medallion migration plan

Run in parallel across the sprint; non-blocking for other waves but **mandatory before W15 Enterprise** so Enterprise schema can be delivered clean.

**Sub-wave 16.1 — Audit & tags (Week 1).** Touch every file in `backend/services/` and confirm its module-level docstring tag matches its true layer. Produce a markdown report in `docs/plans/MEDALLION_AUDIT_2026Q2.md` that lists each module with current path + target path + move risk (HIGH = danger zone per `protected-regions.mdc`; MEDIUM = widely-imported silver code; LOW = leaf-level utility).

**Sub-wave 16.2 — Lint rule + CI gate (Week 2).** New Ruff rule (custom pylint plugin if needed) that forbids:
- `bronze/*` importing from `silver/*` or `gold/*` (circular).
- `silver/*` importing from `gold/*`.
- Any module outside `gold/` writing to gold tables.
- Any module outside `bronze/` calling broker adapters.

**Sub-wave 16.3 — LOW-risk relocations (Weeks 2–3).** Move leaf-level utilities first: e.g. `market/indicator_math_utils.py` → `silver/math/`. Each move is one PR, one-line imports changed via `ruff --fix` or `grep -rl | sed`. Zero behavioral change; easy reverts.

**Sub-wave 16.4 — MEDIUM-risk silver relocations (Weeks 3–5).** `market/indicator_engine.py`, `market/stage_classifier.py`, `market/regime_engine.py` → `silver/`. These touch many downstream imports. One module per PR; CI gate catches misses.

**Sub-wave 16.5 — HIGH-risk relocations (Weeks 5–6, founder-approved per danger zone).** `portfolio/ibkr/*`, `portfolio/schwab_sync_service.py`, `tasks/portfolio/sync.py` → `bronze/<broker>/`. Execution danger-zone code stays put (`execution/*` already neutral to medallion; it reads gold, writes gold). Options to avoid a flag day: keep both paths during a 2-week bake, then remove the old path once import graph is clean.

**Sub-wave 16.6 — Silver as a materialized view layer (Week 7; optional, conditional).** If query patterns on `market_snapshot_history` stabilize (admin metrics, Year-in-Review aggregations, validator dashboards), evaluate whether a PostgreSQL MV refresh job or a push-to-DuckDB export makes sense. Gate condition: p95 query latency on `/admin/metrics` or `/portfolio/year-in-review` > 2s for ≥1 week.

### Plugin SDK + Enterprise implications

Quant Desk ships a plugin SDK ([D110](../KNOWLEDGE.md)). Medallion layering gives us a clean story for plugin surface area:

- **Plugin reads**: read-only access to **gold** views scoped to `current_user.id`. Never direct silver/bronze — too much surface + too many ways to break the warehouse.
- **Plugin writes**: only to a sandboxed `gold_plugin` partition; never to platform-owned gold tables.
- **Plugin execution**: runs in an isolated Celery queue with its own time + memory limits.

Enterprise (W15) gets per-tenant schemas or per-tenant materialized views on top of this layering — a much cleaner job once the layer boundaries are enforced.

### Why this is a moat (the quiet part)

Snowball Analytics doesn't own its warehouse — it rehosts read-only broker data. Trade Ideas / TrendSpider own a market-data warehouse but no portfolio warehouse. Wealthfront / Betterment / Parametric own a portfolio warehouse but it's custody-locked (their users can't leave with it). **AxiomFolio owns a multi-broker, no-custody, append-only portfolio + market data warehouse that a user can download wholesale at any time.** That portability is also a trust asset: users know their data outlives the platform.

The data warehouse is therefore both a defensibility layer (competitor can't replicate without 6–12 months of engineering + no-custody posture) and a retention asset (user's cost to leave grows with every day of ledger history we accumulate).

---

## Chapter 2 — State-of-the-union audit

### What exists on the backend (the iceberg under the water)

Backend is remarkably complete for the product shape. Concrete examples:

- **Indicator engine** (`backend/services/market/indicator_engine.py`): full Stage Analysis (SMA150-anchored 10-sub-stage), RSI, ATR, ADX, MACD, TD Sequential, RS Mansfield. All monetary math in `Decimal`.
- **Execution pipeline** (`backend/services/execution/`): `OrderManager` → `RiskGate` → `PreTradeValidator` → `BrokerRouter`. Paper / shadow / live modes. `ExitCascade` for stops + trails. `CircuitBreaker` for drawdown gates.
- **Regime engine** (`backend/services/market/regime_engine.py`): R1–R5 scoring from 6 inputs; gates long/short/flat access.
- **Backtest** (`backend/services/backtest/`): `BacktestEngine`, bar-replay, `SimulatedOrderManager` (parity with live). Walk-forward and Monte Carlo are Phase 6 (not shipped).
- **Tax lot selector** (`backend/services/tax/`): partial G16; FIFO / LIFO / HIFO / specific-lot; wash-sale guard present but single-broker today.
- **Broker sync**: IBKR FlexQuery + Gateway live; Schwab OAuth sync live (options per D139); TastyTrade SDK live; E*TRADE + Tradier + Coinbase bronze scaffolds.
- **Picks pipeline** (`backend/services/picks/`): inbound webhook, polymorphic LLM parser, validator queue, tier-gated publish.
- **FileFree export** (`backend/services/tax/filefree_exporter.py`): schema 1.0.0 live via Brain webhook.

### What exists on the frontend (the visible tip)

Frontend is where the gap lives. Critical observations:

- **TradeModal** is imported only from `PortfolioTaxCenter.tsx`. The single visible "place a trade" button in the entire product lives inside the tax-loss-harvesting page. This is the literal manifestation of the founder's "autotrade got lost" feedback.
- **Shadow (paper) trading** is buried under a `/lab` route. Users with full Pro+ entitlement do not see shadow mode unless they know to look for it.
- **Kill switch** was globally visible, broke with per-route remount thrash (commit `eb8d3be3`), got scoped to `/portfolio` only. Currently reachable only when user is on that one route.
- **Strategy lifecycle** (Draft → Backtest → Shadow → PaperValidate → LivePull → LivePush) exists in backend state enums but has no UI gate pattern. Users cannot easily "graduate" a strategy through stages.
- **Principles Dashboard** — the 14 trading principles exist in [TRADING_PRINCIPLES.md](../TRADING_PRINCIPLES.md); no surface renders compliance against them per user.
- **Activity Feed** — audit events write to DB; nothing renders them in-app. User cannot see "your circuit breaker tripped 3 times this week."

### The state-of-the-union table

| System | Backend state | Frontend surface | Gap |
|--------|--------------|----------------|-----|
| Order execution | Live, IBKR only | `TradeModal` hidden in Tax Center | Promote to every page; Trade Card as primary UI |
| Kill switch | `CircuitBreaker` fully wired | Scoped to `/portfolio` only | Global top-nav badge via `RiskProvider` context |
| Paper / shadow trading | Fully simulated via `SimulatedOrderManager` | Buried under `/lab` | First-class "Shadow" tab in strategy lifecycle |
| Strategy lifecycle | State enums present | No graduation UI | Shipped Wave 3 per Chapter 6 |
| Principles Dashboard | Rules defined | No dashboard | Wave 2 |
| Activity Feed | Audit events stored | No viewer | Wave 2 |
| Backtest | Bar-replay engine live | `/backtest` page shows mostly-empty state | Chapter 9 audit |
| G16 tax-aware exit | `TaxLotSelector` ships | Selector not wired into `OrderManager` sell path | W3.6 |
| G20 HNW alternatives | Spec only | No engine, no surface | W3.7 |
| FileFree export | 1.0.0 live | Admin-only settings panel | Promote to `/tax-center/year-end`, W3.7 |
| Cross-broker wash-sale | Single-broker only | No surface | W3.7 |
| Direct indexing | None | None | W3.7 Option A (referrals) or W3.8 (own SMA) |
| Sleeve tagging (active/conviction) | D135 shipped | No UI to tag | Wave 2 (add to position row) |
| Sync completeness (Schwab ACATS + options) | D139 + D140 shipped; unverified live | "Tax lots missing" silent | Wave 8 (companion doc) |

The pattern: **backend maturity > frontend surface area**. The sprint ahead is overwhelmingly a surfacing exercise, not a backend build.

---

## Chapter 3 — User journeys

### Journey 1 — Free user migrates from Snowball (P1)

1. User signs up at `/register` from a "best-of Snowball alternatives" article.
2. Connects IBKR via FlexQuery (`/settings/brokers`).
3. Lands on `/portfolio` — sees equity curve, drawdown, allocation treemap, dividend calendar (all free forever).
4. 3–4 weeks later, curiosity hook fires: "what did I do wrong buying XYZ at $45?" — `chart.trade_annotations` is gated (Pro). Upgrade nudge.
5. Converts to Pro ($29/mo) or drops to long-term free user.

**Acceptance**: Journey works end-to-end with no broken state, zero paywalls before the trade-annotation nudge. Lives in Wave 7.

### Journey 2 — Discretionary trader converts on a validated pick (P2a)

1. User receives a 07:15 ET notification: "Twisted Slice published: AAOI long entry $41.50, stop $39.80, target $47."
2. Taps notification → lands on Trade Card view with the pick, rationale, pre-staged order (size computed from their equity + ATR).
3. One-click "Execute" → order routes through `OrderManager` → IBKR.
4. Position appears in `/portfolio` with pink-highlight "new" marker; exit cascade active.
5. Two weeks later, adaptive trailing stop triggers at $45.80; position exits; trade journal auto-writes R-multiple ledger entry.

**Acceptance**: End-to-end latency from pick-publish to order-sent <60s. Lives in Wave 2 + Wave 6.

### Journey 3 — Systematic trader graduates a strategy (P2b)

1. User authors a rule set in the Strategy Composer (Draft state).
2. Runs backtest (`/backtest`) — sees equity curve, win rate, Sharpe, drawdown, regime attribution.
3. Promotes Draft → Shadow. Strategy runs in shadow mode for 2 weeks (real market data, no orders).
4. `/strategies/{id}/shadow-results` shows divergence from backtest (expected vs actual fills).
5. Promotes Shadow → PaperValidate. Paper orders through `SimulatedOrderManager` for 4 weeks.
6. Promotes PaperValidate → LivePull (user manually clicks "Take" on each signal). 2 weeks at LivePull.
7. Promotes LivePull → LivePush (fully automated). Circuit breaker + kill switch + portfolio-heat always active.
8. Graduation modal at each step requires explicit consent + writes an `AuditEventType.STRATEGY_TRANSITION` row.

**Acceptance**: No stage skippable; each transition records consent. Lives in Wave 3.

### Journey 4 — HNW peak-signal exit decision (P3, Quant Desk)

Founder's canonical scenario. Founder is long 30k shares of $SYM bought at $18 average; now at $72 (300% gain, $1.62M unrealized; most lots short-term). TD Sequential 13 fires on daily; weekly RSI 89; RSI divergence present. Peak signal triggers.

1. Peak-signal alert fires in-app: "$SYM peak signal detected. Consider exit."
2. User opens Trade Card → "Exit" tab. G16 `TaxLotSelector` has pre-computed three options:
   - **Full exit HIFO**: realize $1.62M gain; $1.1M short-term (ordinary income ~37% fed + state); after-tax keep ~$1.02M.
   - **Full exit LT-only lots**: realize $450k LT gain; $140k tax; keep $310k. But leaves 70% of position exposed to reversal.
   - **Scale out 1/3 now (HIFO), collar remainder, then exit remaining 2/3 over 6mo into LT**: est. blended tax $280k; keep $1.34M.
3. G20 HNW alternatives engine renders three additional options:
   - **Protective put** ($72 strike, 3mo exp): pay $1.50/sh = $45k; caps downside at $72 while deferring realization.
   - **Collar** ($72 put / $85 call): net premium $0.50/sh = $15k cost; defines exit band $72–$85.
   - **Exchange fund** (Section 351 eligibility calculator): contributes $1M of $SYM to diversified exchange fund, defers gain indefinitely; 7-year lockup.
4. FileFree preview shows year-to-date tax picture with each decision modeled.
5. User clicks decision → one-click execute → order routes → audit log captures rationale + method + lot IDs.

**Acceptance**: The entire decision surfaces in a single Trade Card; dollar math is visible at decision time; every path has a post-decision audit entry. Lives in Wave 3.6 + 3.7.

### Journey 5 — Cross-broker wash-sale avoidance (P3, Quant Desk)

1. User holds $ABC in IBKR (loss $8k) and in Schwab HSA (gain $2k).
2. User wants to harvest the $8k loss in IBKR.
3. Cross-broker wash-sale watcher flags: "selling $ABC in IBKR will trigger wash-sale against HSA $ABC position bought 18 days ago. Recommended: wait 13 days, or sell HSA lot first, or substitute with $ABD (similar but not identical; IRS safe harbor)."
4. User picks option 2 (sell HSA lot first). Orders route in sequence with audit trail.

**Acceptance**: Cross-broker check runs on every proposed disposition; IRS Rev. Rul. 2008-5 logic correct; substitute suggestions are safe-harbor-compliant. Lives in Wave 3.7.

### Journey 6 — Emergency kill

1. Market opens wildly against positions; user panics.
2. User on any page — `/portfolio`, `/pricing`, `/market`, even `/register` — sees a top-nav kill-switch badge.
3. One click → confirmation modal ("This will halt all automated trading and cancel all pending orders. Confirm?") → trip.
4. Circuit breaker state broadcasts via `/ws/risk`. All active strategies paused. Pending orders cancelled. Audit event `KILL_SWITCH_TRIP` written.
5. Banner stays on every page until manually reset from `/settings/safety`.

**Acceptance**: Reachable in one click from every authenticated page; does not re-mount per route; broadcasts to all tabs; audit is written even if UI crashes. Lives in Wave 1.

---

## Chapter 4 — Pricing audit + feature-to-tier remap

### Pricing is locked

Tier catalog per [`backend/services/billing/tier_catalog.py`](../../backend/services/billing/tier_catalog.py):

| Tier | Monthly | Annual (2-months-free) |
|------|---------|------------------------|
| Free | $0 | $0 |
| Pro | $29 | $290 |
| Pro+ | $79 | $790 |
| Quant Desk | $299 | $2,990 |
| Enterprise | custom | custom |

Founder confirmed 2026-04-22: **"we always had this yo!"** — pricing is not on the table in this review. Re-visit at Month 9 with retention data, not before.

### Current tagline leak

Current taglines per [`backend/services/billing/tier_catalog.py`](../../backend/services/billing/tier_catalog.py):

| Tier | Current tagline | Issue |
|------|-----------------|-------|
| Free | "Gorgeous charts. Forever free." | Good, keep |
| Pro | "Signals and BYOK for active traders." | OK; misses autotrade; see rewrite |
| Pro+ | "Trade cards, replay, tax engine, unlimited chat." | OK; misses autotrade surface |
| Quant Desk | "Research kit, custom universes, plugin SDK." | **Major leak**: omits autotrade + tax-alpha stack. These are the two reasons a P3 buys Quant Desk. |
| Enterprise | "SSO, dedicated cluster, custom SLA." | Good, keep |

### Proposed tagline rewrites (Wave 7)

| Tier | Proposed tagline | Why |
|------|-----------------|-----|
| Free | (unchanged) | |
| Pro | "Validated picks, single-broker autotrade, chart annotations." | Names the 3 concrete conversion hooks |
| Pro+ | "Trade cards, autotrade on every broker, tax-aware exits, replay, unlimited chat." | Surfaces multi-broker + tax-aware — both Pro+ value anchors |
| Quant Desk | "Autopilot strategies, tax-aware exits, HNW alternatives, research kit, plugin SDK." | Leads with the two moat layers |
| Enterprise | (unchanged) | |

These are two-line copy changes in [`tier_catalog.py`](../../backend/services/billing/tier_catalog.py) with Vitest snapshot updates. Ship as part of Wave 7 (launch marketing).

### Feature-to-tier remap

Current [`backend/services/billing/feature_catalog.py`](../../backend/services/billing/feature_catalog.py) places `strategy.hnw_tax_deferral` at PRO_PLUS. Per Chapter 1.7 G20 tier-gating resolution, this needs to split. New proposed mapping for features added by this review:

| New feature key | Min tier | Wave |
|-----------------|----------|------|
| `strategy.trim_signals` | Pro | W3.5 |
| `strategy.adaptive_trailing_stop` | Pro | W3.5 |
| `execution.tax_aware_exit_full` | Pro+ | W3.6 (supersedes current partial) |
| `execution.live_pull` | Pro+ | W3 |
| `execution.live_push` | Pro+ | W3 |
| `tax.g20_basics` (SBLOC / put / call educational) | Pro+ | W3.7 |
| `tax.g20_full_engine` (ranked alternatives + dollar math) | Quant Desk | W3.7 |
| `tax.cross_broker_wash_sale` | Quant Desk | W3.7 |
| `tax.filefree_1_1_0_export` | Quant Desk | W3.7 |
| `tax.direct_indexing_referrals` | Quant Desk | W3.7 (Option A) |
| `tax.direct_indexing_sma_engine` | Quant Desk | W3.8 (conditional) |
| `tax.concierge_quarterly_call` | Quant Desk add-on or bundled | W3.7+ |
| `portfolio.sleeve_tagging` | Pro+ | Already shipped ([D135](../KNOWLEDGE.md)); surface in Wave 2 |
| `safety.kill_switch_global` | Free (safety never paywalled) | W1 |
| `safety.portfolio_heat_gauge` | Free | W1 |
| `safety.circuit_breaker_per_user` | Free | W1 |
| `strategy.lifecycle_graduation` | Pro+ | W3 |
| `principles.dashboard` | Free (Pro+ for full per-principle drilldown) | W2 |
| `activity.feed_viewer` | Free | W2 |
| `portfolio.r_multiple_ledger` | Pro | W2.5 |
| `portfolio.year_in_review` | Pro+ | W9 |

The strategy split: safety + feedback surfaces (kill switch, activity, principles basics) are **Free forever** — we never gate user-protection. Revenue anchors are at Pro+ (multi-broker + tax-aware + autotrade) and Quant Desk (HNW tax-alpha + research + plugin SDK).

---

## Chapter 5 — Marketing narrative: two funnels

### Funnel 1 — Retail-pain / discipline (Free → Pro → Pro+)

**Anchor asset**: founder's public trading history + redemption arc ($1.85M → $750k → $1.47M). Updated weekly. Verifiable against IBKR statements.

**Landing pages to ship (Wave 7):**

- `/public/founder-portfolio` — live equity curve from a read-only FlexQuery tap, redacted to not leak specific positions; shows % drawdown recovery, current leverage, principle-compliance score. The single highest-leverage marketing asset; one page that no competitor can match.
- `/principles` — the 14 Trading Principles rendered beautifully with each principle's in-product enforcement linked ("Principle 1: Risk First → see it in action").
- `/journal` — founder's public trade journal. Each trade: why taken, stage at entry, regime, what principle was invoked, exit rationale, R-multiple outcome. Raw and honest.
- `/compare/snowball-analytics` — feature-matrix comparison; highlights the execution + tax layer Snowball lacks.
- `/compare/trade-ideas`, `/compare/trendspider` — similar for signal-layer competitors.

**Copy spine**: Chapter 1.6 pain-to-feature table. Each pain becomes a landing-page H2 with a screenshot + 3-sentence explanation + "try it free" CTA.

**SEO keywords (retail-pain tail)**: "trading discipline", "cut losses automatically", "swing trading journal", "stage 2 stocks", "weinstein stage analysis", "trailing stop losses", "trade review year in review".

### Funnel 2 — HNW tax-alpha (Quant Desk acquisition)

**Anchor asset**: the tax savings calculator + YTD FileFree preview.

**Landing pages to ship (Wave 7):**

- `/tax-alpha` — explains the 9-alternative G20 stack with dollar-math examples at $500k / $1M / $2.5M / $5M portfolio sizes. Leads with "$10k–$75k/yr" hero.
- `/compare/wealthfront-premier`, `/compare/betterment-premium`, `/compare/parametric`, `/compare/canvas`, `/compare/frec` — feature matrices with the fee table from Chapter 1.7.
- `/tax-calculator` — lead magnet. User inputs portfolio size + unrealized gains + income; outputs estimated savings. Captures email. Drops into `nurture_hnw` Brain sequence.
- `/filefree-integration` — explains the Paperwork Labs ecosystem + what the 1.1.0 enriched export delivers at 1099-time.
- `/hnw-journal` — P3-specific journal entries; less trade-heavy, more tax-decision-heavy. Every entry shows realized-vs-optimal tax outcome.
- `/partners/cpa` — for CPAs advising HNW clients. Positions AxiomFolio as a tool their clients should use; inbound referrals from CPA network.

**SEO keywords (HNW tail)**: "tax loss harvesting", "direct indexing", "tax efficient investing", "section 351 exchange fund", "protective put strategy", "SBLOC alternatives", "harvest losses multi-broker", "wash sale multi-account".

---

## Chapter 6 — Trading OS deep dive

### Desk IA (new navigation structure, Wave 2)

Currently the Trade button lives inside `PortfolioTaxCenter.tsx`. This is the "got lost" surface. Proposed Desk IA:

```
Top nav
├── Portfolio              (current /portfolio)
├── Market                 (current /market)
├── Desk                   (NEW)
│   ├── Trade Cards        (pick queue + pre-staged orders)
│   ├── Strategies         (Draft/Backtest/Shadow/PaperValidate/LivePull/LivePush)
│   ├── Activity           (audit + order history)
│   ├── Principles         (14 principles dashboard)
│   └── Safety             (kill switch state + circuit breaker history + portfolio heat)
├── Backtest               (current /backtest)
├── Brain                  (AgentBrain chat, Pro+)
└── Settings               (existing)
```

The **Desk** section is the unified operator surface. Trade Card is the atomic unit; Strategies is the control plane for running Trade Card flows automatically; Activity is the record; Principles is the discipline scorecard; Safety is the control surface for kill + circuit state.

### Global kill switch — designed right this time

**Why it went nuts before.** Per commit `eb8d3be3`, the old banner was imported on every route-level component and re-mounted on every route change. Each mount fired a fresh WS subscription to `/ws/risk` + a REST poll to `/risk/state`. ~20+ route changes per session × 2 requests each = "opening on every page" thrash that the founder observed and shut off by scoping the banner to `/portfolio`.

**Wave 1 redesign:**

- **Single `RiskProvider` React context** at `App.tsx` root (above router). Subscribes to `/ws/risk` **once per session**. Broadcasts via context to any component that calls `useRiskState()`.
- Compact **kill-switch badge** in the top nav, mounted inside the `AppShell`. Renders green (normal) / amber (warning) / red (tripped). One-click opens the confirmation modal.
- Modal is a separate component mounted under `App.tsx` via Radix dialog portal. Confirmation requires typing "KILL" to prevent misclick.
- Badge is reachable from **every authenticated page** including `/pricing`, `/settings`, `/register`, `/login` (iron law — safety before paywall).
- On trip: `AuditEventType.KILL_SWITCH_TRIP` written with `actor=user`, `reason=manual`; all active strategies paused via Celery task; pending orders cancelled via broker router.
- Reset requires explicit action from `/desk/safety`; cannot be reset by accident.

### Portfolio heat + leverage gauge (Wave 1)

Two gauges alongside the kill switch in the Desk Safety page (and compact in Desk top strip):

- **Portfolio heat** (Principle #3, 6% red band): aggregate at-risk capital across open positions, computed as sum of (entry - stop) × position size. Block new entries via `PortfolioHeatGuard` when red.
- **Leverage** (>1.75× red band for the founder's IBKR use case): gross long / equity. Founder currently 2.13×; gauge honestly red. Gate: no new entries above 2.5× without explicit override.

### Strategy lifecycle (Wave 3)

Backend enums exist; frontend needs a 6-stage Kanban-style view + graduation modals:

1. **Draft** — user edits rules; no execution.
2. **Backtest** — user runs walk-forward or bar-replay; results visible; promote button enabled when Sharpe > threshold.
3. **Shadow** — strategy listens to live market data, logs hypothetical orders (no real orders). 2-week minimum.
4. **PaperValidate** — `SimulatedOrderManager` executes paper orders. 4-week minimum.
5. **LivePull** — strategy emits signals; user manually approves each before order sends. 2-week minimum.
6. **LivePush** — fully automated. Circuit breaker + kill switch + portfolio heat always active.

**Graduation modal at each transition** — user must:
- Confirm target size of this strategy in their portfolio (% of equity).
- Confirm regime-gate overrides they want to allow.
- Acknowledge specific risk language ("this strategy can lose X% in a single trade").
- Write consent → `AuditEventType.STRATEGY_TRANSITION` row.

Ladder from `SHADOW_TRADING_MODE=True` default ([D137](../KNOWLEDGE.md)) to LivePush is **opt-in at every step**.

### Trade Card — atomic UI unit

A Trade Card is Portfolio × Intelligence × Strategy wrapped in one component. Key fields:

- Symbol, current price, stage, regime.
- Entry target, stop, exit target, size (computed from equity + ATR).
- Rationale (picks source; indicator signals; Oliver Kell pattern if detected).
- Pre-staged order (editable; defaults to market-on-open or limit at entry target).
- Tax lot preview (HIFO default; user can pick alternate).
- One-click Execute → routes through `OrderManager`.

Trade Card replaces `TradeModal` as the primary "place a trade" UI. `TradeModal` becomes a fallback for manual orders not tied to a pick.

### Principles Dashboard (Wave 2)

Per-user scorecard against the 14 principles. Example rows:

| Principle | Enforcement mechanism | Current score |
|-----------|----------------------|---------------|
| 1 — Risk First | `MAX_SINGLE_POSITION_PCT` enforced | 100% (13 of 13 positions within cap) |
| 2 — Cut Losses | Every live position has a stop | 92% (12 of 13 positions have active stops) |
| 3 — Portfolio Heat | Heat gauge | 78% (currently at 4.7% of 6% cap) |

Free tier sees scoring; Pro+ sees drilldown per principle with historical trend.

### Activity Feed (Wave 2)

Chronological stream of user-scoped `AuditEvent` rows with filters:

- All / Orders / Strategy transitions / Kill switch / Risk violations / Picks published / Brain interactions.
- Each row: timestamp, event type, summary, link to context.

Free tier sees last 30 days; Pro+ sees unbounded history with search.

---

## Chapter 7 — Broker-for-trading matrix

This chapter is a summary. Detail lives in **[`BROKER_COVERAGE_TRACKER.md`](BROKER_COVERAGE_TRACKER.md)** (the evergreen single-source-of-truth matrix).

### Live trading today (one broker)

- **IBKR** via `ib_insync` + Gateway. This is the only LIVE broker for write-side today.

### Trading-capable-but-not-wired-for-live

- **Schwab**: OAuth + Trader API client methods exist in `backend/services/clients/schwab_client.py`. Not routed through `OrderManager` for live orders yet.
- **TastyTrade**: SDK supports trading. Options execution rich. Not routed for live orders yet.

### Dropped

- **Alpaca**: removed per [D128](../KNOWLEDGE.md) / PR #392 (`db6fd281`). Reason: Alpaca's fractional-share model and lack of options made it strictly a subset of what Schwab/Tastytrade/IBKR already cover, with added maintenance burden. No plan to re-add.

### Explicitly not pursued

- **Plaid Investments**: rejected for v1 per [D129](../KNOWLEDGE.md). Reason: read-only, no write path; no options data; a custody middleware with its own failure modes. v1 ships direct-connect brokers only.
- **Fidelity / Robinhood / Webull / M1 / Public**: planned read-only via bronze pattern ([D130](../KNOWLEDGE.md)); no trading integration on v1 roadmap.

### Summary matrix (current state)

| Broker | Read | Options read | Tax lots | Live trading | Sleeve tagging (D135) | Wave to completeness |
|--------|------|--------------|----------|--------------|----------------------|----------------------|
| IBKR | LIVE | LIVE | LIVE (D140 verifying) | **LIVE** | LIVE | W8 (G22 re-verify) |
| Schwab | LIVE | PARTIAL (D139 verifying) | PARTIAL (ACATS gap) | PLANNED (W5) | LIVE | W8 (ACATS recovery) |
| TastyTrade | LIVE | LIVE | LIVE | PLANNED (W5) | LIVE | — |
| E*TRADE | PARTIAL (bronze) | PLANNED | PLANNED | — | — | W5 |
| Tradier | PARTIAL (bronze) | PLANNED | PLANNED | — | — | W5 |
| Coinbase | PARTIAL (bronze, crypto-only) | N/A | PARTIAL | — | N/A | W5 |
| Fidelity / RH / Webull / M1 / Public | PLANNED | — | — | — | — | Phase 5 post-v1 |

Full per-capability table with code citations in [`BROKER_COVERAGE_TRACKER.md`](BROKER_COVERAGE_TRACKER.md).

---

## Chapter 8 — Portfolio sync completeness

Summary; full diagnostic runbook + recovery paths in **[`PORTFOLIO_SYNC_COMPLETENESS_2026Q2.md`](PORTFOLIO_SYNC_COMPLETENESS_2026Q2.md)**.

### The two symptoms (founder 2026-04-22)

1. *"i dont see lots and stuff in schwab and i am wondering if that is because these positions were acats — we should figure out a strategy to ingest that info"*
2. *"svhwab options dont show either — we should ensure we get options too from portfolios"*

### Why "just fix it" is wrong

Per [D121](../KNOWLEDGE.md) evidence-based diagnosis: [D139](../KNOWLEDGE.md) (Schwab options `positionEffect` classification fix) and [D140](../KNOWLEDGE.md) (IBKR option tax-lot backfill via FIFO matcher) both shipped 2026-04-22. Per [D120](../KNOWLEDGE.md) "CI green ≠ shipped", merging to main does not equal live in prod. Before writing any new code for symptom 1 or 2, we must **verify D139 and D140 are actually live on the founder's specific accounts**.

If they are, symptom 2 may be already-resolved (no code; just UI refresh). If they aren't, Wave 8's first step is live-in-prod verification via Render deploy SHA + `/api/v1/market-data/admin/health` + direct API probe.

### Recovery paths for data brokers don't return

For cost basis on ACATS-transferred positions, 4-path fallback:

1. **Broker-native API** (first-class when it works; Schwab `/accounts/{id}/positions` sometimes returns cost basis on transferred lots if the ACATS data was complete).
2. **1099-B annual parse** (IRS-authoritative; parse PDF via existing `pymupdf` stack; user uploads once per year).
3. **CSV import** (user-provided; current-year data; accept `symbol, acquired_date, quantity, cost_basis, sub_account_id`).
4. **Manual entry** (last resort; lot editor UI; require explicit confirmation).

Schema addition: `TaxLot.cost_basis_source` enum (`broker_reported | acats_recovered_csv | acats_recovered_1099b | manual_entry | unknown`).

### Wave 8 gating

Wave 8 blocks Wave 3.7 FileFree 1.1.0 bump. Sleeves + tax-alpha exports are only as accurate as the tax lots underneath them; we will not ship a "year-end tax package" built on partial cost-basis data.

---

## Chapter 9 — Backtest reality check

### Founder claim (verbatim)

*"Backtest does Nothing."*

### What exists on the backend

- `BacktestEngine` in `backend/services/backtest/`, bar-replay via `SimulatedOrderManager` (parity with live `OrderManager`).
- Walk-forward + Monte Carlo are Phase 6 scope, not shipped.
- Rule evaluator accepts `Strategy` definitions and produces `OrderIntent` lists.

### What doesn't work end-to-end

- `/backtest` frontend page renders mostly-empty state for most strategies.
- No regime-conditional performance breakdown in UI.
- No equity-curve + drawdown chart; just a results table that doesn't load.
- No "backtest-to-live parity" reports (is live execution diverging from what backtest predicted?).

### Audit outcome

Backtest is **not "does Nothing"** — the engine computes real results. It **is** a UX dead zone. The founder's perception reflects the frontend: the page returns numbers, but they're not useful because the visualization and comparison layer is missing. Fix is mostly frontend + result persistence, not a backend rebuild.

### Wave 4 scope (backtest surfacing)

- Persist `BacktestRun` with full equity curve as time-series.
- New `/backtest/{id}` page: equity curve with annotations (entries/exits), drawdown, rolling Sharpe, regime-attributed returns.
- Compare 2+ runs side-by-side.
- Promote-to-Shadow button at bottom (ties into Chapter 6 strategy lifecycle).
- Parity report: for a live strategy, compare YTD live equity curve against the backtest's YTD projection; flag divergence.

Walk-forward + Monte Carlo remain Phase 6 (World-Class milestone).

---

## Chapter 10 — Marketing channels + per-channel CAC

### Retail funnel (Chapter 5 Funnel 1)

| Channel | Hypothesized CAC | Notes |
|---------|------------------|-------|
| Organic SEO (stage-analysis, trading-discipline keywords) | $0 variable; $30k upfront content | 6-month lag before meaningful traffic |
| Twitter/X founder account (Axis 2 trades public) | $0 variable; requires founder time | Primary early channel; high retention of followers |
| YouTube long-form (founder trade reviews, drawdown recovery) | $100–$300 per sub; time-heavy | High-trust channel for swing traders |
| Reddit r/stocks, r/swingtrading, r/wallstreetbets | $0 direct; paid AMAs $500–$2k | Narrow-window opportunistic |
| Podcast sponsorships (Chat With Traders, etc.) | $2k–$10k per spot | Test 2–3 before scaling |
| Paid search (low-intent "best stock screener" etc.) | $40–$120 per signup | Likely poor LTV/CAC until Pro+ upsell proven |

**Recommended Month-1 mix**: organic SEO content build + Twitter/X founder + Reddit AMAs + 1 podcast spot. Paid search deferred until Funnel 2 (HNW) is proven — organic alone isn't enough there.

### HNW funnel (Chapter 5 Funnel 2)

| Channel | Hypothesized CAC | Notes |
|---------|------------------|-------|
| CPA partner referrals (`/partners/cpa`) | Revenue share 10–20% of year-1 sub; no upfront CAC | Highest-trust; slow to build |
| LinkedIn targeted content ("for $1M+ portfolios") | $200–$800 per qualified signup | Most scalable HNW channel |
| `/tax-calculator` lead magnet + `nurture_hnw` Brain sequence | $50–$200 per email captured; converts at 3–8% | Primary funnel engine |
| "Compare" pages + SEO (wealthfront-premier alternative, parametric alternative) | $30k content upfront; organic over 6–12 months | Defensible against incumbent marketing spend |
| Conferences (Bogleheads, FPA, NAPFA) | $2k–$10k per event; high LTV if landed | Try 1 in Month 9 |

**Recommended Month-1 mix**: `/tax-calculator` + LinkedIn content + comparison SEO pages. CPA partner outreach starts Month 3 after at least 20 Quant Desk subs are on the platform.

### LTV/CAC targets

- **Retail funnel**: LTV/CAC ≥ 3× at 12mo. Blended ARPU ~$480/yr (weighted across Pro-heavy mix).
- **HNW funnel**: LTV/CAC ≥ 5× at 12mo (longer payback tolerable). Blended ARPU ~$4,000+/yr once retention compounds.

---

## Chapter 11 — Execution roadmap: 15 waves

### Wave dependency graph (summary)

```
W1 Safety ─→ W2 Desk IA ─→ W2.5 R-ledger ─→ W3 Strategy lifecycle ─→ W3.5 Trim/trail
                                                                  ─→ W3.6 G16 exit wiring
                                                                  ─→ W3.7 HNW alternatives (G20 + wash-sale + FileFree 1.1.0)
                                                                  ─→ W3.8 Direct-Indexing SMA engine [CONDITIONAL, gated Month 6]
                                                                  ─→ W4 Backtest surfacing
W1 Safety ─→ W8 Sync completeness ─→ W3.7 (blocks FileFree 1.1.0) ─→ W5 Multi-broker live
W2 Desk IA ─→ W6 Pick-to-Trade-Card flow
W2 + W3 ─→ W7 Launch marketing (taglines + public pages)
W10 Dogfood amplification runs in parallel W1–W7
W9 Year-in-Review (Q4 shipped)
W11 Principles Dashboard (parallel W2)
W12 Activity Feed (parallel W2)
W13 Per-user circuit breaker (parallel W1)
W14 Brain expansion (parallel W3+)
W15 Enterprise scaffold (post-launch)
```

### Wave 1 — Safety foundation (Week 1)

**Goal**: kill switch, portfolio heat, leverage gauge visible on every page; circuit breaker per-user; safety is Free-tier always.

- Single `RiskProvider` React context at `App.tsx`.
- Compact kill-switch badge in `AppShell` top nav.
- Confirmation modal requires typing "KILL".
- Portfolio-heat gauge + leverage gauge in new `/desk/safety` page, compact strip in top-nav for Pro+ users.
- Per-user circuit breaker refactor (move from global singleton to `CircuitBreakerService(user_id)`).
- Danger-zone touches: `backend/services/execution/circuit_breaker.py`, `backend/services/execution/risk_gate.py`. Get founder approval per `protected-regions.mdc` before modifying.

**Acceptance**: kill switch reachable in one click from every page; WS opens once per session not per route; trips write audit; UI never re-mounts on route change.

**Reversibility**: yes — revert `RiskProvider` to prior per-route banner.

### Wave 2 — Desk IA + Principles + Activity (Week 2)

- New `/desk/*` routes: `trade-cards`, `strategies`, `activity`, `principles`, `safety`.
- Top-nav restructure per Chapter 6.
- Principles Dashboard (basic scorecard, Free tier; drilldown Pro+).
- Activity Feed viewer (30 days Free; unbounded Pro+).
- Sleeve tagging UI added to position row ([D135](../KNOWLEDGE.md) already ships backend).

**Acceptance**: user can find every previously hidden surface via top nav in ≤2 clicks. Activity Feed renders user-scoped audit rows. Principles Dashboard scores at least 6 principles with real-time data.

### Wave 2.5 — R-multiple ledger (Week 2, parallel W2)

- On every order fill, write `RMultipleLedger` row with planned-R, actual-R, regime, stage, pick source.
- Read endpoint + UI card on `/desk/activity`.
- Aggregate view: distribution histogram, cumulative R by regime.

### Wave 3 — Strategy lifecycle (Weeks 2–3)

- Strategy Kanban view: Draft → Backtest → Shadow → PaperValidate → LivePull → LivePush.
- Graduation modal at each transition with consent copy + audit event.
- Minimum-duration enforcement (Shadow ≥ 2wk, PaperValidate ≥ 4wk, LivePull ≥ 2wk).
- Feature gates: `execution.live_pull` + `execution.live_push` at Pro+.

### Wave 3.5 — Trim signals + adaptive trailing (Week 3)

- Trim-signal detector (peak-signal: TD13 + RSI divergence + RS roll-over).
- Adaptive trailing stop: widens in early Stage 2, tightens in late Stage 2 and Stage 3.
- Alert + UI surface on position row.

### Wave 3.6 — G16 wiring (Week 4)

- Wire `TaxLotSelector` into `OrderManager` sell path. Default HIFO on tax-aware exit orders.
- Tax-lot preview in Trade Card exit flow.
- Audit event `TRADE_EXECUTE` includes `lot_selection_method` + `selected_lot_ids`.
- Feature gate: `execution.tax_aware_exit_full` at Pro+.

### Wave 3.7 — HNW alternatives + cross-broker wash-sale + FileFree 1.1.0 (Weeks 4–5)

**Largest single wave; ships the tax-alpha moat layer.**

- `DeferralAlternativesEngine` with 9-alternative evaluator (Ch 1.7).
- Cross-broker wash-sale watcher (IRS Rev. Rul. 2008-5 logic across IBKR + Schwab + TT).
- Direct-indexing **Option A** partner referrals (Cache / Aperture / Canvas / Frec / Parametric).
- FileFree schema 1.1.0 bump (Ch 1.7 table).
- Tier gates: basics at Pro+ (`tax.g20_basics`), full engine + cross-broker + direct-indexing + FileFree 1.1.0 at Quant Desk.
- GAPS spec amendment ([`GAPS_2026Q2.md:1141`](GAPS_2026Q2.md)) — split G20 tier gates per Ch 1.7 resolution.
- **Blocks on Wave 8** (sync completeness).

### Wave 3.8 — Direct-indexing SMA engine (Month 6, CONDITIONAL)

- Build `DirectIndexingEngine` that harvests losses on individual holdings inside a tracked index.
- **Gate conditions** (all three must hold):
  1. ≥20 Quant Desk subscribers with ≥$500k portfolios.
  2. Outside RIA counsel approves user-selects-index posture, OR founder elects to register AxiomFolio as an RIA.
  3. ≥30% of W3.7 Option A partner referrals convert within 6 months.
- If any gate fails, W3.7 Option A is sufficient moat.

### Wave 4 — Backtest surfacing (Week 5)

- Persist `BacktestRun` equity curve as time series.
- New `/backtest/{id}` page (Chapter 9).
- Side-by-side comparison UI.
- Parity report for live strategies.
- Walk-forward + Monte Carlo remain Phase 6.

### Wave 5 — Multi-broker live trading (Week 6)

- Route Schwab through `OrderManager` for live orders.
- Route TastyTrade through `OrderManager` for live options.
- Per-broker config panel in `/settings/brokers` (paper / shadow / live toggle).
- `ALLOW_LIVE_ORDERS` feature flag per-broker per-user.

### Wave 6 — Trade Card as primary UI (Week 4)

- New `TradeCard.tsx` component replacing `TradeModal` as primary.
- Wired into picks feed, strategy signals, peak-signal alerts.
- Pre-staged order fields editable before execute.

### Wave 7 — Launch marketing (Week 7)

- Tagline rewrites ([`tier_catalog.py`](../../backend/services/billing/tier_catalog.py)).
- Public pages: `/public/founder-portfolio`, `/principles`, `/journal`, `/tax-alpha`, `/tax-calculator`, `/compare/*`, `/hnw-journal`, `/partners/cpa`, `/filefree-integration`.
- Blog seed content: 5 retail posts + 5 HNW posts before launch.

### Wave 8 — Portfolio sync completeness (Week 1–2, blocks W3.7)

- See [`PORTFOLIO_SYNC_COMPLETENESS_2026Q2.md`](PORTFOLIO_SYNC_COMPLETENESS_2026Q2.md) for full spec.
- Wave 8.0: diagnostic runbook verifies D139 + D140 live.
- Wave 8.1: `cost_basis_source` enum schema migration.
- Wave 8.2: CSV import (Path 3).
- Wave 8.3: 1099-B parser (Path 2).
- Wave 8.4: manual-entry UI (Path 4).
- Wave 8.5: `/api/v1/portfolio/sync-completeness` + tax-center banner.

### Wave 9 — Trading Year in Review (Q4 2026)

- Per-user end-of-year wrap: trade journal stats, top winners/losers, regime-attributed performance, principle compliance score, R-multiple histogram.
- FileFree 1.1.0 export downloadable from the YIR surface.

### Wave 10 — Dogfood amplification (parallel, runs Week 1–7)

- `/public/founder-portfolio` live feed.
- `/journal` entries authored 2–3× per week by the founder.
- Twitter/X automation: auto-post trade closures above a threshold with R-multiple and P&L.
- Post-drawdown-recovery hero sequence on `/public/founder-portfolio`.

### Wave 11 — Principles Dashboard deepening (parallel W2)

- Per-principle trend lines, week-over-week.
- Coach-mode hints when compliance drops ("You're below 90% on Principle 2 this week; 3 positions missing stops").

### Wave 12 — Activity Feed power-user features (parallel W2)

- Filter / search.
- Export CSV.
- Brain chat integration: "summarize last 30 days of activity".

### Wave 13 — Per-user circuit breaker (parallel W1)

- Refactor existing global `CircuitBreaker` to per-user. Multi-tenancy fix.
- Each user has own drawdown threshold, own order-count threshold, own kill-switch state.

### Wave 14 — Brain expansion (parallel W3+)

- NL strategy builder ("build me a rule that buys Stage 2A under $50 with insider buying").
- Trade decision explainer per order.
- Incident postmortem bot for Quant Desk.

### Wave 15 — Enterprise scaffold (post-launch, Year 2)

- SSO (SAML + OIDC).
- Audit export to SIEM.
- Dedicated infra provisioning.
- White-label surfaces.

### Wave 16 — Medallion migration + warehouse lint (parallel, 7 weeks, non-blocking for W1–W14; mandatory gate before W15)

Formalizes [D127](../KNOWLEDGE.md) and [D145](../KNOWLEDGE.md) per Chapter 1.8. Runs in parallel with feature waves; no shared code paths beyond file moves + import rewrites.

- **Sub-wave 16.1 — Audit & tags** (Week 1). Produce `docs/plans/MEDALLION_AUDIT_2026Q2.md` listing every `backend/services/*` module with current path, target layer, and move risk (HIGH / MEDIUM / LOW).
- **Sub-wave 16.2 — Lint rule + CI gate** (Week 2). Custom Ruff/pylint rule forbidding cross-layer import violations (`bronze → silver/gold` banned; `silver → gold` banned; non-`gold/` write to gold tables banned).
- **Sub-wave 16.3 — LOW-risk relocations** (Weeks 2–3). Leaf-level utilities; one PR per move; `ruff --fix` handles imports.
- **Sub-wave 16.4 — MEDIUM-risk silver relocations** (Weeks 3–5). `market/indicator_engine.py` + `stage_classifier.py` + `regime_engine.py` → `silver/`. One PR per module. CI gate catches misses.
- **Sub-wave 16.5 — HIGH-risk bronze relocations** (Weeks 5–6, founder-approved). `portfolio/ibkr/*`, `portfolio/schwab_sync_service.py`, `portfolio/tastytrade_sync_service.py` → `bronze/<broker>/`. 2-week dual-path bake before removing old path.
- **Sub-wave 16.6 — Materialized-view / DuckDB export** (Week 7, conditional). Gated by `/admin/metrics` or `/portfolio/year-in-review` p95 > 2s for ≥1 week.

**Acceptance criteria for Wave 16:**
- Every file under `backend/services/` is either inside `bronze/ | silver/ | gold/` or has an explicit `# medallion: grandfathered; move in issue #NNN` docstring tag.
- CI lint rule fails any PR that introduces a cross-layer violation.
- `docs/ARCHITECTURE.md` medallion section reflects the post-move reality.
- Audit counters in the last 30 days of `market_snapshot_history` writes show `written + skipped + errors == total` with zero silent-no-op rows.

---

## Chapter 12 — Risks, reversibility, decision boundaries

### The five biggest platform risks, ranked

**R1 — Live trading incident with real capital.** Wave 1 (safety) + Wave 3 (strategy lifecycle with paper-first graduation) + Wave 13 (per-user circuit breaker) are all mitigations. Reversibility: kill switch + manual order cancel. Residual: user-error on a misconfigured strategy that executes before the kill switch engages. Accept risk; document per-wave in `KNOWLEDGE.md`.

**R2 — Regulatory / fiduciary surprise on direct indexing (W3.8).** Gated by outside RIA counsel review. Option C (W3.7 Option A partner referrals as default) limits exposure. If RIA registration is required, 3–6mo lead time + $25–50k/yr cost; that's a business decision the founder owns, not an engineering one. Reversibility: revert to referral-only model.

**R3 — FileFree schema contract drift.** Any 1.1.0 field added must be backward-compatible on Paperwork Labs Brain side. Coordinate with Brain team via existing HMAC webhook contract; version in schema field. Reversibility: downgrade to 1.0.0 at API level while keeping DB fields populated.

**R4 — Quant Desk LTV lift fails to materialize.** Thesis: retention lifts from 2% → 1.3% monthly once tax-alpha stack is live. If it doesn't, Quant Desk pricing is under-anchored. Reversibility: re-tier features from Quant Desk down to Pro+ (but this is a bad move — better to double down on concierge, content, and CPA partnerships).

**R5 — Kill switch re-thrash.** The redesigned `RiskProvider` pattern must not regress. Acceptance tests: WS opens once per session; route changes do not trigger new subscriptions; badge renders in <50ms on mount. Reversibility: revert to per-route banner (known-bad, but safe fallback).

### Reversibility policy

Every wave in Chapter 11 must be reversible without data loss. Patterns:

- **Feature flags**: every new gated feature must have a kill-flag that disables it without rolling back the deploy.
- **Additive schema**: all schema changes are additive (new columns, new tables); no drops, no renames.
- **Audit log**: every significant state change writes an audit event so rollback can reconstruct state.
- **Paper-first**: any live-trading path must have a paper-mode counterpart; paper must be the default.

### Danger-zone approvals needed

Per `protected-regions.mdc`, the following require explicit founder approval before any PR touches them:

- `backend/services/execution/risk_gate.py` (W1, W13, W3.6, W3.7)
- `backend/services/execution/order_manager.py` (W3.6, W5)
- `backend/services/execution/exit_cascade.py` (W3.5)
- `backend/services/risk/circuit_breaker.py` (W1, W13)
- `backend/services/market/indicator_engine.py` (no wave touches; confirmed)
- `backend/services/market/stage_classifier.py` (no wave touches; confirmed)
- `backend/services/market/regime_engine.py` (no wave touches; confirmed)
- `backend/api/routes/auth.py` (W15 only; no earlier waves)
- `backend/config.py`, Alembic versions, `backend/tasks/job_catalog.py` (W1, W3, W8, W13)

### Decision boundaries

- **Pricing**: locked this review. Next revisit Month 9 post-retention-data.
- **Alpaca re-add**: no. Stay firm per [D128](../KNOWLEDGE.md).
- **Plaid**: no for v1 per [D129](../KNOWLEDGE.md). Revisit Month 12 if direct-connect broker roster stalls.
- **Direct indexing own-engine (Option B)**: Month-6 gate review. No earlier.
- **Founder personal capital exposure on public pages**: stay aggregate-only (no specific positions, no specific dollar amounts below $100k granularity). Exact IBKR equity + leverage is OK (already public here); position-level detail is not.

---

## Chapter 13 — D144 + D145 commitments (summary)

Per decision log [`docs/KNOWLEDGE.md#d144`](../KNOWLEDGE.md) and [`docs/KNOWLEDGE.md#d145`](../KNOWLEDGE.md), the platform is organized around 15 commitments. Restated for convenience:

1. **Two-layer moat**: retail-discipline (Ch 1.6) + HNW tax-alpha (Ch 1.7), both dogfooded by the founder per [D118](../KNOWLEDGE.md).
2. **Pricing ladder unchanged** (Free / Pro $29 / Pro+ $79 / Quant Desk $299 / Enterprise custom). Taglines rewritten in Wave 7.
3. **Quant Desk LTV lift** $3,588/yr nominal → $14–25k/yr blended from tax-alpha retention (churn 2% → 1.3% monthly) + annual tier-upgrade cadence + partner-referral take-rate.
4. **Competitive anchoring**: Pro+ vs Trade Ideas / TrendSpider / Composer; Quant Desk vs Wealthfront / Betterment / Parametric / Canvas / Frec with no-custody + multi-broker structural edge at $5M+.
5. **16 waves total; 14 on critical path. W3.8 conditional; W16 parallel non-blocking through W14, mandatory gate before W15.**
6. **New waves** not in MASTER_PLAN Phase 3: W2.5 R-multiple ledger, W3.5 trim + trailing, W3.6 G16 wiring, W3.7 HNW alternatives + cross-broker wash + FileFree 1.1.0, W3.8 conditional SMA engine.
7. **G20 tier-gating resolved**: Pro+ basics / Quant Desk full engine. Requires `GAPS_2026Q2.md` amendment.
8. **Direct-indexing strategy**: W3.7 Option A default (partner referrals); W3.8 Option B optional on Month-6 gate (≥20 Quant Desk subs ≥$500k + RIA counsel + ≥30% partner attach).
9. **FileFree 1.1.0 via Brain webhook** per [D89](../KNOWLEDGE.md) / [D99](../KNOWLEDGE.md) / [D100](../KNOWLEDGE.md). Never import FileFree code.
10. **Two-funnel marketing**: retail-pain (founder redemption arc) + HNW tax-alpha (tax calculator + compare pages). Ch 5 + Ch 10 copy.
11. **Founder capital pinned**: IBKR $1.47M equity at 2.13× leverage (margin **used** $1.67M); Schwab HSA $33k equities-only; $2.5M target next 8–12 weeks as speculative-sleeve unwind.
12. **Sync completeness (W8) blocks FileFree 1.1.0 (W3.7)**. [D139](../KNOWLEDGE.md) + [D140](../KNOWLEDGE.md) must be verified live in prod per [D120](../KNOWLEDGE.md) before re-diagnosing options / tax-lot symptoms.
13. **G22 FlexQuery validator** per [handoff](../handoffs/2026-04-21-g22-shipped-next-g23.md) applied to W8: evidence-based diagnosis per [D121](../KNOWLEDGE.md).
14. **Kill switch redesigned** via single `RiskProvider` React context at `App.tsx` root. Reachable on every authenticated page, iron law. Portfolio-heat + leverage gauges ship alongside in W1.
15. **Medallion + data-warehouse discipline** per [D127](../KNOWLEDGE.md) + [D145](../KNOWLEDGE.md) + Ch 1.8. Bronze / silver / gold layering enforced by CI lint from Wave 16.2. Five warehouse disciplines (append-only ledgers, idempotent bronze writes, deterministic silver, additive schema, counter-based auditing) codified as iron laws. Warehouse is treated as a first-class moat asset: no-custody + multi-broker + portable data outlives the platform.

---

*Last reviewed: 2026-04-22. Next review at end of Wave 3.7 ship (6 weeks out).*
