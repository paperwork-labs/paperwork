import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.dependencies import evaluate_release_access, require_non_market_access
from app.api.main import app
from app.models.user import UserRole
from app.tests.auth_test_utils import approve_user_for_login_tests


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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_release_policy_authenticated_non_admin_portfolio_allowed():
    user = SimpleNamespace(role=UserRole.ANALYST)
    admin = SimpleNamespace(role=UserRole.OWNER)

    assert evaluate_release_access("market", admin)[0] is True
    assert evaluate_release_access("portfolio", admin)[0] is True

    assert evaluate_release_access("market", user)[0] is True
    assert evaluate_release_access("portfolio", user)[0] is True
    assert evaluate_release_access("other", user)[0] is True


def test_authenticated_non_admin_portfolio_api_allowed(client: TestClient):
    user_username = f"user_{uuid.uuid4().hex[:8]}"
    user_token = _register_and_login(
        client, user_username, "Passw0rd!", f"{user_username}@example.com"
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
    assert portfolio_res.status_code == 200


@pytest.mark.asyncio
async def test_require_non_market_access_admin_bypass():
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
    admin_user = SimpleNamespace(role=UserRole.OWNER)
    result = await require_non_market_access(
        request=request,
        current_user=admin_user,
    )
    assert result is admin_user


@pytest.mark.asyncio
async def test_require_non_market_access_non_admin_portfolio_path():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/portfolio/stocks",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope)
    user = SimpleNamespace(role=UserRole.ANALYST)
    result = await require_non_market_access(
        request=request,
        current_user=user,
    )
    assert result is user
