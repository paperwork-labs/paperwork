---
owner: engineering
last_reviewed: 2026-04-24
doc_kind: plan
domain: trading
status: active
---
# AxiomFolio Master Plan 2026

**Status**: ACTIVE — source of truth for sprint planning. Supersedes all prior production-stabilization plans.
**Created**: 2026-04-09
**Owner**: Staff Engineer (Opus orchestrator)
**Reviewed**: see `docs/KNOWLEDGE.md` D81-D90 for decision rationale.
**Companions**:
- [GAPS_2026Q2.md](GAPS_2026Q2.md) — production gaps discovered 2026-04-20.
- [PLATFORM_REVIEW_2026Q2.md](PLATFORM_REVIEW_2026Q2.md) — 13-chapter strategic review (2026-04-22, D144 + D145). Defines the 16-wave execution roadmap, two-layer moat (retail-discipline + HNW tax-alpha), founder dogfood flywheel, pricing audit + feature-to-tier remap, marketing narrative, and the **medallion + data-warehouse discipline** (Ch 1.8 + Wave 16; D127/D145 iron laws). **The 16-wave roadmap in Ch 11 is the unit of execution — prefer it over Phase-3 wave numbers in this file where the two diverge.**
- [BROKER_COVERAGE_TRACKER.md](BROKER_COVERAGE_TRACKER.md) — evergreen broker read/write matrix + ACATS cost-basis recovery playbook.
- [PORTFOLIO_SYNC_COMPLETENESS_2026Q2.md](PORTFOLIO_SYNC_COMPLETENESS_2026Q2.md) — Wave 8 spec (blocks W3.7 FileFree 1.1.0 bump). Diagnostic runbook + 4-path recovery for founder's Schwab ACATS tax-lot + options symptoms.

- Scope: G1–G27, dual-mode return-maximization platform per D116, IBKR sync correctness
  per D117, founder-replay-corpus discipline per D118, and discipline-bounded year-end
  target $2.0M–$2.5M for the founder joint book per D119.
- G14–G19 form the Active/Conviction discipline layer.
- G20 adds the HNW tax-deferral surface.
- G21 turns the founder portfolio into the canonical acceptance test.
- G22–G25 close the broker-sync correctness gap (silent partial-success guard,
  historical XML backfill, account-type-aware strategy routing, multi-account
  auto-discovery) so every downstream engine actually receives correct data.
  G22 is merged to `main` but its live-in-prod status depends on the G28 deploy-
  health guardrail landing first.
- G28 closes the deploy-pipeline silent-failure class of bug (D120) plus the
  validator-specific PARTIAL messaging improvement that prevents
  evidence-free diagnosis claims (D121). Both are retrospective fixes for
  the 2026-04-20 session where `main` was green for 8+ hours while prod
  silently stayed 7+ commits behind; ships in Phase 0 alongside the sync-
  correctness bundle.
- G26 anchors the "inability to close when winning" founder-self-identified pain as
  the explicit G15 acceptance criterion.
- G27 (per-account risk profile) ships in Phase 1 after G24/G25 land. It lets users
  tune position-sizing dial-settings within the discipline (Conservative / Balanced /
  Aggressive / Speculative) but never disable RiskGate, RegimeGate, ExitCascade, or
  the Kill Switch. Founder IRA defaults Aggressive (no tax friction → can run faster
  within discipline); Joint Taxable defaults Balanced.
- The G7 (PickQualityScorer) + G9 (Options Chain Surface) + G10 (Trade Card UX) trio
  remains the visible product surface that turns AxiomFolio from "shows you 156
  stocks" into "renders 1–3 ranked Trade Cards with the order pre-staged".
- Resolve in parallel with phases below; sync-correctness gaps (G22 + G23 Path A +
  G24 + G25) are bundled in `feat/ibkr-multi-account-historical-import` PR
  (Phase 0). G28 (deploy-health + validator-specific messaging) ships as an
  independent small PR in Phase 0, blocks nothing but prevents recurrence of
  the 2026-04-20 silent-prod-drift incident.

---

## Strategic Frame

### Mission

> Snowball Analytics + Bloomberg Terminal + a hedge fund analyst — but for retail, with one-click execution. Help retail investors actually make money, not just receive signals.

### Positioning

| Competitor | Their thing | Our edge |
|------------|-------------|----------|
| Snowball Analytics | Beautiful read-only portfolio viz | + execution + picks + autotrade |
| Bloomberg Terminal | Pro-grade data + analytics | 1/100th price, retail UX, one-click execute |
| StocksToBuyNow.ai | Picks via Discord/email | Picks land in your portfolio with stops + position sizing already wired |
| Hedge fund research notes | Brilliant but expensive and unactionable | Validator-curated picks → executable orders → tax-aware exits |

### Product shape

- **Standalone product** with own subscription tiers (Free / Pro / Pro+ / Quant Desk / Enterprise).
- **Native AgentBrain chat panel** for Pro+ — not a separate app, lives in-product.
- **Cross-sells into Paperwork ecosystem** (FileFree for taxes, Paperwork Brain for cross-domain conversational AI). Bundles available, not required.

### Key personas

- **Self (founder)** — power user, runs everything, validates edge cases.
- **Twisted Slice** — hedge fund validator persona. Forwards analyst notes / writes original picks. Pseudonym in all user-facing artifacts. Inbound validator sender(s) configured server-side via the `PICKS_TRUSTED_SENDERS` env var; real identifiers never live in code, docs, or version control.
- **Pro retail trader** — wants picks + auto-executed entries with stops, doesn't have time to sit at terminal.
- **Free-tier retail user** — Snowball replacement, free portfolio viz, gateway to Pro.

### Two milestones

| Milestone | Date | Definition |
|-----------|------|------------|
| **v1 Launch** | **2026-06-21** (10 weeks) | Paying users on Free / Pro / Pro+. Validated Picks live (founder + Twisted Slice). Native AgentBrain chat. Beautiful portfolio charts. TRIM/ADD/rebalance. Tax-aware exits. Email parser. PWA mobile. |
| **World-Class Complete** | **2026-08-31** (20 weeks) | + 8 brokers via Plaid + hand-rolled. + Walk-forward + Monte Carlo + event-driven backtester. + Symbol master + multi-source quorum. + OpenTelemetry + SLOs + chaos engineering. + Trade Copy + AI Portfolio Optimizer. + Quant Desk tier with white-label. |

### Year 2 backlog (post-Aug 31)

