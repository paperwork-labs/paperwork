# Knowledge — Decision Log

Architectural decisions with rationale. Grouped by domain, newest first within each section. Decision IDs are globally unique (D1–D99). Resolved issues use R-prefixed IDs.

---

## Active Issues

| ID | Issue | Status |
|----|-------|--------|
| D14 | Schwab `TRADE → BUY` mapping loses sell-side distinction | Open |
| D15 | TastyTrade tax lots are synthetic (CALCULATED) — not for tax reporting | Accepted limitation |

---

## Architecture Decisions

### Stage Analysis & Regime

| ID | Date | Decision |
|----|------|----------|
| D1 | 2026-03-23 | **SMA150 replaces 30-week SMA** as primary stage anchor (per Stage_Analysis.docx) |
| D2 | 2026-03-23 | **Regime Engine is mandatory hard gate** — R1-R5 gates all sizing, scan access, exits |
| D3 | 2026-03-23 | **10 sub-stages** (1A/1B, 2A/2B/2C, 3A/3B, 4A/4B/4C) replace simplified labels |
| D9 | 2026-03-23 | **Stage_Analysis.docx is canonical spec** — all implementation must match |
| D10 | 2026-03-23 | **SMA150 slope uses 20-day lookback**, thresholds ±0.35% |
| D11 | 2026-03-23 | **EMA10 Distance normalized by ATR** (`EMA10_Dist_N = EMA10_Dist% / ATR%14`) |
| D46 | 2026-03-31 | **ATR/ADX use Wilder's smoothing** — SMA seed for first N bars, then recursive `(prev * (N-1) + curr) / N`. Not simple rolling mean. |
| D47 | 2026-03-31 | **52-week High/Low from H/L columns** — not Close. Fallback to Close only if H/L missing. |
| D48 | 2026-03-31 | **Bollinger Bands use population std** (ddof=0) — not sample std (ddof=1). |
| D49 | 2026-03-31 | **TD Sequential caps at 9** — counter resets to 0 after completing a 9-count setup. |
| D50 | 2026-03-31 | **Bar guard = 175** — minimum bars needed for reliable stage classification (SMA150 + 20-bar slope + 5-bar warmup). |
| D51 | 2026-03-31 | **UNKNOWN stage treated as null** — `compute_stage_run_lengths` and `repair_stage_history_window` skip UNKNOWN labels. Displayed as "New" in UI. |
| D52 | 2026-03-31 | **Regime rounding uses half-up** — `math.floor(avg * 2 + 0.5) / 2` not Python's banker's `round()`. |
| D53 | 2026-03-31 | **RiskGate.check mandatory on submit path** — not just preview. Rejected orders logged with reason. |
| D54 | 2026-04-04 | **FMP rate limits via ProviderPolicy** — single `MARKET_PROVIDER_POLICY` env var selects tier (free/starter/paid/unlimited). Legacy per-var config (`RATE_LIMIT_FMP_CPM`, `PROVIDER_DAILY_BUDGET_FMP`) deprecated. |
| D55 | 2026-04-04 | **Deep backfill bypasses L2 DB cache** — `daily_since` sets `skip_l2=True` so `get_historical_data` always reaches L3 external APIs. Prevents partial-history short-circuit when DB already has fresh bars. |
| D59 | 2026-04-05 | **VolatilityService extracted** — VIX/VVIX/VIX3M logic moved from inline route handler to `backend/services/market/volatility_service.py`. Route is now a thin wrapper. |
| D60 | 2026-04-05 | **Dashboard universe filter** — `GET /dashboard?universe=all\|etf\|holdings` filters tracked symbols server-side before all aggregations. Cache key includes universe. |
| D61 | 2026-04-05 | **Server-side table endpoint** — `GET /snapshots/table` with sort/page/filter replaces client-side 5000-row fetch for the scanner/table views. |
| D62 | 2026-04-05 | **Frontend dedup hooks** — `useVolatility()` and `useRegime()` share React Query cache across TopDownView/RegimeBanner/MarketDashboard. |
| D63 | 2026-04-05 | **Budget check fail-closed** — if Redis is unreachable during FMP daily budget check, the provider is skipped (fail-closed) instead of allowing unlimited calls. |

