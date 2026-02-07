AxiomFolio Market Data Tasks
=============================

Purpose
-------
End-to-end market data pipeline built around a simple, scalable principle: fetch and store OHLCV once (PriceData), compute everything else locally and deterministically (indicators, chart metrics, history) from the database. No internet calls for metrics, ever.

Task Inventory
--------------
Backfill (writes `price_data`)
- backfill_last_bars(days=200): Fetch last-N daily OHLCV for tracked symbols (delta-only; concurrent fetch, bulk upsert).
- backfill_symbols(symbols=[...]): Fetch last-year-ish daily OHLCV for a provided list (delta-only).

Indicators (writes `market_analysis_cache`)
- recompute_indicators_universe(batch_size=50): Consolidated compute for indices + portfolio from PriceData. Fills all core indicators (RSI, SMA/EMA, MACD, ATR, perf windows, MA bucket, distances) and chart metrics (TD counts, gaps, trendlines) in one pass.

Constituents (DB + cache)
- refresh_index_constituents(): Persist SP500/NASDAQ100/DOW30 to `index_constituents`, track `is_active`/first/last seen.
- update_tracked_symbol_cache(): Build Redis `tracked:all` and `tracked:new` from DB (index_constituents ∪ portfolio).

Coverage & operator flow
- bootstrap_daily_coverage_tracked(): Primary operator chain (refresh → tracked → daily backfill → recompute → rolling history backfill (default 5 trading days) → coverage refresh; no 5m).
- monitor_coverage_health(): Computes and caches coverage snapshot/history in Redis.

History (writes `market_analysis_history`)
- record_daily_history(symbols=None): Persist immutable daily snapshots (denormalized heads + full payload). Defaults to portfolio symbols.

Schedules (Celery Beat)
-----------------------
Configured in `backend/tasks/celery_app.py` (UTC):
- restore-daily-coverage-tracked: nightly guided operator chain
- monitor-coverage-health-hourly: hourly coverage cache refresh
- ibkr-daily-flex-sync: nightly comprehensive FlexQuery sync

Runbooks
--------
Daily restore (recommended)
1) `bootstrap_daily_coverage_tracked.delay()`

Daily manual refresh
- `recompute_indicators_universe.delay(batch_size=60)`
- Optional: `record_daily_history.delay(symbols=[...])`

Notes & Troubleshooting
-----------------------
- Providers: prefer FMP/TwelveData; fallback yfinance. Cache in Redis; compute locally from `price_data`.
- Retention: ~270 daily bars support SMA200/252d windows; increase if needed.
- Worker offline or tasks pending: check logs (Docker dev):
  - `make logs` (recommended), or
  - `docker compose --env-file infra/env.dev -f infra/compose.dev.yaml logs celery_worker`
  Then verify includes, restart worker/beat; requeue tasks.