- Validator Marketplace (multiple Twisted Slices, revenue share)
- Strategy Marketplace (publish backtested strategies)
- Native iOS / Android
- International markets (LSE, TSX, ASX, EU)
- AI Portfolio Optimizer Pro tier
- Discovery Feed (TikTok-style swipe through picks/strategies)

---

## Working Patterns

### Defaults

- **Cloud Background Agents** for bulk PR work, dispatched in parallel from this Opus session.
- **Opus orchestrator** (this session): architecture, financial logic, schema design, code review, decision logging.
- **Per-PR cadence**: ping user only when PR is ready for review/merge. Otherwise silent.
- **Stripe**: test mode only until founder explicitly says "go live with billing".
- **Live broker creds**: untouched until founder is at laptop and explicitly authorizes wiring.
- **No emojis** anywhere in code, docs, commits, PR bodies, UI copy.
- **Twisted Slice pseudonym** enforced everywhere user-facing. Real name and email never exposed.

### Branch convention (per sprint phase)

- `fix/phase-N-<name>` — Phase 0 stabilization fixes
- `feat/v1-<feature>` — v1 milestone features
- `feat/wc-<feature>` — World-Class milestone features
- `chore/<topic>` — docs, configs, infra

### PR requirements

- Linked to one milestone (v1 or wc) and one phase
- CI green before merge
- No silent zero fallbacks (see `.cursor/rules/no-silent-fallback.mdc`)
- Production verification post-merge (see `.cursor/rules/production-verification.mdc`)
- KNOWLEDGE.md decision entry if architectural

---

## Phase Map

```mermaid
gantt
  title AxiomFolio — Apr 9 to Aug 31, 2026
  dateFormat  YYYY-MM-DD

  section v1 Foundation
  Phase 0: Stabilization          :p0, 2026-04-09, 7d
  Phase 0.5: Stripe scaffolding   :p05a, 2026-04-09, 7d
  Phase 0.5: CandidateGenerator   :p05b, 2026-04-09, 7d

  section v1 Picks Pipeline
  Phase 1: Email parser + ingest  :p1a, after p0, 10d
  Phase 1: Validator queue UI     :p1b, after p05a, 10d
  Phase 1: Pick publish + tier    :p1c, after p1a, 5d

  section v1 Snowball Parity
  Phase 2: Multi-broker base      :p2a, after p0, 10d
  Phase 2: Snowball viz parity    :p2b, after p2a, 10d
  Phase 2: Sentiment overlay      :p2c, after p2b, 5d

  section v1 Execution
  Phase 3: TRIM/ADD order types   :p3a, after p1c, 7d
  Phase 3: Rebalance engine       :p3b, after p3a, 7d
  Phase 3: Tax-aware exits        :p3c, after p3b, 5d

  section v1 Brain + Mobile
  Phase 4: Native AgentBrain chat :p4a, after p1c, 10d
  Phase 4: PWA mobile             :p4b, after p2b, 7d
  Phase 4: Tier gating + UX       :p4c, after p4a, 7d
  v1 LAUNCH                       :milestone, m1, 2026-06-21, 0d

  section World-Class Brokers
  Phase 5: Plaid Investments      :p5a, after m1, 14d
  Phase 5: 5 hand-rolled brokers  :p5b, after p5a, 14d

  section World-Class Backtesting
  Phase 6: Walk-forward optimizer :p6a, after m1, 14d
  Phase 6: Monte Carlo simulator  :p6b, after p6a, 7d
  Phase 6: Event-driven engine    :p6c, after p6b, 7d

  section World-Class Data
  Phase 7: Symbol master          :p7a, after m1, 7d
  Phase 7: Multi-source quorum    :p7b, after p7a, 14d
  Phase 7: Corporate action engine:p7c, after p7b, 7d

  section World-Class Ops
  Phase 8: OpenTelemetry + SLO    :p8a, after p7a, 10d
  Phase 8: Chaos engineering      :p8b, after p8a, 7d
  Phase 8: Multi-tenant hardening :p8c, after p8a, 14d

  section World-Class AI
  Phase 9: Trade Copy             :p9a, after p3c, 14d
  Phase 9: AI Portfolio Optimizer :p9b, after p9a, 14d
  Phase 9: Trading YIR + scorecard:p9c, after p4c, 14d
  WORLD-CLASS COMPLETE            :milestone, m2, 2026-08-31, 0d
```

---

## v1 Launch Phases (Apr 9 - Jun 21)

### Phase 0 — Stabilization (Week 1, ships first)

**Goal**: stop the bleeding from the prod incidents documented in KNOWLEDGE D76-D80, R34-R37. Make pipeline self-healing. No new features.

| Todo | File(s) | Acceptance |
|------|---------|------------|
| Split worker into fast + heavy queues | [render.yaml](../../render.yaml), [app/tasks/celery_app.py](../../app/tasks/celery_app.py) | `axiomfolio-worker` (--beat, -Q celery,account_sync,orders, --concurrency=2, max-mem 750000) and `axiomfolio-worker-heavy` (-Q heavy, --concurrency=1, max-mem 1500000); `repair_stage_history`, `fundamentals.fill_missing`, `snapshot_history.*`, `full_historical`, `prune_old_bars` routed to `heavy` queue |
| Pipeline waiting state | [app/services/pipeline/dag.py](../../app/services/pipeline/dag.py) | `_QUEUED_TIMEOUT_S` raised to 900s; new `RunStatus.WAITING` surfaces `current_task` + age via Celery `inspect()`; only `error` if no worker reachable; API + `SystemStatus.tsx` render amber row |
| Tracked aggregates resilience | [frontend/src/pages/MarketTracked.tsx](../../frontend/src/pages/MarketTracked.tsx) | `useSnapshotAggregates` `isLoading`/`isError` handled; chips show `—` not `0` on loading/error; top strip shows Retry button on error; per-hook retry to 3 with exponential backoff |
| Dashboard warming truth | [frontend/src/pages/MarketDashboard.tsx](../../frontend/src/pages/MarketDashboard.tsx) | When `/dashboard?universe=X` returns 202 `warming` for >3 polls, render snapshot coverage stats from `/market-data/admin/health` instead of generic spinner |
| DAG stale state (not error) | [frontend/src/components/pipeline/PipelineDAG.tsx](../../frontend/src/components/pipeline/PipelineDAG.tsx) | `resolveVisualStatus` renders gray `stale` instead of red `error` when `last_run_at` >12h old |
| Yahoo backoff | [app/tasks/market/fundamentals.py](../../app/tasks/market/fundamentals.py) | tenacity retry with exponential backoff on 429; `limit_per_run` 500→200; warn-and-skip after 3 retries; structured counters |
| IBKR watchdog gate | [app/tasks/portfolio/ibkr_watchdog.py](../../app/tasks/portfolio/ibkr_watchdog.py) | Early-return if no enabled `BrokerAccount(provider='ibkr')` rows exist; eliminates every-2-min `SoftTimeLimitExceeded` noise |
| Snapshot history coverage fix | [app/tasks/market/indicators.py](../../app/tasks/market/indicators.py) | Add structured counters (written/skipped_no_data/errors) to `recompute_universe`; assert `written+skipped+errors == tracked_total`; coverage test |
| Monotonicity index migration | new Alembic migration, [app/services/market/stage_quality_service.py](../../app/services/market/stage_quality_service.py) | `CREATE INDEX CONCURRENTLY ix_market_snapshot_history_symbol_btree`; rewrite `SELECT DISTINCT symbol` query in `repair_stage_history_window` to use `tracked_symbols_with_source` |
| Bulk repair + regime schedule | [app/tasks/job_catalog.py](../../app/tasks/job_catalog.py) | One-time `repair_stage_history` on heavy worker clears 2820 monotonicity violations; add `JobTemplate` for `compute_daily_regime` cron `'20 3 * * *'` (currently missing) |
| Phase 0 verification | post-merge | composite_status green; dashboard 200; active-tasks balanced; manual trigger shows `waiting`; tracked shows real symbol count not "0"; no OOMs for 24h; 3 consecutive successful nightly runs |

