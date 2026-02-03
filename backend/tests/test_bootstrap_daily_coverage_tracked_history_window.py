def test_bootstrap_daily_coverage_tracked_defaults_to_rolling_20_day_history(db_session, monkeypatch):
    """Restore Daily Coverage (Tracked) should backfill a short rolling snapshot-history window by default."""
    from backend.tasks import market_data_tasks

    # Force tasks to use pytest DB + avoid Redis side effects.
    monkeypatch.setattr(market_data_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(market_data_tasks, "_set_task_status", lambda *args, **kwargs: None)

    # Stub all sub-steps; we only care about history window wiring.
    monkeypatch.setattr(market_data_tasks, "refresh_index_constituents", lambda: {"status": "ok"})
    monkeypatch.setattr(market_data_tasks, "update_tracked_symbol_cache", lambda: {"status": "ok"})
    monkeypatch.setattr(market_data_tasks, "backfill_last_bars", lambda days=200: {"status": "ok", "days": days})
    monkeypatch.setattr(market_data_tasks, "recompute_indicators_universe", lambda batch_size=50: {"status": "ok"})
    monkeypatch.setattr(
        market_data_tasks,
        "monitor_coverage_health",
        lambda: {"status": "ok", "daily_pct": 100, "stale_daily": 0},
    )

    called = {}

    def fake_backfill_snapshot_history_last_n_days(days: int, batch_size: int = 25, since_date=None):
        called["days"] = days
        called["batch_size"] = batch_size
        return {"status": "ok", "days": days, "processed_symbols": 0, "written_rows": 0}

    monkeypatch.setattr(market_data_tasks, "backfill_snapshot_history_last_n_days", fake_backfill_snapshot_history_last_n_days)

    res = market_data_tasks.bootstrap_daily_coverage_tracked()
    assert res["status"] == "ok"
    assert called["days"] == 20


