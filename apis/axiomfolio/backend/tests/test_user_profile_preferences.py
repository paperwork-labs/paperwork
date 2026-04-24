import uuid

import pytest

from backend.tests.auth_test_utils import approve_user_for_login_tests

try:
    from fastapi.testclient import TestClient
    from backend.api.main import app

    FASTAPI_AVAILABLE = True
except Exception:
    FASTAPI_AVAILABLE = False


@pytest.fixture(scope="module")
def client():
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI TestClient not available in this env")
    try:
        return TestClient(app, raise_server_exceptions=False)
    except TypeError:
        pytest.skip("Starlette TestClient incompatible in this runtime")


def _register_and_login(client: "TestClient", username: str, password: str, email: str):
    r = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password, "full_name": "Test User"},
    )
    assert r.status_code == 200
    approve_user_for_login_tests(username)
    r2 = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200
    return r2.json()["access_token"]


def test_me_includes_preferences_and_has_password(client):
    u = f"user_{uuid.uuid4().hex[:6]}"
    token = _register_and_login(client, u, "Passw0rd!", f"{u}@example.com")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["username"] == u
    assert "timezone" in body
    assert "currency_preference" in body
    assert "notification_preferences" in body
    assert "ui_preferences" in body
    assert body.get("has_password") is True


def test_update_email_requires_current_password_when_password_exists(client):
    u = f"user_{uuid.uuid4().hex[:6]}"
    pw = "Passw0rd!"
    token = _register_and_login(client, u, pw, f"{u}@example.com")

    # Without current_password -> 400
    r = client.put(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": f"{u}+new@example.com"},
    )
    assert r.status_code == 400

    # Wrong password -> 400
    r2 = client.put(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": f"{u}+new@example.com", "current_password": "wrongpw"},
    )
    assert r2.status_code == 400

    # Correct password -> 200 and /me reflects new email
    r3 = client.put(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": f"{u}+new@example.com", "current_password": pw},
    )
    assert r3.status_code == 200
    assert r3.json()["email"] == f"{u}+new@example.com"


def test_update_preferences_persists(client):
    u = f"user_{uuid.uuid4().hex[:6]}"
    token = _register_and_login(client, u, "Passw0rd!", f"{u}@example.com")

    payload = {
        "timezone": "America/New_York",
        "currency_preference": "usd",
        "ui_preferences": {"color_mode_preference": "system", "table_density": "compact"},
    }
    r = client.put(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert r.status_code == 200

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["timezone"] == "America/New_York"
    assert body["currency_preference"] == "USD"
    assert (body.get("ui_preferences") or {}).get("color_mode_preference") == "system"
    assert (body.get("ui_preferences") or {}).get("table_density") == "compact"


def test_change_password_allows_login_with_new_password(client):
    u = f"user_{uuid.uuid4().hex[:6]}"
    old_pw = "Passw0rd!"
    new_pw = "NewPassw0rd!"
    email = f"{u}@example.com"
    token = _register_and_login(client, u, old_pw, email)

    r = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": old_pw, "new_password": new_pw},
    )
    assert r.status_code == 200

    # Old password should fail
    bad = client.post("/api/v1/auth/login", json={"email": email, "password": old_pw})
    assert bad.status_code == 401

    # New password should work
    good = client.post("/api/v1/auth/login", json={"email": email, "password": new_pw})
    assert good.status_code == 200


