"""Tests for the auth system — register, login, me, logout, delete, CSRF."""

import pytest
from httpx import AsyncClient

from tests.conftest import FakeRedis

pytestmark = pytest.mark.asyncio

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"
LOGOUT_URL = "/api/v1/auth/logout"
DELETE_URL = "/api/v1/auth/account"

VALID_USER = {
    "email": "test@example.com",
    "password": "SecurePass1",
    "full_name": "Test User",
}


def _get_session_cookie(response) -> str | None:
    for header_name, header_value in response.headers.multi_items():
        if header_name.lower() == "set-cookie" and "session=" in header_value:
            for part in header_value.split(";"):
                part = part.strip()
                if part.startswith("session="):
                    return part.split("=", 1)[1]
    return None


async def _register_user(client: AsyncClient, user: dict | None = None) -> dict:
    """Helper to register and return response data + cookie."""
    payload = user or VALID_USER
    resp = await client.post(REGISTER_URL, json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["success"] is True
    session_cookie = _get_session_cookie(resp)
    assert session_cookie is not None
    csrf_token = data["data"]["csrf_token"]
    return {
        "response": resp,
        "data": data,
        "session_cookie": session_cookie,
        "csrf_token": csrf_token,
        "user": data["data"]["user"],
    }


# ── Register ──────────────────────────────────────────────────────────────


async def test_register_success(client: AsyncClient):
    result = await _register_user(client)
    user = result["user"]
    assert user["email"] == "test@example.com"
    assert user["full_name"] == "Test User"
    assert user["auth_provider"] == "local"
    assert user["email_verified"] is False
    assert len(user["referral_code"]) > 0
    assert result["csrf_token"]


async def test_register_duplicate_email(client: AsyncClient):
    await _register_user(client)
    resp = await client.post(REGISTER_URL, json=VALID_USER)
    assert resp.status_code == 409
    assert resp.json()["error"] == "An account with this email already exists"


async def test_register_invalid_email(client: AsyncClient):
    resp = await client.post(
        REGISTER_URL,
        json={"email": "not-an-email", "password": "SecurePass1", "full_name": "Test"},
    )
    assert resp.status_code == 422


async def test_register_weak_password_too_short(client: AsyncClient):
    resp = await client.post(
        REGISTER_URL,
        json={"email": "a@b.com", "password": "Short1", "full_name": "Test"},
    )
    assert resp.status_code == 422


async def test_register_weak_password_no_uppercase(client: AsyncClient):
    resp = await client.post(
        REGISTER_URL,
        json={"email": "a@b.com", "password": "nouppercase1", "full_name": "Test"},
    )
    assert resp.status_code == 422


async def test_register_weak_password_no_number(client: AsyncClient):
    resp = await client.post(
        REGISTER_URL,
        json={"email": "a@b.com", "password": "NoNumberHere", "full_name": "Test"},
    )
    assert resp.status_code == 422


async def test_register_short_name(client: AsyncClient):
    resp = await client.post(
        REGISTER_URL,
        json={"email": "a@b.com", "password": "SecurePass1", "full_name": "A"},
    )
    assert resp.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────


async def test_login_success(client: AsyncClient):
    await _register_user(client)
    resp = await client.post(
        LOGIN_URL, json={"email": "test@example.com", "password": "SecurePass1"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["user"]["email"] == "test@example.com"
    assert data["data"]["csrf_token"]
    assert _get_session_cookie(resp) is not None


async def test_login_wrong_password(client: AsyncClient):
    await _register_user(client)
    resp = await client.post(
        LOGIN_URL, json={"email": "test@example.com", "password": "WrongPass1"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "Invalid email or password"


async def test_login_nonexistent_email(client: AsyncClient):
    resp = await client.post(
        LOGIN_URL, json={"email": "nobody@example.com", "password": "SecurePass1"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "Invalid email or password"


# ── Me ────────────────────────────────────────────────────────────────────


async def test_me_success(client: AsyncClient):
    result = await _register_user(client)
    resp = await client.get(
        ME_URL, cookies={"session": result["session_cookie"]}
    )
    assert resp.status_code == 200
    user = resp.json()["data"]["user"]
    assert user["email"] == "test@example.com"
    assert user["full_name"] == "Test User"


async def test_me_no_cookie(client: AsyncClient):
    resp = await client.get(ME_URL)
    assert resp.status_code == 401


async def test_me_invalid_session(client: AsyncClient):
    resp = await client.get(ME_URL, cookies={"session": "bogus-token"})
    assert resp.status_code == 401


# ── Logout ────────────────────────────────────────────────────────────────


async def test_logout_success(client: AsyncClient, fake_redis: FakeRedis):
    result = await _register_user(client)
    resp = await client.post(
        LOGOUT_URL,
        cookies={"session": result["session_cookie"]},
        headers={"X-CSRF-Token": result["csrf_token"]},
    )
    assert resp.status_code == 200

    me_resp = await client.get(
        ME_URL, cookies={"session": result["session_cookie"]}
    )
    assert me_resp.status_code == 401


# ── Delete Account ────────────────────────────────────────────────────────


async def test_delete_account_success(client: AsyncClient, fake_redis: FakeRedis):
    result = await _register_user(client)
    resp = await client.delete(
        DELETE_URL,
        cookies={"session": result["session_cookie"]},
        headers={"X-CSRF-Token": result["csrf_token"]},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["message"] == "Account deleted"

    me_resp = await client.get(
        ME_URL, cookies={"session": result["session_cookie"]}
    )
    assert me_resp.status_code == 401


# ── CSRF Protection ──────────────────────────────────────────────────────


async def test_logout_missing_csrf(client: AsyncClient):
    result = await _register_user(client)
    resp = await client.post(
        LOGOUT_URL,
        cookies={"session": result["session_cookie"]},
    )
    assert resp.status_code == 403
    assert "CSRF" in resp.json()["error"]


async def test_logout_wrong_csrf(client: AsyncClient):
    result = await _register_user(client)
    resp = await client.post(
        LOGOUT_URL,
        cookies={"session": result["session_cookie"]},
        headers={"X-CSRF-Token": "wrong-token"},
    )
    assert resp.status_code == 403


async def test_delete_missing_csrf(client: AsyncClient):
    result = await _register_user(client)
    resp = await client.delete(
        DELETE_URL,
        cookies={"session": result["session_cookie"]},
    )
    assert resp.status_code == 403


# ── Cookie properties ────────────────────────────────────────────────────


async def test_register_rate_limited(client: AsyncClient):
    for i in range(5):
        resp = await client.post(
            REGISTER_URL,
            json={
                "email": f"ratelimit{i}@example.com",
                "password": "SecurePass1",
                "full_name": "Rate Limiter",
            },
        )
        assert resp.status_code == 201, f"Request {i+1} should succeed: {resp.text}"

    resp = await client.post(
        REGISTER_URL,
        json={
            "email": "ratelimit5@example.com",
            "password": "SecurePass1",
            "full_name": "Rate Limiter",
        },
    )
    assert resp.status_code == 429


async def test_register_sets_httponly_cookie(client: AsyncClient):
    resp = await client.post(REGISTER_URL, json=VALID_USER)
    assert resp.status_code == 201
    cookie_headers = [
        v for k, v in resp.headers.multi_items()
        if k.lower() == "set-cookie" and "session=" in v
    ]
    assert len(cookie_headers) == 1
    cookie = cookie_headers[0].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie
