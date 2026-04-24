"""API tests for notify-me broker launch endpoint."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.main import app
from app.database import get_db
from app.models.user import User, UserRole


@pytest.fixture(scope="module")
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("FastAPI TestClient not available")


def _make_user(db_session) -> User:
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"notify_{suffix}@example.com",
        username=f"notify_{suffix}",
        password_hash="dummy",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_user(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    return _make_user(db_session)


@pytest.fixture
def _wire_overrides(db_session, auth_user):
    if db_session is None:
        yield
        return

    def _get_db():
        yield db_session

    def _get_user():
        return auth_user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def test_notify_unknown_slug_returns_404(
    client: TestClient, db_session, auth_user, _wire_overrides
):
    if db_session is None:
        pytest.skip("database not configured")

    res = client.post(
        "/api/v1/notify/broker-launch",
        json={
            "broker_slug": "not-a-real-broker-slug-xyz",
            "email": "subscriber@example.com",
        },
    )
    assert res.status_code == 404


def test_notify_non_coming_soon_slug_returns_400(
    client: TestClient, db_session, auth_user, _wire_overrides
):
    """Live (`available`) broker must not accept notify-me."""

    if db_session is None:
        pytest.skip("database not configured")

    res = client.post(
        "/api/v1/notify/broker-launch",
        json={
            "broker_slug": "schwab",
            "email": "subscriber@example.com",
        },
    )
    assert res.status_code == 400


def test_notify_valid_slug_returns_200_and_sets_queued_true(
    client: TestClient, db_session, auth_user, _wire_overrides
):
    if db_session is None:
        pytest.skip("database not configured")

    res = client.post(
        "/api/v1/notify/broker-launch",
        json={
            "broker_slug": "etrade",
            "email": "subscriber@example.com",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["queued"] is True
    assert body["persisted"] is False
