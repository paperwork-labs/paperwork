---
owner: infra-ops
last_reviewed: 2026-04-24
doc_kind: runbook
domain: data
status: active
severity_default: yellow
---
# Runbook: Market Data Outage

> Operational procedures for the market data pipeline. **Default severity: YELLOW** — market data degradation rarely halts trading directly; escalate to RED if execution, compliance, or customer-facing data guarantees are at risk. For architecture details, see [MARKET_DATA.md](MARKET_DATA.md). For decision rationale, see [KNOWLEDGE.md](KNOWLEDGE.md).

## When this fires

- Admin Health (and `/api/v1/market-data/admin/health`) shows any composite or sub-dimension **red** (e.g. `audit`, `regime`, `stage_quality`, `picks_pipeline`, `snapshot_history`) for ≥ 5 min after a Beat cycle
- `GET /api/v1/market-data/coverage` shows daily coverage or freshness buckets outside SLA (see table below)
- `admin_coverage_backfill` / `app.tasks.market.coverage.daily_bootstrap` JobRun in **failed** or **stuck** state in Admin Jobs
- Pipeline telemetry: `daily_bootstrap` rollup shows a step with unexpected duration or error payload
- FMP: `fmp_calls_today` approaches or reaches `fmp_daily_budget` on Admin Health
- Stale materialized views: dashboard tiles for breadth/stage/sector lag known-good nightly refresh

| Metric | Warning | Critical |
|--------|---------|----------|
| Daily coverage % | < 95% | < 90% |
| FMP daily budget used | > 80% | > 95% |
| Stage unknown rate | > 5% | > 10% |
| Stale symbols (>48h) | > 10 | > 50 |

**Monitoring (normal references)**

- **Admin Health Dashboard**: provider metrics, pipeline telemetry, task runs
- **FMP bandwidth**: `fmp_calls_today` / `fmp_daily_budget` + 7-day rolling total
- **Pipeline telemetry**: `daily_bootstrap` reports per-step durations in rollup payload
- **Coverage**: `GET /api/v1/market-data/coverage` shows freshness buckets

**Normal nightly pipeline (context)**

Celery Beat runs catalog job **`admin_coverage_backfill`**, which dispatches **`app.tasks.market.coverage.daily_bootstrap`**. That single orchestration performs the full chain (see rollup `steps` in JobRun), including roughly:

1. Index constituents refresh and tracked-universe cache rebuild  
2. Daily OHLCV backfill for the tracked universe  
3. **`recompute_universe`** (JobRun label `admin_indicators_recompute_universe`) — indicators from local bars  
4. Daily regime computation, scan overlay, **`snapshot_last_n_days`** history (`admin_snapshots_history_backfill`), exit cascade, strategy evaluation  
5. **`health_check`** (task name / label `admin_coverage_refresh`) — Redis coverage snapshot  
6. **`admin_refresh_market_mvs`** (JobRun label `admin_refresh_market_mvs`) — refresh dashboard materialized views; runs after indicators and before the market audit  
7. Market audit quality + intelligence digest  

There are **no** separate catalog entries named `admin_recompute_universe` or `admin_record_daily`; those are steps inside `daily_bootstrap` unless you add explicit catalog jobs.

## Triage

Classify the incident in one shot, then jump to the matching subsection.

```bash
# Local dev — replace with your API base in prod, e.g. https://api.axiomfolio.com
curl -s "http://localhost:8000/api/v1/market-data/admin/health" | jq
```

If the JSON points at a specific red dimension → see **### Failure-mode playbook (by health dimension)** below. If coverage is the symptom → **### Troubleshooting**. If FMP budget is the bottleneck → **### Tier switching** and **FMP budget** under Troubleshooting. If jobs hang → **Celery task stuck** and **### Two-worker operations (v1)**.

### Tier switching

All provider budgets, rate limits, and concurrency are controlled by a single env var: `MARKET_PROVIDER_POLICY`.

