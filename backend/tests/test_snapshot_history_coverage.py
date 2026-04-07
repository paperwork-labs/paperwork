def test_coverage_snapshot_uses_snapshot_history(db_session, monkeypatch):
    """Regression: snapshot_fill_by_date should come from MarketSnapshotHistory (ledger), not MarketSnapshot (latest-only)."""
    import time
    from datetime import datetime, timezone

    from backend.models.market_data import MarketSnapshotHistory
    from backend.services.market.market_data_service import coverage_analytics, infra
    from backend.services.market.universe import TRACKED_ALL_UPDATED_AT_KEY

    # Ensure coverage_snapshot sees a stable universe
    def _redis_get(key):
        if key == "tracked:all":
            return b'["AAA","BBB"]'
        if key == TRACKED_ALL_UPDATED_AT_KEY:
            return str(time.time()).encode()
        return None

    monkeypatch.setattr(infra.redis_client, "get", _redis_get)

    # Insert history for two dates
    d1 = datetime(2026, 1, 8, tzinfo=timezone.utc).replace(tzinfo=None)
    d2 = datetime(2026, 1, 9, tzinfo=timezone.utc).replace(tzinfo=None)
    db_session.add(
        MarketSnapshotHistory(
            symbol="AAA",
            analysis_type="technical_snapshot",
            as_of_date=d1,
            current_price=1,
        )
    )
    db_session.add(
        MarketSnapshotHistory(
            symbol="BBB",
            analysis_type="technical_snapshot",
            as_of_date=d2,
            current_price=2,
        )
    )
    db_session.commit()

    snap = coverage_analytics.coverage_snapshot(db_session)
    series = (snap.get("daily") or {}).get("snapshot_fill_by_date") or []
    dates = {row.get("date") for row in series}

    assert "2026-01-08" in dates
    assert "2026-01-09" in dates


