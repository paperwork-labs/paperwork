# Knowledge — Decision Log

Architectural decisions with rationale. Grouped by domain, newest first within each section.

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
| D1 | 2026-03-23 | **SMA150 replaces 30-week SMA** as primary stage anchor (per Stage_Analysis_v4.docx) |
| D2 | 2026-03-23 | **Regime Engine is mandatory hard gate** — R1-R5 gates all sizing, scan access, exits |
| D3 | 2026-03-23 | **10 sub-stages** (1A/1B, 2A/2B/2C, 3A/3B, 4A/4B/4C) replace simplified labels |
| D9 | 2026-03-23 | **Stage_Analysis_v4.docx is canonical spec** — all implementation must match |
| D10 | 2026-03-23 | **SMA150 slope uses 20-day lookback**, thresholds ±0.35% |
| D11 | 2026-03-23 | **EMA10 Distance normalized by ATR** (`EMA10_Dist_N = EMA10_Dist% / ATR%14`) |

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
| D4 | 2026-03-23 | **7 persona-based cursor rules** for domain-specific AI context |
| D5 | 2026-03-23 | **Celery time limits per-task** — match job_catalog.py timeout_s |
| D17 | 2026-03-23 | **Intelligence Brief system** — daily/weekly/monthly proactive delivery |
| D25 | 2026-03-24 | **Auto-Ops Agent** — 15-min health checks with auto-remediation |
| D28 | 2026-03-24 | **Greenfield DB rebuild** — single baseline migration, fresh Postgres |
| D29 | 2026-03-25 | **Celery task routing must match `name=`** exactly — no auto-derivation |
| D30 | 2026-03-25 | **Quarterly dependency audit** — Postgres, Python, Vite major versions |
| D31 | 2026-03-26 | **Agent codebase access policy** — allowlist prefixes, denylist sensitive patterns |
| D42 | 2026-03-28 | **IBKR Gateway settings persistence** — `TWS_SETTINGS_PATH` + `ibkr-settings` volume, IBC auto-accept API clients, `portfolio_sync` health dimension |

### Platform Integration

| ID | Date | Decision |
|----|------|----------|
| D21 | 2026-03-24 | **AxiomFolio is a Paperwork Brain skill** — exposes clean API surface |
| D32 | 2026-03-27 | **Brain API key auth** — X-Brain-Api-Key header validated via secrets.compare_digest |
| D33 | 2026-03-27 | **Unified notifications via Brain** — Discord removed, all alerts route through Brain webhook |
| D34 | 2026-03-27 | **Three-tier user roles** — owner/analyst/viewer replacing admin/user/readonly |
| D35 | 2026-03-27 | **Trade approval workflow** — Tier 3 actions require owner approval, ApprovalService tracks state |
| D43 | 2026-03-30 | **HMAC-SHA256 webhook signing** — AxiomFolio signs webhook body, Brain verifies; approve/reject bind to service identity |

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

### D32–D41 — Gold Standard & Brain Integration (2026-03-27)

Major rebuild implementing production-grade trading infrastructure:

**Circuit Breaker (D36)**: Three daily loss tiers (2%, 3%, 5%) with progressive restrictions. Kill switch at 5% halts all trading. Configurable via `CircuitBreakerConfig` dataclass.

**Brain Integration (D32, D33, D35)**: AxiomFolio exposes `/api/v1/tools/*` endpoints for Brain orchestrator. API key in header, webhooks for events. Discord service deleted — Brain handles Slack routing.

**User Roles (D34)**: Migrated from `admin/user/readonly` to `owner/analyst/viewer`. Analyst can propose trades but requires owner approval. Stored as VARCHAR via SQLEnum(native_enum=False).

**Async Redis (D41)**: All async functions must use `redis.asyncio` to avoid blocking the event loop. Sync Redis retained only for sync callers (Celery tasks).

### D31 — Agent codebase access policy (2026-03-26)

Agent `read_file`/`list_files` have explicit security boundaries:
- **Allowed**: `services/`, `api/`, `tasks/`, `models/`, `utils/`, `tests/`
- **Denied**: `.env`, `.pem`, `.key`, `secret`, `credential`, `password`

INLINE_ONLY tools always execute regardless of autonomy level (admin authenticated, needs sync response).

### D28 — Greenfield DB rebuild (2026-03-24)

Deleted 33 Alembic migrations, created single `0001_baseline.py` with `Base.metadata.create_all()`. Production was broken by blocked migration chain referencing non-existent `strategies` table.

Bundled: Google OAuth, refresh tokens, BrokerAdapter ABC, multi-tenant enforcement, TanStack Query v5, SystemStatus admin, agent cold-start backfill.

### D29 — Celery task routing (2026-03-25)

All task references must match `@shared_task(name="...")` exactly. Found 4 critical mismatches:
1. `backend.tasks.order_tasks.*` vs `backend.tasks.portfolio.orders.*`
2. `refresh_index_constituents_task` vs `refresh_index_constituents`
3. `backend.tasks.intelligence.tasks.*` vs `backend.tasks.intelligence_tasks.*`
4. `recover_stale_job_runs_impl` vs `recover_stale_job_runs`

### D3 — Scan tier rename (2026-03-28)