**Available tiers**

| Tier | FMP Daily | FMP CPM | Backfill Concurrency | Deep Backfill |
|------|-----------|---------|---------------------|---------------|
| `free` | 200 | 250 | 5 | No |
| `starter` | 3,000 | 280 | 25 | No |
| `paid` | 100,000 | 700 | 50 | No |
| `unlimited` | 999,999 | 2,800 | 100 | Yes |

**How to switch**

1. **Render (prod)**: Change `MARKET_PROVIDER_POLICY` on both API and Worker services
2. **Local (dev)**: Edit `infra/env.dev` → `MARKET_PROVIDER_POLICY=starter`
3. Deploy / restart services
4. Verify: Admin Health Dashboard shows `policy_tier: <new tier>`
5. No code changes required

**Downgrade considerations**

- All existing data stays in the DB — no data loss on tier downgrade
- Daily maintenance needs ~50-100 FMP calls/day, works at any paid tier
- On `free` tier: yfinance becomes effective primary; FMP reserved for high-priority symbols

### Local backfill (dev only)

**Initial setup (fresh DB)**

```bash
make up                    # Start dev stack
make migrate-up            # Apply migrations
```

**Backfill tracked universe (daily bars)**

From Admin UI:
1. Navigate to Settings → Admin → Dashboard
2. Click "Backfill Daily Coverage (Tracked)"
3. This runs: refresh constituents → update tracked → backfill last-200 bars → recompute indicators → record history

From CLI:
```bash
make task-run TASK=app.tasks.market.coverage.daily_bootstrap
```

**Deep historical backfill (10+ years)**

**WARNING: Only for local dev. Never in production.**

1. Ensure `ALLOW_DEEP_BACKFILL=true` in `infra/env.dev` (default is `false`)
2. Set `MARKET_PROVIDER_POLICY=unlimited` (or at least `paid`)
3. Run:
```bash
make task-run TASK=app.tasks.market.backfill.full_historical
```
4. Expected time at `paid` tier: ~2500 symbols at 700/min ≈ 20 min fetch + 60 min persist + 60 min indicators

### Troubleshooting

#### Coverage dropped below SLA

**Symptoms**: Dashboard shows many symbols in `>48h` or `none` freshness buckets.

**Steps**:
1. Check Admin Health → Provider Metrics for FMP budget exhaustion
2. If budget exhausted: wait for next day, or switch to higher tier
3. If budget available: run "Backfill Daily Coverage (Tracked)" from Admin
4. If specific symbols stale: run "Backfill Daily (Stale Only)"

#### FMP budget exhausted

**Symptoms**: `fmp_calls_today >= fmp_daily_budget` in Admin Health.

**Steps**:
1. Do NOT trigger more backfills — they will fail-closed
2. yfinance handles daily maintenance automatically as fallback
3. If urgent: upgrade `MARKET_PROVIDER_POLICY` temporarily
4. Budget resets at midnight UTC (Redis key: `provider:calls:{date}`)

#### Indicators show NULL/UNKNOWN

**Symptoms**: Symbols with >175 bars still show UNKNOWN stage.

**Steps**:
1. Check that symbol has sufficient bars: `GET /api/v1/market-data/admin/db/history?symbol=XXX&interval=1d`
2. If bars present: run "Recompute Indicators (Market Snapshot)" from Admin
3. If bars missing: run backfill first, then recompute
4. For systematic issues: run "Repair Stage History" under Show Advanced > Maintenance

#### Fundamentals missing (NULL sector/industry)

**Steps**:
1. Click "Fill Missing Fundamentals" under Show Advanced > Maintenance
2. Safe to re-run — idempotent
3. If FMP rate-limits, retry later

#### Celery task stuck / timed out

**Symptoms**: Admin Jobs shows task running > 2x its expected duration.

