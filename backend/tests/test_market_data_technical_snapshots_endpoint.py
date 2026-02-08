from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.dependencies import get_optional_user


def test_technical_snapshots_endpoint_returns_rows(monkeypatch):
    from backend.api.routes import market_data as routes
    from backend.models.market_data import MarketSnapshot

    # Avoid auth requirements
    app.dependency_overrides[get_optional_user] = lambda: None

    # Stub DB session + tracked universe + query chain
    class _FakeQuery:
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

    class _FakeDB:
        def query(self, _model):
            return _FakeQuery()

    monkeypatch.setattr(routes, "tracked_symbols", lambda _db, redis_client=None: ["AAA"])

    app.dependency_overrides[routes.get_db] = lambda: _FakeDB()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/market-data/snapshots?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["rows"][0]["symbol"] == "AAA"
    finally:
        app.dependency_overrides.pop(routes.get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)


