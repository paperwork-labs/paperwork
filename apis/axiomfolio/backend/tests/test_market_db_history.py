from fastapi.testclient import TestClient
from backend.api.main import app
from backend.api.dependencies import get_admin_user

client = TestClient(app, raise_server_exceptions=False)


def test_db_history_requires_admin():
    resp = client.get("/api/v1/market-data/admin/db/history", params={"symbol": "ZZZZ", "interval": "1d"})
    assert resp.status_code in (401, 403)


def test_db_history_empty_ok():
    # Should return 200 with empty bars for unknown symbol
    app.dependency_overrides[get_admin_user] = object
    try:
        resp = client.get("/api/v1/market-data/admin/db/history", params={"symbol": "ZZZZ", "interval": "1d"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "ZZZZ"
        assert isinstance(data["bars"], list)
    finally:
        app.dependency_overrides.pop(get_admin_user, None)


