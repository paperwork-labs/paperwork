# Plan Reality Check — 2026-04-21

> Companion to `2026-04-20-midnight-merge-storm.md` and `2026-04-21-g22-shipped-next-g23.md`. The user asked "where are we on those tonight/worlds-best plans and is MASTER_PLAN's phase map even up to date?" Answer: we've shipped **a lot more than MASTER_PLAN_2026 thinks we have** — the "Sprint Marker" at the bottom of MASTER_PLAN_2026 still says `v1 Week 1 (Apr 9-16, 2026)` with the three original Background Agent PRs listed as "Active". Reality is we're 13 days past that with **~70 PRs merged** (#303 → #385) including deep pulls into World-Class phases 5–9 that were originally scoped for Jun 21–Aug 31.

This doc audits the two `.cursor/plans/` files against shipped reality and flags:
1. Which plan todos are **done** (with the PRs that did them).
2. Which are **still pending** (and whether they matter before prod unblocks).
3. Where **MASTER_PLAN_2026.md is stale** and needs rewriting.
4. A **"what's actually next"** list that accounts for the deploy freeze.

---

## TL;DR — the 60-second pickup

- **v1_sprint_tonight (27-PR plan, ~31 todos)**: ~80% shipped. The flagship chart suite, design system, UX elevation, picks pipeline, transparency, and connection hub all landed. **7 items still pending**: chart share/OG (`p2-chart-polish`), equity curve, sentiment overlay, mobile card mode on tables, realtime/undo, beautiful CSV upload, tier-gating UX polish.
- **axiomfolio_worlds_best_v1 (Week 1 docs + 3 PR dispatch plan)**: fully shipped. Every doc-sweep todo and all three Week-1 Background Agent PRs landed in PR #316 + #317–#330.
- **MASTER_PLAN_2026.md phase map**: Phases 0, 0.5, and 1 are **done**. Phase 2 is **~60% done**. Phase 3 is **doc-only** (spec in #368, zero code). Phase 4 is **~50% done** (chat v0, mobile sheets, PWA, pricing; chat panel / LLM gateway / YIR / full tier-UX missing). Phases 5–9 (World-Class, originally post-v1-launch) are **substantially pulled forward**: walk-forward, Monte Carlo, symbol master, quorum, corp actions, OTel, multi-tenant hardening, Trade Decision Explainer, OAuth foundation — all shipped already. **Sprint Marker at line 446–455 is 3 weeks stale** and needs rewriting.
- **Plus bonus surface that wasn't in any plan**: MCP server (#370), per-account risk profile + discipline-bounded trajectory groundwork (G27/G26 specs), G22 sync-completeness validation (#383) — all shipped.

---

## v1_sprint_tonight_b79f3695 — what shipped vs pending

Plan header claimed "27 PRs tonight + 4 OAuth/SnapTrade PRs queued for v1.1/v1.2." Reality: ~24 of those shipped.

### Track 1 — Quick wins — 100% shipped

| Todo | PR | Status |
|------|----|--------|
| `qw-341` Copilot on #341 doc/test | #341 | Shipped |
| `qw-342` Copilot x5 on #342 | #342 | Shipped |
| `qw-auth` Auth-401 cascade fix | #345 | Shipped |
| `qw-heatmap` Heatmap surgical backfill | #343 | Shipped |
| `qw-knowledge` KNOWLEDGE.md restructure | #344 | Shipped |

### Track 2 — Phase 1 picks pipeline — 100% shipped

| Todo | PR | Status |
|------|----|--------|
| `p1-inbound` Postmark webhook + parser dispatch | #346 | Shipped |
| `p1-queue` validator queue UI + state machine | #351 | Shipped |
| `p1-publish` publish + tier-gated feed | #351 (combined) | Shipped |

### Track 3 — Phase 2 Snowball viz + design + UX — mostly shipped

**Flagship chart 4-PR mini-suite** (3/4 shipped):

| Todo | PR | Status |
|------|----|--------|
| `p2-chart-core` price + benchmark + aliveness | #357 | Shipped |
| `p2-chart-tooltip` rich tooltip + trade markers | #358 | Shipped |
| `p2-chart-overlays` S/R + stage bands + metric strip | #359 | Shipped |
| `p2-chart-polish` share + OG image + personality copy | — | **PENDING** (plan marked in_progress; this was one of the 4 stuck-agent PRs from the earlier cloud-agent dispatch round; never opened) |

**Design system 3-PR foundation** (100% shipped):

| Todo | PR | Status |
|------|----|--------|
| `p2-design-foundation` Geist + palette + ChartGlassCard | #349 | Shipped |
| `p2-design-motion` motion + chart skeletons + AnimatedNumber | #354 | Shipped |
| `p2-design-microinteractions` segmented + crosshair + a11y | #355 | Shipped |

**Supporting viz** (partial):

| Todo | PR | Status |
|------|----|--------|
| `p2-equity` portfolio equity curve + drawdown | — | **PENDING** |
| `p2-treemap` allocation treemap + sunburst | #362 | Shipped |
| `p2-income` income calendar grid | #367 | Shipped |
| `p2-sentiment` VIX/AAII/F&G composite overlay | — | **PENDING** |
| `p2-mobile` card-mode toggle on tables | — | **PENDING** (mobile bottom-sheets shipped in #365, but that's modal-pattern, not the table card-mode from this plan) |

**UX elevation 3-PR** (2/3 shipped):

| Todo | PR | Status |
|------|----|--------|
| `p2-cmdk` ⌘K command palette | #348 | Shipped |
| `p2-daily-narrative` AI daily narrative | #350 | Shipped |
| `p2-realtime-undo` live updates + optimistic + undo toast | — | **PENDING** |

**Connection layer** (half shipped):

| Todo | PR | Status |
|------|----|--------|
| `p2-connection-hub` unified `/connect` page | #363 | Shipped |
| `p2-csv-elevated` beautiful CSV + 15 templates + statement-PDF parse | — | **PENDING** |

**Transparency + trust**:

| Todo | PR | Status |
|------|----|--------|
| `p2-transparency` `/why-free` + public stats + cost microcopy | #347 | Shipped |

### Track 4 — Phase 4 quick wins — partial

| Todo | PR | Status |
|------|----|--------|
| `p4-autoops-fe` AutoOps explanations drawer + panel | #364 | Shipped |
| `p4-tier-ux` lock icons + 402 toast + useUpgradePrompt | — | **PENDING** (some gating landed via `<TierGate>` in #326; the polish pass in this todo didn't ship) |
| `p4-pricing` `/pricing` page with 6-tier comparison | #366 | Shipped |

### Decisions log

| Todo | PR | Status |
|------|----|--------|
| `decisions` Log D95-D106 in KNOWLEDGE.md | #356 | Shipped (logged as D103-D112) |

### v1.1 / v1.2 deferrals — as-planned-not-tonight

`v11-etrade-oauth`, `v11-tradier-oauth`, `v11-coinbase-oauth`, `v12-snaptrade` — all still pending per plan. **The OAuth foundation for these shipped in #379** (generic OAuth broker + E*TRADE sandbox), which is actually *ahead* of schedule. E*TRADE live adapter, Tradier, Coinbase, and SnapTrade gating are still future work as the plan intended.

### Summary of v1_sprint_tonight pending items (7)

1. `p2-chart-polish` — flagship chart 4/4 (share + OG + personality copy pass)
2. `p2-equity` — portfolio equity curve + drawdown sub-chart
3. `p2-sentiment` — VIX/AAII/F&G composite banner
4. `p2-mobile` — table card-mode toggle on max-md breakpoint
5. `p2-realtime-undo` — WebSocket price ticks + optimistic + undo toast
6. `p2-csv-elevated` — drag-and-drop + 15 broker templates + statement-PDF email parsing
7. `p4-tier-ux` — lock icons + 402 upgrade toast + `useUpgradePrompt` hook

Of these, `p2-csv-elevated` is the most strategically important (it's the Plaid replacement for Fidelity/Vanguard users — the ~50% US-retail CSV gap documented in D100). `p2-realtime-undo` is the snappiness play. `p2-equity` is the Free-tier acquisition hook. The other four are polish on already-shipped surfaces.

---

## axiomfolio_worlds_best_v1_bb68aed5 — fully shipped

This plan was the original **docs-sweep + Week-1 dispatch** setup. All 16 todos landed:

| Todo | Where it landed |
|------|-----------------|
| `docs-master-plan` rewrite to two-milestone | #316 |
| `docs-delete-delta` redirect stub | #316 |
| `docs-prd-banner` + STRATEGIC UPDATE | #316 |
| `docs-tasks-sprint` v1 Week 1 marker | #316 |
| `docs-knowledge` D81-D90 + R37-R39 | #316 + subsequent sprint PRs |
| `docs-architecture` two-worker topology | #316 |
| `docs-runbook` failure-mode playbook | #316 |
| `rules-new-five` plan-mode / prod-verify / no-silent-fallback / market-data-platform / point-in-time | #316 |
| `rules-personas-six` alpha-researcher / capital-allocator / microstructure / brain-skill / revenue / validator-curator | #316 |
| `rules-update-three` delegation / engineering / quant-analyst | #316 |
| `switch-mode` → agent mode | operational |
| `delete-delta-plan` | #316 |
| `pr-a-phase0` worker split + DAG + yfinance backoff | #317 (split across #317, #318, #319, #320, #321, #322, #323, #324) |
| `pr-b-stripe` User.tier + Entitlement + Stripe client + TierGate | #326 + #330 + #338 |
| `pr-c-candidate` CandidateGenerator + daily Beat + API | #328 |
| `monitor-week1` | operational |
| `dispatch-week2` | operational (morphed into the full v1_sprint_tonight dispatch) |

**Nothing pending from this plan.** It was effectively superseded by v1_sprint_tonight + the subsequent World-Class forward-pull.

---

## MASTER_PLAN_2026.md phase map — where it's stale

### Sprint Marker (lines 446–455) — wrong

Current file claims:

```
Current sprint: v1 Week 1 (Apr 9-16, 2026)
Active PRs (Background Agent dispatch):
- fix/v1-phase-0-stabilization — Agent A
- feat/v1-stripe-test-scaffolding — Agent B
- feat/v1-candidate-generator — Agent C
Next up after Week 1 merges: Phase 1 picks pipeline and Phase 2 Snowball parity start in parallel.
```

**Reality (2026-04-21)**:

- Sprint is not Week 1 — it's effectively Week 2 of the post-v1-sprint-tonight cleanup / G22-G28 bundle.
- Agents A/B/C all merged 2026-04-18 (PR #317, #330, #328).
- Phase 1 picks pipeline shipped (#327, #331, #346, #351).
- Phase 2 is mid-flight (see below).
- Phases 5–9 (World-Class) are **partially shipped ahead of schedule** — that was never in the original phase map.

### Phase-by-phase reality audit

| Phase | Plan status | Reality | Evidence |
|-------|-------------|---------|----------|
| **0** Stabilization | "Week 1, ships first" | **Shipped** | #317, #318, #319, #320, #321, #322, #323, #324, #336 |
| **0.5** Stripe + CandidateGenerator | "Week 1, parallel" | **Shipped** | Stripe: #326, #330, #338. Candidate: #328 |
| **1** Picks pipeline | "Weeks 2-3" | **Shipped** | Models #327, parser #331, inbound #346, queue+publish #351 |
| **2** Snowball parity | "Weeks 2-4" | **~60% shipped** | Equity curve, sentiment, x-feed, mobile-card, discipline-trajectory widget still missing. Chart suite, treemap, income, design system, cmdK, narrative, connection hub, transparency all shipped |
| **3** Execution (TRIM/ADD/rebalance/tax/bracket) | "Weeks 4-6" | **Spec only** | Engineering spec in #368; zero code. Per D98 Phase 3 is deferred to a dedicated review session — that's still the right call |
| **4** Agent chat + PWA + tier UX | "Weeks 5-9" | **~50% shipped** | PortfolioChat v0 #329, OpenAI adapter #334, mobile bottom-sheets #365, PWA #372, pricing #366, AutoOps FE #364. **Missing**: native chat panel (right-rail), full LLM gateway with circuit breaker, constitution YAML, tier-gating UX polish, Trading Year in Review |
| **5** Multi-broker expansion | "Weeks 11-14" (post-launch) | **Foundation shipped early** | OAuth broker base + E*TRADE sandbox #379. Plaid replaced by CSV strategy per D100. Hand-rolled adapters for the remaining brokers (Tradier, Coinbase Pro, Webull, Public, M1) still future work |
| **6** Backtesting excellence | "Weeks 11-14" | **~66% shipped early** | Walk-forward #373, Monte Carlo #375. **Missing**: event-driven engine, regime-conditional reports, backtest-to-live parity |
| **7** Data excellence | "Weeks 11-14" | **~60% shipped early** | Symbol master #374, multi-source quorum #371, corp-action engine #378. **Missing**: point-in-time correctness enforcement, provider drift detector (partial in #371) |
| **8** Ops excellence | "Weeks 13-18" | **~40% shipped early** | OTel #369, multi-tenant hardening #377. **Missing**: SLO definitions, Grafana dashboards, chaos engineering, predictive failure detector, auto-runbook generator |
| **9** AI-powered differentiation | "Weeks 15-20" | **~20% shipped early** | Trade Decision Explainer #376. **Missing**: Trade Copy, AI Portfolio Optimizer, Strategy Assistant, Incident Postmortem Bot |

### New surfaces not in the original phase map

- **MCP server** (#370) — per-user tokens + 6 read-only tools. Was a v1+ "followup" in v1_sprint_tonight; landed now.
- **G22 FlexQuery sync completeness validation** (#383) — entire G22/G23/G24/G25/G26/G27/G28 spec set (#382) — added to the plan on 2026-04-20 as a production-gap response to D117–D121 and is live in code (stuck behind deploy freeze).
- **Transparency play** (#347) — `/why-free` page + public stats + cost microcopy was implicit in D106 but not in the phase table.
- **Daily AI narrative** (#350) — D105, slotted under Phase 4 in practice.

---

## Proposed rewrite of MASTER_PLAN_2026 Sprint Marker

Replace lines 446–455 with:

```markdown
## Sprint Marker

**Current sprint**: v1 Cleanup + G22-G28 bundle (Apr 18–21, 2026 midnight merge storm)

**Last merged**: 2026-04-21 PR #385 (G22 handoff doc)

**Prod deploy state**: FROZEN since 2026-04-20 19:48 UTC (Render build_failed streak).
First successful deploy after unblock will ship 11 migrations (0043–0053) and
~13 feature PRs simultaneously. See docs/handoffs/2026-04-20-midnight-merge-storm.md
and docs/handoffs/2026-04-21-g22-shipped-next-g23.md for staged-restart plan.

**Phase completion (2026-04-21)**:
- v1 Phase 0, 0.5, 1: shipped ✅
- v1 Phase 2: ~60% shipped (7 polish items pending — see 2026-04-21-plan-reality-check.md)
- v1 Phase 3: spec only (#368); deferred to dedicated review session per D98
- v1 Phase 4: ~50% shipped (chat panel + LLM gateway + Trading YIR still pending)
- WC Phase 5: OAuth foundation shipped (#379); 5–10 broker adapters remain
- WC Phase 6: walk-forward + Monte Carlo shipped; event-driven engine remains
- WC Phase 7: symbol master + quorum + corp actions shipped; PIT + drift remain
- WC Phase 8: OTel + multi-tenant hardening shipped; SLO/chaos/predictive remain
- WC Phase 9: Trade Decision Explainer shipped; Trade Copy / Optimizer / Postmortem Bot remain

**Next up (once prod unblocks)**:
1. G28 deploy-health guardrail (the thing that would have caught this freeze)
2. Staged restart + /admin/health verification of the 11-migration delta
3. IBKR re-sync to exercise G22 validator in prod
4. v1 Phase 2 finishing PRs (equity curve, sentiment, CSV upload, realtime/undo)
5. v1 Phase 4 remaining PRs (native chat panel, LLM gateway, Trading YIR)
6. G23 historical import + G24 account-type routing + G25 multi-account discovery

**Not blocked on deploy**:
- v1 Phase 3 execution spec → implementation (when founder is awake + reviewing)
- WC Phase 6 event-driven backtester
- WC Phase 7 point-in-time correctness + drift detector
- WC Phase 8 SLO definitions + chaos scheduling
- WC Phase 9 Trade Copy (depends on Phase 3 execution)
```

Also recommend **moving the World-Class phase shipped-items into the v1 table** with an "early" annotation, since keeping them in the Jun 21–Aug 31 section while they're already on `main` is actively confusing.

---

## What's actually next (priority stack)

Accepting that prod is frozen and nothing new is reaching users until the Render issue is resolved:

### Blocker (before anything else ships)
- **G28 deploy-health guardrail** — the polling probe + alert that would have caught the 19:48 UTC freeze. Independent small PR; documented in G22 handoff section CRITICAL.
- **Read Render build logs** for 2026-04-20 19:48 UTC and the next 2 failed deploys. Either confirm billing (accept D120) or identify the code regression and revert-bisect #377 → #379 → #376 per the midnight-merge-storm handoff.

### v1 Phase 2 remaining (user-facing acquisition)
- `p2-equity` portfolio equity curve — Free-tier hook, highest leverage for acquisition
- `p2-csv-elevated` beautiful CSV + statement-PDF parsing — the Plaid replacement, unblocks Fidelity/Vanguard/JPM/Merrill/Wells user segments (~50% US retail)
- `p2-realtime-undo` live ticks + optimistic UI + undo toast — the Linear-grade snappiness cap
- `p2-sentiment` VIX/AAII/F&G overlay — quick win, one PR
- `p2-chart-polish` share + OG images — the social loop, high leverage for organic distribution
- `p2-mobile` table card-mode — PWA needs it to feel native on phones
- `p4-tier-ux` lock icons + 402 toast — monetization funnel polish

### v1 Phase 4 remaining (differentiation)
- **Native AgentBrain chat panel** — the Pro+ hook. `PortfolioChat` v0 (#329) is the headless interface; the right-rail UI panel isn't built.
- **LLM gateway with circuit breaker + constitution YAML** — the reliability/safety layer under the chat panel. Blocks Trade Copy (Phase 9a).
- **Trading Year in Review** — end-of-year wrap feature. Time-sensitive (most valuable in Dec/Jan). Can wait until Nov.

### G22/G23/G24/G25/G26/G27/G28 bundle — specs in #382
- G23 historical XML backfill from IBKR Flex
- G24 account-type-aware strategy routing (IRA vs taxable)
- G25 multi-account auto-discovery
- G26 "inability to close when winning" G15 acceptance criterion
- G27 per-account risk profile (Conservative/Balanced/Aggressive/Speculative)

### World-Class forward-pull (already ahead)
- Phase 6 event-driven backtester
- Phase 7 PIT correctness + drift detector
- Phase 8 SLO + chaos engineering
- Phase 9 Trade Copy + AI Portfolio Optimizer + Strategy Assistant + Incident Postmortem Bot

---

## One more thing worth noting

The **pace of this sprint already exceeded the MASTER_PLAN_2026 timeline**. The plan scheduled World-Class Phases 5–9 for weeks 11–20 post-June-21-launch; a meaningful slice of each phase is on `main` as of 2026-04-21 — that's ~8 weeks of original schedule shipped in ~3 days of midnight merge storm. That's cool but it introduces a new risk: **we're shipping faster than prod can ingest** (the 19:48 UTC freeze is the first symptom). Before we keep adding features, the G28 deploy-health loop needs to land so that "main is green and auto-merged" doesn't mean "shipped to users."

The discipline layer for the next sprint should be:
1. No new feature PR merges until G28 lands and prod deploys are green-and-verified.
2. Every merge post-G28 includes a `curl`-against-prod-health verification step in the PR body (production-verification.mdc already says this; the discipline just needs to actually be enforced).
3. MASTER_PLAN_2026 Sprint Marker gets updated at end-of-sprint, not left to drift.
