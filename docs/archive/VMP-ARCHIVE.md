# Paperwork Labs — Venture Master Plan Archive

Detailed specs archived from VENTURE_MASTER_PLAN.md per D52 (Doc Hygiene rules). These specs are Phase 5+ features that aren't needed in full detail yet, and review findings that are all FIXED. The main VMP retains summaries with references to this archive.

**Archived**: 2026-03-18

---

## Section 8: Plan Hygiene (Archived)

The anti-bloat rules from Section 8 are now baked into the cleanup process. Key rules:
1. Phase Completion Collapse: completed phase tables become one-line summaries
2. KNOWLEDGE.md Rotation: archive every 6 months, keep under 500 lines
3. TASKS.md Sprint Archive: completed sprints collapse to summaries
4. Master Plan Target: under 3,500 lines

Previously superseded plans (15 Cursor plan files) are tracked in git history only.

---

## Section 9: McKinsey Self-Review Findings (All Rounds)

All findings below are FIXED. Preserved here for audit trail.

### Review Round 4-5: Distill Brand + Architecture Optimization

| # | Finding | Persona | Severity | Status | Action |
|---|---------|---------|----------|--------|--------|
| H1 | packages/data/ overloaded | Engineering | HIGH | FIXED | Split into data/, tax-engine/, document-processing/. D70. |
| H2 | Multi-tenant data isolation unspec'd | Engineering | HIGH | FIXED | Added RLS + firm-scoped middleware. P9.9 security audit. |
| H3 | B2B creates DPA need | Legal | HIGH | FIXED | Added DPA to Section 1C. P9.10 task. |
| M1 | Phase 9 timing unrealistic | Engineering | MEDIUM | FIXED | Accelerated to Summer 2026 (D74). |
| M2 | B2B API and CPA SaaS conflated | Strategy | MEDIUM | FIXED | Distill brand architecture resolves. |
| M3 | Infra cost doesn't reflect 5 apps | CFO | MEDIUM | FIXED | Added Vercel Pro to FINANCIALS.md. |
| M5 | 2M user projection double-counts | Growth | MEDIUM | FIXED | Split Direct Users vs API Volume. |
| M6 | PARTNERSHIPS.md missing CPA motion | Partnerships | MEDIUM | FIXED | Added Section 3.5 to PARTNERSHIPS.md. |
| L1 | Circuit breaker needs B2B SLA | QA | LOW | FIXED | Added 99.5% uptime SLA note. |
| L2 | CPA referral flywheel under-emphasized | Strategy | LOW | FIXED | Added moat point 6. |
| L3 | Phase 1 missing Distill scaffold | Engineering | LOW | FIXED | Added P1.9c. |
| L4 | Annual billing discount not in financials | CFO | LOW | FIXED | Added to FINANCIALS.md. |
| R5a | "FileFree Pro" B2B trust issue | Growth | HIGH | FIXED | Renamed to Distill. D71. |
| R5b | B2B GTM strategy missing | Growth | HIGH | FIXED | Added Section 5M. |
| R5c | Audit trail needed for CPA compliance | QA | MEDIUM | FIXED | Added to Section 1C. P9.11 task. |
| R5d | TaxWire missing from competitors | Strategy | LOW | FIXED | Added TaxWire. |

### Review Round 3: Marketplace Architecture Deep Dive

| # | Finding | Persona | Severity | Status | Action |
|---|---------|---------|----------|--------|--------|
| F13 | No Phase tasks for marketplace tables | Engineering | MEDIUM | FIXED | Added to P5.1. |
| F14 | Partner auth not in Phase tasks | Engineering | MEDIUM | FIXED | Added P5.12. |
| F15 | Tier 2 consent only on Refund Plan | Legal | MEDIUM | FIXED | Added profile/settings page opt-in. |
| F16 | Stage 3 chicken-and-egg | Strategy | MEDIUM | FIXED | Added key account strategy. |
| F17 | Data reciprocity mechanism unspecified | Partnerships | MEDIUM | FIXED | Added technical mechanism by stage. |
| F18 | ARPU jump S1->S2 needs justification | CFO | MEDIUM | FIXED | Added worked example. |
| F19 | CCPA "sale" analysis needed | Legal | LOW | OPEN | Review before Stage 3. |
| F20 | FTC consent order reference missing | Legal | LOW | FIXED | Added FTC v. Credit Karma. |
| F21 | CK no longer does tax filing | Strategy | LOW | FIXED | Updated competitor table. |
| F22 | factors_json encryption | QA | LOW | FIXED | Clarified: no PII values stored. |
| F23 | Missing competitors | Growth | LOW | FIXED | Added NerdWallet, TaxSlayer, TaxDown, MagneticTax. |
| F24 | Partner hit list not scored | Partnerships | LOW | OPEN | Score when outreach begins. |

