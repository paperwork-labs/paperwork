"""Tests for GET /api/v1/picks/candidates/today pagination."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

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
def picks_user(db_session):
    u = User(
        email="candtoday@example.com",
        username="candtoday",
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


def _seed_today_candidates(db_session, *, n: int) -> datetime:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    for i in range(n):
        db_session.add(
            Candidate(
                symbol=f"S{i:02d}",
                generator_name="g",
                generator_version="v1",
                action_suggestion=PickAction.BUY,
                generated_at=start,
                pick_quality_score=Decimal(str(100 - i)),
                status=CandidateQueueState.DRAFT,
            )
        )
    db_session.commit()
    return start


def test_candidates_today_limit_and_total(client, db_session, picks_user):
    _seed_today_candidates(db_session, n=15)
    _override_db(db_session)
    _override_user(picks_user)
    try:
        r = client.get("/api/v1/picks/candidates/today?limit=10&offset=0")
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 10
        assert body["total"] == 15
        assert body["limit"] == 10
        assert body["offset"] == 0
    finally:
        _restore()


def test_candidates_today_offset(client, db_session, picks_user):
    _seed_today_candidates(db_session, n=15)
    _override_db(db_session)
    _override_user(picks_user)
    try:
        r = client.get("/api/v1/picks/candidates/today?limit=10&offset=5")
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 10
        assert body["total"] == 15
        assert body["items"][0]["ticker"] == "S05"
    finally:
        _restore()


def test_candidates_today_limit_zero_is_422(client, db_session, picks_user):
    _seed_today_candidates(db_session, n=3)
    _override_db(db_session)
    _override_user(picks_user)
    try:
        r = client.get("/api/v1/picks/candidates/today?limit=0")
        assert r.status_code == 422
        r2 = client.get("/api/v1/picks/candidates/today?limit=-1")
        assert r2.status_code == 422
    finally:
        _restore()
