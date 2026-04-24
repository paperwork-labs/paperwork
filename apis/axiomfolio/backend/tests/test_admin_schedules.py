from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_admin_schedules_readonly_mode():
    # Endpoint requires admin; without token expect 401, but ensure route exists
    resp = client.get("/api/v1/admin/schedules")
    assert resp.status_code in (401, 403)


