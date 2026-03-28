from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.dependencies import get_admin_user
from backend.models.market_data import MarketSnapshotHistory, PriceData
from backend.models.user import UserRole


@pytest.fixture(autouse=True)
def allow_admin_user():
    class _DummyUser:
        role = UserRole.OWNER
        is_active = True
        email = "admin@example.com"

    app.dependency_overrides[get_admin_user] = lambda: _DummyUser()
    yield
    app.dependency_overrides.pop(get_admin_user, None)


def test_admin_sanity_coverage_payload(db_session, monkeypatch):
    from backend.api.routes.market import admin as routes
    from backend.database import get_db

    # Force route codepaths to use pytest DB session.
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        async def _fake_tracked_symbols_async(_db, redis_async=None):
            return ["AAA", "BBB"]

        monkeypatch.setattr(routes, "tracked_symbols_async", _fake_tracked_symbols_async)

        # Latest daily OHLCV exists for AAA only.
        db_session.add(
            PriceData(
                symbol="AAA",
                date=datetime(2026, 1, 9, tzinfo=timezone.utc),
                interval="1d",
                open_price=1,
                high_price=1,
                low_price=1,
                close_price=1,
                volume=0,
            )
        )
        # Snapshot history exists for AAA only.
        db_session.add(
            MarketSnapshotHistory(
                symbol="AAA",
                analysis_type="technical_snapshot",
                analysis_timestamp=datetime(2026, 1, 10, tzinfo=timezone.utc),
                as_of_date=datetime(2026, 1, 9, tzinfo=timezone.utc).date(),
                current_price=1.0,
            )
        )
        db_session.commit()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/admin/coverage/sanity")
        assert resp.status_code == 200
        data = resp.json()

        assert data["tracked_total"] == 2
        assert data["latest_daily_date"] == "2026-01-09"
        assert data["latest_daily_symbol_count"] == 1
        assert data["latest_snapshot_history_date"] == "2026-01-09"
        assert data["latest_snapshot_history_symbol_count"] == 1
        assert data["latest_snapshot_history_fill_pct"] == 50.0
        assert "BBB" in data["missing_snapshot_history_sample"]
        assert data["benchmark"]["symbol"] == "SPY"
        assert data["benchmark"]["ok"] is False
    finally:
        app.dependency_overrides.pop(get_db, None)