### Review Rounds 1-2: Original Self-Review

All 12 findings addressed. Key outcomes incorporated throughout the plan.

| # | Finding | Severity | Impact |
|---|---------|----------|--------|
| F1 | Scope risk | CRITICAL | Managed via 3-tier command center |
| F2 | CAN-SPAM + company structure | CRITICAL | Section 0B-0C added |
| F3 | Social content pipeline | HIGH | DIY n8n pipeline ($0.10/video) |
| F4 | 50-state data pipeline | RESOLVED | Full coverage via AI extraction |
| F5 | Founder 2 bandwidth | RESOLVED | Scale with traction |
| F6 | Studio + brand palettes | HIGH | Multi-brand CSS variable theming |
| F7 | RA legal + trademark risk | CRITICAL | Section 0C added |
| F8 | Cross-sell compliance | HIGH | Content Review Gate checklist |
| F9 | Admin UX approach | MEDIUM | Functional over beautiful |
| F10 | Content compliance | LOW | 30-day manual review period |
| F11 | CI path filters | MEDIUM | dorny/paths-filter spec |
| F12 | Voice clone quality | LOW | ElevenLabs startup grant |

---

## Section 10: Key Decisions (All Decided)

All 11 decisions are resolved. See KNOWLEDGE.md for the decisions log.

1. LLC Name: Paperwork Labs LLC (California) - D54
2. RA Strategy: Partner RA with wholesale volume pricing - D41
3. Phase 4 Scope: Full 13-page command center in 3 tiers
4. Social Content: Build pipeline first, validate 2 weeks
5. Founder 2 Priority: Scale with traction
6. Domains: paperworklabs.com + launchfree.ai + filefree.ai purchased
7. Trademark timing: File after product launch (need specimen)
8. AI Model Routing: 9-model strategy - D39
9. Trinkets: Phase 1.5, financial calculators first - D38
10. Trinkets domain: tools.filefree.ai subdomain - D57
11. LLC State: California - D54

---

## Section 11: Valuation Estimate (Merged)

Merged into Section 0D of main VMP. See Section 0D for the single authoritative valuation analysis.

---

## Archived Detail: 4C Event Taxonomy (Full)

Every user action with intelligence value captured as a UserEvent (immutable, append-only log).

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

CREDIT SCORE EVENTS (Phase 1.5):
  credit_score_opt_in       -- consent_timestamp, provider (Array/SavvyMoney)
  credit_score_requested    -- provider, request_type (soft_pull)
  credit_score_received     -- score_band (e.g., 700-749), provider
  credit_score_changed      -- previous_band, new_band, direction (up/down/stable)

CROSS-PRODUCT EVENTS:
  cross_product_opt_in      -- source_product, consent_timestamp
  cross_product_opt_out     -- source_product
  email_sent                -- campaign_id, template_id
  email_opened              -- campaign_id
  email_clicked             -- campaign_id, link_id
  email_unsubscribed        -- campaign_id
  in_app_notification_shown -- notification_id
  in_app_notification_clicked -- notification_id

MARKETPLACE EVENTS (all stages):
  partner_product_viewed        -- partner_product_id, placement, fit_score, rank_position
  partner_product_clicked       -- partner_product_id, fit_score, rank_position, scoring_method
  fit_score_computed            -- venture_identity_id, partner_product_id, score, score_version
  match_confidence_displayed    -- partner_product_id, confidence_label
  recommendation_list_rendered  -- list_length, scoring_method, placement, profile_completeness
  personalized_matching_opt_in  -- consent_timestamp, consent_tier
  personalized_matching_opt_out -- consent_timestamp

PARTNER-SIDE EVENTS (Stage 3+):
  partner_product_submitted     -- partner_id, product_type, eligibility_criteria_count
  partner_criteria_updated      -- partner_product_id, fields_changed[]
  partner_bid_placed            -- partner_product_id, segment_id, bid_cents
  partner_bid_adjusted          -- partner_product_id, old_bid_cents, new_bid_cents
  partner_dashboard_viewed      -- partner_id, page
  partner_segment_report_downloaded -- partner_id, segment_id, report_type
```

---

## Archived Detail: 4E Recommendation Engine (Full Spec)

3-layer pipeline. Scorer interface stays the same from Stage 1 to Stage 4.

```
Layer 1: CANDIDATE GENERATION
  Input:  user's financial profile + consent status + placement context
  Output: list of eligible partner_products
  Stage 1:  SELECT * FROM partner_products WHERE status = 'active' AND state match
  Stage 2+: Add credit score range filter, income range filter
  Stage 3+: Run partner_eligibility criteria matching per product