**Steps**:
1. Check Redis for job lock: `redis-cli GET job_lock:<task_name>`
2. If stale lock: the `recover_stale_job_runs` task cleans these up every 15 minutes
3. If task genuinely hung: kill the Celery worker and restart
4. Check `soft_time_limit` / `time_limit` match `job_catalog.py`

#### Redis connection errors

**Symptoms**: Warnings about Redis unreachable in logs.

**Impact**:
- Budget checks fail-closed (FMP calls skip, not unlimited)
- Dashboard cache misses (falls through to DB)
- Tracked symbols fall back to DB resolution
- Rate limiter degrades gracefully

**Steps**:
1. Check Redis health: `redis-cli ping`
2. Check connection pool: `redis-cli info clients`
3. Restart Redis if needed
4. Pipeline continues to work with DB fallback, but slower

#### Materialized views

Three MVs pre-compute dashboard aggregations nightly:

- `mv_breadth_daily` — % above SMA50/SMA200 per trading day
- `mv_stage_distribution` — stage label counts per day
- `mv_sector_performance` — sector averages from latest snapshots

**Manual refresh** (if dashboard shows stale data):

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_breadth_daily;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_stage_distribution;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sector_performance;
```

Or trigger via Celery: the `refresh_market_mvs` task in `maintenance.py`.

**If MVs don't exist** (pre-migration): the dashboard falls back to raw table queries automatically via `MarketMVService`.

### Failure-mode playbook (by health dimension)

Diagnose by which dimension is red on `/api/v1/market-data/admin/health`.

#### `audit` red — provider/quality alarms

**Symptoms**: `audit.composite_status = critical`; provider drift flagged.

**Steps**:
1. Open `/api/v1/market-data/admin/health` — note which provider is in drift and any provider-specific error details returned by the endpoint
2. Inspect provider call counters in Redis under `provider:calls:{YYYY-MM-DD}` for the day in question. (`ProviderDriftReport` and a dedicated `provider_calls` audit table are **planned** as part of the World-Class drift detector; until then Redis + Render logs are the source of truth.)
3. If single provider: `ProviderRouter` should auto-failover; verify by tailing worker logs for `ProviderRouter` failover entries
4. If multiple providers diverge from each other: a market-wide event likely (vendor outage). Wait + watch
5. If sustained >2h: open incident ticket; consider switching `MARKET_PROVIDER_POLICY` tier or pinning to single trusted provider

#### `regime` red — regime stale or wrong

**Symptoms**: `regime.last_run > 36h ago`; or regime score differs wildly from VIX-implied.

**Steps**:
1. Confirm `compute_daily_regime` is scheduled in `job_catalog.py` with cron `'20 3 * * *'` (added Phase 0; was missing pre-fix)
2. Check VIX/VVIX/VIX3M data freshness on `/market-data/regime` endpoint
3. If breadth inputs (NH-NL, %above50D/200D) are zero, root cause is upstream OHLCV gap — fix that first
4. Manual recompute: from System Status → Operator Actions → "Recompute Daily Regime"
5. If still wrong: check `RegimeEngine.compute()` against `Stage_Analysis.docx` — half-up rounding (D52), 6-input scoring

#### `stage_quality` red — high unknown rate or monotonicity violations

**Symptoms**: `stage_quality.unknown_rate > 5%` or `monotonicity_violations > 100`.

**Steps**:
1. **Unknown rate high**: usually means insufficient bars (>175 needed for SMA150 + slope + warmup, see D50). Check `tracked_symbols_with_source` for symbols with <175 bars; backfill OHLCV first
2. **Monotonicity violations**: stage label changed by more than 1 sub-stage between adjacent days, indicating noisy classification. Run `repair_stage_history` on heavy worker queue. Pre-Phase-0 this would die at 30s statement timeout (R39); post-Phase-0 the index `ix_market_snapshot_history_symbol_btree` + query rewrite resolves
3. Verify Wilder smoothing on ATR/ADX (D46) and bar guard 175 (D50) are applied

#### `picks_pipeline` red (v1) — picks ingestion or publish broken

**Symptoms**: drafts stuck in `DRAFT` >24h; inbound webhook 4xx/5xx; LLM cost spiking.

**Steps**:
1. Check inbound webhook signature: `PICKS_INBOUND_SECRET` env var matches Postmark/Resend config
2. Verify sender in `PICKS_TRUSTED_SENDERS` allowlist; reject silently if not (security)
3. Check LLM gateway circuit breaker status (`/admin/llm-gateway/status`); if open, OpenAI is degraded — pause vision calls first (most expensive)
4. Verify per-tier LLM budgets aren't exceeded (D87); degraded tier shows "feature unavailable this month" instead of failing
5. Check validator queue UI — drafts may be stuck waiting for human approval; ping Twisted Slice if SLA missed
6. Verify webhook to subscribers fires on `PUBLISHED` transition; check `notification_delivery_log` table

#### `snapshot_history` red — coverage gap

**Symptoms**: `snapshot_fill_pct < 95%`.

**Steps**:
1. Check `recompute_universe` structured counters in last run (Phase 0 fix) — written/skipped/errors
2. If `errors > 0`: inspect logs for the per-symbol exceptions; common cause is corrupted OHLCV or missing fundamentals
3. If `skipped_no_data > 100`: OHLCV gap upstream; run "Backfill Daily Coverage (Tracked)"
4. Diagnostic query: coverage for second-most-recent `as_of_date` — should be >98% for a healthy nightly
5. If genuine gap: run `safe_recompute` with `since_date` set to gap start (no FMP cost)

### Deep indicator recompute (snapshot history gap fill)

When new symbols are added to the tracked universe but lack historical indicator
data (OHLCV exists but `market_snapshot_history` rows are missing), run a deep
recompute. This is a **local CPU task** — no API calls to FMP/Finnhub.

**When to use**

- Coverage strip shows < 100% snapshot fill on older days
- New symbols were added to index constituents but historical indicators were
  never back-computed

**Procedure — local dev**

```bash
# 1. Clear any stale lock from a prior run
docker exec backend python -c "
import redis, os
r = redis.from_url(os.environ.get('REDIS_URL', 'redis://redis:6379/0'))
r.delete('lock:admin_recompute_since_date:admin_recompute_since_date')
print('Lock cleared')
"

