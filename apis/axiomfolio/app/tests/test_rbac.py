import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.tests.auth_test_utils import approve_user_for_login_tests


@pytest.fixture(scope="module")
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("FastAPI TestClient not available in this env")


def _register_and_login(client, username: str, password: str, email: str):
    r = client.post("/api/v1/auth/register", json={"username": username, "email": email, "password": password})
    assert r.status_code == 200
    approve_user_for_login_tests(username)
    r2 = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200
    token = r2.json()["access_token"]
    return token


def test_me_includes_role(client):
    u = f"user_{uuid.uuid4().hex[:6]}"
    token = _register_and_login(client, u, "Passw0rd!", f"{u}@example.com")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert "role" in body
    assert body["username"] == u


def test_admin_guard_blocks_non_admin(client):
    u = f"user_{uuid.uuid4().hex[:6]}"
    token = _register_and_login(client, u, "Passw0rd!", f"{u}@example.com")
    r = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in (401, 403)



