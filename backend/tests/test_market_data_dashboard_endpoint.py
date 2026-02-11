import uuid

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


@pytest.fixture(scope="module")
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("FastAPI TestClient not available in this env")


def _register_and_login(client: TestClient, username: str, password: str, email: str) -> str:
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert reg.status_code == 200
    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def _login(client: TestClient, username: str, password: str) -> str:
    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def _elevate_user_to_admin(username: str) -> None:
    from backend.database import SessionLocal
    from backend.models.user import User, UserRole

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        assert user is not None
        user.role = UserRole.ADMIN
        db.commit()
    finally:
        db.close()


def test_market_dashboard_endpoint_returns_summary_shape(client: TestClient):
    username = f"admin_{uuid.uuid4().hex[:8]}"
    password = "AdminPassw0rd!"
    _register_and_login(client, username, password, f"{username}@example.com")
    _elevate_user_to_admin(username)
    token = _login(client, username, password)

    res = client.get(
        "/api/v1/market-data/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "generated_at" in body
    assert "tracked_count" in body
    assert "snapshot_count" in body
    assert "coverage" in body
    assert "regime" in body
    assert "leaders" in body
    assert "setups" in body
    assert "sector_momentum" in body
    assert "action_queue" in body
    assert isinstance(body["leaders"], list)
    assert isinstance(body["sector_momentum"], list)
    assert isinstance(body["action_queue"], list)
