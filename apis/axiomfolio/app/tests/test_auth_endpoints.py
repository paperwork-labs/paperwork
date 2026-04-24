import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.user import User
from app.tests.auth_test_utils import (
    approve_user_for_login_tests,
    approve_user_only_for_login_tests,
)

try:
    from fastapi.testclient import TestClient

    from app.api.main import app
    from app.database import get_db

    FASTAPI_AVAILABLE = True
except Exception:
    FASTAPI_AVAILABLE = False


@pytest.fixture(autouse=True)
def _bind_api_to_test_session(db_session):
    """Bind FastAPI get_db to the pytest db_session so HTTP and ORM share state."""
    if not FASTAPI_AVAILABLE:
        yield
        return

    def _override():
        try:
            yield db_session
        finally:
            pass  # db_session fixture owns lifecycle

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="module")
def client():
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI TestClient not available in this env")
    try:
        return TestClient(app, raise_server_exceptions=False)
    except TypeError:
        pytest.skip("Starlette TestClient incompatible in this runtime")


def test_auth_health(client):
    r = client.get("/api/v1/auth/health")
    assert r.status_code == 200
    assert r.json().get("status") == "healthy"


def test_register_and_login(client, db_session):
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "TestPassw0rd!"

    # Register
    r_reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": "Test User",
        },
    )
    # Either created (200) or already exists (400) if test re-runs against same DB
    assert r_reg.status_code in (200, 400)
    if r_reg.status_code == 200:
        reg_body = r_reg.json()
        assert reg_body.get("is_approved") is False
        assert "message" in reg_body
        assert "approval" in reg_body["message"].lower()

    approve_user_for_login_tests(username, db_session)

    # Login
    r_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r_login.status_code == 200
    data = r_login.json()
    assert isinstance(data.get("access_token"), str) and data.get("token_type") == "bearer"
    token = data["access_token"]

    # Verify /me with token
    r_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r_me.status_code == 200
    me = r_me.json()
    assert me.get("username") == username


def test_login_rejects_unverified_password_user(client, db_session):
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "TestPassw0rd!"

    r_reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": "Test User",
        },
    )
    assert r_reg.status_code == 200
    approve_user_only_for_login_tests(username, db_session)

    r_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r_login.status_code == 403
    assert r_login.json().get("detail") == "Please verify your email before signing in"


def test_refresh_rotates_and_second_refresh_succeeds(client, db_session):
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "TestPassw0rd!"

    r_reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": "Test User",
        },
    )
    assert r_reg.status_code == 200
    approve_user_for_login_tests(username, db_session)

    r_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r_login.status_code == 200
    # The refresh cookie is set with `path=/api/v1/auth`. httpx's persistent
    # cookie jar in the TestClient is unreliable about replaying path-scoped
    # cookies on subpath requests; pass it explicitly so the test exercises
    # the cookie-auth flow rather than the cookie-jar implementation detail.
    refresh_cookie = r_login.cookies.get("refresh_token")
    assert refresh_cookie

    r1 = client.post("/api/v1/auth/refresh", cookies={"refresh_token": refresh_cookie})
    assert r1.status_code == 200
    assert isinstance(r1.json().get("access_token"), str)
    rotated_cookie = r1.cookies.get("refresh_token")
    assert rotated_cookie

    r2 = client.post("/api/v1/auth/refresh", cookies={"refresh_token": rotated_cookie})
    assert r2.status_code == 200
    assert isinstance(r2.json().get("access_token"), str)


def test_refresh_grace_accepts_prior_family_concurrent_race(client, db_session):
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "TestPassw0rd!"

    r_reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": "Test User",
        },
    )
    assert r_reg.status_code == 200
    approve_user_for_login_tests(username, db_session)

    r_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r_login.status_code == 200
    stale_refresh = r_login.cookies.get("refresh_token")
    assert stale_refresh

    # Pass the cookie explicitly — see same note in the previous test.
    r_rotate = client.post("/api/v1/auth/refresh", cookies={"refresh_token": stale_refresh})
    assert r_rotate.status_code == 200

    other = TestClient(app, raise_server_exceptions=False)
    r_grace = other.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": stale_refresh},
    )
    assert r_grace.status_code == 200
    assert isinstance(r_grace.json().get("access_token"), str)


def test_refresh_prior_family_rejected_after_grace_window(client, db_session):
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "TestPassw0rd!"

    r_reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": "Test User",
        },
    )
    assert r_reg.status_code == 200
    approve_user_for_login_tests(username, db_session)

    r_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r_login.status_code == 200
    stale_refresh = r_login.cookies.get("refresh_token")
    assert stale_refresh

    r_rotate = client.post("/api/v1/auth/refresh", cookies={"refresh_token": stale_refresh})
    assert r_rotate.status_code == 200

    user = db_session.query(User).filter(User.username == username).first()
    assert user is not None
    user.previous_refresh_token_rotated_at = datetime.now(UTC) - timedelta(seconds=11)
    db_session.commit()

    other = TestClient(app, raise_server_exceptions=False)
    r_replay = other.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": stale_refresh},
    )
    assert r_replay.status_code == 401
