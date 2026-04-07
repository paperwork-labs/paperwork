# Market Tasks

> **Canonical reference** for all `backend.tasks.market` tasks—schedules, dependencies, runbooks, and troubleshooting live here.

Celery tasks under `backend.tasks.market` drive the **Intelligence** pillar: daily and intraday price ingestion, index universes, indicator recomputation, `MarketSnapshot` / `MarketSnapshotHistory`, coverage health in Redis, regime (R1–R5), fundamentals enrichment, retention, and related maintenance.

Tasks are registered as `backend.tasks.market.<module>.<function>`. Most use the `@task_run` decorator for `JobRun` tracking, Redis status keys, single-flight locks, and failure alerts.

**Production schedules** default from [`job_catalog.py`](../job_catalog.py) and sync to Render via Admin Schedules. Dev Celery Beat only runs auto-ops on an interval; use `make task-run` to enqueue market jobs locally.

### Market data service layer

[`market_data_service.py`](../../services/market/market_data_service.py) is a **factory module** (not a class): it constructs an acyclic graph once at import and exposes **named singletons**. Tasks should import the sub-service they use instead of a monolithic handle.

```python
from backend.services.market.market_data_service import provider_router, infra, snapshot_builder
```

| Export | Type | Use for |
|--------|------|---------|
| `infra` | `MarketInfra` | Redis, provider HTTP clients, call/budget tracking, admin toggles (e.g. 5m backfill). |
| `provider_router` | `ProviderRouter` | Circuit breakers, retries, historical bars/dividends from providers. |
| `quote` | `QuoteService` | Current price resolution, fundamentals lookups. |
| `snapshot_builder` | `SnapshotBuilder` | Snapshot compute (DB/providers), persist, stage helpers, `get_snapshot_from_store`. |
| `price_bars` | `PriceBarWriter` | OHLCV persistence, daily/5m backfill (coordinates with `provider_router`). |
| `index_universe` | `IndexUniverseService` | Index constituents, aggregated tradeable symbols. |
| `coverage_analytics` | `CoverageAnalytics` | Per-interval coverage, Redis coverage health payloads. |
| `stage_quality` | `StageQualityService` | Stage-quality summaries, history repair windows. |
| `fundamentals` | `FundamentalsService` | Shared enrichment primitives (often reached via `quote` / `snapshot_builder`). |

**Legacy:** `market_data_service` (and `MarketDataService()`) still resolve to a thin facade over the same singletons for older call sites; prefer direct imports for new code.

---

## Task Modules

### `backfill`

Module: daily bar backfill, index constituents, and tracked-universe cache ([`backfill.py`](./backfill.py)).

| Task | Description | Schedule | Dependencies |
|------|-------------|----------|--------------|
| `symbol` | Delta backfill and recompute indicators for a single symbol. | On-demand | Calls `symbols([sym])`, then `snapshot_builder.compute_snapshot_from_db` + `snapshot_builder.persist_snapshot`. Per-symbol lock. |
| `symbols` | Delta backfill daily bars for a provided symbol list. | On-demand | Async `_fetch_daily_for_symbols`, `_persist_daily_fetch_results`, `daily_backfill_params`. |
| `daily_bars` | Delta backfill last *N* trading days (approx.) of daily bars for the tracked universe. | On-demand; also **step 3** inside `daily_bootstrap` | Loads tracked universe from DB; calls `symbols(list(universe), days=...)`. |
| `daily_since` | Deep backfill of daily bars since a given date for the tracked universe. | On-demand | `_get_tracked_symbols_safe`, `_fetch_daily_for_symbols` (`period="max"`), `_persist_daily_fetch_results` with `since_dt`. |
| `full_historical` | Deep backfill pipeline since a date: daily, indicators, snapshot history, coverage. | Cold start / on-demand | Runs `daily_since` → `indicators.recompute_universe` → `history.snapshot_last_n_days` → `coverage.health_check`. Global lock on `since_date`. |
| `stale_daily` | Backfill daily bars for symbols flagged stale or missing 1d coverage in the tracked universe. | **Auto-ops** (coverage dimension); on-demand | `coverage_analytics._compute_interval_coverage_for_symbols`; then `symbols(stale_symbols)`; then `coverage.health_check`. |
| `constituents` | Refresh index constituents for SP500, NASDAQ100, DOW30, RUSSELL2000 (DB + providers via `index_universe` / `infra`). | **Step 1** of `daily_bootstrap` (`0 1 * * *` UTC, job id `admin_coverage_backfill`); on-demand | FMP key preflight; `IndexConstituent` rows; optional Discord warning on low counts. |
| `tracked_cache` | Compute union of tracked symbols and publish to Redis (`tracked:all`, `tracked:new`). | **Step 2** of `daily_bootstrap`; on-demand | DB tracked universe; if empty, seeds from provider constituents and `IndexConstituent`. |

