import json

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.dependencies import get_admin_user

client = TestClient(app, raise_server_exceptions=False)


def test_market_data_audit_requires_admin():
    resp = client.get("/api/v1/market-data/admin/market-audit")
    assert resp.status_code in (401, 403)


def test_market_data_audit_reads_cached_payload(monkeypatch):
    from backend.api.routes import market_data as routes

    class _RedisStub:
        def get(self, key):
            if key == "market_audit:last":
                return json.dumps({"schema_version": 1, "tracked_total": 3})
            return None

    class _StubService:
        def __init__(self):
            self.redis_client = _RedisStub()

    app.dependency_overrides[get_admin_user] = object
    monkeypatch.setattr(routes, "MarketDataService", _StubService)
    try:
        resp = client.get("/api/v1/market-data/admin/market-audit")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["audit"]["schema_version"] == 1
        assert payload["audit"]["tracked_total"] == 3
    finally:
        app.dependency_overrides.pop(get_admin_user, None)
