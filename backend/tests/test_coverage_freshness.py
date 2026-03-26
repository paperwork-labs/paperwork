from datetime import datetime, timedelta
from fastapi.testclient import TestClient
import pytest

from backend.api.main import app
from backend.api.dependencies import get_market_data_viewer
from backend.database import get_db
from backend.models.market_data import PriceData
from backend.models.market_data import MarketSnapshot
from backend.tasks.market import coverage as market_coverage_tasks
from backend.tasks.market.coverage import health_check
from backend.models.user import UserRole


@pytest.fixture(autouse=True)
def allow_market_data_viewer():
    class _DummyUser:
        role = UserRole.ADMIN
        is_active = True
        email = "admin@example.com"

    app.dependency_overrides[get_market_data_viewer] = lambda: _DummyUser()
    yield
    app.dependency_overrides.pop(get_market_data_viewer, None)


def _seed_prices(db):
    db.query(PriceData).delete()
    db.query(MarketSnapshot).delete()
    now = datetime.utcnow()
    rows = [
        # fresh <24h
        PriceData(
            symbol="FRESH",
            date=now - timedelta(hours=2),
            open_price=1,
            high_price=1,
            low_price=1,
            close_price=1,
            adjusted_close=1,
            volume=100,
            interval="1d",
            is_adjusted=True,
            data_source="test",
        ),
        # 24-48h
        PriceData(
            symbol="MID",
            date=now - timedelta(hours=36),
            open_price=1,
            high_price=1,
            low_price=1,
            close_price=1,
            adjusted_close=1,
            volume=100,
            interval="1d",
            is_adjusted=True,
            data_source="test",
        ),
        # stale >48h
        PriceData(
            symbol="STALE",
            date=now - timedelta(hours=72),
            open_price=1,
            high_price=1,
            low_price=1,
            close_price=1,
            adjusted_close=1,
            volume=100,
            interval="1d",
            is_adjusted=True,
            data_source="test",
        ),
    ]
    for r in rows:
        db.add(r)
    # Seed a technical snapshot for one symbol "today" (UTC date bucket)
    db.add(
        MarketSnapshot(
            symbol="FRESH",
            analysis_type="technical_snapshot",
            analysis_timestamp=now - timedelta(hours=1),
            expiry_timestamp=now + timedelta(days=1),
            current_price=1.0,
        )
    )
    db.commit()


@pytest.mark.destructive
def test_monitor_recomputes_freshness(db_session, monkeypatch):
    if db_session is None:
        pytest.skip("DB session unavailable")
    monkeypatch.setattr(market_coverage_tasks, "SessionLocal", lambda: db_session)

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    _seed_prices(db_session)
    try:
        res = health_check()
    finally:
        app.dependency_overrides.pop(get_db, None)
    # total = 3; fresh = 2; stale =1
    assert res["symbols"] == 3
    assert res["tracked_count"] == 3
    assert res["stale_daily"] == 1
    assert 65.0 <= res["daily_pct"] <= 70.0  # 2/3 ~= 66.7, clamped within range


@pytest.mark.destructive
def test_coverage_endpoint_uses_recomputed_freshness(db_session, monkeypatch):
    if db_session is None:
        pytest.skip("DB session unavailable")
    monkeypatch.setattr(market_coverage_tasks, "SessionLocal", lambda: db_session)

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    _seed_prices(db_session)
    try:
        res = health_check()  # ensures cache is set
        assert res["stale_daily"] == 1
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/coverage")
        assert resp.status_code == 200
        data = resp.json()
        daily = data["daily"]
        status = data["status"]
        assert daily["count"] == 2
        assert daily["stale_48h"] == 1
        assert status["stale_daily"] == 1
        assert 65.0 <= status["daily_pct"] <= 70.0
        # New: date-bucket fill series exists (daily OHLCV) + snapshot series exists.
        assert "fill_by_date" in daily
        assert isinstance(daily["fill_by_date"], list)
        assert "snapshot_fill_by_date" in daily
        assert isinstance(daily["snapshot_fill_by_date"], list)
    finally:
        app.dependency_overrides.pop(get_db, None)

