# Market Data Ingest and Storage Strategy

## Goals
- Centralize market data access via `backend/services/market/market_data_service.py`
- Provide reliable indicators for last 200 trading days for: SPY, NASDAQ 100, Dow 30, and all held symbols (Russell 2000 roadmap)
- Persist lightweight, query-friendly snapshots when needed; avoid over-storing raw API payloads
- Schedule refreshes and cache to keep API usage efficient

## Scope and Sources
- OHLCV only from providers; ALL indicators computed locally from stored OHLCV
- Provider priority (paid mode): FMP → Twelve Data → yfinance; (free mode): Finnhub → Twelve Data → yfinance
- Redis cache for transient responses and computed indicators

## Environment configuration (dev)

- **Run dev via Makefile only**: `make up` (or `./run.sh start`) uses `docker compose --env-file infra/env.dev ...` and injects `infra/env.dev` into backend/celery containers.
- **Source of truth**: put all dev secrets (FMP/Finnhub keys, Discord webhooks, etc.) into **`infra/env.dev`** (gitignored).
- **Do not rely on root `.env`**: backend settings no longer implicitly load a repo-root `.env`. If you truly need an env file outside Docker, set `QM_ENV_FILE=/path/to/file`.
- **Frontend safety**: the `frontend` and `ladle` containers do **not** receive `infra/env.dev` (to avoid leaking secrets). Only `VITE_*` variables explicitly passed in compose are available to the browser build.

## Data We Compute/Serve (indicator_engine)
For each symbol:
- RSI(14)
- SMA(5/8/21/20/50/100/200), EMA(10/8/21/200)
- ATR(14), ATR percent, ATR distance to SMA50
- ADX(14), DI+, DI-
- MACD(12,26,9), signal line
- Performance: 1d, 3d, 5d, 20d, 60d, 120d, 252d, MTD, QTD, YTD
- MA alignment flags, MA bucket (LEADING/LAGGING/NEUTRAL)
- Classification: sector, industry, sub-industry (best-effort)

Responsibilities by layer
-------------------------
- indicator_engine.py: Pure computations from OHLCV (SMA/EMA/RSI/ATR/MACD/ADX, perf windows, MA bucket, TD/gaps/trendlines, weekly stage helpers).
- market_data_service.py: Provider access (prices/history/info), Redis caching, DB snapshot assembly from local `price_data`, enrichment (chart metrics + fundamentals), and persistence to `MarketAnalysisCache`.
- market_data_tasks.py: Orchestration only. Builds tracked sets, backfills OHLCV, invokes service to build/enrich/persist snapshots, and records daily history.

## Persistence Model
- `market_data.PriceData`: daily/intraday OHLCV with unique `(symbol, date, interval)` (constraint: `uq_symbol_date_interval`)
- `market_data.MarketAnalysisCache`: compact latest technical snapshot per symbol with expiry (`expiry_timestamp`), including `ma_bucket`
  - Includes persisted stage fields: `stage_label`, `stage_slope_pct`, `stage_dist_pct`
- `market_data.MarketAnalysisHistory`: immutable daily snapshots keyed by `(symbol, analysis_type, as_of_date)`

## Scheduling
- Weekly constituents refresh (SP500, NASDAQ100, DOW30) → table `index_constituents`
- Nightly tracked-universe cache build (Redis: `tracked:all`, `tracked:new`)
- Nightly backfill for newly tracked symbols only (reads `tracked:new`)
- Nightly delta backfill safety for portfolio symbols (last-200)
- Nightly recompute indicators for full universe (from local `price_data`)
- Nightly history recording (`market_analysis_history`)
- Hourly coverage-health snapshot (`monitor_coverage_health`) caches freshness buckets + stale symbol lists in Redis so Admin → Coverage can render SLAs instantly and alert on drift.

Paid mode operations
--------------------
- Ensure provider policy is set to paid (default): `MARKET_PROVIDER_POLICY=paid`
- Configure API keys in `.env`: `FMP_API_KEY`, `TWELVE_DATA_API_KEY`, `FINNHUB_API_KEY`
- To force ingestion now (admin flow):
  - Refresh constituents: POST `/api/v1/market-data/admin/backfill/index?index=SP500`
  - Backfill index OHLCV: POST `/api/v1/market-data/admin/backfill/index` (SP500/NASDAQ100/DOW30)
  - Refresh portfolio indicators: Celery task `refresh_portfolio_indicators`
  - Refresh index indicators: POST `/api/v1/market-data/admin/indicators/refresh-index`
  - Record history: POST `/api/v1/market-data/admin/history/record`
  - Compute chart metrics for an index: scheduled via Celery (`chart-metrics-sp500`) or call task `compute_chart_metrics_index`
  - Compute chart metrics for the universe: scheduled via Celery 

Notes on retention
------------------
- Default OHLCV backfill keeps ~270 recent daily bars to support SMA(200) and 252d windows quickly.
- For deeper history, call provider directly via service or extend tasks to multi-year fetch using FMP `historical_price_full`.

