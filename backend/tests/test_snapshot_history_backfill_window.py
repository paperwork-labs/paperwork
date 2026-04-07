def test_snapshot_last_n_days_writes_rows(db_session, monkeypatch):
    """Smoke test: snapshot_last_n_days writes ledger rows for last N SPY trading days."""
    import time
    from datetime import datetime

    import backend.tasks.market.history as history_tasks
    from backend.services.market.universe import TRACKED_ALL_UPDATED_AT_KEY

    monkeypatch.setattr(history_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(history_tasks, "_set_task_status", lambda *args, **kwargs: None)

    # Stable tracked universe (history uses market_data_service from this module)
    def _redis_get(key):
        if key == "tracked:all":
            return b'["AAA"]'
        if key == TRACKED_ALL_UPDATED_AT_KEY:
            return str(time.time()).encode()
        return None

    import backend.tasks.utils.task_utils as tu

    monkeypatch.setattr(tu.infra, "_redis_sync", type("_R", (), {"get": staticmethod(_redis_get)})())

    from backend.models.market_data import PriceData, MarketSnapshotHistory

    # Create a tiny SPY calendar (5 days)
    spy_dates = [
        datetime(2026, 1, 1),
        datetime(2026, 1, 2),
        datetime(2026, 1, 3),
        datetime(2026, 1, 4),
        datetime(2026, 1, 5),
    ]
    for d in spy_dates:
        db_session.add(
            PriceData(
                symbol="SPY",
                interval="1d",
                date=d,
                open_price=100,
                high_price=101,
                low_price=99,
                close_price=100,
                adjusted_close=100,
                volume=0,
                data_source="test",
                is_adjusted=True,
            )
        )

    # Create AAA prices for same dates
    for i, d in enumerate(spy_dates):
        px = 10 + i
        db_session.add(
            PriceData(
                symbol="AAA",
                interval="1d",
                date=d,
                open_price=px,
                high_price=px + 1,
                low_price=px - 1,
                close_price=px,
                adjusted_close=px,
                volume=0,
                data_source="test",
                is_adjusted=True,
            )
        )
    db_session.commit()

    from backend.tasks.market.history import snapshot_last_n_days

    res = snapshot_last_n_days(days=5, batch_size=10)
    assert res["status"] == "ok"
    assert res["processed_symbols"] == 1
    assert res["written_rows"] >= 5

    rows = (
        db_session.query(MarketSnapshotHistory)
        .filter(MarketSnapshotHistory.symbol == "AAA", MarketSnapshotHistory.analysis_type == "technical_snapshot")
        .order_by(MarketSnapshotHistory.as_of_date.asc())
        .all()
    )
    assert len(rows) == 5
    # Wide/flat table: verify some computed fields landed on columns.
    assert rows[0].current_price is not None
    assert rows[-1].sma_5 is not None or rows[-1].sma_14 is not None or rows[-1].sma_21 is not None


