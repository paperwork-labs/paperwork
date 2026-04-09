# Market Data Runbook

Operational procedures for the market data pipeline. For architecture details, see [MARKET_DATA.md](MARKET_DATA.md). For decision rationale, see [KNOWLEDGE.md](KNOWLEDGE.md).

---

## Table of Contents

- [Tier Switching](#tier-switching)
- [Local Backfill (Dev Only)](#local-backfill-dev-only)
- [Production Daily Operations](#production-daily-operations)
- [Troubleshooting](#troubleshooting)
- [Invariants Checklist](#invariants-checklist)
- [Emergency Procedures](#emergency-procedures)

---

## Tier Switching

All provider budgets, rate limits, and concurrency are controlled by a single env var: `MARKET_PROVIDER_POLICY`.

### Available Tiers

| Tier | FMP Daily | FMP CPM | Backfill Concurrency | Deep Backfill |
|------|-----------|---------|---------------------|---------------|
| `free` | 200 | 250 | 5 | No |
| `starter` | 3,000 | 280 | 25 | No |
| `paid` | 100,000 | 700 | 50 | No |
| `unlimited` | 999,999 | 2,800 | 100 | Yes |

### How to Switch

1. **Render (prod)**: Change `MARKET_PROVIDER_POLICY` on both API and Worker services
2. **Local (dev)**: Edit `infra/env.dev` → `MARKET_PROVIDER_POLICY=starter`
3. Deploy / restart services
4. Verify: Admin Health Dashboard shows `policy_tier: <new tier>`
5. No code changes required

### Downgrade Considerations

- All existing data stays in the DB — no data loss on tier downgrade
- Daily maintenance needs ~50-100 FMP calls/day, works at any paid tier
- On `free` tier: yfinance becomes effective primary; FMP reserved for high-priority symbols

---

## Local Backfill (Dev Only)

### Initial Setup (Fresh DB)

```bash
make up                    # Start dev stack
make migrate-up            # Apply migrations
```

### Backfill Tracked Universe (Daily Bars)

From Admin UI:
1. Navigate to Settings → Admin → Dashboard
2. Click "Backfill Daily Coverage (Tracked)"
3. This runs: refresh constituents → update tracked → backfill last-200 bars → recompute indicators → record history

From CLI:
```bash
make task-run TASK=backend.tasks.market.coverage.daily_bootstrap
```

### Deep Historical Backfill (10+ Years)

**WARNING: Only for local dev. Never in production.**

1. Ensure `ALLOW_DEEP_BACKFILL=true` in `infra/env.dev` (default is `false`)
2. Set `MARKET_PROVIDER_POLICY=unlimited` (or at least `paid`)
3. Run:
```bash
make task-run TASK=backend.tasks.market.backfill.full_historical
```
4. Expected time at `paid` tier: ~2500 symbols at 700/min ≈ 20 min fetch + 60 min persist + 60 min indicators

### Post-Backfill Verification

```bash
# Check coverage
curl -s localhost:8000/api/v1/market-data/coverage | jq '.daily.coverage.pct'
# Should be > 98%

# Check stage quality
curl -s localhost:8000/api/v1/market-data/admin/health | jq '.stage_quality'
# unknown_rate should be < 5%
```

---

## Production Daily Operations

### Normal Nightly Pipeline

Celery Beat runs catalog job **`admin_coverage_backfill`**, which dispatches **`backend.tasks.market.coverage.daily_bootstrap`**. That single orchestration performs the full chain (see rollup `steps` in JobRun), including roughly:

1. Index constituents refresh and tracked-universe cache rebuild  
2. Daily OHLCV backfill for the tracked universe  
3. **`recompute_universe`** (JobRun label `admin_indicators_recompute_universe`) — indicators from local bars  
4. Daily regime computation, scan overlay, **`snapshot_last_n_days`** history (`admin_snapshots_history_backfill`), exit cascade, strategy evaluation  
5. **`health_check`** (task name / label `admin_coverage_refresh`) — Redis coverage snapshot  
6. Market audit quality + intelligence digest  

There are **no** separate catalog entries named `admin_recompute_universe` or `admin_record_daily`; those are steps inside `daily_bootstrap` unless you add explicit catalog jobs.

### Monitoring

- **Admin Health Dashboard**: Shows provider metrics, pipeline telemetry, task runs
- **FMP bandwidth**: `fmp_calls_today` / `fmp_daily_budget` + 7-day rolling total
- **Pipeline telemetry**: `daily_bootstrap` reports per-step durations in rollup payload
- **Coverage**: `GET /api/v1/market-data/coverage` shows freshness buckets

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Daily coverage % | < 95% | < 90% |
| FMP daily budget used | > 80% | > 95% |
| Stage unknown rate | > 5% | > 10% |
| Stale symbols (>48h) | > 10 | > 50 |

---

## Troubleshooting

### Coverage Dropped Below SLA

**Symptoms**: Dashboard shows many symbols in `>48h` or `none` freshness buckets.

**Steps**:
1. Check Admin Health → Provider Metrics for FMP budget exhaustion
2. If budget exhausted: wait for next day, or switch to higher tier
3. If budget available: run "Backfill Daily Coverage (Tracked)" from Admin
4. If specific symbols stale: run "Backfill Daily (Stale Only)"

### FMP Budget Exhausted

**Symptoms**: `fmp_calls_today >= fmp_daily_budget` in Admin Health.

**Steps**:
1. Do NOT trigger more backfills — they will fail-closed
2. yfinance handles daily maintenance automatically as fallback
3. If urgent: upgrade `MARKET_PROVIDER_POLICY` temporarily
4. Budget resets at midnight UTC (Redis key: `provider:calls:{date}`)

### Indicators Show NULL/UNKNOWN

**Symptoms**: Symbols with >175 bars still show UNKNOWN stage.

**Steps**:
1. Check that symbol has sufficient bars: `GET /api/v1/market-data/admin/db/history?symbol=XXX&interval=1d`
2. If bars present: run "Recompute Indicators (Market Snapshot)" from Admin
3. If bars missing: run backfill first, then recompute
4. For systematic issues: run "Repair Stage History" under Show Advanced > Maintenance

### Fundamentals Missing (NULL sector/industry)

**Steps**:
1. Click "Fill Missing Fundamentals" under Show Advanced > Maintenance
2. Safe to re-run — idempotent
3. If FMP rate-limits, retry later

### Celery Task Stuck / Timed Out

**Symptoms**: Admin Jobs shows task running > 2x its expected duration.

**Steps**:
1. Check Redis for job lock: `redis-cli GET job_lock:<task_name>`
2. If stale lock: the `recover_stale_job_runs` task cleans these up every 15 minutes
3. If task genuinely hung: kill the Celery worker and restart
4. Check `soft_time_limit` / `time_limit` match `job_catalog.py`

### Redis Connection Errors

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

---

## Invariants Checklist

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

---

## Emergency Procedures

### Kill Switch: Stop All FMP Calls

```bash
# Option 1: Exhaust budget via Redis hash (immediate, no deploy)
redis-cli HSET "provider:calls:$(date -u +%Y-%m-%d)" fmp 999999

# Option 2: Switch to free tier (deploys required)
# Set MARKET_PROVIDER_POLICY=free in Render
```

### Kill Switch: Stop All Backfills

```bash
# Pause all backfill-related schedules in Admin > Schedules
# Or set ALLOW_DEEP_BACKFILL=false (should already be false in prod)
```

### Bandwidth Emergency (FMP Approaching Plan Limits)

1. Check current 30-day rolling usage in FMP account dashboard
2. Set `MARKET_PROVIDER_POLICY=free` temporarily to cap at 200/day
3. Once bandwidth resets, switch back to appropriate tier
4. All historical data remains — no re-backfill needed

---

## Deep Indicator Recompute (Snapshot History Gap Fill)

When new symbols are added to the tracked universe but lack historical indicator
data (OHLCV exists but `market_snapshot_history` rows are missing), run a deep
recompute. This is a **local CPU task** — no API calls to FMP/Finnhub.

### When to Use

- Coverage strip shows < 100% snapshot fill on older days
- New symbols were added to index constituents but historical indicators were
  never back-computed

### Procedure

#### Local Dev

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
from backend.tasks.market.backfill import safe_recompute
result = safe_recompute.delay(since_date='1993-01-01')
print(f'Task ID: {result.id}')
"

# 3. Monitor progress (runs 30–90 min depending on symbol count)
docker logs -f celery-worker 2>&1 | grep -E 'recompute|snapshot_last_n'
```

#### Production (Render)

Option A — via Admin UI:
1. Navigate to System Status > Operator Actions > Advanced > Backfill
2. Set "Since date" to `1993-01-01`
3. Click "Backfill Full Flow (since date)"

Option B — via Render Shell:
```bash
# SSH into the backend service on Render
render shell --service backend

python -c "
from backend.tasks.market.backfill import safe_recompute
result = safe_recompute.delay(since_date='1993-01-01')
print(f'Task ID: {result.id}')
"
```

Option C — via API:
```bash
curl -X POST "https://api.axiomfolio.com/api/v1/market-data/admin/backfill/since-date?since_date=1993-01-01&confirm_bandwidth=true" \
  -H "Authorization: Bearer $TOKEN"
```

### What It Does

1. `recompute_universe()` — recomputes all indicators for 2,500+ symbols
2. `snapshot_last_n_days(since_date=...)` — builds `market_snapshot_history`
   rows from the recomputed indicators for every trading day since the date
3. `health_check()` — refreshes coverage metrics

### Duration

- Local: 30–90 minutes (depends on CPU and DB performance)
- Production: 15–45 minutes (Render has faster I/O)

### Verification

After completion, check the coverage strip on System Status. All days should
show 100% snapshot fill. Or query directly:

```sql
SELECT as_of_date, COUNT(DISTINCT symbol)
FROM market_snapshot_history
WHERE analysis_type = 'technical_snapshot'
GROUP BY as_of_date
ORDER BY as_of_date
LIMIT 10;
```