# 2. Dispatch the recompute task
docker exec backend python -c "
from app.tasks.market.backfill import safe_recompute
result = safe_recompute.delay(since_date='1993-01-01')
print(f'Task ID: {result.id}')
"

# 3. Monitor progress (runs 30–90 min depending on symbol count)
docker logs -f celery-worker 2>&1 | grep -E 'recompute|snapshot_last_n'
```

**Procedure — production (Render)**

Do **not** use **"Backfill Full Flow (since date)"** for this — that queues `full_historical`, which downloads OHLCV from FMP first. For snapshot-history gaps when daily bars already exist in Postgres, use **`safe_recompute`** only.

Option A — via Admin UI:
1. Navigate to **System Status** → **Operator Actions** → **Advanced Controls** → **Backfill**
2. Set **Since date** to `1993-01-01` (or your desired floor)
3. Click **"Rebuild indicators + snapshot history (DB only, since date)"**

Option B — via Render Shell (worker or API service; same Redis broker):
```bash
render shell --service axiomfolio-worker

python -c "
from app.tasks.market.backfill import safe_recompute
result = safe_recompute.delay(since_date='1993-01-01')
print(f'Task ID: {result.id}')
"
```

Option C — via API (no `confirm_bandwidth`; does not call FMP for bulk daily download):
```bash
curl -X POST "https://api.axiomfolio.com/api/v1/market-data/admin/recompute/since-date?since_date=1993-01-01" \
  -H "Authorization: Bearer $TOKEN"