**PR**: `fix/v1-phase-0-stabilization` — single PR, dispatched as Background Agent A.

### Phase 0.5 — Stripe + CandidateGenerator (Week 1, parallel with Phase 0)

**Goal**: lay billing scaffold and pick generation engine without touching production money or production data.

#### Stripe scaffolding (test mode only)

| Todo | File(s) | Acceptance |
|------|---------|------------|
| `User.tier` enum | [app/models/user.py](../../app/models/user.py) + Alembic | Enum: `FREE`, `PRO`, `PRO_PLUS`, `QUANT_DESK`, `ENTERPRISE`; default `FREE`; backfill existing user to `PRO_PLUS` |
| `Entitlement` model | new model + Alembic | `user_id`, `feature_key`, `value` (jsonb), `granted_via` (`tier`/`override`/`bundle`), `expires_at` |
| Stripe client wrapper | new `app/services/billing/stripe_client.py` | Test-mode keys only; idempotency keys; webhook signature verification |
| Webhook receiver | new `app/api/routes/billing/webhooks.py` | `customer.subscription.created/updated/deleted`, `invoice.payment_succeeded/failed`; updates `User.tier` + `Entitlement` rows |
| `TierGate` decorator | new `app/api/dependencies/tier_gate.py` | `@require_tier(Tier.PRO)` on routes; returns 402 with upgrade URL on insufficient tier |
| Feature catalog | new `app/services/billing/feature_catalog.py` | Maps feature keys → tier requirements; single source of truth for "what does Pro get?" |

**PR**: `feat/v1-stripe-test-scaffolding` — Background Agent B.

#### CandidateGenerator service

| Todo | File(s) | Acceptance |
|------|---------|------------|
| `Candidate` model | new model + Alembic | `as_of_date`, `symbol`, `tier_min` (which subscription tier sees this), `regime` (R1-R5), `score` (composite), `reason` (jsonb), `source` (`algorithmic`/`validator`/`hybrid`), unique on (date, symbol, source) |
| `CandidateGenerator` service | new `app/services/picks/candidate_generator.py` | Reads `MarketSnapshot` + composite scores from `scan_engine` + current `Regime`; produces top-N per tier per regime per day; deterministic given inputs (testable) |
| Daily Beat job | [app/tasks/job_catalog.py](../../app/tasks/job_catalog.py) | `generate_candidates` runs daily at 03:30 UTC after indicator recompute + regime; idempotent re-run safe |
| `GET /candidates` API | new `app/api/routes/picks/candidates.py` | Tier-gated (`@require_tier`); returns latest candidates for caller's tier; pagination; filters by regime/sector |
| Frontend Candidates page | new `frontend/src/pages/Candidates.tsx` | Reads `GET /candidates`; renders ranked list with reason chips; tier-locked rows show "Upgrade to Pro" CTA for Free |
| Test fixture | new `backend/tests/test_candidate_generator.py` | Given canned MarketSnapshot + R3 regime, produces expected top-10 picks per tier |

**PR**: `feat/v1-candidate-generator` — Background Agent C.

### Phase 1 — Picks Pipeline (Weeks 2-3)

**Goal**: ingest Twisted Slice's emails → polymorphic LLM extraction → validator queue → tier-gated publish.

| Todo | Notes |
|------|-------|
| Inbound email webhook | Postmark or Resend inbound; signature verification; routes to `/api/v1/picks/inbound` |
| PDF + image attachment ingestion | `pymupdf` for PDF text + image extraction; gpt-4o vision for chart captioning; cost-gated to trusted senders |
| LLM polymorphic parser | Detects schema: `single_stock_bullets` / `single_stock_research_note` / `macro_recap_with_position_changes` / `daily_market_recap_narrative` / `mixed`; uses gpt-4o for synthesis |
| Schema set | `ValidatedPick`, `MacroOutlook`, `SectorRanking`, `PositionChange`, `RegimeCall`, `FlowSignal`, `AttributedQuote` SQLAlchemy models |
| Source attribution extraction | Track `original_author` (Keith McCullough/Hedgeye, Stock Pulse, ZeroHedge, Goldman, Nomura, etc.); separate from `validator` (always Twisted Slice) |
| Cross-email signal linking | Vector similarity + symbolic level matching; surfaces "this email reinforces email X from Y days ago" |
| Validator queue UI | `/picks/queue` for OWNER + ANALYST roles; tabs for picks / macro / mixed; bulk-approve + per-item edit |
| Approval state machine | `DRAFT` → `APPROVED` → `PUBLISHED` (or `REJECTED`); webhook to subscribers on `PUBLISHED` |
| Publish to subscribers | Tier-gated read; Free sees 24h-delayed; Pro sees real-time picks and autotrade per `feature_catalog` (former mid-tier is folded into Pro; see D123) |
| Test fixtures | All 4 example emails (AAOI/CIEN, Hedgeye, STT, ZeroHedge) round-trip into expected schemas with >85% field accuracy |

