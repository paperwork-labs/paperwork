def test_bootstrap_daily_coverage_tracked_defaults_to_rolling_20_day_history(
    db_session, monkeypatch
):
    """Backfill Daily Coverage (Tracked) should backfill a short rolling snapshot-history window by default."""
    # daily_bootstrap imports subtasks from app.tasks.market.* — patch those modules.
    monkeypatch.setattr("app.tasks.market.backfill.constituents", lambda: {"status": "ok"})
    monkeypatch.setattr("app.tasks.market.backfill.tracked_cache", lambda: {"status": "ok"})
    monkeypatch.setattr(
        "app.tasks.market.backfill.daily_bars",
        lambda days=200: {"status": "ok", "days": days},
    )
    monkeypatch.setattr(
        "app.tasks.market.indicators.recompute_universe",
        lambda batch_size=50: {"status": "ok"},
    )
    monkeypatch.setattr("app.tasks.market.regime.compute_daily", lambda: {"status": "ok"})
    monkeypatch.setattr("app.tasks.market.coverage._run_scan_overlay", lambda: {"status": "ok"})
    monkeypatch.setattr(
        "app.tasks.market.coverage._evaluate_exit_cascade_all", lambda: {"status": "ok"}
    )
    monkeypatch.setattr(
        "app.tasks.strategy.tasks.evaluate_strategies_task", lambda: {"status": "ok"}
    )
    monkeypatch.setattr(
        "app.tasks.market.coverage.health_check",
        lambda: {"status": "ok", "daily_pct": 100, "stale_daily": 0},
    )
    monkeypatch.setattr(
        "app.tasks.intelligence.tasks.generate_daily_digest_task",
        lambda deliver_brain=True: {"status": "ok"},
    )

    called = {}

    def fake_snapshot_last_n_days(days: int, batch_size: int = 25, since_date=None):
        called["days"] = days
        called["batch_size"] = batch_size
        return {"status": "ok", "days": days, "processed_symbols": 0, "written_rows": 0}

    monkeypatch.setattr(
        "app.tasks.market.history.snapshot_last_n_days",
        fake_snapshot_last_n_days,
    )
    monkeypatch.setattr("app.tasks.market.coverage._resolve_history_days", lambda _: 20)

    from app.tasks.market.coverage import daily_bootstrap

    res = daily_bootstrap()
    assert res["status"] == "ok"
    assert called["days"] == 20
