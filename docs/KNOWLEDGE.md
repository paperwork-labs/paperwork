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

### Infrastructure & Ops

| ID | Date | Decision |
|----|------|----------|
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
| D46 | 2026-03-31 | **Webhook events wired** — scan_alert (new Breakout Elite/Standard), regime_change (R-state shift), exit_alert (cascade non-HOLD) emit to Brain |
| D47 | 2026-03-31 | **HTTP schedule tools** — `GET /tools/schedules` + `POST /tools/run-task` exposed to Brain (total Brain HTTP tools: 12) |
| D48 | 2026-03-31 | **Approval timeout** — stale PENDING_APPROVAL orders auto-rejected after 30 min; `sweep_stale_approvals` task every 5 min; `approval_expired` webhook |

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
| D40 | 2026-03-27 | **Redis Streams for real-time events** — price:feed:alpaca, signals:evaluated, signals:output |
| D41 | 2026-03-27 | **Async Redis in async contexts** — redis.asyncio for FastAPI routes and services |

---

## Decision Details

### D44–D48 — Paperwork Integration Sprint (2026-03-31)

**Celery Beat (D44)**: All scheduling driven by `backend/tasks/job_catalog.py` via Celery Beat. 20 catalog entries with cron, timezone, timeout. Render worker runs `celery ... worker --beat`. Three legacy Render cron jobs (`admin_coverage_backfill`, `admin_retention_enforce`, `ibkr-daily-flex-sync`) suspended. `render_sync_service.py` remains for optional non-Beat / Render-cron deployments.

**run_task_now routing (D45)**: `run_task_now` is MODERATE risk but implemented inline in `_tool_run_task_now`. Without `INLINE_ONLY_AGENT_TOOLS` membership, it falls to `_dispatch_celery_task` which has no mapping. Fix: add to INLINE_ONLY.

**Webhook events (D46)**: Three events wired to Celery tasks: `scan_alert` from `_run_scan_overlay` (compares previous vs new tier), `regime_change` from `check_regime_alerts` (regime_shift type), `exit_alert` from `evaluate_exits_task` (non-HOLD recommendations). All use `brain_webhook.notify_sync()`.

**HTTP schedule tools (D47)**: `GET /api/v1/tools/schedules` lists all catalog tasks with last run status. `POST /api/v1/tools/run-task` dispatches any catalog task immediately by ID. Total Brain HTTP tools: 12.

**Approval timeout (D48)**: Orders in PENDING_APPROVAL beyond `APPROVAL_TIMEOUT_MINUTES` (default 30) are auto-rejected by `sweep_stale_approvals` task (every 5 min). Fires `approval_expired` webhook. `GET /api/v1/tools/pending-approvals` lets Brain poll pending orders.

### D43 — HMAC-SHA256 Webhook Signing (2026-03-30)

Replace plain `X-Webhook-Secret` header with HMAC-SHA256 body signing. Remove `approver_user_id`/`rejector_user_id` from approve/reject endpoints — routes bind to `BRAIN_TOOLS_USER_ID`.

`webhook_client.py`: Serializes JSON, computes `hmac.new(secret, body, sha256)`, sends `X-Webhook-Signature: sha256=<hex>`.

Alternatives: Plain shared secret (rejected — no payload integrity), OAuth/JWT (overkill for M2M webhook). Reversible.

### D32–D41 — Gold Standard & Brain Integration (2026-03-27)

**Circuit Breaker (D36)**: Three daily loss tiers (2%, 3%, 5%) with progressive restrictions. Kill switch at 5% halts all trading.

**Brain Integration (D32, D33, D35)**: AxiomFolio exposes `/api/v1/tools/*` endpoints for Brain orchestrator. API key in header, webhooks for events. Discord service deleted — Brain handles Slack routing. Total Brain HTTP tools: 12.

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