### Execution & Orders

| ID | Date | Decision |
|----|------|----------|
| D6 | 2026-03-23 | **Single order path**: OrderManager → RiskGate → BrokerRouter (OrderService merged) |
| D16 | 2026-03-23 | **No alternative execution paths** — all orders through OrderManager |
| D18 | 2026-03-23 | **IBKR is primary execution broker** — Schwab/TastyTrade read-only for now |

### Frontend & UX

| ID | Date | Decision |
|----|------|----------|
| D13 | 2026-03-23 | **Bloomberg-style multi-view dashboard**: Top-Down, Bottom-Up, Sector, Heatmap |
| D22 | 2026-03-24 | **Intelligence brief has Universe + Book sections** |
| D23 | 2026-03-24 | **TopDown is dual-mode** — Universe view + Portfolio view |

### Strategic Direction

| ID | Date | Decision |
|----|------|----------|
| D81 | 2026-04-09 | **Two-milestone plan replaces 6+ month roadmap** — v1 Launch 2026-06-21 (10 weeks) ships paying users on 6 tiers + Validated Picks + native AgentBrain chat + Snowball viz + TRIM/ADD/rebalance + tax-aware exits + email parser + PWA mobile. World-Class Complete 2026-08-31 (20 weeks) ships Plaid + 5 brokers + walk-forward + Monte Carlo + symbol master + multi-source quorum + OpenTelemetry + chaos + Trade Copy + AI optimizer. No features cut, just sequenced. Master plan: `docs/plans/MASTER_PLAN_2026.md`. Reversible: revert plan + reduce milestone scope. |
| D82 | 2026-04-09 | **Six-tier subscription model** — Free / Lite / Pro / Pro+ / Quant Desk / Enterprise. Free = read-only Snowball viz + 24h-delayed picks (acquisition hook). Lite = real-time picks (no autotrade). Pro = autotrade + tax-aware exits. Pro+ = + native AgentBrain chat + multi-portfolio + advanced backtests. Quant Desk = + walk-forward + plugin SDK + white-label. Enterprise = SSO + SLA + custom integrations. Stripe-backed; `User.tier` enum + `Entitlement` table. Alternatives: 3-tier (rejected — less ARR per user), usage-based (rejected — fights retail intuition). Reversible. |
| D83 | 2026-04-09 | **Native AgentBrain chat panel as Pro+ hook** — Pro+ users see pinned right-rail chat panel powered by internal `AgentBrain`. Auto-injects portfolio context, current page, recent picks. Differentiates from Snowball (no chat) and StocksToBuyNow (signals only, no analysis). Cross-sell to Paperwork Brain for cross-domain conversational AI remains optional. Alternative: route everything through external Paperwork Brain (rejected — couples products, weakens AxiomFolio standalone value); ship to Pro instead of Pro+ (rejected — anchor feature for Pro+ upgrade). Reversible: gate behind feature flag. |
| D84 | 2026-04-09 | **Twisted Slice pseudonym for hedge fund validator** — All references to founder's brother in code, docs, UI, marketing copy, public scorecard use `twisted_slice` / "Twisted Slice". Real identifying details live only in the `PICKS_TRUSTED_SENDERS` env var (server-side, never exposed in code, docs, version control, or any user-facing artifact). Enforced via `.cursor/rules/validator-curator.mdc`. Alternatives: real name (rejected — privacy), generic "validator" (rejected — less brand). Reversible. |
| D85 | 2026-04-09 | **Polymorphic LLM picks parser, not template-based** — Inbound emails from validators have N different formats (single-stock bullets, hedge fund research recap with timestamps, research-note paragraph, daily market recap narrative, mixed). LLM (gpt-4o for synthesis, gpt-4o-mini for triage) picks the right schema template at parse time and extracts polymorphically. Schema set: `ValidatedPick`, `MacroOutlook`, `SectorRanking`, `PositionChange`, `RegimeCall`, `FlowSignal`, `AttributedQuote`. Cross-email signal linking via vector similarity + symbolic level matching. Alternatives: per-template regex parsers (rejected — fragile, doesn't generalize), pure structured-output API (rejected — emails are too varied). Reversible: per-format fallback parsers. |
| D86 | 2026-04-09 | **PDF + image attachment ingestion first-class** — Validators forward research notes as PDFs with embedded charts (e.g., ZeroHedge daily). `pymupdf` for PDF text + image extraction, gpt-4o vision for chart captioning. Cost-gated to trusted senders (vision is expensive). Email + PDF dedupe layer flags duplicates and merges into single ValidatedPick draft. Alternative: text-only ingestion (rejected — drops half the signal). Reversible: disable vision via flag. |
| D87 | 2026-04-09 | **Per-tier LLM cost budgets** — Free: $0/mo, Lite: $0/mo, Pro: $5/mo, Pro+: $20/mo, Quant: unlimited. Tracked via Langfuse per-user per-feature. Hard cap with degradation to "feature unavailable this month" message. Alternatives: per-call charging (rejected — fights retail UX), no cap (rejected — runaway costs). Reversible. |
| D88 | 2026-04-09 | **Multi-tenancy hardening blocks v1 launch** — Current code has hardcoded `BRAIN_TOOLS_USER_ID=1` and global `CircuitBreaker`. Per-user circuit breaker, per-tenant Redis namespaces, per-tenant rate limits, GDPR data export/delete are v1 launch requirements. Tracked in MASTER_PLAN_2026 Phase 8d (lifted from World-Class to v1 critical path). Alternative: ship single-tenant first (rejected — billing requires multi-tenant). Reversible: revert per-user changes. |
| D89 | 2026-04-09 | **FileFree and AxiomFolio integrate via Brain, never direct imports** — FileFree ([filefree.ai](https://filefree.ai/)) is a separate Paperwork Labs product. AxiomFolio exports year-end tax package (1099 + tax lots + wash-sale ledger) via existing brain webhook channel. FileFree consumes via Brain. Codebases stay independent. Alternative: shared monorepo (rejected — couples release cadence). Reversible: collapse via direct API if needed. |
| D90 | 2026-04-09 | **Cloud Background Agents pattern for parallel sprint execution** — Heavy v1+WC sprint dispatched as parallel Cursor Background Agents from this Opus orchestrator. Each agent owns one PR end-to-end (clone, branch, code, test, push, open PR, fix CI). Founder reviews/merges from anywhere (laptop or Cursor mobile). Opus stays in-session for architecture, schema, code review of agent output, decision logging. Pattern documented in `.cursor/rules/delegation.mdc`. Alternative: serial in-session work (rejected — too slow for 10-week v1 timeline). Reversible. |

### Infrastructure & Ops

| ID | Date | Decision |
|----|------|----------|
| D76 | 2026-04-16 | **Worker plan: Render Standard (2 GiB)** — Worker on Starter (512 MiB) was OOM-killed daily. 24h memory observed: avg 430 / peak 508.6 MiB on a 512 MiB ceiling = zero headroom. Indicator recompute over 2,500 symbols + IBKR FlexQuery + OrderManager + Beat in one process legitimately needs 1+ GiB. `--max-memory-per-child` raised in lockstep from 750000 (above ceiling, never fired) to 1500000 KiB so Celery recycles before kernel OOM. Alternatives: Render Pro 4 GiB ($85/mo, only if a full snapshot_history rebuild is added back); migrate to DigitalOcean App Platform (Plan B). Reversible: revert render.yaml. |
| D77 | 2026-04-16 | **API uvicorn workers: 2** — PR #295 cut workers from 2 → 1 on 2026-04-06 to mask memory pressure. Real cause (heavy synchronous `build_dashboard()` in web process) was fixed in `291f2e0` on 2026-04-11. API peak RAM observed at 255 MiB / 2 GiB Standard plan = ample room for 2 workers. Restoring doubles request capacity. Reversible: revert Dockerfile.backend. |
| D78 | 2026-04-16 | **Position.status filters use `PositionStatus.OPEN` enum, never `"open"` string** — Postgres `positionstatus` enum is uppercase (`OPEN`, `CLOSED`, `EXPIRED`); literal `"open"` raises `psycopg2.errors.InvalidTextRepresentation` and crashed the exit_cascade nightly step. Regression test in `backend/tests/test_position_status_filter.py`. |
| D79 | 2026-04-16 | **Dashboard cache warming every 15 minutes** — `/market-data/dashboard` reads exclusively from Redis (cache miss returns 202). Without periodic warming the cache goes cold between nightly runs and after worker restarts, forcing every dashboard load to wait 30+s. Three Beat entries (universes `all`/`etf`/`holdings`) staggered at minutes 0/5/10 of every 15-min window keep all keys hot and absorb worker recycles cleanly. |
| D80 | 2026-04-16 | **Stale-session UX: explicit `/login` redirect on `auth:logout`** — When `/auth/refresh` itself 401s (expired refresh cookie or rotated token family), the API interceptor dispatches `auth:logout`. AuthContext clears React state but does not navigate. Added `AuthLogoutListener` inside `<Router>` to navigate to `/login` with a "Session expired" toast, eliminating the silent "Loading…" state on protected pages after long idle. |
| D74 | 2026-04-10 | **Statement timeout 30s on all DB connections** — Added `-c statement_timeout=30000` to SQLAlchemy connect_args to prevent runaway queries from blocking connection pool. Configurable via DB_STATEMENT_TIMEOUT_MS env var. Alternatives: per-query timeout (fragile), pg-level idle_in_transaction_session_timeout (complementary). Reversible: remove connect_args. |
| D75 | 2026-04-10 | **Health check split: /health (fast) vs /health/full (DB)** — Render health probes now hit a lightweight /health endpoint with no DB queries. Full DB validation moved to /health/full for admin use. Eliminates health check timeouts that caused 502 cascades. Alternatives: cache health response (still risks first-request timeout). Reversible: merge endpoints back. |
| D4 | 2026-03-23 | **Persona-based cursor rules** for domain-specific AI context |
| D5 | 2026-03-23 | **Celery time limits per-task** — match job_catalog.py timeout_s |
| D17 | 2026-03-23 | **Intelligence Brief system** — daily/weekly/monthly proactive delivery |
| D25 | 2026-03-24 | **Auto-Ops Agent** — 15-min health checks with auto-remediation |
| D28 | 2026-03-24 | **Greenfield DB rebuild** — single baseline migration, fresh Postgres |
| D29 | 2026-03-25 | **Celery task routing must match `name=`** exactly — no auto-derivation |
| D30 | 2026-03-25 | **Quarterly dependency audit** — Postgres, Python, Vite major versions |
| D31 | 2026-03-26 | **Agent codebase access policy** — allowlist prefixes, denylist sensitive patterns |
| D42 | 2026-03-28 | **IBKR Gateway settings persistence** — `TWS_SETTINGS_PATH` + volume mount |
| D44 | 2026-03-31 | **Celery Beat replaces Render crons** — all scheduling via job_catalog.py, Beat embedded in worker with `--beat` flag. Legacy Render crons suspended; sync code (`render_sync_service.py`) retained if platform crons are re-enabled |
| D45 | 2026-03-31 | **run_task_now in INLINE_ONLY** — MODERATE risk tool must route through _execute_safe_tool, not _dispatch_celery_task (no TOOL_TO_CELERY_TASK mapping needed) |

### Platform Integration (Brain)

| ID | Date | Decision |
|----|------|----------|
| D21 | 2026-03-24 | **AxiomFolio is a Paperwork Brain skill** — exposes clean API surface |
| D32 | 2026-03-27 | **Brain API key auth** — `X-Brain-Api-Key` header validated via `secrets.compare_digest` |
| D33 | 2026-03-27 | **Unified notifications via Brain** — Discord removed, all alerts route through Brain webhook |
| D34 | 2026-03-27 | **Three-tier user roles** — owner/analyst/viewer replacing admin/user/readonly |
| D35 | 2026-03-27 | **Trade approval workflow** — Tier 3 actions require owner approval, ApprovalService tracks state |
| D43 | 2026-03-30 | **HMAC-SHA256 webhook signing** — body signing replaces plain secret; approve/reject bind to service identity |
| D69 | 2026-03-31 | **HTTP schedule tools** — `GET /tools/schedules` + `POST /tools/run-task` exposed to Brain (total Brain HTTP tools: 12) |
| D70 | 2026-04-06 | **Brain API key / webhook concentrated risk** — `BRAIN_API_KEY` and Brain webhook URL are a single M2M lane for outbound alerts. If the key is compromised or Brain is unavailable, **all** alerting on that path stops until rotated or restored. Mitigation: treat key like a production secret (rotation, least privilege), monitor delivery failures, and consider a **fallback alert channel** for critical ops signals. |
| D71 | 2026-03-31 | **Webhook events wired** — scan_alert (new Breakout Elite/Standard), regime_change (R-state shift), exit_alert (cascade non-HOLD) emit to Brain |
| D72 | 2026-03-31 | **Approval timeout** — stale PENDING_APPROVAL orders auto-rejected after 30 min; `sweep_stale_approvals` task every 5 min; `approval_expired` webhook |

### Risk & Execution

| ID | Date | Decision |
|----|------|----------|
| D36 | 2026-03-27 | **Circuit breaker with 3 tiers** — 2%/3%/5% daily loss limits, kill switch at 5% |
| D37 | 2026-03-27 | **Trading day resets at 4 AM ET** — configurable via trading_day_timezone/trading_day_reset_hour |
| D38 | 2026-03-27 | **TradingView webhook secrets hashed** — SHA-256 hex, constant-time comparison |
| D39 | 2026-03-27 | **Webhook orders start as PREVIEW** — OrderManager.submit() handles state transitions |

### Data Pipeline

| ID | Date | Decision |
|----|------|----------|
| D73 | 2026-04-10 | **Materialized Views for dashboard aggregations** — Pre-compute breadth (% above SMA50/200), stage distribution, and sector performance into PostgreSQL materialized views (mv_breadth_daily, mv_stage_distribution, mv_sector_performance). Refreshed nightly via CONCURRENTLY after indicator computation. Eliminates 7M-row aggregation queries from API hot path. Alternatives: query-time aggregation (current, causes 502s), summary tables (more maintenance). Reversible: DROP VIEW. |
| D40 | 2026-03-27 | **Redis Streams for real-time events** — price:feed:alpaca, signals:evaluated, signals:output |
| D41 | 2026-03-27 | **Async Redis in async contexts** — redis.asyncio for FastAPI routes and services |
| D64 | 2026-04-02 | **iShares IWM ETF fallback for Russell 2000** — FMP/Finnhub lack R2K endpoint; parse CSV holdings from iShares; never cache empty constituent lists |
| D65 | 2026-04-02 | **HISTORY_TARGET_YEARS = 10** — one-time deep backfill, then delta-only nightly pipeline; 400-bar window sufficient for all rolling indicators |
| D66 | 2026-04-02 | **Agent chat tool_choice = auto** — first turn no longer forces tool call; out-of-scope guard in SYSTEM_PROMPT |
| D67 | 2026-04-02 | **User FK cascade policy** — CASCADE for user-owned data, SET NULL for audit/tracking columns; Alembic migration for 20+ FKs |
| D68 | 2026-04-02 | **Curated ETFs for multi-asset exposure** — IBIT, BITO, GLD, SLV, UNG, TLT, IEF, HYG, ARKK added to CURATED_MARKET_SYMBOLS |

---

## Decision Details

### D44–D45, D69, D71–D72 — Paperwork Integration Sprint (2026-03-31)

**Celery Beat (D44)**: All scheduling driven by `backend/tasks/job_catalog.py` via Celery Beat. 20 catalog entries with cron, timezone, timeout. Render worker runs `celery ... worker --beat`. Three legacy Render cron jobs (`admin_coverage_backfill`, `admin_retention_enforce`, `ibkr-daily-flex-sync`) suspended. `render_sync_service.py` remains for optional non-Beat / Render-cron deployments.

**run_task_now routing (D45)**: `run_task_now` is MODERATE risk but implemented inline in `_tool_run_task_now`. Without `INLINE_ONLY_AGENT_TOOLS` membership, it falls to `_dispatch_celery_task` which has no mapping. Fix: add to INLINE_ONLY.

**HTTP schedule tools (D69)**: `GET /api/v1/tools/schedules` lists all catalog tasks with last run status. `POST /api/v1/tools/run-task` dispatches any catalog task immediately by ID. Total Brain HTTP tools: 12.

**Webhook events (D71)**: Three events wired to Celery tasks: `scan_alert` from `_run_scan_overlay` (compares previous vs new tier), `regime_change` from `check_regime_alerts` (regime_shift type), `exit_alert` from `evaluate_exits_task` (non-HOLD recommendations). All use `brain_webhook.notify_sync()`.

**Approval timeout (D72)**: Orders in PENDING_APPROVAL beyond `APPROVAL_TIMEOUT_MINUTES` (default 30) are auto-rejected by `sweep_stale_approvals` task (every 5 min). Fires `approval_expired` webhook. `GET /api/v1/tools/pending-approvals` lets Brain poll pending orders.

### D43 — HMAC-SHA256 Webhook Signing (2026-03-30)

Replace plain `X-Webhook-Secret` header with HMAC-SHA256 body signing. Remove `approver_user_id`/`rejector_user_id` from approve/reject endpoints — routes bind to `BRAIN_TOOLS_USER_ID`.

`webhook_client.py`: Serializes JSON, computes `hmac.new(secret, body, sha256)`, sends `X-Webhook-Signature: sha256=<hex>`.

Alternatives: Plain shared secret (rejected — no payload integrity), OAuth/JWT (overkill for M2M webhook). Reversible.

### D32–D41 — Gold Standard & Brain Integration (2026-03-27)

**Circuit Breaker (D36)**: Three daily loss tiers (2%, 3%, 5%) with progressive restrictions. Kill switch at 5% halts all trading.

**Brain Integration (D32, D33, D35)**: AxiomFolio exposes `/api/v1/tools/*` endpoints for Brain orchestrator. API key in header, webhooks for events. Outbound alerts route through the **Brain webhook** (D33), not Discord. Total Brain HTTP tools: 12.

**User Roles (D34)**: Migrated from `admin/user/readonly` to `owner/analyst/viewer`. Analyst can propose trades but requires owner approval.

**Async Redis (D41)**: All async functions must use `redis.asyncio` to avoid blocking the event loop. Sync Redis retained for Celery tasks.

### D31 — Agent Codebase Access Policy (2026-03-26)

Allowed: `services/`, `api/`, `tasks/`, `models/`, `utils/`, `tests/`. Denied: `.env`, `.pem`, `.key`, `secret`, `credential`, `password`. INLINE_ONLY tools always execute regardless of autonomy level.

### D28 — Greenfield DB Rebuild (2026-03-24)

Deleted 33 Alembic migrations, created single `0001_baseline.py`. Production was broken by blocked migration chain. Bundled: Google OAuth, refresh tokens, BrokerAdapter ABC, multi-tenant enforcement.

### D29 — Celery Task Routing (2026-03-25)

All task references must match `@shared_task(name="...")` exactly. Found 4 critical mismatches between `job_catalog.py` and actual task registrations.

### D3 — Scan Tier Rename (2026-03-28)

`Set 1` → `Breakout Elite`, `Set 2` → `Breakout Standard`, `Set 3` → `Early Base`, `Set 4` → `Speculative`, `Short Set 1` → `Breakdown Elite`, `Short Set 2` → `Breakdown Standard`. Names describe setup quality instead of internal jargon.

### D2 — Regime as Hard Gate (2026-03-23)

6 daily inputs → composite score → R1-R5: VIX spot, VIX3M/VIX, VVIX/VIX, NH-NL ratio, % above 200D, % above 50D. All position sizing, scan access, entry timing, and exit acceleration inherit current Regime.

---

## 10-Year Backfill Runbook

### Why 10 Years

- SMA150 + SMA200 need ~200 trading days of warmup; 5 years would give only ~3.5 years of usable stage history
- 10 years (2516 trading days) provides ~8 years of fully warmed-up data for backtesting
- RS Mansfield (252-day MA) needs 1 year of warmup — 10 years gives 9 years of RS data
- FMP historical data cost is flat (no per-year charge)

### Steps

1. **Increase `SNAPSHOT_DAILY_BARS_LIMIT`** in `backend/config.py` from 400 to 2600 (10 years + buffer)
2. **Run full backfill**: Use "Backfill Daily Coverage (Tracked)" from Operator Actions — covers all tracked symbols
3. **Recompute indicators**: "Recompute Indicators (Market Snapshot)" — recalculates all indicators with full 10-year series
4. **Verify**: Check Admin Health Dashboard — stage_quality should show <5% unknown rate, fundamentals should show >90% fill
5. **Russell 2000**: Add via "Sync Index Constituents" then run coverage backfill — this adds ~2000 symbols and will take longer

### Russell 2000 Coverage

- Index constituents sync supports `russell_2000` via FMP
- In prod, enable by adding to the tracked index list
- Backfill will take ~30-60 min for 2000 symbols at 10 years each
- FMP rate limits may require batching — the pipeline handles this with built-in retry/backoff

### Data Quality Checklist (Post-Backfill)

- [ ] Stage Quality: unknown_rate < 5%
- [ ] Fundamentals: fill_pct > 90%
- [ ] Daily coverage: > 98%
- [ ] RS Mansfield: non-null for all symbols with > 252 bars
- [ ] No UNKNOWN stages for symbols with > 175 bars of data

---

## Resolved Issues

| ID | Issue | Resolution |
|----|-------|------------|
| R1 | Celery 360s global limit kills long tasks | Raised defaults to 3500s/3600s, explicit per-task limits |
| R2 | Dual order paths will drift | OrderService merged into OrderManager |
| R3 | `get_portfolio_user` falls back to `User.first()` | Now requires JWT via `get_current_user` |
| R4 | RSI uses SMA not Wilder | False alarm — already uses Wilder smoothing |
| R5 | React Query v3 is legacy | Migrated to TanStack Query v5 |
| R6 | MarketDashboard.tsx 1400+ lines | Decomposed to 5-tab lazy-loaded views |
| R7 | Silent `except: pass` in indicators | Replaced with proper logging |
| R8 | Scan overlay field-name bugs | Fixed wrong column names |
| R9 | compute_daily_regime missing commit | Added session.commit() after persist_regime() |
| R10 | Intelligence tasks not registered | Added to celery_app.py include list |
| R11 | Circuit breaker banner on every page | Moved to PortfolioOverview only |
| R12 | Snapshot history 0% on dashboard | Unified query path in AdminHealthService with 5-min Redis cache |
| R13 | Render cron jobs retired | All scheduling via Celery Beat from job_catalog.py (D44) |
| R14 | Auto-ops backoff used 2^n exponentiation | Replaced with explicit BACKOFF_SEQUENCE tuple (15m, 30m, 60m, 2h) |
| R15 | run_task_now bypassed Celery dispatch | Added to INLINE_ONLY_AGENT_TOOLS — routes through _execute_safe_tool (D45) |
| R16 | ATR/ADX used SMA instead of Wilder's | Replaced with Wilder's exponential smoothing in indicator_engine.py (D46) |
| R17 | 52-week H/L used Close instead of High/Low | Fixed to use High/Low columns with Close fallback (D47) |
| R18 | Bollinger Bands used sample std (ddof=1) | Changed to population std (ddof=0) (D48) |
| R19 | TD Sequential could exceed 9-count | Capped at 9 with counter reset (D49) |
| R20 | UNKNOWN stage propagated through history | Skip UNKNOWN in run-length computation, display as "New" in UI (D51) |
| R21 | Regime rounding used banker's | Switched to half-up rounding (D52) |
| R22 | Exit cascade T2/T7 trailing stop structural bug | Fixed comparison to `current_price < hwm - trail_distance` |
| R23 | S4 short exit 35% tier unreachable | Reordered conditions: check 35% before 20% |
| R24 | OrderManager.submit skipped RiskGate | Added RiskGate.check before broker place_order (D53) |
| R25 | fundamentals_fill not scheduled | Added to job_catalog.py with daily 3:15 UTC cron |
| R26 | symbol String(10) truncation risk | Widened to String(20) via Alembic migration |
| R27 | PriceData.volume Integer overflow | Changed to BigInteger via Alembic migration |
| R28 | Zombie job runs stuck for 2h+ | Reduced STALE_JOB_RUN_MINUTES from 120 to 45 |
| R29 | scan_engine coerced None RS to 0 | Now skips Elite tiers when rs_mansfield is None |
| R30 | FMP capped at 250 calls/day on paid plans | Replaced per-var config with ProviderPolicy tiers; paid tier allows 100,000/day at 700 CPM (D54) |
| R31 | deep backfill short-circuited at L2 DB cache | Added skip_l2 param to fetch_daily_for_symbols; daily_since always bypasses L2 |
| R32 | Worker silently dead since Apr 10 — tz-aware Timestamp + forked engine pool | `provider_router.py` strips tz before exchange_calendars; `celery_app.py` `worker_process_init` calls `engine.dispose()` (commit a70f09a, 2026-04-15) |
| R33 | Async Redis client invalid across Celery event loops + DB pool exhaustion under concurrent backfills | `market_infra.py` re-initializes async Redis if loop is closed; `_daily_backfill_concurrency` capped at 20 to stay below SQLAlchemy pool of 30 (PR #314, 2026-04-15) |
| R34 | Worker OOM-killed daily on Render Starter (512 MiB) | Upgraded to Standard (2 GiB); `--max-memory-per-child` raised from 750000 to 1500000 KiB so Celery recycles before kernel OOM (D76, 2026-04-16) |
| R35 | Exit_cascade nightly step crashed: `invalid input value for enum positionstatus: "open"` | Replaced `Position.status == "open"` with `Position.status == PositionStatus.OPEN` in coverage.py and monitoring.py + regression test (D78, 2026-04-16) |
| R36 | Stale-session UX trap: page sat at "Loading…" forever after refresh-token expiry | `AuthLogoutListener` inside Router navigates to `/login` with toast on `auth:logout` event (D80, 2026-04-16) |
| R37 | API SIGSEGV (exit 139) ×6 — investigation closed | All 6 events occurred in one 5-hour window on 2026-04-10 during the deploy storm (7 PRs in one day). Zero SIGSEGVs since. Root cause: uvicorn graceful-shutdown race during rapid container churn (likely psycopg2/asyncio teardown). The pre-merge CI gate rule (commit 8a202e7, 2026-04-09) prevents the deploy-storm pattern. No code fix needed. |
| R38 | Snapshot history coverage 1.7% on most days (43/2534 symbols) | `recompute_universe` was silently swallowing per-symbol exceptions for 2491 symbols. Phase 0 fix adds structured counters (`written`, `skipped_no_data`, `errors`) to the loop in `backend/tasks/market/indicators.py` plus a final assertion that `written + skipped + errors == tracked_total`. Coverage test fails the build if assertion violated. Tracked under `fix/v1-phase-0-stabilization`. |
| R39 | 2820 monotonicity violations in `market_snapshot_history` + repair task killed by Postgres `statement_timeout` | `repair_stage_history_window` ran `SELECT DISTINCT symbol FROM market_snapshot_history` against a 7M+ row table with no covering index, exceeding the 30s statement timeout (D74). Phase 0 fix: Alembic migration `CREATE INDEX CONCURRENTLY ix_market_snapshot_history_symbol_btree`; rewrite query in `backend/services/market/stage_quality_service.py` to use `tracked_symbols_with_source` (already in cache). One-time bulk repair on the new heavy worker queue clears the 2820 violations. Tracked under `fix/v1-phase-0-stabilization`. |

---

## Strategic Direction (v1 sprint)

Decisions D81–D90 live on the `feat/v1-master-plan` branch (PR #316, merged
2026-04-18). The following decisions are added in subsequent v1-sprint PRs
and chain off that base.

| ID | Date | Decision |
|----|------|----------|
| D91 | 2026-04-18 | **Entitlement is the single source of truth for tier access.** `backend/services/billing/feature_catalog.py` is the only place that maps a feature key to a minimum tier. Backend (`require_feature` dependency) and frontend (`useEntitlement` + `<TierGate>`) both consume it so they cannot drift. Stripe webhooks are the only writers besides operator manual overrides. Past-due subscriptions get a 72h grace period; manual entitlements (founders, validator pseudonyms) cannot be overwritten by Stripe events. |
| D92 | 2026-04-18 | **Tier-gating returns HTTP 402 (Payment Required), not 403.** This lets the frontend distinguish "you need to log in" from "you need to upgrade" without a string sniff on the error body, matching how Stripe-gated APIs across the industry signal paywalls. Routes mounted via `Depends(require_feature("..."))` always return a structured `{error: "tier_required", feature, current_tier, required_tier}` body. |