**PRs (sequential)**: `feat/v1-picks-inbound`, `feat/v1-picks-parser`, `feat/v1-picks-validator-queue`, `feat/v1-picks-publish-gating`.

### Phase 2 — Snowball Parity + Sentiment (Weeks 2-4)

**Goal**: free-tier hook is best-in-class portfolio viz. Connect more brokers. Show sentiment.

| Todo | Notes |
|------|-------|
| Plaid Investments client | Stub for v1 (full broker support in WC Phase 5); minimum viable for "connect Robinhood/Fidelity read-only" |
| Equity curve with annotations | Buy/sell/dividend markers on time series chart; benchmark overlay (SPY/QQQ/sector ETF) |
| Allocation treemap + sunburst | Interactive drill-down by sector/asset class/account |
| Drawdown chart | Underwater + max-drawdown stats |
| Income calendar | Heatmap of dividends + interest by month with projection |
| Sector rotation heatmap | Time x sector with color-coded performance/regime |
| X (Twitter) curated feed | Twisted Slice's allowlist of accounts; ingest via API; sentiment scoring; mention count per symbol |
| Market sentiment overlay | VIX, AAII bull/bear, Fear/Greed, news sentiment composite; rendered as banner on dashboard |
| Mobile-first card mode | Toggle on tables; renders rows as stacked cards on `max-md` breakpoint |
| **Discipline-Bounded Trajectory widget** | Per-account dashboard tile rendering: starting equity → discipline anchors (unleveraged + with-leverage tiers per D119) → current % to anchor → projected year-end with current trajectory; visually distinguishes the three tiers (unleveraged $1.95M-$2.5M, leveraged $2.5M-$3.0M, speculative $3.0M-$3.5M) and shades anything beyond as "outside discipline". Reads from `account_balances.total_equity_usd` time series + per-account `account_risk_profile` (G27). For founder joint book, anchors hardcode-default to D119 numbers; for other users anchors compute from their starting equity × (50% / 100% / 200% return ranges). Tile is glanceable: one number prominent (current equity), one ratio (% to anchor), one trend arrow (on track / behind / ahead). No projections beyond the anchor — the discipline ceiling is the ceiling, by design. |

**PRs**: `feat/v1-snowball-equity-curve`, `feat/v1-snowball-allocation`, `feat/v1-snowball-income`, `feat/v1-sentiment-overlay`, `feat/v1-x-curated-feed`, `feat/v1-mobile-card-mode`, `feat/v1-discipline-trajectory-widget`.

### Phase 3 — Execution (Weeks 4-6)

**Goal**: TRIM/ADD as first-class order types. Rebalance engine. Tax-aware exits via existing `TaxLossHarvester`.

| Todo | Notes |
|------|-------|
| TRIM/ADD as `OrderType` | Extend `app/services/execution/order_manager.py`; TRIM = sell N% of position; ADD = buy to bring to target weight |
| Rebalance engine | Compute target weights from current portfolio + target weights; produce `OrderIntent` list; preview UI before execute |
| Tax-aware exit selector | Wire `tax_loss_harvester.py` into `OrderManager` for SELL orders; choose tax lots that minimize tax impact (HIFO / specific lot / wash-sale-aware) |
| `SignalToOrder` generator | Validated picks with `auto_execute=true` flag → `OrderIntent` via configurable rules (size pct of equity, max loss, regime gate) |
| `PortfolioHeatGuard` | Per-user concurrent risk cap; rejects new orders when portfolio heat exceeds threshold |
| Per-user circuit breaker | Refactor existing global `CircuitBreaker` to be per-user; multi-tenancy fix |
| Bracket orders | OCO stop + target on entry via broker APIs (where supported) |
| Adaptive trailing stop manager | Already partially built in `exit_cascade.py`; extend with per-pick custom stops from validated picks |

**PRs**: `feat/v1-trim-add-orders`, `feat/v1-rebalance-engine`, `feat/v1-tax-aware-exits`, `feat/v1-signal-to-order`, `feat/v1-per-user-circuit-breaker`, `feat/v1-bracket-orders`.

### Phase 4 — Native AgentBrain + Mobile + Tier UX (Weeks 5-9)

**Goal**: native chat panel as Pro+ hook. PWA. Polished tier gating.

| Todo | Notes |
|------|-------|
| Internal `AgentBrain` extension | Anomaly explanation, NL queries, trade decision explainer, strategy suggestions |
| LLM gateway with circuit breaker | New `app/services/agent/llm_gateway.py`; OpenAI calls with retry + fail-closed |
| Constitution YAML | New `app/services/agent/constitution.yaml`; immutable rules enforced on every LLM action |
| Native chat panel | New `frontend/src/components/chat/AgentBrainChat.tsx`; pinned right-rail for Pro+ users; markdown + tool-call rendering |
| Chat context providers | Auto-inject portfolio state, current page context, recent picks into chat context window |
| Tier gating UX | Lock icons + upgrade CTAs on gated features; pricing page; checkout flow (Stripe Checkout) |
| Pricing page | `/pricing` with 6-tier comparison table |
| PWA manifest + service worker | Installable on iOS/Android; offline read of cached portfolio + picks |
| Mobile bottom-sheet modals | Replace popovers with bottom-sheets on `max-md` |
| Trading Year in Review | Native end-of-year wrap-up: trade journal stats, top winners/losers, regime-attributed performance |

**PRs**: `feat/v1-agentbrain-chat`, `feat/v1-llm-gateway`, `feat/v1-tier-gating-ux`, `feat/v1-pricing-page`, `feat/v1-pwa`, `feat/v1-mobile-bottom-sheets`, `feat/v1-trading-year-in-review`.

### v1 Launch Acceptance Criteria

- [ ] All Phase 0 verification items green
- [ ] At least 4 different email formats parsed correctly into validator queue
- [ ] Twisted Slice can publish a pick from email-arrival → subscriber-visible in <60s
- [ ] Pro user can one-click execute a published pick (paper mode minimum, live broker if wired)
- [ ] Snowball equity curve + benchmark overlay live for 5+ test portfolios
- [ ] Stripe test-mode checkout completes for all 6 tiers; tier gating actually blocks features
- [ ] Native AgentBrain chat answers "what's my biggest risk right now" using real portfolio data
- [ ] PWA installs on iOS Safari + Android Chrome
- [ ] Mobile UX score: no horizontal scroll on any page <768px
- [ ] At least 3 brokers connectable (IBKR + Schwab + Plaid-routed)
- [ ] Tax-aware exit chooses HIFO lot for a SELL with documented test
- [ ] No P0 prod incidents for 7 consecutive days pre-launch
- [ ] Documentation updated: PRD v2, ARCHITECTURE updated, KNOWLEDGE D81-D100, runbook for picks pipeline

