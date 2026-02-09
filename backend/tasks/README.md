AxiomFolio Market Data Tasks
=============================

Purpose
-------
End-to-end market data pipeline built around a simple, scalable principle: fetch and store OHLCV once (PriceData), compute everything else locally and deterministically (indicators, chart metrics, history) from the database. No internet calls for metrics, ever.

Task Inventory
--------------
Backfill (writes `price_data`)
- backfill_last_bars (task name: `admin_backfill_daily`): Fetch last-N daily OHLCV for tracked symbols (delta-only; concurrent fetch, bulk upsert).
- backfill_symbols (task name: `admin_backfill_daily_symbols`): Fetch last-year-ish daily OHLCV for a provided list (delta-only).

Indicators (writes `market_analysis_cache`)
- recompute_indicators_universe (task name: `admin_indicators_recompute_universe`): Consolidated compute for indices + portfolio from PriceData. Fills all core indicators (RSI, SMA/EMA, MACD, ATR, perf windows, MA bucket, distances) and chart metrics (TD counts, gaps, trendlines) in one pass.

Constituents (DB + cache)
- refresh_index_constituents (task name: `market_indices_constituents_refresh`): Persist SP500/NASDAQ100/DOW30 to `index_constituents`, track `is_active`/first/last seen.
- update_tracked_symbol_cache (task name: `market_universe_tracked_refresh`): Build Redis `tracked:all` and `tracked:new` from DB (index_constituents ∪ portfolio).

Coverage & operator flow
- bootstrap_daily_coverage_tracked (task name: `admin_coverage_backfill`): Primary backfill chain (refresh → tracked → daily backfill → recompute → rolling history backfill (dynamic window based on last successful run; minimum 5 trading days, fallback 20 trading days) → coverage refresh; no 5m).
- monitor_coverage_health (task name: `admin_coverage_refresh`): Computes and caches coverage snapshot/history in Redis.

History (writes `market_analysis_history`)
- record_daily_history (task name: `admin_snapshots_history_record`): Persist immutable daily snapshots (denormalized heads + full payload). Defaults to portfolio symbols.

Schedules (Celery Beat)
-----------------------
Configured in `backend/tasks/celery_app.py` (UTC):
- admin_coverage_backfill: nightly guided backfill chain
- admin_coverage_refresh: hourly coverage cache refresh
- ibkr-daily-flex-sync: nightly comprehensive FlexQuery sync

Runbooks
--------
Daily backfill (recommended)
1) `bootstrap_daily_coverage_tracked.delay()` (task name: `admin_coverage_backfill`)

Daily manual refresh
- `recompute_indicators_universe.delay(batch_size=60)` (task name: `admin_indicators_recompute_universe`)
- Optional: `record_daily_history.delay(symbols=[...])` (task name: `admin_snapshots_history_record`)

Notes & Troubleshooting
-----------------------
- Providers: prefer FMP/TwelveData; fallback yfinance. Cache in Redis; compute locally from `price_data`.
- Retention: ~270 daily bars support SMA200/252d windows; increase if needed.
- Worker offline or tasks pending: check logs (Docker dev):
  - `make logs` (recommended), or
  - `docker compose --env-file infra/env.dev -f infra/compose.dev.yaml logs celery_worker`
  Then verify includes, restart worker/beat; requeue tasks.