```

**What it does**

1. `recompute_universe(force=True)` — refreshes `market_snapshot` from local `price_data`
2. `snapshot_last_n_days(days=RECOMPUTE_HISTORY_MAX_DAYS, since_date=...)` — rebuilds `market_snapshot_history` from DB OHLCV
3. `health_check()` — refreshes coverage metrics

If **daily bars** are missing for symbols or dates, run **"Backfill Daily Coverage (Tracked)"**, **"Backfill Daily Bars (since)"** (with bandwidth confirm), or **"Backfill Full Flow (since date)"** first, then run **`safe_recompute`** again.

**Duration**

- Local: 30–90 minutes (depends on CPU and DB performance)
- Production: often 30–120+ minutes for a full universe; the Celery task allows up to **6 hours** hard limit. A **Pro** worker (4 GB RAM) reduces OOM risk versus Standard (2 GB) during `snapshot_last_n_days`.

### Two-worker operations (v1)

After Phase 0 stabilization (see [`docs/plans/MASTER_PLAN_2026.md`](plans/MASTER_PLAN_2026.md)), Celery runs as **two workers** on Render:

| Service | Queue(s) | Concurrency | Max-mem-per-child | Purpose |
|---------|----------|-------------|-------------------|---------|
| `axiomfolio-worker` (`--beat`) | `celery`, `account_sync`, `orders` | 2 | 750000 KiB | Beat scheduler, dashboard warming, account sync, order processing, exit cascade evaluation |
| `axiomfolio-worker-heavy` | `heavy` | 1 | 1500000 KiB | `repair_stage_history`, `fundamentals.fill_missing`, `snapshot_history.*`, `full_historical`, `prune_old_bars` |

**Routing rules (`app/tasks/celery_app.py`)**

> **Target state after Phase 0 PR #317 merges.** Until that PR ships, `celery_app.py` declares only `celery` / `account_sync` / `orders` and the `heavy` queue is **not yet defined**. Always consult the actual file in `app/tasks/celery_app.py` for the authoritative routing list.

```python
task_routes = {
    "app.tasks.market.indicators.repair_stage_history": {"queue": "heavy"},
    "app.tasks.market.fundamentals.fill_missing": {"queue": "heavy"},
    "app.tasks.market.snapshots.snapshot_last_n_days": {"queue": "heavy"},
    "app.tasks.market.backfill.full_historical": {"queue": "heavy"},
    "app.tasks.market.maintenance.prune_old_bars": {"queue": "heavy"},
    "app.tasks.account_sync.*": {"queue": "account_sync"},
    "app.tasks.execution.*": {"queue": "orders"},
}
```

**When the heavy worker is busy**

Pipeline DAG surfaces `RunStatus.WAITING` (Phase 0 fix): the API does **not** error if a task can't start within 120s; it polls Celery `inspect()` and returns `waiting` with `current_task` + age until either the worker becomes reachable or 900s elapse. Frontend renders amber instead of red.

**Memory tuning rationale**

- `--max-memory-per-child` is set to ~50% of the Render Standard 2 GiB ceiling so Celery recycles workers before kernel OOM (D76)
- Fast worker at 750000 KiB allows two child processes to fit comfortably
- Heavy worker at 1500000 KiB allows the indicator recompute over 2,500 symbols to complete in a single child without recycling mid-task

## Verification

**Post-backfill (local dev)**

```bash
# Check coverage
curl -s localhost:8000/api/v1/market-data/coverage | jq '.daily.coverage.pct'
# Should be > 98%