## API Contracts
- `GET /api/v1/market/prices?symbol=SPY&range=200d&interval=1d`: returns OHLCV
- `GET /api/v1/market/atr?symbol=SPY`: ATR and volatility regime
- `GET /api/v1/market/ta?symbol=SPY`: RSI, MAs, MACD, ADX, performance windows

## Index Constituents
- `backend/services/market/index_constituents_service.py` fetches SP500, NASDAQ100, DOW30 (R2K roadmap)
- Persisted in DB: `backend/models/index_constituent.py` with `is_active`, `first_seen_at`, `became_inactive_at`
- We do not drop symbols that leave an index; they are marked inactive and remain tracked

## Notes
- Provider selection is adaptive; when keys exist, paid providers take precedence
- Avoid duplicating raw provider payloads; store normalized OHLCV + compact snapshots

## End-to-End Indicator Pipeline
1) Fetch historical data
   - Source order: FMP → Twelve Data → yfinance (fallbacks) with adaptive rate limiting (free mode uses Finnhub first)
   - Cached in Redis per `(symbol, period, interval)`
2) Compute indicators (indicator_engine)
   - Core set: RSI, ATR, SMA/EMA, MACD+signal, ADX/DI, performance windows, MA alignment, ATR-matrix metrics
3) Build snapshot
   - Prefer local DB: `MarketDataService.build_snapshot_from_db_prices(db, symbol)`
   - Fallback: `MarketDataService.build_indicator_snapshot(symbol)` (pull OHLCV then compute)
   - Enrich: `MarketDataService.enrich_chart_metrics_and_fundamentals(db, symbol, snapshot)` adds TD/gaps/trendlines + best-effort sector/industry/market_cap
4) Persist snapshot
   - `MarketDataService.persist_snapshot(db, symbol, snapshot)` upserts latest into `MarketAnalysisCache` and stores `raw_analysis`
5) History recording (optional)
   - `record_daily_history` writes one row per `(symbol, as_of_date)` into `MarketAnalysisHistory` with headline fields + full payload
6) Scheduling
   - Celery Beat triggers:
     - nightly guided daily restore → `bootstrap_daily_coverage_tracked`
     - hourly coverage cache refresh → `monitor_coverage_health`
     - nightly 5m backfill → `backfill_5m_last_n_days`
     - retention enforcement (5m) → `enforce_price_data_retention`

## Intraday (5m) Backfill and Retention
- Persist 5m bars for tracked symbols (default lookback: 5–30 days)
- Providers: FMP `historical_chart(5min)` → Twelve Data 5min → yfinance 5m
- Retain last 90 days of 5m data by default; enforce via scheduled retention task

## Admin Area (RBAC: admin)
- Dashboard: freshness KPIs, last task statuses, quick actions (tracked update, backfills, recompute, record history, coverage monitor)
- Jobs: view recent `job_run` rows with durations, counters, errors, and drill-in modal for params/counters/logs
- Schedules: full CRUD via RedBeat with cron preview, queue/priority routing, maintenance windows, preflight hooks, export/import, pause/resume, and run-now controls (see “Scheduler Metadata & Export/Import” below)
- Coverage: daily and 5m coverage summary, stale (>48h) lists, missing 5m table, education/hints, one-click schedule for coverage monitor
- Tracked: view `tracked:all` and `tracked:new` (Redis), optional columns (price, ATR, stage, market cap, sector), quick actions to refresh/update/backfill

## API Additions
- `GET /api/v1/market-data/db/history?symbol=SPY&interval=1d|5m&start&end&limit`
- `GET /api/v1/market-data/coverage` and `/coverage/{symbol}`
- `POST /api/v1/market-data/backfill/5m?n_days=5&batch_size=50` (admin)
- `POST /api/v1/market-data/retention/enforce?max_days_5m=90` (admin)
- `GET /api/v1/market-data/admin/jobs` (admin)
- `GET /api/v1/market-data/admin/tasks` and `POST /api/v1/market-data/admin/tasks/run` (limited set; admin)
- `GET /api/v1/admin/schedules` / `POST|PUT|DELETE /admin/schedules` / `POST /admin/schedules/import|export|pause|resume|run-now|preview` – dynamic RedBeat management with queue routing, metadata, and import/export workflows

## Coverage & Freshness (SLA)

- `GET /api/v1/market-data/coverage` returns:
  - symbols: distinct symbols in `price_data`
  - tracked_count: Redis `tracked:all` size
  - indices: active member counts (SP500, NASDAQ100, DOW30)
  - daily/m5: { count, last: {symbol->iso ts}, freshness buckets: {"<=24h","24-48h",">48h","none"} }
- SLA guidance:
  - Daily coverage ≥ 90% of symbols
  - No symbols in >48h bucket under normal operation
  - 5m coverage present for D‑1 during market days

## Universe Bootstrap Runbook

This runbook has been replaced by the guided operator flow below (“Restore Daily Coverage (Tracked)”),
which encapsulates the daily restore chain without exposing redundant backfill endpoints.

