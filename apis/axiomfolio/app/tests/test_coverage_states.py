from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
import json
import pytest
from sqlalchemy.exc import OperationalError
from app.api.main import app
from app.api.dependencies import get_market_data_viewer
from app.database import get_db
from app.models.market_data import PriceData
from app.models.user import UserRole
from app.config import settings
from app.services.silver.market.coverage_analytics import CoverageAnalytics

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def allow_market_data_viewer():
    class _DummyUser:
        role = UserRole.OWNER
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
        def _override_db():
            yield db_session
        app.dependency_overrides[get_db] = _override_db
        db_session.query(PriceData).delete()
        now = datetime.now(timezone.utc)
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

    resp = client.get("/api/v1/market-data/coverage")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "daily" in data
    assert data["status"]["label"].lower() in ("ok", "degraded", "stale")


def _make_stub_analytics(redis_stub, *, coverage_snapshot_fn=None, benchmark_health_fn=None, backfill_5m=True):
    """Build a CoverageAnalytics with stubbed infra and optional method overrides."""
    class _InfraStub:
        redis_client = redis_stub
        def is_backfill_5m_enabled(self):
            return backfill_5m

    ca = CoverageAnalytics(_InfraStub())
    if coverage_snapshot_fn:
        ca.coverage_snapshot = coverage_snapshot_fn
    if benchmark_health_fn:
        ca.benchmark_health = benchmark_health_fn
    else:
        ca.benchmark_health = lambda db, **kw: {
            "symbol": kw.get("benchmark_symbol", "SPY"),
            "latest_daily_dt": None, "latest_daily_date": None,
            "daily_bars": 0, "required_bars": int(kw.get("required_bars") or 260),
            "ok": False, "stale": False,
        }
    return ca


def test_coverage_prefers_cached_snapshot(monkeypatch):
    from app.api.routes.market import coverage as routes

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
                json.dumps({
                    "ts": "2025-01-01T00:00:00",
                    "daily_pct": 100, "m5_pct": 50,
                    "stale_daily": 0, "stale_m5": 0, "label": "ok",
                })
            ]

    def _should_not_hit_db(db, **kw):
        raise AssertionError("Should not hit DB when cache is present")

    stub = _make_stub_analytics(_RedisStub(), coverage_snapshot_fn=_should_not_hit_db)
    monkeypatch.setattr(routes, "coverage_analytics", stub)

    resp = client.get("/api/v1/market-data/coverage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["source"] == "cache"
    assert body["status"]["label"].lower() == "ok"
    assert body["history"]


def test_coverage_meta_exposes_kpis_and_sparkline(monkeypatch):
    from app.api.routes.market import coverage as routes

    monkeypatch.setattr(settings, "MARKET_DATA_SECTION_PUBLIC", True)

    class _RedisStub:
        def get(self, key):
            return None
        def lrange(self, key, start, end):
            return []

    def _live_snapshot(db, **kw):
        return {
            "generated_at": "2025-01-01T00:00:00",
            "symbols": 2,
            "tracked_count": 2,
            "daily": {"count": 2, "last": {"AAA": "2025-01-01T00:00:00", "BBB": "2025-01-01T00:00:00"}, "stale": []},
            "m5": {"count": 1, "last": {"AAA": "2025-01-01T00:00:00"}, "stale": []},
        }

    stub = _make_stub_analytics(_RedisStub(), coverage_snapshot_fn=_live_snapshot)
    monkeypatch.setattr(routes, "coverage_analytics", stub)

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
    from app.api.routes.market import coverage as routes

    monkeypatch.setattr(settings, "MARKET_DATA_SECTION_PUBLIC", True)

    cached_snapshot = {
        "generated_at": "2025-01-01T00:00:00",
        "symbols": 2, "tracked_count": 2,
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

    def _live_snapshot(db, **kw):
        coverage_called["hit"] = True
        return {
            "generated_at": "2025-01-01T00:00:00",
            "symbols": 2, "tracked_count": 2,
            "daily": {"count": 2, "stale": []},
            "m5": {"count": 1, "stale": []},
        }

    stub = _make_stub_analytics(_RedisStub(), coverage_snapshot_fn=_live_snapshot)
    monkeypatch.setattr(routes, "coverage_analytics", stub)

    resp = client.get("/api/v1/market-data/coverage")
    assert resp.status_code == 200
    assert coverage_called["hit"] is True