---

### `coverage`

Module: nightly coverage bootstrap, scan overlay, exit cascade hooks, and coverage health ([`coverage.py`](./coverage.py)).

| Task | Description | Schedule | Dependencies |
|------|-------------|----------|--------------|
| `daily_bootstrap` | Orchestrates daily-only pipeline: constituents → tracked cache → daily bars → full indicator recompute → regime → scan overlay → snapshot history → exit cascade (log-only) → strategy eval → coverage health → daily intelligence digest. | **`0 1 * * *` UTC** (`job_catalog`: Nightly Coverage Pipeline); **auto-ops** audit dimension uses a shorter history window | Imports `backfill.constituents`, `tracked_cache`, `daily_bars`; `indicators.recompute_universe`; `regime.compute_daily`; `history.snapshot_last_n_days`; `strategy.tasks.evaluate_strategies_task`; `intelligence.tasks.generate_daily_digest_task`; `health_check`. Stage Analysis spec steps 0–10 run inside indicator recompute / engine. |
| `health_check` | Snapshots coverage into Redis for Admin UI (`coverage:health:last`, history list). | On-demand; end of `daily_bootstrap`; **auto-ops** coverage path | `coverage_analytics.coverage_snapshot`, `compute_coverage_status`, optional 5m toggle metadata. |

---

### `history`

Module: snapshot history recording and backfill ([`history.py`](./history.py)).

| Task | Description | Schedule | Dependencies |
|------|-------------|----------|--------------|
| `snapshot_for_date` | Backfill `market_snapshot_history` for one calendar date from local `price_data` (DB-only; does not refresh latest `market_snapshot`). | On-demand | `snapshot_builder.compute_snapshot_from_db` per symbol; upsert `MarketSnapshotHistory`. |
| `snapshot_last_n_days` | Backfill `market_snapshot_history` for the last *N* SPY-calendar trading days from local DB prices (ledger / dots for history UI). | **Step** inside `daily_bootstrap` and `full_historical`; on-demand | Tracked symbols; trading-day calendar from SPY (with fallbacks); core indicators / stage series; bulk upsert `MarketSnapshotHistory`. |
| `snapshot_for_symbol` | Backfill history for one symbol over a date range using `compute_full_indicator_series`. | On-demand | `PriceData` 1d + SPY benchmark; `compute_full_indicator_series`; upsert by date. |
| `record_daily` | Persist immutable daily rows into `market_snapshot_history` from latest `MarketSnapshot` (or recompute if needed). | **Auto-ops** audit dimension; on-demand | `snapshot_builder.compute_snapshot_from_db` when needed; upsert by `as_of_date`. |

---

### `indicators`

Module: indicator recompute, stage metadata, and related maintenance ([`indicators.py`](./indicators.py)).