Troubleshooting:
- If Refresh fetched 0 members: check provider reachability; FMP quota; Wikipedia blocked; rerun.
- If freshness shows many >48h: run Backfill Daily, Recompute, then Record History.
- If 5m coverage is 0 after market opens: run Backfill 5m (D‑1).

## Index Refresh Observability

- Provider strategy: FMP-first, Wikipedia fallback (HTML tables)
- JobRun.counters per index include: fetched, inserted, reactivated, inactivated, provider_used, fallback_used
- Redis meta: `index_constituents:{INDEX}:meta` stores {provider_used, fallback_used, count} for 24h

## Scheduler Metadata & Export/Import

- `ScheduleMetadata` is persisted per RedBeat entry (`redbeat:meta:{name}`) and includes:
  - `queue` / `priority` → passed into Celery `apply_async` for routing and QoS
  - `dependencies`, `maintenance_windows`, `preflight_checks`, `safety` (single-flight, max concurrency, timeout, retry/backoff), `hooks` (Discord webhooks, Prometheus endpoints), audit fields (`created_by/at`, `updated_by/at`)
- API payloads accept a `metadata` object (`ScheduleMetadataPatch`) on create/update/import; Admin UI surfaces editable fields alongside cron/args.
- Pausing a schedule snapshots args/kwargs/metadata to `redbeat:paused:{name}`; resuming requires cron but restores the saved metadata automatically.
- Export returns an array of schedules (name/task/cron/tz/args/kwargs/metadata) that can be versioned in git; import replays that list with audit stamping.
- Catalog seeding writes metadata defaults for every template (e.g., `account_sync` jobs route to their queue, market-data jobs enforce single-flight + timeouts) so new environments get consistent guard rails without hand editing Redis.

### Scheduler Alerts & Prometheus Hooks

- `hooks.discord_webhook` accepts either a full webhook URL or an alias (`system_status`, `signals`, `portfolio`, `morning_brew`, `playground`). Multiple targets can be supplied via comma-delimited values.
- Event types emitted by `task_run`:
  - `failure` (default) when task raises.
  - `slow` when runtime exceeds `metadata.safety.timeout_s`.
  - `success` when runs complete (opt-in by including `"success"` in `alert_on`).
- Discord alerts render embeds with job id, duration, queue, counters, and any error snippet to the configured channels.
- `hooks.prometheus_endpoint` can point to a Pushgateway-compatible URL. Each run writes `axiomfolio_task_duration_seconds{task="...",event="...",queue="..."} <value>` so Grafana/Prometheus alerting rules can detect spikes.
- If no per-job hook is configured, failures still emit to the global `DISCORD_WEBHOOK_SYSTEM_STATUS` endpoint (when set) so regressions cannot go unnoticed.
- Admin Schedules UI surfaces these fields under “Alerts & Observability,” allowing operators to wire Discord aliases, comma-separated channel lists, Prometheus endpoints, and opt-in events (slow/success) without touching Redis exports.

## Coverage Health Monitor

- Celery task `monitor_coverage_health` runs hourly (Admin schedule) and caches:
  - `generated_at`, total tracked symbols, index member counts
  - Daily + 5m coverage counts, freshness buckets, stale lists (first 50 symbols per bucket)
  - Status summary (`ok` / `degraded`) plus tracked symbols
- Redis key `coverage:health:last` feeds Admin Dashboard/Coverage quick actions and SLA banners, enabling Discord/alert hooks to detect drift without hitting Postgres every refresh.

### Manual refresh / UI behavior

- **Admin Dashboard “Refresh coverage now”** calls `POST /api/v1/market-data/admin/coverage/refresh` which enqueues `monitor_coverage_health`.
- **Auto-refresh**: Admin Dashboard will auto-trigger a refresh when the cached snapshot is missing or older than ~15 minutes, but still renders immediately using the current response.
- **Cache vs DB**: `GET /api/v1/market-data/coverage` returns `meta.source` (`cache` or `db`) and `meta.updated_at` so you can see whether you’re looking at the last monitor run or a direct DB fallback.

## Operator Runbook (recommended)

### Goal: restore Daily coverage to green (tracked universe)

- **Use this when**: Coverage shows `>48h` or `none` buckets, or Daily % drops.\n
- **Primary button** (Settings → Admin → Dashboard): **Restore Daily Coverage (Tracked)**\n
  - Enqueues: `bootstrap_daily_coverage_tracked`\n
  - What it does (no 5m): refresh constituents → update tracked → backfill last-200 daily bars (tracked) → recompute indicators → record history → refresh coverage cache.\n

### Fast fix: stale-only backfill

- **Use this when**: Only a subset of symbols are stale.\n
- Click **Backfill Daily (Stale Only)**\n
  - Calls: `POST /api/v1/market-data/admin/coverage/backfill-stale-daily` then refreshes coverage.\n

### Advanced: index-only vs tracked-universe

Legacy per-universe daily backfill endpoints were removed to keep the operator surface area minimal.
