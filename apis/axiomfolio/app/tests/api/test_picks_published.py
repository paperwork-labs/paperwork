"""Subscriber picks published feed tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

try:
    from app.api.main import app
    from app.api.dependencies import get_current_user, get_db
    from app.models import Candidate, CandidateQueueState
    from app.models.picks import PickAction
    from app.models.user import User, UserRole
    from app.services.billing.entitlement_service import EntitlementService
    from app.models.entitlement import SubscriptionTier

    AVAILABLE = True
except Exception:  # pragma: no cover
    AVAILABLE = False

pytestmark = pytest.mark.skipif(not AVAILABLE, reason="App import failed")


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _override_db(db_session):
    def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db


def _override_user(user: User):
    def _get_user():
        return user

    app.dependency_overrides[get_current_user] = _get_user


def _restore():
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def free_user(db_session):
    u = User(
        email="pickfree@example.com",
        username="pickfree",
        password_hash="x",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    EntitlementService.get_or_create(db_session, u)
    db_session.commit()
    return u


@pytest.fixture
def pro_user(db_session):
    u = User(
        email="pickpro@example.com",
        username="pickpro",
        password_hash="x",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    EntitlementService.manual_set_tier(
        db_session,
        user=u,
        new_tier=SubscriptionTier.PRO,
        actor="pytest",
        note="picks feed test",
    )
    db_session.commit()
    return u


def _published(
    db_session, *, symbol: str = "NVDA", generator: str = "src_a", published_at=None
):
    from datetime import datetime, timezone

    when = published_at or datetime.now(timezone.utc)
    c = Candidate(
        symbol=symbol,
        generator_name=generator,
        generator_version="v1",
        action_suggestion=PickAction.BUY,
        rationale_summary="Pub thesis",
        status=CandidateQueueState.PUBLISHED,
        published_at=when,
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


def test_free_user_preview_flag(client, db_session, free_user):
    _published(db_session, symbol="A", generator="g1")
    _published(db_session, symbol="B", generator="g2")
    _override_db(db_session)
    _override_user(free_user)
    try:
        r = client.get("/api/v1/picks/published")
        assert r.status_code == 200
        body = r.json()
        assert body["is_preview"] is True
        assert len(body["items"]) <= 2
    finally:
        _restore()


def test_pro_user_full_feed(client, db_session, pro_user):
    _published(db_session, symbol="X", generator="g1")
    _published(db_session, symbol="Y", generator="g2")
    _override_db(db_session)
    _override_user(pro_user)
    try:
        r = client.get("/api/v1/picks/published")
        assert r.status_code == 200
        body = r.json()
        assert body["is_preview"] is False
        assert len(body["items"]) == 2
    finally:
        _restore()


def test_anonymous_unauthenticated(client, db_session):
    _published(db_session)
    _override_db(db_session)
    try:
        r = client.get("/api/v1/picks/published")
        assert r.status_code in (401, 403)
    finally:
        _restore()