| Task | Description | Schedule | Dependencies |
|------|-------------|----------|--------------|
| `recompute_universe` | Recompute indicators for the tracked universe from local DB (orchestrator); persists `MarketSnapshot`. Skips symbols with snapshots newer than ~4h. | **Step** inside `daily_bootstrap`; **auto-ops** stage_quality; on-demand | May fetch benchmark daily bars if thin; `snapshot_builder.compute_snapshot_from_db` + `snapshot_builder.persist_snapshot` per symbol; clears stuck `JobRun` rows for this task. |
| `position_metadata` | Backfill `Position.sector` and `Position.market_cap` from `MarketSnapshot` where NULL. | On-demand | Open positions + snapshot join. |
| `stage_durations` | Backfill stage duration fields on `market_snapshot_history` and latest `market_snapshot`. | On-demand | `compute_stage_run_lengths`; bulk update history + per-symbol snapshot update. |
| `stage_changes` | Compare today vs yesterday stage in `market_snapshot_history` for held symbols; Discord alert on transitions. | On-demand | `MarketSnapshotHistory` + `Position` symbols. |

---

### `fundamentals`

Module: fundamentals enrichment for index rows and snapshots ([`fundamentals.py`](./fundamentals.py)).

| Task | Description | Schedule | Dependencies |
|------|-------------|----------|--------------|
| `enrich_index` | Fill sector / industry / market_cap on `IndexConstituent` using DB-first snapshots, then providers if needed. | On-demand | `snapshot_builder.get_snapshot_from_store` / `snapshot_builder.compute_snapshot_from_db` / `snapshot_builder.compute_snapshot_from_providers`; `FUNDAMENTAL_FIELDS`. |
| `fill_missing` | Fill missing fundamental/display columns on `MarketSnapshot` rows. | On-demand | `snapshot_builder.compute_snapshot_from_db`; `quote.get_fundamentals_info`; `snapshot_builder.persist_snapshot`. |
| `refresh_stale` | Re-fetch fundamentals for snapshots older than *stale_days*. | On-demand | `quote.get_fundamentals_info`; updates row + `analysis_timestamp`. |

---

### `maintenance`

Module: retention, job-run recovery, quality audit ([`maintenance.py`](./maintenance.py)).

| Task | Description | Schedule | Dependencies |
|------|-------------|----------|--------------|
| `prune_old_bars` | Delete 5m `price_data` rows older than retention window. | **`30 4 * * *` UTC** (`job_catalog`: Data Retention Cleanup) | `settings.RETENTION_MAX_DAYS_5M`; optional Discord if delete count exceeds warn threshold. |
| `recover_jobs` | Mark `JobRun` rows stuck in `running` past threshold as cancelled. | **`0 */6 * * *` UTC** (`job_catalog`); **auto-ops** jobs dimension | Updates `JobRun` with explanatory error message. |
| `audit_quality` | Audit tracked vs latest daily bar date and latest snapshot-history date; caches JSON in Redis (`market_audit:last`). | On-demand | `_get_tracked_symbols_safe`, `PriceData`, `MarketSnapshotHistory`. |

---

### `regime`

Module: market regime computation and intraday VIX monitoring ([`regime.py`](./regime.py)).

| Task | Description | Schedule | Dependencies |
|------|-------------|----------|--------------|
| `compute_daily` | Compute and persist daily regime R1–R5 from gathered inputs (VIX, breadth, etc.); idempotent upsert by `as_of_date`. | **Step** inside `daily_bootstrap`; **auto-ops** regime (06:00–22:00 ET only); on-demand | `gather_regime_inputs`, `compute_regime`, `persist_regime`. |
| `vix_alert` | Poll VIX; on spike vs prior close or absolute level, recompute regime and optionally notify Discord. | On-demand (docstring suggests frequent cadence during market hours if scheduled) | `yfinance`; same regime persist path as `compute_daily`. |

---

### `iv`

Module: implied volatility snapshot and IV rank ([`iv.py`](./iv.py)).

| Task | Description | Schedule | Dependencies |
|------|-------------|----------|--------------|
| `sync_gateway` | Snapshot implied vol for open positions from IB Gateway into `HistoricalIV`. | On-demand | Requires IB Gateway connected (`ibkr_client`); iterates open `Position` symbols. **Note:** current loop uses placeholder `iv_data`; extend when wiring live IV reads. |
| `compute_rank` | Compute IV rank / 252d high-low fields on latest `HistoricalIV` rows. | On-demand | Queries IV history per symbol; updates `iv_rank_252`, spreads. |

