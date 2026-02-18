"""Tests for the monotonicity checker fix that skips weekend/holiday gaps."""

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.dependencies import get_admin_user
from backend.models.market_data import MarketSnapshot, MarketSnapshotHistory


client = TestClient(app, raise_server_exceptions=False)


def _make_history_row(symbol, date, stage_label, current_stage_days):
    return MarketSnapshotHistory(
        symbol=symbol,
        analysis_type="technical_snapshot",
        as_of_date=date,
        stage_label=stage_label,
        current_stage_days=current_stage_days,
        previous_stage_label=None,
        previous_stage_days=None,
    )


def _recent_monday(min_days_ago: int = 7) -> date:
    """Return a Monday in the recent past (within lookback windows)."""
    today = datetime.now(timezone.utc).date()
    candidate = today - timedelta(days=min_days_ago)
    while candidate.weekday() != 0:  # Monday=0
        candidate -= timedelta(days=1)
    return candidate


def test_monotonicity_skips_weekend_gaps(db_session):
    """Friday→Monday gap should NOT count as a monotonicity violation."""
    from backend.api.routes import market_data as routes
    from backend.services.market.market_data_service import MarketDataService

    now = datetime.now(timezone.utc)
    snap = MarketSnapshot(
        symbol="AAA",
        analysis_type="technical_snapshot",
        stage_label="2A",
        current_stage_days=10,
        as_of_timestamp=now,
        expiry_timestamp=now + timedelta(days=1),
    )
    db_session.add(snap)

    # Simulate Mon-Fri trading week then Mon again (weekend gap)
    monday = _recent_monday(min_days_ago=14)
    friday = monday - timedelta(days=3)  # Friday (3 calendar days earlier)
    tuesday = monday + timedelta(days=1)

    db_session.add(_make_history_row("AAA", friday, "2A", 5))
    db_session.add(_make_history_row("AAA", monday, "2A", 6))
    db_session.add(_make_history_row("AAA", tuesday, "2A", 7))
    db_session.commit()

    svc = MarketDataService()
    result = svc.stage_quality_summary(db_session, lookback_days=30)
    assert result["monotonicity_issues"] == 0


def test_monotonicity_catches_real_violations(db_session):
    """Consecutive trading days with wrong counter should still be caught."""
    from backend.services.market.market_data_service import MarketDataService

    now = datetime.now(timezone.utc)
    snap = MarketSnapshot(
        symbol="BBB",
        analysis_type="technical_snapshot",
        stage_label="2A",
        current_stage_days=5,
        as_of_timestamp=now,
        expiry_timestamp=now + timedelta(days=1),
    )
    db_session.add(snap)

    mon = _recent_monday(min_days_ago=14)
    tue = mon + timedelta(days=1)  # 1 calendar day later

    db_session.add(_make_history_row("BBB", mon, "2A", 5))
    db_session.add(_make_history_row("BBB", tue, "2A", 5))  # Should be 6, not 5
    db_session.commit()

    svc = MarketDataService()
    result = svc.stage_quality_summary(db_session, lookback_days=30)
    assert result["monotonicity_issues"] >= 1


def test_monotonicity_stage_transition_over_weekend(db_session):
    """Stage transition over a weekend should not flag a violation."""
    from backend.services.market.market_data_service import MarketDataService

    now = datetime.now(timezone.utc)
    snap = MarketSnapshot(
        symbol="CCC",
        analysis_type="technical_snapshot",
        stage_label="2B",
        current_stage_days=1,
        as_of_timestamp=now,
        expiry_timestamp=now + timedelta(days=1),
    )
    db_session.add(snap)

    monday = _recent_monday(min_days_ago=14)
    friday = monday - timedelta(days=3)

    db_session.add(_make_history_row("CCC", friday, "2A", 20))
    db_session.add(_make_history_row("CCC", monday, "2B", 1))  # New stage, reset to 1
    db_session.commit()

    svc = MarketDataService()
    result = svc.stage_quality_summary(db_session, lookback_days=30)
    assert result["monotonicity_issues"] == 0


def test_admin_fundamentals_endpoint_requires_admin():
    resp = client.post("/api/v1/market-data/admin/fundamentals/fill-missing")
    assert resp.status_code in (401, 403)
