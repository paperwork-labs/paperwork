from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import json
import pytest
from sqlalchemy.exc import OperationalError
from backend.api.main import app
from backend.api.dependencies import get_market_data_viewer
from backend.database import get_db
from backend.models.market_data import PriceData
from backend.models.user import UserRole
from backend.config import settings
from backend.tasks import market_data_tasks
from backend.services.market.coverage_service import CoverageService

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def allow_market_data_viewer():
    class _DummyUser:
        role = UserRole.ADMIN
        is_active = True
        email = "admin@example.com"

    app.dependency_overrides[get_market_data_viewer] = lambda: _DummyUser()
    yield
    app.dependency_overrides.pop(get_market_data_viewer, None)


@pytest.mark.destructive
def test_coverage_endpoint_buckets(monkeypatch, db_session):
    if db_session is None:
        pytest.skip("DB session unavailable for coverage test")
    monkeypatch.setattr(settings, "MARKET_DATA_SECTION_PUBLIC", True)
    try:
        # Route monitor_coverage_health to the test session
        monkeypatch.setattr(market_data_tasks, "SessionLocal", lambda: db_session)
        def _override_db():
            yield db_session
        app.dependency_overrides[get_db] = _override_db
        # Clean and insert two symbols: one fresh, one stale
        db_session.query(PriceData).delete()
        now = datetime.utcnow()
        rows = [
            PriceData(symbol="TESTF", date=now - timedelta(hours=2), open_price=1, high_price=1, low_price=1, close_price=1, adjusted_close=1, volume=100, interval="1d", is_adjusted=True, data_source="test"),
            PriceData(symbol="TESTS", date=now - timedelta(days=3), open_price=1, high_price=1, low_price=1, close_price=1, adjusted_close=1, volume=100, interval="1d", is_adjusted=True, data_source="test"),
        ]
        for r in rows:
            db_session.add(r)
        db_session.commit()
    except OperationalError:
        db_session.rollback()
        pytest.skip("Database unavailable for coverage test")

    try:
        resp = client.get("/api/v1/market-data/coverage")
        assert resp.status_code == 200
        data = resp.json()
        assert "daily" in data
        assert "freshness" in data["daily"]
        # Buckets should exist
        buckets = data["daily"]["freshness"]
        assert all(k in buckets for k in ["<=24h", "24-48h", ">48h", "none"])
        # Sanity: buckets cover the full universe; daily.count represents <=48h freshness.
        assert sum(buckets.values()) == data["symbols"]
        assert (
            int(data["daily"].get("count") or 0)
            + int(data["daily"].get("stale_48h") or 0)
            + int(data["daily"].get("missing") or 0)
        ) == data["symbols"]
        assert "status" in data
        assert "history" in data
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_coverage_prefers_cached_snapshot(monkeypatch):
    from backend.api.routes.market import coverage as routes

    monkeypatch.setattr(settings, "MARKET_DATA_SECTION_PUBLIC", True)
    cached_snapshot = {
        "generated_at": "2025-01-01T00:00:00",
        "symbols": 2,
        "tracked_count": 2,
        "daily": {"count": 2, "stale": []},
        "m5": {"count": 1, "stale": []},
    }
    cached_status = {
        "label": "ok",
        "summary": "Cached snapshot",
        "daily_pct": 100,
        "m5_pct": 50,
        "stale_daily": 0,
        "stale_m5": 0,
    }
    payload = {
        "schema_version": 1,
        "snapshot": cached_snapshot,
        "updated_at": "2025-01-01T00:00:00",
        "status": cached_status,
    }

    class _RedisStub:
        def get(self, key):
            if key == "coverage:health:last":
                return json.dumps(payload)
            return None

        def lrange(self, key, start, end):
            return [
                json.dumps(
                    {
                        "ts": "2025-01-01T00:00:00",
                        "daily_pct": 100,
                        "m5_pct": 50,
                        "stale_daily": 0,
                        "stale_m5": 0,
                        "label": "ok",
                    }
                )
            ]

    class _StubService:
        def __init__(self):
            self.redis_client = _RedisStub()
            self.coverage = CoverageService(self)

        def coverage_snapshot(self, db):
            raise AssertionError("Should not hit DB when cache is present")

        def is_backfill_5m_enabled(self) -> bool:
            return True

        def benchmark_health(self, db, benchmark_symbol="SPY", required_bars=None, latest_daily_dt=None):
            return {
                "symbol": benchmark_symbol,
                "latest_daily_dt": None,
                "latest_daily_date": None,
                "daily_bars": 0,
                "required_bars": int(required_bars or 260),
                "ok": False,
                "stale": False,
            }

    monkeypatch.setattr(routes, "MarketDataService", _StubService)

    resp = client.get("/api/v1/market-data/coverage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["source"] == "cache"
    assert body["status"]["label"].lower() == "ok"
    assert body["history"]


def test_coverage_meta_exposes_kpis_and_sparkline(monkeypatch):
    from backend.api.routes.market import coverage as routes

    monkeypatch.setattr(settings, "MARKET_DATA_SECTION_PUBLIC", True)

    class _RedisStub:
        def get(self, key):
            return None

        def lrange(self, key, start, end):
            return []

    class _StubService:
        def __init__(self):
            self.redis_client = _RedisStub()
            self.coverage = CoverageService(self)

        def coverage_snapshot(self, db, **_kwargs):
            return {
                "generated_at": "2025-01-01T00:00:00",
                "symbols": 2,
                "tracked_count": 2,
                "daily": {
                    "count": 2,
                    "last": {
                        "AAA": "2025-01-01T00:00:00",
                        "BBB": "2025-01-01T00:00:00",
                    },
                    "stale": [],
                },
                "m5": {
                    "count": 1,
                    "last": {
                        "AAA": "2025-01-01T00:00:00",
                    },
                    "stale": [],
                },
            }

        def is_backfill_5m_enabled(self) -> bool:
            return True

        def benchmark_health(self, db, benchmark_symbol="SPY", required_bars=None, latest_daily_dt=None):
            return {
                "symbol": benchmark_symbol,
                "latest_daily_dt": None,
                "latest_daily_date": None,
                "daily_bars": 0,
                "required_bars": int(required_bars or 260),
                "ok": False,
                "stale": False,
            }

    monkeypatch.setattr(routes, "MarketDataService", _StubService)

    resp = client.get("/api/v1/market-data/coverage")
    assert resp.status_code == 200
    payload = resp.json()
    meta = payload["meta"]
    assert "sparkline" in meta
    assert "kpis" in meta
    assert isinstance(meta["kpis"], list)
    assert meta["kpis"][0]["id"] == "tracked"
    assert len(meta["sparkline"]["daily_pct"]) >= 1
    assert len(meta["sparkline"]["m5_pct"]) >= 1
    assert len(meta["sparkline"]["labels"]) >= 1
    assert meta["sla"]["daily_pct"] == payload["status"]["thresholds"]["daily_pct"]


def test_coverage_cache_schema_mismatch_falls_back(monkeypatch):
    from backend.api.routes.market import coverage as routes

    monkeypatch.setattr(settings, "MARKET_DATA_SECTION_PUBLIC", True)

    cached_snapshot = {
        "generated_at": "2025-01-01T00:00:00",
        "symbols": 2,
        "tracked_count": 2,
        "daily": {"count": 2, "stale": []},
        "m5": {"count": 1, "stale": []},
    }
    payload = {
        "schema_version": 0,
        "snapshot": cached_snapshot,
        "updated_at": "2025-01-01T00:00:00",
        "status": {"label": "ok"},
    }
    coverage_called = {"hit": False}

    class _RedisStub:
        def get(self, key):
            if key == "coverage:health:last":
                return json.dumps(payload)
            return None

        def lrange(self, key, start, end):
            return []

    class _StubService:
        def __init__(self):
            self.redis_client = _RedisStub()
            self.coverage = CoverageService(self)

        def coverage_snapshot(self, db, **_kwargs):
            coverage_called["hit"] = True
            return {
                "generated_at": "2025-01-01T00:00:00",
                "symbols": 2,
                "tracked_count": 2,
                "daily": {"count": 2, "stale": []},
                "m5": {"count": 1, "stale": []},
            }

        def is_backfill_5m_enabled(self) -> bool:
            return True

        def benchmark_health(self, db, benchmark_symbol="SPY", required_bars=None, latest_daily_dt=None):
            return {
                "symbol": benchmark_symbol,
                "latest_daily_dt": None,
                "latest_daily_date": None,
                "daily_bars": 0,
                "required_bars": int(required_bars or 260),
                "ok": False,
                "stale": False,
            }

    monkeypatch.setattr(routes, "MarketDataService", _StubService)

    resp = client.get("/api/v1/market-data/coverage")
    assert resp.status_code == 200
    assert coverage_called["hit"] is True

