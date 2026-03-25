from types import SimpleNamespace
import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.api.dependencies import evaluate_release_access, require_non_market_access
from backend.api.main import app
from backend.models.user import UserRole
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
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def _login(client: TestClient, email: str, password: str) -> str:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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


def _set_app_settings(
    client: TestClient,
    admin_token: str,
    *,
    market_only_mode: bool,
    portfolio_enabled: bool,
    strategy_enabled: bool,
) -> None:
    res = client.patch(
        "/api/v1/admin/app-settings",
        json={
            "market_only_mode": market_only_mode,
            "portfolio_enabled": portfolio_enabled,
            "strategy_enabled": strategy_enabled,
        },
        headers=_auth(admin_token),
    )
    assert res.status_code == 200


def test_release_policy_matrix_non_admin_rules():
    app_settings = SimpleNamespace(
        market_only_mode=True,
        portfolio_enabled=False,
        strategy_enabled=False,
    )
    user = SimpleNamespace(role=UserRole.USER)
    admin = SimpleNamespace(role=UserRole.ADMIN)

    # Admin always allowed.
    assert evaluate_release_access("market", admin, app_settings)[0] is True
    assert evaluate_release_access("portfolio", admin, app_settings)[0] is True
    assert evaluate_release_access("strategy", admin, app_settings)[0] is True

    # Non-admin market is always allowed (authenticated).
    assert evaluate_release_access("market", user, app_settings)[0] is True

    # Non-admin portfolio/strategy blocked by market-only.
    ok, reason = evaluate_release_access("portfolio", user, app_settings)
    assert ok is False
    assert reason == "Market-only mode: access restricted"
    ok, reason = evaluate_release_access("strategy", user, app_settings)
    assert ok is False
    assert reason == "Market-only mode: access restricted"

    # Flip market_only off; section flags decide.
    app_settings.market_only_mode = False
    app_settings.portfolio_enabled = True
    app_settings.strategy_enabled = False
    assert evaluate_release_access("portfolio", user, app_settings)[0] is True
    ok, reason = evaluate_release_access("strategy", user, app_settings)
    assert ok is False
    assert reason == "Strategy section is not enabled"


def test_authenticated_non_admin_market_allowed_and_portfolio_locked_by_default(client: TestClient):
    admin_username = f"admin_{uuid.uuid4().hex[:8]}"
    admin_password = "AdminPassw0rd!"
    _register_and_login(client, admin_username, admin_password, f"{admin_username}@example.com")
    _elevate_user_to_admin(admin_username)
    admin_token = _login(client, f"{admin_username}@example.com", admin_password)

    user_username = f"user_{uuid.uuid4().hex[:8]}"
    user_token = _register_and_login(client, user_username, "Passw0rd!", f"{user_username}@example.com")

    try:
        _set_app_settings(
            client,
            admin_token,
            market_only_mode=True,
            portfolio_enabled=False,
            strategy_enabled=False,
        )

        market_res = client.get(
            "/api/v1/market-data/universe/tracked",
            headers=_auth(user_token),
        )
        assert market_res.status_code == 200

        portfolio_res = client.get(
            "/api/v1/portfolio/stocks",
            headers=_auth(user_token),
        )
        assert portfolio_res.status_code == 403
        assert portfolio_res.json().get("detail") == "Market-only mode: access restricted"
    finally:
        _set_app_settings(
            client,
            admin_token,
            market_only_mode=True,
            portfolio_enabled=False,
            strategy_enabled=False,
        )


@pytest.mark.asyncio
async def test_require_non_market_access_admin_bypass_without_app_settings():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/admin/users",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope)
    admin_user = SimpleNamespace(role=UserRole.ADMIN)
    result = await require_non_market_access(
        request=request,
        current_user=admin_user,
        db=None,  # must not be dereferenced for admin bypass
    )
    assert result is admin_user

