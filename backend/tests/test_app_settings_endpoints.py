import uuid

import pytest

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.tests.auth_test_utils import approve_user_for_login_tests


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
    approve_user_for_login_tests(username)
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
    # Imported inside the function to satisfy test DB safety checks in conftest.
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


def test_app_settings_get_requires_authenticated_user(client: TestClient):
    username = f"user_{uuid.uuid4().hex[:8]}"
    token = _register_and_login(client, username, "Passw0rd!", f"{username}@example.com")
    res = client.get(
        "/api/v1/app-settings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body.get("market_only_mode"), bool)
    assert isinstance(body.get("portfolio_enabled"), bool)
    assert isinstance(body.get("strategy_enabled"), bool)


def test_admin_app_settings_endpoints_block_non_admin(client: TestClient):
    username = f"user_{uuid.uuid4().hex[:8]}"
    token = _register_and_login(client, username, "Passw0rd!", f"{username}@example.com")

    get_res = client.get(
        "/api/v1/admin/app-settings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_res.status_code == 403

    patch_res = client.patch(
        "/api/v1/admin/app-settings",
        json={"market_only_mode": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_res.status_code == 403


def test_admin_can_update_market_only_mode(client: TestClient):
    username = f"admin_{uuid.uuid4().hex[:8]}"
    password = "AdminPassw0rd!"
    _register_and_login(client, username, password, f"{username}@example.com")
    _elevate_user_to_admin(username)

    admin_token = _login(client, username, password)

    initial = client.get(
        "/api/v1/admin/app-settings",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert initial.status_code == 200
    assert isinstance(initial.json().get("market_only_mode"), bool)
    assert isinstance(initial.json().get("portfolio_enabled"), bool)
    assert isinstance(initial.json().get("strategy_enabled"), bool)

    updated = client.patch(
        "/api/v1/admin/app-settings",
        json={"market_only_mode": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert updated.status_code == 200
    assert updated.json()["market_only_mode"] is False

    public_view = client.get(
        "/api/v1/app-settings",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert public_view.status_code == 200
    assert public_view.json()["market_only_mode"] is False

    section_update = client.patch(
        "/api/v1/admin/app-settings",
        json={"portfolio_enabled": True, "strategy_enabled": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert section_update.status_code == 200
    assert section_update.json()["portfolio_enabled"] is True
    assert section_update.json()["strategy_enabled"] is True

    # Restore default to reduce cross-test coupling.
    restore = client.patch(
        "/api/v1/admin/app-settings",
        json={
            "market_only_mode": True,
            "portfolio_enabled": False,
            "strategy_enabled": False,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert restore.status_code == 200
    assert restore.json()["market_only_mode"] is True
    assert restore.json()["portfolio_enabled"] is False
    assert restore.json()["strategy_enabled"] is False
