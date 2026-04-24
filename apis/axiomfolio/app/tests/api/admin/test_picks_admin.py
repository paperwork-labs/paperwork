"""Admin picks validator queue API tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

try:
    from app.api.dependencies import get_current_user, get_db
    from app.api.main import app
    from app.models.picks import Candidate, CandidateQueueState, PickAction
    from app.models.user import User, UserRole

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
def owner_user(db_session):
    u = User(
        email="picksadmin@example.com",
        username="picksadmin",
        password_hash="x",
        role=UserRole.OWNER,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def analyst_user(db_session):
    u = User(
        email="picksanalyst@example.com",
        username="picksanalyst",
        password_hash="x",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _make_candidate(db_session, *, state: CandidateQueueState = CandidateQueueState.DRAFT):
    c = Candidate(
        symbol="NVDA",
        generator_name="test_gen",
        generator_version="v1",
        action_suggestion=PickAction.BUY,
        rationale_summary="Thesis here",
        status=state,
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


def test_approve_happy_path(client, db_session, owner_user):
    c = _make_candidate(db_session)
    _override_db(db_session)
    _override_user(owner_user)
    try:
        r = client.post(f"/api/v1/admin/picks/{c.id}/approve")
        assert r.status_code == 200
        body = r.json()
        assert body["state"] == "APPROVED"
        db_session.refresh(c)
        assert c.status == CandidateQueueState.APPROVED
    finally:
        _restore()


def test_approve_409_when_published(client, db_session, owner_user):
    c = _make_candidate(db_session, state=CandidateQueueState.PUBLISHED)
    _override_db(db_session)
    _override_user(owner_user)
    try:
        r = client.post(f"/api/v1/admin/picks/{c.id}/approve")
        assert r.status_code == 409
    finally:
        _restore()


def test_reject_from_draft(client, db_session, owner_user):
    c = _make_candidate(db_session)
    _override_db(db_session)
    _override_user(owner_user)
    try:
        r = client.post(
            f"/api/v1/admin/picks/{c.id}/reject",
            json={"reason": "bad signal"},
        )
        assert r.status_code == 200
        assert r.json()["state"] == "REJECTED"
    finally:
        _restore()


def test_reject_409_from_published(client, db_session, owner_user):
    c = _make_candidate(db_session, state=CandidateQueueState.PUBLISHED)
    _override_db(db_session)
    _override_user(owner_user)
    try:
        r = client.post(f"/api/v1/admin/picks/{c.id}/reject", json={"reason": "nope"})
        assert r.status_code == 409
    finally:
        _restore()


def test_publish_from_approved(client, db_session, owner_user):
    c = _make_candidate(db_session, state=CandidateQueueState.APPROVED)
    _override_db(db_session)
    _override_user(owner_user)
    try:
        r = client.post(f"/api/v1/admin/picks/{c.id}/publish")
        assert r.status_code == 200
        assert r.json()["state"] == "PUBLISHED"
        assert r.json()["published_at"] is not None
    finally:
        _restore()


def test_publish_409_from_draft(client, db_session, owner_user):
    c = _make_candidate(db_session)
    _override_db(db_session)
    _override_user(owner_user)
    try:
        r = client.post(f"/api/v1/admin/picks/{c.id}/publish")
        assert r.status_code == 409
    finally:
        _restore()


def test_patch_allowed_in_draft(client, db_session, owner_user):
    c = _make_candidate(db_session)
    _override_db(db_session)
    _override_user(owner_user)
    try:
        r = client.patch(
            f"/api/v1/admin/picks/{c.id}",
            json={
                "ticker": "AMD",
                "action": "hold",
                "thesis": "Updated",
                "target_price": "150.25",
                "stop_loss": "140",
            },
        )
        assert r.status_code == 200
        assert r.json()["ticker"] == "AMD"
        assert r.json()["action"] == "HOLD"
        assert r.json()["thesis"] == "Updated"
    finally:
        _restore()


def test_patch_forbidden_after_approved(client, db_session, owner_user):
    c = _make_candidate(db_session, state=CandidateQueueState.APPROVED)
    _override_db(db_session)
    _override_user(owner_user)
    try:
        r = client.patch(f"/api/v1/admin/picks/{c.id}", json={"ticker": "QQQ"})
        assert r.status_code == 409
    finally:
        _restore()


def test_non_admin_forbidden(client, db_session, analyst_user):
    c = _make_candidate(db_session)
    _override_db(db_session)
    _override_user(analyst_user)
    try:
        r = client.get("/api/v1/admin/picks/queue?state=DRAFT")
        assert r.status_code == 403
    finally:
        _restore()