---

## World-Class Phases (Jun 21 - Aug 31)

### Phase 5 — Multi-broker Expansion (Weeks 11-14)

| Sub-phase | Scope |
|-----------|-------|
| 5a | Plaid Investments full coverage — read-only positions/transactions for 12,000+ institutions |
| 5b | Hand-rolled adapters for top 5 brokers Plaid doesn't cover well: TastyTrade (full), Schwab (full incl. wash sales), Webull, Public, M1 |
| 5c | Broker plugin SDK — third-party broker adapters via plugin architecture |

### Phase 6 — Backtesting Excellence (Weeks 11-14)

| Sub-phase | Scope |
|-----------|-------|
| 6a | Walk-forward optimizer with Optuna — hyperparameter search per regime |
| 6b | Monte Carlo simulator — bootstrap resampling for confidence intervals on returns |
| 6c | Event-driven backtester — order-book-aware fill simulation; complements existing `BarReplayBacktester` |
| 6d | Regime-conditional reports — strategy performance broken down by R1-R5 |
| 6e | Backtest-to-live parity reports — flag drift between backtest expectation and live execution |

### Phase 7 — Data Excellence (Weeks 11-14)

| Sub-phase | Scope |
|-----------|-------|
| 7a | Symbol master — single source of truth for symbols, mergers, splits, ticker changes; DB-backed |
| 7b | Multi-source quorum — for critical fields (price, volume, fundamentals), fetch from N providers and require majority agreement; flag disagreements |
| 7c | Corporate action engine — splits, dividends, mergers automatically adjust positions, cost basis, and historical OHLCV |
| 7d | Point-in-time correctness — historical reads return data as it was known on that date (no look-ahead leakage in backtests) |
| 7e | Provider drift detector — flags when a provider's values diverge from historical norms |

### Phase 8 — Operations Excellence (Weeks 13-18)

| Sub-phase | Scope |
|-----------|-------|
| 8a | OpenTelemetry traces + metrics for all critical paths |
| 8b | SLO definitions + Grafana dashboards (pipeline freshness, picks publish latency, order fill latency) |
| 8c | Chaos engineering — scheduled fault injection (provider outage, DB latency, Redis failure) with auto-remediation verification |
| 8d | Multi-tenant hardening — per-tenant rate limits, cost attribution, GDPR data export/delete, Brain M2M auth scoping |
| 8e | Predictive failure detector — LightGBM model on operational metrics predicts incidents before they fire |
| 8f | Auto-runbook generator — `AgentBrain` drafts runbook entries from N historical incidents |

### Phase 9 — AI-Powered Differentiation (Weeks 15-20)

| Sub-phase | Scope |
|-----------|-------|
| 9a | Trade Copy — Pro+ users can mirror Twisted Slice's published picks automatically |
| 9b | AI Portfolio Optimizer — LLM-driven rebalance suggestions with risk/tax constraints |
| 9c | Strategy Assistant — NL → strategy spec → backtest → publish |
| 9d | Incident Postmortem Bot — drafts structured RCA when red persists >1h |
| 9e | Trade Decision Explainer — for every executed order, generates "why was this trade taken" explanation |

### World-Class Acceptance Criteria

- [ ] 8+ brokers connectable
- [ ] 3 backtesting modes (bar replay, event-driven, Monte Carlo) with parity to live
- [ ] Symbol master backed; corporate actions auto-applied; point-in-time queries verified
- [ ] OpenTelemetry traces visible in Grafana for every Celery task
- [ ] At least one chaos test passes per week (provider failure → auto-failover documented)
- [ ] Multi-tenant isolation verified (per-user data, per-user rate limits, per-user cost attribution)
- [ ] AI optimizer produces tax-aware rebalance suggestions at least as good as manual baseline
- [ ] Trade Copy live for 10+ paying subscribers

---

## Cross-Cutting Concerns

### Security & Multi-Tenancy

- All routes user-scoped via `current_user.id` dependency
- Per-tenant Redis namespaces
- Per-tenant rate limits (no noisy-neighbor)
- GDPR: data export endpoint + delete endpoint (Phase 8d)
- Brain M2M auth scoped per tenant (no `BRAIN_TOOLS_USER_ID=1` hardcoding)
- All secrets via env vars + Render secret store; never in code or commits

### Cost Management

- LLM call cost tracking per user per feature (Langfuse)
- Per-tier LLM budget caps (Free: 0, Pro: $5/mo, Pro+: $20/mo, Quant: unlimited)
- Provider call cost tracking (FMP, Massive when added, etc.) per user
- Daily cost summary email to founder

### Decision Logging

Every architectural decision goes into `docs/KNOWLEDGE.md` as `D##: [date] [decision] — [rationale] — [alternatives] — [reversible?]`. Every resolved incident as `R##`.

### Documentation Hygiene

- PRD updated end of each milestone (v1: Jun 21, WC: Aug 31)
- ARCHITECTURE.md updated when modules added
- AxiomFolio sprint tracking: this file; historical phase tables in [`AXIOMFOLIO_TASKS.md`](../archive/AXIOMFOLIO_TASKS.md) (archived 2026-04-24).
- New runbook section per major feature (picks pipeline, billing, etc.)

---

## Cross-Domain Integration (Paperwork Ecosystem)