Renamed informal "Set 1/2/3/4" terminology to descriptive labels:
- `Set 1` → `Breakout Elite` (2A/2B, RS>0, tight EMA10, top ATRE)
- `Set 2` → `Breakout Standard` (2A/2B/2C, relaxed criteria)
- `Set 3` → `Early Base` (1B/2A/2B, pattern forming)
- `Set 4` → `Speculative` (1A/1B, early stage)
- `Short Set 1` → `Breakdown Elite` (4A/4B, RS<0)
- `Short Set 2` → `Breakdown Standard` (3B/4A/4B/4C)

Rationale: "Set 1" was internal jargon with no meaning to users. New names describe the setup quality. Constants renamed (TIER_SET_1 → TIER_BREAKOUT_ELITE).

### D4 — AgentChat persistence (2026-03-28)

Conversations now persist to PostgreSQL via `agent_messages` table instead of Redis-only. Redis remains as a 7-day TTL cache for performance. Fallback: if Redis key expires, load from DB.

Migration: `0012_add_agent_messages.py`
Retention: Indefinite (matches session list behavior). Archive strategy TBD.

### D5 — Auto-backtest on strategy change (2026-03-28)

Added `_trigger_auto_backtest()` hook to strategy create/update endpoints. Fire-and-forget: queues `trigger_auto_backtest_on_change` task without blocking the API response. Only triggers when `config` (rules) changes.

### D42 — IBKR Gateway Settings Persistence (2026-03-28)

**Decision**: Use TWS_SETTINGS_PATH + volume mount for Gateway settings persistence.

**Context**: Gateway's jts.ini was defaulting to LocalServerPort=4000 but the `ghcr.io/extrange/ibkr:stable` image's socat forwards to 4001 (live) / 4002 (paper). Without persistence, settings reset on every container restart.

**Solution**:

- Added `TWS_SETTINGS_PATH=/settings` env var
- Added `ibkr-settings` named volume mounted at `/settings`
- Added `IBC_AcceptIncomingConnectionAction=accept` for auto-accept API clients
- Added portfolio_sync health dimension to auto-ops monitoring

### D43 — HMAC-SHA256 Webhook Signing + Approve/Reject Hardening (2026-03-30)

**Decision**: Replace plain `X-Webhook-Secret` header with HMAC-SHA256 body signing. Remove `approver_user_id`/`rejector_user_id` from approve/reject endpoints.

**Context**: Go-live audit (S3) flagged that approve/reject accepting arbitrary user IDs is a cross-user risk with a compromised API key. Webhook auth was plain shared secret comparison — insufficient for payload integrity verification.

**Changes**:
- `webhook_client.py`: Serializes JSON, computes `hmac.new(secret, body, sha256)`, sends `X-Webhook-Signature: sha256=<hex>`
- `brain_tools.py`: `ApproveTradeBody` and `RejectTradeBody` no longer accept user IDs; routes bind to `BRAIN_TOOLS_USER_ID`
- Brain side: `webhooks.py` verifies HMAC over raw request body (parallel PR in Paperwork repo)

**Alternatives**: Plain shared secret (rejected — no payload integrity), OAuth/JWT (overkill for M2M webhook).

**Reversible**: Yes (can fall back to plain secret by reverting both repos).

### D2 — Regime as hard gate (2026-03-23)

6 daily inputs → composite score → R1-R5:
- VIX spot, VIX3M/VIX, VVIX/VIX
- NH-NL ratio
- % above 200D, % above 50D

All position sizing, scan access, entry timing, and exit acceleration inherit current Regime. Not advisory — mandatory.

---

## Resolved Issues

These were flagged, investigated, and closed:

| ID | Issue | Resolution |
|----|-------|------------|
| D5 | Celery 360s global limit kills long tasks | Raised defaults to 3500s/3600s, explicit per-task limits |
| D6 | Dual order paths will drift | OrderService merged into OrderManager |
| D7 | `get_portfolio_user` falls back to `User.first()` | Now requires JWT via `get_current_user` |
| D8 | RSI uses SMA not Wilder | False alarm — already uses Wilder smoothing |
| D12 | React Query v3 is legacy | Migrated to TanStack Query v5 |
| D19 | MarketDashboard.tsx 1400+ lines | Decomposed to 5-tab lazy-loaded views |
| D20 | Silent `except: pass` in indicators | Replaced with proper logging |
| D24 | Scan overlay field-name bugs | Fixed wrong column names |
| D26 | compute_daily_regime missing commit | Added session.commit() after persist_regime() |
| D27 | Intelligence tasks not registered | Added to celery_app.py include list |
| D28 | Circuit breaker banner on every page | Moved to PortfolioOverview only — no auto-trading yet, global placement was disorienting and added API polling overhead on every route |
| D29 | Snapshot history 0% on dashboard | audit_quality task queried MarketSnapshotHistory without analysis_type filter; API endpoint used it. Unified to single-path DB query in AdminHealthService.compute_audit_metrics() with 5-min Redis cache. audit_quality is now a cache-warmer only |
| D30 | Render cron jobs retired | All scheduling via Celery Beat from job_catalog.py. Render crons added cost (3 Docker builds) with no resilience benefit. RENDER_SYNC_ON_STARTUP=false |
| D31 | Auto-ops backoff used 2**n exponentiation | Replaced with explicit BACKOFF_SEQUENCE tuple (15m, 30m, 60m, 2h). No overflow risk, no off-by-one, trivially auditable |
| D32 | run_task_now bypassed approval | Was in INLINE_ONLY_AGENT_TOOLS (safe-tool path). Removed — now routes through MODERATE approval flow like other side-effect tools |