# Check stage quality
curl -s localhost:8000/api/v1/market-data/admin/health | jq '.stage_quality'
# unknown_rate should be < 5%
```

**After `safe_recompute` or deep gap fill (DB)**

```sql
SELECT as_of_date, COUNT(DISTINCT symbol)
FROM market_snapshot_history
WHERE analysis_type = 'technical_snapshot'
GROUP BY as_of_date
ORDER BY as_of_date
LIMIT 10;
```

After completion, check the coverage strip on System Status. All days should show 100% snapshot fill.

**Verifying both Celery workers are healthy**

```bash
# In each worker shell:
celery -A app.tasks.celery_app inspect active_queues
celery -A app.tasks.celery_app inspect active
celery -A app.tasks.celery_app inspect stats
```

### Invariants checklist (pre-release)

Run this checklist before any release touching market data code:

- [ ] Every FMP call has `provider_rate_limiter.acquire("fmp")` before it
- [ ] Every FMP call has `_record_provider_call("fmp")` after it
- [ ] Budget check in `get_historical_data` fails-closed (skips provider on Redis error)
- [ ] No `except Exception: pass` — all exceptions logged with context
- [ ] Celery `soft_time_limit` / `time_limit` match `job_catalog.py` `timeout_s`
- [ ] `ALLOW_DEEP_BACKFILL` is `false` in prod env files
- [ ] All indicator computation goes through `indicator_engine.py`
- [ ] No hardcoded budgets or rate limits — all from `settings.provider_policy`
- [ ] New server-side endpoints for any large data display (no client-side 5000-row fetches)
- [ ] Dashboard cache key includes universe variant

_TODO: document automated production smoke (curl `https://api.axiomfolio.com/.../health` in CI or Beat probe) if not already covered by deploy checks._

## Rollback

**Tier / bandwidth (config)**

- Revert `MARKET_PROVIDER_POLICY` to the previous value on both API and Worker (Render) or `infra/env.dev` locally; redeploy / restart
- All historical data remains on downgrade — no re-backfill needed (see **Downgrade considerations** under Triage)

**Kill switch: stop all FMP calls**

```bash
# Option 1: Exhaust budget via Redis hash (immediate, no deploy)
redis-cli HSET "provider:calls:$(date -u +%Y-%m-%d)" fmp 999999

# Option 2: Switch to free tier (deploys required)
# Set MARKET_PROVIDER_POLICY=free in Render
```

**Kill switch: stop all backfills**

- Pause all backfill-related schedules in Admin > Schedules
- Or set `ALLOW_DEEP_BACKFILL=false` (should already be false in prod)

**Bandwidth emergency (FMP approaching plan limits)**

1. Check current 30-day rolling usage in FMP account dashboard
2. Set `MARKET_PROVIDER_POLICY=free` temporarily to cap at 200/day
3. Once bandwidth resets, switch back to appropriate tier
4. All historical data remains — no re-backfill needed

**Code regression**

- `git revert <sha>` if a deploy caused the outage and you need to back out; restore previous deploy via Render dashboard → Service → Deploys → previous → "Redeploy" if that is the team’s standard.
- _TODO: document Vercel env rollback steps if any market-data Admin UI is served from Vercel._

## Escalation

- **Primary on-call / ops channel**: use the team’s incidents or ops Slack channel (e.g. `#ops`) and DM the infra/market-data owner. _TODO: document canonical channel + `@` handle for axiomfolio market data._
- **Sustained multi-provider drift or vendor outage** (`audit` red >2h with no failover relief): open an incident ticket; link Redis keys and `provider:calls` evidence; _TODO: document FMP (and other provider) support portal URLs_.
- **Picks pipeline** (human/validator SLA): ping **Twisted Slice** if drafts exceed SLA under **### `picks_pipeline` red** in Triage.
- **Page / RED**: if customer-facing or execution guarantees are broken (not the default for pure market data lag), follow the org’s incident commander / PagerDuty process — _TODO: document schedule name_.

## Post-incident

- Add a row to `docs/KNOWLEDGE.md` (or the product’s KNOWLEDGE section) under "Recent incidents" with the pattern and the Triage subsection that fixed it
- If a new guardrail emerged, file a `.cursor/rules/*.mdc` update PR
- If this runbook was wrong or incomplete, update it and bump `last_reviewed` before closing the ticket
- _TODO: document Linear / sprint log location for axiomfolio incidents if used_