AxiomFolio is one product in the [Paperwork Labs](https://github.com/paperwork-labs/paperwork) ecosystem. Cross-product integrations live behind clean API boundaries.

| Product | Integration | Direction |
|---------|-------------|-----------|
| **Paperwork Brain** | `brain.paperworklabs.com` consumes AxiomFolio HTTP tools at `/api/v1/tools/*`; AxiomFolio sends HMAC-signed webhooks | Bi-directional |
| **FileFree** ([filefree.ai](https://filefree.ai/)) | AxiomFolio exports year-end tax package (1099 + tax lot summary + wash-sale ledger) → FileFree consumes via Brain | AxiomFolio → FileFree |
| **Future Paperwork products** | Cross-product subscription bundles ("All Access"); shared identity via Paperwork SSO | Bi-directional |

**Boundary**: AxiomFolio code never imports FileFree code or vice versa. Integration always via HTTP + Brain.

---

## What This Plan Replaces

This plan supersedes:

- `production-stabilization-final_*.plan.md` (CreatePlan tool storage, stale)
- `axiomfolio_standalone_+_brain_skill_*.plan.md` (CreatePlan tool delta, stale)
- All "future phases (post-stabilization)" rows in `docs/TASKS.md` (Phase 15-18)
- Outdated PRD non-goals ("Multi-user SaaS" / "Mobile native app")

`docs/PRD.md` carries a STRATEGIC UPDATE banner pointing here until v2 PRD rewrite (scheduled v1 Week 8).

---

## Sprint Marker

**Current sprint**: sync-correctness-pricing-nav (Apr 21, 2026)

**Active PRs** (Background Agent dispatch):
- `fix/v1-phase-0-stabilization` — Agent A
- `feat/v1-phase-0-pricing-ladder3-byok` — Agent B
- `feat/v1-phase-0-pricing-nav` — Agent C

**Next up after Week 1 merges**: Phase 1 picks pipeline (email parser + validator queue) and Phase 2 Snowball parity start in parallel.

## Roadmap timeline (merged from ROADMAP.md, 2026-04-24)

The archived section-based `ROADMAP.md` (now `docs/archive/AXIOMFOLIO_ROADMAP.md`) ordered delivery as Section 1, then 1.5, 1.75, 2, 2.5, 2.6, 2.75, 2.8 (mostly **[DONE]**) and forward Sections 3 and 3.5.

**Calendar milestones in this file** (v1 **2026-06-21**, World-Class **2026-08-31**) in *Strategic Frame* remain the canonical product dates. The material below is the **legacy engineering sequence** plus **forward backlog** not otherwise spelled out in phase tables.

### Completed sequence (traceability)

Order of shipped sections in the old roadmap: **1** (Foundation) -> **1.5** (Brokerage Infra + Per-User Credentials, PR 191) -> **1.75** (Market Data DB-First + Portfolio Intelligence) -> **2** (Options, Categories, IB Gateway) -> **2.5** (Backend-Served Indicator Series) -> **2.6** (Portfolio Finish Line) -> **2.75** (BRAIN + PORTFOLIO Integration) -> **2.8** (Streamline Three Pillars). Detail lives under [Done / superseded](#done--superseded).

### Reconciled duplicates (one pointer each)

- **Execution / live orders** — `ROADMAP` Section 3 (buy path, multi-broker orders, strategy execution pipeline, kill switch, watchlist, mobile polish) overlaps *in theme* with [Phase 3 — Execution (Weeks 4-6)](#phase-3--execution-weeks-4-6) and [Phase 4 — Native AgentBrain + Mobile + Tier UX (Weeks 5-9)](#phase-4--native-agentbrain--mobile--tier-ux-weeks-5-9) above. **Keep both**: master-plan phases for milestone alignment and AC; this subsection for the legacy app’s concrete checklist (e.g. `OrderModal` buy/sell, TastyTrade/Schwab order APIs, `Watchlist` model) until work is mapped into phases.
- **Charts / technical analysis** — Section 3.5 (upgrade `lightweight-charts` to v5, backend-driven sub-panes) complements Phase 2 Snowball-viz work (equity curve, overlays) and World-Class backtesting phases; it is the **in-app chart stack** upgrade track, not a duplicate of the product milestone table.
- **Circuit breakers / per-user risk** — ROADMAP Section 3 lists a strategy pipeline and breakers; master plan [Phase 3](#phase-3--execution-weeks-4-6) lists `PortfolioHeatGuard`, per-user circuit breaker, and bracket orders. **Deduplicated** by treating master-plan Phase 3 as the authoritative requirement set and Section 3 bullets below as additional implementation notes from the old doc.

### Forward / not yet calendar-mapped (from `ROADMAP.md`)

**Section 3 — Live Execution + Polish (PR 3)**

*Prerequisites*: IB Gateway connected and stable; order pipeline tested in paper mode (done in Section 2.8).

- Buy order support: extend `SellOrderModal` -> `OrderModal` with buy/sell toggle; integrate into Intelligence Panel and Workspace.
- Broker expansion: TastyTrade SDK `place_order`, Schwab OAuth order endpoints.
- Strategy engine execution pipeline: Signal -> Order -> RiskGate -> Execution.
- Circuit breakers and kill switch (max daily loss, max position size, max orders/minute).
- `StrategyDetail` page, `StrategyBacktest` page (reads from `MarketSnapshotHistory` for historical indicator values).
- Paper-to-live toggle with confirmation gate.
- Order reconciliation: link filled `Order`s to `Trade`s created by broker sync.
- Watchlist management: `Watchlist` model, "Watch" toggle button, auto-add to tracked universe.
- Mobile polish: responsive layouts, touch-friendly drag-and-drop fallback.

**Section 3.5 — Charts and TA Enhancement**

- Upgrade `lightweight-charts` from v4.2.1 (CDN) to v5 (npm). Gain native `createPane()` for sub-charts.
- RSI/MACD/Bollinger sub-panes using backend indicator series.
- Stage background coloring (subtle tint by Weinstein stage).
- Earnings markers, comparison overlay (SPY/sector ETF), multi-timeframe toggle.
- Screenshot button via `chart.takeScreenshot()`.
- **Do not build** (per source): drawing tools, volume profile, custom indicators, Elliott Wave, Fibonacci (use TradingView for these).

**Open from Section 1.75 (table)**

| Status | Item |
|--------|------|
| PLANNED | Frontend indicator migration (Track 1: scalar from DB, Track 2: geometric overlays stay on frontend) |

**Testing requirements (from `ROADMAP.md`)**

- **Financial calculations**: Unit tests for every indicator in `compute_full_indicator_series()`. Parity tests comparing Python output vs TypeScript `utils/indicators/` output for same OHLCV input.
- **Strategy detection**: Unit tests for every pattern in `utils/optionStrategies.ts` with known position sets.
- **Integration**: DB-first read path (L1 miss -> L2 hit), indicator gap detection and backfill trigger, race condition handling (indicators requested before OHLCV fetched).
- **Backend**: Pytest for all new endpoints, Alembic migration up/down.
- **Frontend**: Vitest for utility functions and hooks.

**Operational (ongoing)**

- CI runs tests, lints, `alembic upgrade head`.
- CHANGELOG from conventional commits.
- Run commands and migration workflow: see `ONBOARDING.md`.

## Done / superseded

The following was marked **[DONE]** (or **DONE** in status tables) in `docs/archive/AXIOMFOLIO_ROADMAP.md` (archived from `ROADMAP.md` on 2026-04-24). It is retained for audit traceability; current planning follows this master plan and the companion docs in the frontmatter.

### Section 1 — Foundation (PR 1) [DONE]

**Backend** — Remove dead portfolio endpoints; fix N+1 in statements, live, options; async sync-all; auto-sync on account add; re-enable strategies route.

**Frontend** — Shared portfolio utils (`buildAccountsFromBroker`, `toStartEnd`, `timeAgo`, etc.); type safety (API response types, typed hooks, `AccountContext`); `useDebounce`; account filter consistency (`AccountContext`); mutation toasts; skeletons (`TableSkeleton`, `StatCardSkeleton` in Holdings, Options, Transactions); `SortableTable` Chakra + filter debounce; accessibility (`PnlText` aria-label, `StageBar` role=img + aria-label, table overflowX); Pagination on Transactions.

**Docs** — ARCHITECTURE, ROADMAP, PORTFOLIO, FRONTEND_UI, MODELS updated with mermaid and current patterns.

### Section 1.5 — Brokerage Infra + Per-User Credentials (PR 191) [DONE]

**Backend** — TastyTrade migrated to OAuth (SDK v12+); per-user encrypted credentials via `AccountCredentials` + `CredentialVault` (Fernet); Redis-backed `ConnectJobStore` for multi-worker connect flows; sync history recording (`AccountSync` model); API-level sync rejection tracking; Celery task time limits.

**Frontend** — Connect wizard for TT (OAuth) and IBKR (FlexQuery); credential edit modal; sync history table with error tooltips; `useConnectJobPoll` hook with exponential backoff; modal centering fix (Chakra v3 `DialogPositioner`).

**Infra** — Dev/prod parity: Celery restart policies, healthchecks, `depends_on` conditions; removed New Relic wrapper from dev backend; fixed celery beat volume-as-directory crash.

### Section 1.75 — Market Data DB-First + Portfolio Intelligence [DONE]

**Backend**

- Refactor `get_historical_data()` to check `PriceData` table before calling external APIs. Current flow: Redis -> FMP/yfinance. Target flow: Redis (L1) -> `PriceData` table (L2) -> External API (L3, backfills DB on fetch).
- Write-through: every chart load that hits an external API persists bars to `PriceData` via `persist_price_bars()`.
- Portfolio analytics uses `MarketSnapshot.beta` for weighted portfolio beta (replaces hardcoded 1.0) and `MarketSnapshot.sector` as fallback for sector attribution.
- Unified indicator engine: single `compute_full_indicator_series()` replacing four scattered compute paths. Adds ADX, Bollinger, StochRSI, 52w H/L, volume avg, TD Sequential per-bar to both `MarketSnapshot` and `MarketSnapshotHistory`.
- Indicator series endpoint: `GET /market-data/prices/{symbol}/indicators` reads from `MarketSnapshotHistory` (SQL read, not on-the-fly computation). Gap detection triggers `backfill_snapshot_history_for_symbol()` for missing history.

**Frontend** — Workspace shows `MarketSnapshot` fundamentals (Stage, RSI, ATR%, P/E, Div Yield, Beta, RS Mansfield, Earnings date) in a context strip. Support/Resistance horizontal price levels from clustered pivot highs/lows. Persistent colored circle markers on chart event days (buy/sell/dividend) without hover. Settings > Brokerages renamed to Settings > Connections. TradingView external link removed; in-app charting; default studies/interval synced to server preferences.

**Benefits (source wording)** — Offline chart rendering, no wasted API credits, instant loads for known symbols, richer portfolio intelligence from existing BRAIN data. "Fetch once, ready forever" for both OHLCV and indicator history.

| Status | Item |
|--------|------|
| DONE | Write-through to `PriceData` on API fetch |
| DONE | `MarketSnapshot` LEFT JOIN for portfolio enrichment |
| DONE | Workspace context strip with fundamentals |
| DONE | DB-first read path (L1 Redis -> L2 `PriceData` -> L3 API) |
| DONE | Unified indicator engine rewrite |
| DONE | `SettingsBrokerages` -> `SettingsConnections` rename |
| DONE | Indicator series endpoint from `MarketSnapshotHistory` |
| DONE | 5-year snapshot history backfill (36,806 rows) |

### Section 2 — Options, Categories, IB Gateway [DONE]

**WS-1: IB Gateway Connection [P0]** — Validate credentials and Docker config. `make ib-verify` for end-to-end check. Exponential backoff in `connect_with_retry` (1s, 2s, 4s, 8s, 16s). No Celery auto-reconnect. Manual reconnect -> `POST /portfolio/options/gateway-connect`. `GatewayStatusBadge` in portfolio nav shell. IB Gateway card in Settings > Connections.

**WS-2: Options Page Overhaul** — P0: `SortableTable` P/L table, decompose 1263-line `PortfolioOptions.tsx` into seven components. P1: strategy detection to full pattern set (Covered Call, CSP, Calendar, Diagonal, Butterfly), credit/debit, max P/L, breakeven, strategy card UX. P2 (deferred): payoff diagrams, theta calendar, Greeks dashboard, etc.

**WS-3: Categories Redesign** — P0: ticker chips on category cards, table view + category dropdown, `Category.user_id` fix, auto-categorize presets, preview modal. P1: `@dnd-kit`, allocation ring, rebalance preview.

### Section 2.5 — Backend-Served Indicator Series [DONE]

Architecture: `MarketSnapshotHistory` is the indicator series. Endpoint is SQL read.

```
Indicator Data Flow:
┌──────────┐     ┌──────────────────────────────┐     ┌──────────────────────┐
│ PriceData│ --> │ compute_full_indicator_series │ --> │ MarketSnapshotHistory│
│ (OHLCV)  │     │ (one unified function)        │     │ (immutable ledger)   │
└──────────┘     └──────────────────────────────┘     └──────────────────────┘
                                                              │
                                                    ┌────────┴─────────┐
                                                    │                  │
                                              .iloc[-1]          SQL read
                                                    │                  │
                                           ┌────────▼───┐    ┌────────▼────────┐
                                           │ MarketSnap- │    │ GET /indicators │
                                           │ shot(latest)│    │ (series endpoint)│
                                           └────────────┘    └─────────────────┘
```

**Track 1** (from `MarketSnapshotHistory`): EMA/SMA, RSI, MACD, Bollinger, ATR, stage coloring, TD Sequential, volume bars — scalar-per-date from DB.

**Track 2** (stays on frontend): Gap zones, trendline geometry, S/R level lists from raw OHLCV.

### Section 2.6 — Portfolio Finish Line [DONE]

**Sync layer (Phase 0.5)** — Split `ibkr_sync_service.py` into `ibkr/` package; fixed silent `except` in TastyTrade sync; `UniqueViolation` on transfers; `recover_stale_syncs` every 5 min; `flexquery-diagnostic` endpoint; Schwab OAuth client scaffold and sync.

**Live data** — `GET /portfolio/live/summary`, `/live/positions`, `/portfolio/dashboard/margin-health`, `/portfolio/dashboard/pnl-summary`; frontend credential error surfacing.

**Frontend** — `PortfolioTransactions` category filter, `PortfolioOverview` API shape, `PortfolioOptions` gateway offline handling.

**Cron alignment** — IBKR Daily Sync: 01:00 UTC. Daily Coverage Pipeline: 03:00 UTC. Stale Sync Recovery: every 5 min.

### Section 2.75 — BRAIN + PORTFOLIO Integration [DONE]

"My Holdings" filter in Market Tracked; "Portfolio" badge on Market Dashboard setup table; intelligence context strip in Workspace; actionable insights (stage deterioration, concentration, sector drift, RS degradation, earnings proximity); portfolio vs SPY benchmark on Dashboard.

### Section 2.8 — Streamline Three Pillars [DONE]

**Market data** — Production ETF data gap: Finnhub third fallback + Discord health alerts; universe filter All / ETFs Only / My Holdings; multi-provider fundamentals cascade (`set_if_missing()`); per-provider rate limiters; `eps_ttm` and `revenue_ttm` on `MarketSnapshot` + `MarketSnapshotHistory`.

**Portfolio** — Overview hero insight cards, SPY benchmark on equity curve, Holdings KPIs, symbol intelligence panel, portfolio badge on `SymbolLink`, workspace context strip enhancements.

**Strategy (trade execution foundation)** — `Order` model, IBKRClient what-if/place/cancel/status (paper), `OrderService` with risk guardrails ($100K max), API routes, 3-step `SellOrderModal`, sell action across Holdings/Tax Center/Intelligence/Workspace, chart order markers, `/portfolio/orders` page, sidebar link.

---

*Archive path*: `docs/archive/AXIOMFOLIO_ROADMAP.md` (full verbatim history).

## Active tasks (merged from TASKS.md, 2026-04-24)

*Lifted from [`docs/archive/AXIOMFOLIO_TASKS.md`](../archive/AXIOMFOLIO_TASKS.md) (archived 2026-04-24). Omitted: every historical phase row marked `DONE` / `MOVED`; Next Sprint rows marked `DONE` or `DROPPED`.*

### [IN PROGRESS] V1 Greenfield — Subscription Platform

Sprint context in source: **2026-04-09 to 2026-04-16** (v1 Week 1 banner); target **credible v1 by 2026-06-21** (8 weeks) per *TASKS.md*.

#### Already in this plan (skipped as duplicates)

- _Already covered: `fix/v1-phase-0-stabilization` — Phase 0 — Stabilization + Sprint Marker._
- _Already covered: `feat/v1-stripe-test-scaffolding` + PR #330 — Phase 0.5 Stripe scaffolding._
- _Already covered: `feat/v1-candidate-generator` — Phase 0.5 CandidateGenerator service._
- _Already covered: PR #326 (Entitlement + TierGate + FeatureCatalog) — Phase 0.5._
- _Already covered: PR #329 (AgentBrain v0 / PortfolioChat) — Phase 4 (Native AgentBrain + Mobile + Tier UX)._
- _Already covered: PR #331 (Polymorphic LLM email parser) — Phase 1 (Picks Pipeline)._
- _Already covered: PR #333 (AnomalyExplainer) + #334 (Sync OpenAI adapter) — Phase 4 (anomaly / LLM gateway)._
- _Already covered: Phases 15–18 (PLANNED in source: Live Trading, Portfolio Optimization, Risk Analytics, Mobile) — World-Class + Year 2 sections + “What This Plan Replaces” (post-stabilization future phases)._

*Skipped duplicate workstreams noted above: **8**.*

#### Open PR — retained (not subsumed by the list above)

| PR | Title | Status | Depends on | Notes |
|----|-------|--------|------------|-------|
| #332 | FileFree.ai tax-export scaffold | CI green | main | New `/api/v1/portfolio/tax/filefree/export?year=YYYY&format=json\|csv` + `/schema-version`. |

**Recommended merge order (TASKS.md, 2026-04-09)**: (1) #326 (2) #329 (3) #330 (4) #331, #332 in parallel (5) #333 (6) #334 after #333. *#326–#331 and #333–#334 are represented in phase sections of this file; use this order only for Git/PR sequencing; **#332** is the independent FileFree track in the table above.*

**Decisions (TASKS.md)**: D95–D102 in `docs/KNOWLEDGE.md` (V1 Greenfield) — entitlements, Stripe sink decoupling, polymorphic parser, dual AgentBrains, FileFree schema versioning, tax-advantaged default-skip, AnomalyExplainer always-degrades, sync-OpenAI rationale.

#### [BLOCKED] Known external (from TASKS.md)

| ID | Issue | Owner |
|----|-------|-------|
| D56 | Copilot reviewer auto-add returns 422 on every PR (`copilot-pull-request-reviewer` not a collaborator). The workflow runs but no review is ever posted. | Repo admin (sankalp404) — invite Copilot as a collaborator on `sankalp404/axiomfolio` or move to a plan that ships `@copilot` reviewer. |

### [PLANNED] Next sprint backlog (source table)

No in-flight rows: N.1 Alpaca broker adapter is **DROPPED** (D128) — not lifted. N.2 Apple Sign-In, N.3 onboarding, N.4 Bloomberg terminal dashboard — **DONE** in source — not lifted.

### [PLANNED / icebox] Future Phases (post-stabilization, TASKS.md)

Superseded as a set by this document’s World-Class and Year-2 content; see _Already in this plan_ and “What This Plan Replaces”.

---