---

### `intraday`

Module: five-minute bar backfill ([`intraday.py`](./intraday.py)).

| Task | Description | Schedule | Dependencies |
|------|-------------|----------|--------------|
| `bars_5m_symbols` | Delta backfill last *N* days of 5m bars for a symbol list. | On-demand | Skips if `infra.is_backfill_5m_enabled()` is false; `price_bars.backfill_intraday_5m` per symbol (uses `provider_router`). |
| `bars_5m_last_n_days` | Backfill last *N* days of 5m bars for full tracked universe in batches. | On-demand | Same toggle and `price_bars` path as above; `_get_tracked_universe_from_db`. |

---

### `institutional`

Module: SEC 13F holdings ingestion ([`institutional.py`](./institutional.py)).

| Task | Description | Schedule | Dependencies |
|------|-------------|----------|--------------|
| `sync_13f` | Fetch recent 13F filings, parse, and persist holdings (monthly cadence recommended in docstring given filing lag). | On-demand | `sec_edgar.fetch_recent_13f_filings`, `fetch_and_parse_13f`, `persist_13f_holdings`. |

---

## Running tasks manually (`make task-run`)

From the repo root (Docker dev stack running):

```bash
make task-run TASK=backend.tasks.market.coverage.health_check
```

Positional and keyword arguments are JSON (see [`Makefile`](../../../Makefile) and [`backend/scripts/run_task.py`](../../scripts/run_task.py)):

```bash
make task-run TASK=backend.tasks.market.coverage.daily_bootstrap \
  TASK_KWARGS='{"history_days":20,"history_batch_size":25}'

make task-run TASK=backend.tasks.market.backfill.symbols \
  TASK_ARGS='[["AAPL","MSFT"]]' \
  TASK_KWARGS='{"days":200}'
```

The command prints the Celery task id. Use Flower or worker logs to follow execution.

Shortcut for a smaller bootstrap window:

```bash
make warm
```

---

## Common troubleshooting

| Symptom | Things to check |
|--------|------------------|
| Task “already running” / no progress | Many tasks use `@task_run` locks (e.g. `daily_bootstrap`, `stale_daily`, `full_historical` per `since_date`). Wait for the holder to finish or cancel the stuck `JobRun` after verifying the worker is dead. |
| Admin Jobs stuck in RUNNING | Run `recover_jobs` (or wait for scheduled / auto-ops). Confirms worker crash, OOM, or cron wall-clock kill. |
| Indicators UNKNOWN / RS warnings | `recompute_universe` logs benchmark bar count; ensure SPY (or fallback benchmark) has enough daily history. Run `daily_bars` or benchmark fetch path. |
| Coverage red / stale_daily loop | Auto-ops fires `health_check` + `stale_daily` with a 30-minute Redis cooldown per dimension. Check provider errors in task result `error_samples`. |
| 5m tasks return `skipped` | Admin toggle `infra.is_backfill_5m_enabled()` is off; see coverage health snapshot. |
| `sync_gateway` no-op | Gateway not connected or no open positions; task returns `gateway_not_connected` / `no_positions`. |
| History backfill errors | Requires 1d bars and a valid trading calendar (SPY or fallback). `snapshot_last_n_days` errors if no daily bars exist. |

---

## Task naming conventions

- **Module** = domain context (`backfill`, `coverage`, `history`, …).
- **Function** = action (`daily_bars`, `health_check`, `recompute_universe`).
- **Celery name** = dotted path `backend.tasks.market.<module>.<function>` (this is what `TASK=` uses).
- **`task_run` job id** (e.g. `admin_coverage_backfill`) is stable for `JobRun` and UI; it may differ from the Python function name—see the first argument to `@task_run` on each task.

Public re-exports for Celery autodiscovery live in [`__init__.py`](./__init__.py).
