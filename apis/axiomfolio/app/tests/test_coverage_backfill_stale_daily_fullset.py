import json
import time
import pytest
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.dependencies import get_admin_user
from app.database import get_db
from app.models.user import UserRole
from app.models.market_data import PriceData
from app.services.silver.market.market_data_service import coverage_analytics, infra
from app.services.silver.market.universe import TRACKED_ALL_UPDATED_AT_KEY


@pytest.fixture(autouse=True)
def allow_admin_user():
    class _DummyUser:
        role = UserRole.OWNER
        is_active = True
        email = "admin@example.com"

    app.dependency_overrides[get_admin_user] = lambda: _DummyUser()
    yield
    app.dependency_overrides.pop(get_admin_user, None)


def test_backfill_stale_daily_returns_full_stale_candidates(monkeypatch, db_session):
    if db_session is None:
        pytest.skip("DB session unavailable")

    # Override DB dependency for this request
    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    try:
        # Create a tracked universe where one symbol is missing from DB entirely.
        tracked = ["FRESH", "STALE", "MISSING"]
        infra.redis_client.set("tracked:all", json.dumps(tracked))
        infra.redis_client.set(TRACKED_ALL_UPDATED_AT_KEY, str(time.time()))

        # Insert bars for FRESH (recent) and STALE (old). MISSING has no bars.
        db_session.query(PriceData).delete()
        now = datetime.now(timezone.utc)
        db_session.add(
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
            )
        )
        db_session.add(
            PriceData(
                symbol="STALE",
                date=now - timedelta(days=3),
                open_price=1,
                high_price=1,
                low_price=1,
                close_price=1,
                adjusted_close=1,
                volume=100,
                interval="1d",
                is_adjusted=True,
                data_source="test",
            )
        )
        db_session.commit()

        # Stub celery delay so we don't run a worker in unit tests.
        from app.api.routes.market import admin as routes

        class _StubTask:
            @staticmethod
            def delay(*_args, **_kwargs):
                return SimpleNamespace(id="task-stale-123")

        monkeypatch.setattr(routes, "stale_daily", _StubTask)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/market-data/admin/backfill/coverage/stale")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload.get("task_id") == "task-stale-123"
        # Must include BOTH: STALE (>48h) and MISSING (none).
        assert payload.get("stale_candidates") == 2
    finally:
        app.dependency_overrides.pop(get_db, None)
        try:
            infra.redis_client.delete("tracked:all")
            infra.redis_client.delete(TRACKED_ALL_UPDATED_AT_KEY)
        except Exception:
            pass


def test_coverage_snapshot_counts_missing_in_none_bucket(db_session):
    if db_session is None:
        pytest.skip("DB session unavailable")

    tracked = ["FRESH2", "MISSING2"]
    infra.redis_client.set("tracked:all", json.dumps(tracked))
    infra.redis_client.set(TRACKED_ALL_UPDATED_AT_KEY, str(time.time()))
    try:
        db_session.query(PriceData).delete()
        now = datetime.now(timezone.utc)
        db_session.add(
            PriceData(
                symbol="FRESH2",
                date=now - timedelta(hours=1),
                open_price=1,
                high_price=1,
                low_price=1,
                close_price=1,
                adjusted_close=1,
                volume=100,
                interval="1d",
                is_adjusted=True,
                data_source="test",
            )
        )
        db_session.commit()

        snap = coverage_analytics.coverage_snapshot(db_session)
        daily = snap.get("daily") or {}
        buckets = (daily.get("freshness") or {})
        assert sum(int(v) for v in buckets.values()) == 2
        assert int(buckets.get("none") or 0) == 1
        assert int(daily.get("missing") or 0) == 1
    finally:
        try:
            infra.redis_client.delete("tracked:all")
            infra.redis_client.delete(TRACKED_ALL_UPDATED_AT_KEY)
        except Exception:
            pass


