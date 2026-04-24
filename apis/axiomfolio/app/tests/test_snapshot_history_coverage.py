def test_coverage_snapshot_uses_snapshot_history(db_session, monkeypatch):
    """Regression: snapshot_fill_by_date should come from MarketSnapshotHistory (ledger), not MarketSnapshot (latest-only)."""
    import time
    from datetime import datetime, timezone

    from app.models.market_data import MarketSnapshotHistory
    from app.services.silver.market.market_data_service import coverage_analytics, infra
    from app.services.silver.market.universe import TRACKED_ALL_UPDATED_AT_KEY

    # Ensure coverage_snapshot sees a stable universe
    def _redis_get(key):
        if key == "tracked:all":
            return b'["AAA","BBB"]'
        if key == TRACKED_ALL_UPDATED_AT_KEY:
            return str(time.time()).encode()
        return None

    monkeypatch.setattr(infra.redis_client, "get", _redis_get)

    # Use recent dates so they always fall inside the lookback window
    from datetime import timedelta
    today = datetime.now(timezone.utc).replace(tzinfo=None)
    d1 = (today - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    d2 = (today - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
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

    d1_str = d1.strftime("%Y-%m-%d")
    d2_str = d2.strftime("%Y-%m-%d")
    assert d1_str in dates
    assert d2_str in dates


