"""
Entitlements API integration tests
==================================

These hit the real FastAPI app via TestClient with overridden dependencies
so we exercise the full request → service → DB → response path. Pure
service-level tests live in ``test_entitlements.py``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

try:
    from app.api.dependencies import get_current_user, get_optional_user
    from app.api.main import app
    from app.database import get_db
    from app.models import User
    from app.models.entitlement import SubscriptionTier
    from app.models.user import UserRole
    from app.services.billing.entitlement_service import EntitlementService

    AVAILABLE = True
except Exception:  # pragma: no cover — only triggers in import-broken envs
    AVAILABLE = False


pytestmark = pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_user(db_session):
    user = User(
        email="enttest@example.com",
        username="enttestuser",
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


def _override(db_session, auth_user):
    def _get_db():
        yield db_session

    def _get_user():
        return auth_user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    app.dependency_overrides[get_optional_user] = _get_user


def _restore():
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_user, None)


# -----------------------------------------------------------------------------
# Catalog
# -----------------------------------------------------------------------------


def test_catalog_is_public_and_returns_features(client, db_session, auth_user):
    _override(db_session, auth_user)
    try:
        r = client.get("/api/v1/entitlements/catalog")
        assert r.status_code == 200
        body = r.json()
        keys = [f["key"] for f in body["features"]]
        # Spot-check a few well-known keys; full completeness is asserted in
        # the catalog unit tests.
        assert "brain.native_chat" in keys
        assert "picks.read" in keys
        assert "execution.tax_aware_exit" in keys
    finally:
        _restore()


def test_catalog_native_chat_is_pro_plus(client, db_session, auth_user):
    """Ladder 3: native chat opens at PRO (with cap); PRO_PLUS removes the cap.

    The historical "native chat is Pro+" assertion from PR #316 was
    updated in the Ladder 3 reshape (PR #388) so the floor is PRO. The
    test name is preserved for grep-ability; the invariant it now locks
    in is that native_chat is a paid feature (not FREE).
    """
    _override(db_session, auth_user)
    try:
        r = client.get("/api/v1/entitlements/catalog")
        body = r.json()
        chat = next(f for f in body["features"] if f["key"] == "brain.native_chat")
        assert chat["min_tier"] == "pro"
    finally:
        _restore()


# -----------------------------------------------------------------------------
# /me
# -----------------------------------------------------------------------------


def test_me_returns_free_for_new_user(client, db_session, auth_user):
    _override(db_session, auth_user)
    try:
        r = client.get("/api/v1/entitlements/me")
        assert r.status_code == 200
        body = r.json()
        assert body["tier"] == "free"
        assert body["status"] == "active"
        assert body["is_active"] is True
        # Pro+ features must be flagged as not allowed for free users.
        chat = next(f for f in body["features"] if f["key"] == "brain.native_chat")
        assert chat["allowed"] is False
    finally:
        _restore()


def test_me_reflects_manual_upgrade(client, db_session, auth_user):
    _override(db_session, auth_user)
    try:
        EntitlementService.manual_set_tier(
            db_session,
            user=auth_user,
            new_tier=SubscriptionTier.PRO_PLUS,
            actor="api_test",
        )
        db_session.commit()

        r = client.get("/api/v1/entitlements/me")
        body = r.json()
        assert body["tier"] == "pro_plus"
        chat = next(f for f in body["features"] if f["key"] == "brain.native_chat")
        assert chat["allowed"] is True
    finally:
        _restore()


# -----------------------------------------------------------------------------
# /check
# -----------------------------------------------------------------------------


def test_check_endpoint_returns_decision(client, db_session, auth_user):
    _override(db_session, auth_user)
    try:
        r = client.post(
            "/api/v1/entitlements/check",
            json={"feature": "brain.native_chat"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["allowed"] is False
        # Ladder 3: native chat opens at PRO.
        assert body["required_tier"] == "pro"
        assert body["current_tier"] == "free"
    finally:
        _restore()


def test_check_endpoint_404s_on_unknown_feature(client, db_session, auth_user):
    _override(db_session, auth_user)
    try:
        r = client.post(
            "/api/v1/entitlements/check",
            json={"feature": "totally.fake.feature"},
        )
        assert r.status_code == 404
    finally:
        _restore()


# -----------------------------------------------------------------------------
# require_feature dependency end-to-end
# -----------------------------------------------------------------------------


def test_require_feature_returns_402_when_blocked(client, db_session, auth_user):
    """Smoke test the dependency factory: mount it on a throwaway route and
    confirm the response is 402 with the structured error body."""
    from fastapi import APIRouter, Depends

    from app.api.dependencies import require_feature

    test_router = APIRouter()

    @test_router.get("/__test_protected_brain_chat")
    def _protected(_user=Depends(require_feature("brain.native_chat"))):
        return {"ok": True}

    app.include_router(test_router)

    _override(db_session, auth_user)
    try:
        r = client.get("/__test_protected_brain_chat")
        assert r.status_code == 402, (
            "402 Payment Required signals 'upgrade' (vs 403 'forbidden') so "
            "the frontend can render an upgrade prompt instead of a security error"
        )
        detail = r.json()["detail"]
        assert detail["error"] == "tier_required"
        assert detail["feature"] == "brain.native_chat"
        assert detail["current_tier"] == "free"
        # Ladder 3: native chat opens at PRO.
        assert detail["required_tier"] == "pro"
    finally:
        _restore()
        # Clean up the throwaway route so it doesn't pollute other tests.
        app.routes[:] = [
            r for r in app.routes if getattr(r, "path", "") != "/__test_protected_brain_chat"
        ]


def test_require_feature_allows_after_upgrade(client, db_session, auth_user):
    from fastapi import APIRouter, Depends

    from app.api.dependencies import require_feature

    test_router = APIRouter()

    @test_router.get("/__test_protected_brain_chat_2")
    def _protected(_user=Depends(require_feature("brain.native_chat"))):
        return {"ok": True}

    app.include_router(test_router)

    EntitlementService.manual_set_tier(
        db_session,
        user=auth_user,
        new_tier=SubscriptionTier.PRO_PLUS,
        actor="api_test",
    )
    db_session.commit()

    _override(db_session, auth_user)
    try:
        r = client.get("/__test_protected_brain_chat_2")
        assert r.status_code == 200
        assert r.json() == {"ok": True}
    finally:
        _restore()
        app.routes[:] = [
            r for r in app.routes if getattr(r, "path", "") != "/__test_protected_brain_chat_2"
        ]