Layer 2: SCORING (the pluggable layer)
  Input:  (user_profile, partner_product) pairs
  Output: fit_score (0-100) per pair
  Stage 1 (static):     score = 50, order by commission DESC
  Stage 2 (rules):      credit_match*0.3 + income_match*0.3 + state*0.2 + conversion*0.2
  Stage 2+ (bandit):    Thompson Sampling, ~200 lines Python
  Stage 3+ (ML):        Collaborative filtering, predicted conversion probability
  Interface:            score(user_profile, product) -> FitScore{score, factors, method, confidence}

Layer 3: RANKING + RENDERING
  Stage 1: order by commission DESC
  Stage 2+: order by fit_score DESC
  Stage 3+: blended = fit_score*0.7 + bid_weight*0.3
  FTC constraint: NEVER "pre-approved"/"guaranteed". PERMITTED: "strong match", "94% fit"
```

Campaign rules (cross-product engagement):
- Rule 1: Post-Filing LLC Cross-Sell (filed_taxes + 1099 income + opted in → email after 72h)
- Rule 2: Post-Formation Tax Cross-Sell (has LLC + tax season + opted in → January email)
- Rule 3: Abandoned Formation Recovery (started + no complete in 48h → email)
- Rule 4: RA Credit Upsell (purchased RA + no credits + 7 days → email)

---

## Archived Detail: 6I Agent Org Chart + Governance (Full)

44 agents total: 24 Cursor personas + 20 n8n workflows.

```
FOUNDER (Root)
├── CHIEF OF STAFF (ea.mdc)
│   ├── EA Ops Monitor (n8n: ea-daily, ea-weekly)
│   └── Compliance Monitor (n8n)
├── VP ENGINEERING (engineering.mdc)
│   ├── Tax Domain (tax-domain.mdc), Formation Domain, Studio Lead
│   ├── AI Ops Lead (agent-ops.mdc)
│   └── QA Lead (qa.mdc) → QA Scanner, State Validator, IRS Monitor
├── VP PRODUCT (ux.mdc)
├── VP GROWTH
│   ├── FileFree Growth → Social + Content Pipeline
│   ├── LaunchFree Growth → Social + Content Pipeline
│   └── Analytics Reporter
├── VP BRAND → FileFree Brand, LaunchFree Brand
├── GENERAL COUNSEL (legal.mdc) → Content Review Gate, Compliance Bot
├── CFO (cfo.mdc) → Affiliate Revenue Tracker
├── VP PARTNERSHIPS (partnerships.mdc) → Outreach Drafter, Intelligence
├── CPA / TAX ADVISOR (cpa.mdc) → CPA Tax Review
├── CUSTOMER SUCCESS → L1/L2 Support Bots, KB Sync
├── COMPETITIVE INTEL (n8n)
├── STRATEGY (strategy.mdc) → Weekly Check-in
├── WORKFLOWS (workflows.mdc)
└── INFRA HEALTH MONITOR (n8n)
```

Agent status levels: Active (live), Standby (prompt ready, not deployed), Planned (in org chart only).

15 Active agents, 10 Standby, 9 Planned. Full status table preserved here.

Governance Protocol (Multi-Agent Consensus): PROPOSE → ROUTE to affected agents → REVIEW from domain perspective → VERDICT (APPROVE/CONCERN/BLOCK) → RESOLVE. Founder is final arbiter. Used for: architecture changes, new forms, legal decisions, partner integrations. NOT for: bug fixes, copy changes, routine tasks.

Overlap Resolution: EA owns operational tracking, CFO owns analysis. EA owns tactical planning, Strategy owns direction. Agent-Ops owns model optimization, QA owns security review.

EA Agent Split: EA Interactive (ea.mdc, Cursor) handles decisions/queries. EA Ops Monitor (n8n cron) handles daily/weekly briefings. Interactive EA does NOT generate briefings. Ops monitor does NOT update docs.

---

## Archived Detail: 6J Agent Interaction Model

Three patterns:

1. **Cursor Personas (interactive)**: Activate via file globs or domain-relevant questions. Real-time collaborators.
2. **n8n Autonomous (they work while you sleep)**: Cron-scheduled. Daily: EA briefing (7am), social content (8am), infra health (hourly), compliance check (6am). Weekly: strategy check-in, competitive intel. Monthly: state validator, compliance bot. Daily founder time: ~15-20 min.
3. **On-Demand n8n (you trigger them)**: Via webhook URL or Slack. /trinket-discover, /support, /competitive-check, /ea.
