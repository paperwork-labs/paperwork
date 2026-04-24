from fastapi.testclient import TestClient

from app.api.main import app
from app.api.dependencies import get_market_data_viewer
from app.models.user import UserRole


def _viewer_override():
    class _DummyUser:
        id = 1
        role = UserRole.OWNER
        is_active = True
        email = "viewer@example.com"

    return _DummyUser()


def test_technical_snapshots_endpoint_returns_rows(monkeypatch):
    from app.api.routes.market import snapshots as routes
    from app.database import get_db
    from app.models.market_data import MarketSnapshot
    from app.models.market_tracked_plan import MarketTrackedPlan

    app.dependency_overrides[get_market_data_viewer] = _viewer_override

    # Stub DB session + tracked universe + query chain (join + window subquery path)
    class _FakeSnapshotQuery:
        def join(self, *_args, **_kwargs):
            return self

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            r = MarketSnapshot()
            r.symbol = "AAA"
            r.analysis_type = "technical_snapshot"
            r.current_price = 10.0
            r.sma_50 = 9.0
            r.stage_label = "2B"
            return [r]

    class _FakePlanQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return []

    class _FakeDB:
        def query(self, model):
            if model is MarketTrackedPlan:
                return _FakePlanQuery()
            return _FakeSnapshotQuery()

    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: ["AAA"])

    app.dependency_overrides[get_db] = lambda: _FakeDB()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/snapshots?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["rows"][0]["symbol"] == "AAA"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_technical_snapshots_endpoint_picks_latest_row_per_symbol(monkeypatch):
    from datetime import datetime, timedelta, timezone

    from app.api.routes.market import snapshots as routes
    from app.database import get_db
    from app.models.market_data import MarketSnapshot
    from app.models.market_tracked_plan import MarketTrackedPlan

    app.dependency_overrides[get_market_data_viewer] = _viewer_override

    now = datetime.now(timezone.utc)

    class _FakeSnapshotQuery:
        def join(self, *_args, **_kwargs):
            return self

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def all(self):
            a_new = MarketSnapshot()
            a_new.symbol = "AAA"
            a_new.analysis_type = "technical_snapshot"
            a_new.analysis_timestamp = now
            a_new.current_price = 20.0

            b = MarketSnapshot()
            b.symbol = "BBB"
            b.analysis_type = "technical_snapshot"
            b.analysis_timestamp = now
            b.current_price = 30.0

            # SQL window path returns one row per symbol (latest by analysis_timestamp).
            return [a_new, b]

    class _FakePlanQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return []

    class _FakeDB:
        def query(self, model):
            if model is MarketTrackedPlan:
                return _FakePlanQuery()
            return _FakeSnapshotQuery()

    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: ["AAA", "BBB"])
    app.dependency_overrides[get_db] = lambda: _FakeDB()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/snapshots?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        row_by_symbol = {r["symbol"]: r for r in data["rows"]}
        assert row_by_symbol["AAA"]["current_price"] == 20.0
        assert row_by_symbol["BBB"]["current_price"] == 30.0
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)


def test_snapshot_history_batch_returns_histories_per_symbol():
    from datetime import date

    from app.database import get_db
    from app.models.market_data import MarketSnapshotHistory

    app.dependency_overrides[get_market_data_viewer] = _viewer_override

    d1 = date(2024, 1, 2)
    d2 = date(2024, 1, 3)

    class _FakeHistoryRow:
        def __init__(self, symbol: str, as_of: date, stage: str):
            self.symbol = symbol
            self.analysis_type = "technical_snapshot"
            self.as_of_date = as_of
            self.stage_label = stage
            self.current_price = 100.0

    class _FakeHistoryQuery:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def all(self):
            return list(self._rows)

    class _FakeDB:
        def query(self, model):
            assert model is MarketSnapshotHistory
            return _FakeHistoryQuery(
                [
                    _FakeHistoryRow("AAA", d2, "2B"),
                    _FakeHistoryRow("AAA", d1, "2A"),
                    _FakeHistoryRow("BBB", d2, "3A"),
                ]
            )

    app.dependency_overrides[get_db] = lambda: _FakeDB()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/v1/market-data/snapshots/history/batch",
            params={"symbols": "AAA,BBB", "days": 90},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["counts"]["AAA"] == 2
        assert data["counts"]["BBB"] == 1
        aaa = data["histories"]["AAA"]
        assert len(aaa) == 2
        assert aaa[0]["as_of_date"] == "2024-01-03"
        assert aaa[0]["stage_label"] == "2B"
        assert data["histories"]["BBB"][0]["stage_label"] == "3A"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_market_data_viewer, None)

