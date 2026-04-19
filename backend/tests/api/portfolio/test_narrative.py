"""API tests for portfolio daily narrative endpoints."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_current_user, get_portfolio_user
from backend.api.main import app
from backend.database import get_db
from backend.models.narrative import PortfolioNarrative
from backend.models.user import User, UserRole


@pytest.fixture(scope="module")
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("FastAPI TestClient not available")


@pytest.fixture
def auth_user(db_session):
    """Approved user inserted via the test session.

    We bypass the register/login/approve dance because the goal of these tests
    is to exercise the narrative endpoints, not the auth flow. Other tests
    that rely on the full auth roundtrip have proven brittle when interacting
    with the per-test savepoint pattern + httpx cookie jar quirks; the
    upstream auth tests cover that path.
    """

    if db_session is None:
        pytest.skip("database not configured")
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"narr_{suffix}@example.com",
        username=f"narr_{suffix}",
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


@pytest.fixture(autouse=True)
def _wire_overrides(db_session, auth_user):
    """Pin get_db to the test session and short-circuit the user dep."""

    if db_session is None:
        yield
        return

    def _get_db():
        yield db_session

    def _get_user():
        return auth_user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    app.dependency_overrides[get_portfolio_user] = _get_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_portfolio_user, None)


def test_narrative_latest_404_when_missing(client: TestClient, db_session, auth_user):
    if db_session is None:
        pytest.skip("database not configured")
    res = client.get("/api/v1/portfolio/narrative/latest")
    assert res.status_code == 404


def test_narrative_latest_returns_row(client: TestClient, db_session, auth_user):
    if db_session is None:
        pytest.skip("database not configured")
    row = PortfolioNarrative(
        user_id=auth_user.id,
        narrative_date=date(2026, 4, 1),
        text="Hello **world**",
        summary_data={"ok": True},
        provider="stub",
        model="stub",
        prompt_hash="e" * 64,
        is_fallback=False,
    )
    db_session.add(row)
    db_session.commit()

    res = client.get("/api/v1/portfolio/narrative/latest")
    assert res.status_code == 200
    body = res.json()
    assert body["text"] == "Hello **world**"
    assert body["provider"] == "stub"
    assert body["is_fallback"] is False


def test_narrative_by_date_404(client: TestClient, db_session, auth_user):
    if db_session is None:
        pytest.skip("database not configured")
    res = client.get(
        "/api/v1/portfolio/narrative",
        params={"date": "2020-01-01"},
    )
    assert res.status_code == 404
