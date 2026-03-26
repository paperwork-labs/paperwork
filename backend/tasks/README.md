AxiomFolio Market Data Tasks
=============================

Purpose
-------
End-to-end market data pipeline built around a simple, scalable principle: fetch and store OHLCV once (PriceData), compute everything else locally and deterministically (indicators, chart metrics, history) from the database. No internet calls for metrics, ever.

Celery paths use the package **`backend.tasks.market.<module>.<function>`** (replacing the retired `backend.tasks.market_data_tasks.*` monolith). JobRun / schedule **ids** from `@task_run(...)` are shown in parentheses where they differ from the Python name.

Task inventory
--------------

**`backend.tasks.market.backfill`** (writes `price_data`)
- `symbols` (`admin_backfill_daily_symbols`): Daily OHLCV for a provided symbol list (delta-only).
- `daily_bars` (`admin_backfill_daily`): Last-N daily OHLCV for tracked symbols (delta-only; concurrent fetch, bulk upsert).
- `daily_since` (`admin_backfill_daily_since_date`): Backfill daily bars since a date.
- `full_historical` (`admin_backfill_since_date`): Deep / full historical daily fetch.
- `stale_daily` (`admin_coverage_backfill_stale`): Stale-only daily backfill for tracked symbols.
- `symbol` (`market_symbol_refresh`): Refresh one symbol.
- `constituents` (`market_indices_constituents_refresh`): SP500 / NASDAQ100 / DOW30 → `index_constituents`.
- `tracked_cache` (`market_universe_tracked_refresh`): Redis `tracked:all` / `tracked:new`.

**`backend.tasks.market.coverage`**
- `daily_bootstrap` (`admin_coverage_backfill`): Primary nightly chain (constituents → tracked → daily bars → indicators → snapshot history → regime → coverage health; no 5m by default).
- `health_check` (`admin_coverage_refresh`): Coverage snapshot / SLA cache in Redis.

**`backend.tasks.market.history`** (writes `market_snapshot_history`)
- `record_daily` (`admin_snapshots_history_record`): Immutable daily snapshot rows; defaults to portfolio symbols.
- `snapshot_for_date` (`admin_snapshots_history_backfill_date`): Backfill history for one `as_of_date`.
- `snapshot_for_symbol` (`admin_snapshots_history_backfill_symbol`): Backfill history for one symbol.
- `snapshot_last_n_days` (`admin_snapshots_history_backfill`): Rolling window backfill.

**`backend.tasks.market.indicators`**
- `recompute_universe` (`admin_indicators_recompute_universe`): Full indicator + chart metrics pass from `price_data`.
- `position_metadata` (`backfill_position_metadata`): Enrich positions from snapshots.
- `stage_durations` (`admin_backfill_stage_durations`): Stage duration backfill.
- `stage_changes` (`admin_stage_change_alerts`): Stage change notifications.

**`backend.tasks.market.fundamentals`**
- `enrich_index` (`market_indices_fundamentals_enrich`): Index fundamentals enrichment.
- `fill_missing` (`market_snapshots_fundamentals_fill`): Fill missing snapshot fundamentals.
- `refresh_stale` (`market_snapshots_fundamentals_refresh`): Refresh stale fundamentals.

**`backend.tasks.market.maintenance`**
- `prune_old_bars` (`admin_retention_enforce`): Purge old 5m bars per retention window.
- `recover_jobs` (`admin_recover_stale_job_runs`): Reset stuck `JobRun` rows.
- `audit_quality` (`admin_market_data_audit`): Data quality audit.

**`backend.tasks.market.regime`**
- `compute_daily` (`compute_daily_regime`): Daily regime persistence.
- `vix_alert` (`monitor_vix_spike`): VIX spike monitor.

**`backend.tasks.market.iv`**
- `sync_gateway` (`snapshot_iv_from_gateway`): IV snapshot from gateway.
- `compute_rank` (`compute_iv_rank`): IV rank computation.

**`backend.tasks.market.intraday`**
- `bars_5m_symbols` (`admin_backfill_5m_symbols`): 5m bars for a symbol list.
- `bars_5m_last_n_days` (`admin_backfill_5m`): 5m bars for tracked universe in batches.

**`backend.tasks.market.institutional`**
- `sync_13f` (`fetch_13f_filings`): SEC 13F ingestion.

Schedules
---------
Default jobs are defined in `backend/tasks/job_catalog.py` and seeded into the `cron_schedule` table (Admin → Schedules). Render production sync mirrors enabled rows to Render cron services.

Examples (see `celery_app.py` beat schedule and `job_catalog.py` for UTC crons):
- `admin_coverage_backfill` → `daily_bootstrap`
- `admin_coverage_refresh` → `health_check`
- `ibkr-daily-flex-sync` → `backend.tasks.account_sync.sync_all_ibkr_accounts`

Runbooks
--------
Daily backfill (recommended)
1) `backend.tasks.market.coverage.daily_bootstrap.delay()` (job id `admin_coverage_backfill`)

Daily manual refresh
- `backend.tasks.market.indicators.recompute_universe.delay(batch_size=60)` (job id `admin_indicators_recompute_universe`)
- Optional: `backend.tasks.market.history.record_daily.delay(symbols=[...])` (job id `admin_snapshots_history_record`)

CLI
---
`make task-run TASK=backend.tasks.market.<module>.<function>`

Notes & troubleshooting
-----------------------
- Providers: prefer FMP/TwelveData; fallback yfinance. Cache in Redis; compute locally from `price_data`.
- Retention: ~270 daily bars support SMA200/252d windows; increase if needed.
- Worker offline or tasks pending: check logs (Docker dev):
  - `make logs` (recommended), or
  - `docker compose --env-file infra/env.dev -f infra/compose.dev.yaml logs celery_worker`
  Then verify includes, restart worker/beat; requeue tasks.
