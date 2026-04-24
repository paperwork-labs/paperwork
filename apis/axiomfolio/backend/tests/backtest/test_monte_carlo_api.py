"""
Integration tests for POST /api/v1/backtest/monte-carlo.

Requires Postgres (``TEST_DATABASE_URL``). Service-level tests are marked
``no_db`` in ``test_monte_carlo.py`` so they can run without a database.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.dependencies import get_current_user, get_optional_user
from backend.api.main import app
from backend.database import get_db
from backend.models import User
from backend.models.entitlement import SubscriptionTier
from backend.models.user import UserRole
from backend.services.backtest.monte_carlo import MIN_SAMPLES
from backend.services.billing.entitlement_service import EntitlementService


def _mc_json_body() -> dict:
    # Minimal valid payload: uniform small returns, length == MIN_SAMPLES.
    return {
        "trade_returns": [0.01] * MIN_SAMPLES,
        "n_simulations": 200,
        "initial_capital": "100000",
    }


def test_cross_tenant_isolation(db_session):
    """User B (free) cannot run the simulator; user A (Pro+) can.

    When ``strategy_id`` loading is added, it must verify
    ``strategy.user_id == current_user.id`` — today the body is
    ``extra=forbid`` so ``strategy_id`` cannot be smuggled in.
    """
    client = TestClient(app, raise_server_exceptions=False)

    user_b = User(
        email="mc_isolation_b@example.com",
        username="mc_isolation_b",
        password_hash="dummy",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(user_b)
    db_session.commit()
    db_session.refresh(user_b)

    def _get_db():
        yield db_session

    def _get_user_b():
        return user_b

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user_b
    app.dependency_overrides[get_optional_user] = _get_user_b
    try:
        r_b = client.post("/api/v1/backtest/monte-carlo", json=_mc_json_body())
        assert r_b.status_code == 402
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_optional_user, None)

    user_a = User(
        email="mc_isolation_a@example.com",
        username="mc_isolation_a",
        password_hash="dummy",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(user_a)
    db_session.commit()
    db_session.refresh(user_a)

    # Monte Carlo is gated to QUANT_DESK in the Ladder 3 catalog.
    EntitlementService.manual_set_tier(
        db_session,
        user=user_a,
        new_tier=SubscriptionTier.QUANT_DESK,
        actor="pytest_monte_carlo_api",
    )
    db_session.commit()

    def _get_user_a():
        return user_a

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user_a
    app.dependency_overrides[get_optional_user] = _get_user_a
    try:
        r_a = client.post("/api/v1/backtest/monte-carlo", json=_mc_json_body())
        assert r_a.status_code == 200
        assert r_a.json()["mode"] == "single"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_optional_user, None)


def test_rejects_unscoped_strategy_id_field(db_session):
    """Regression: reject unknown keys so ``strategy_id`` cannot bypass scoping."""
    client = TestClient(app, raise_server_exceptions=False)

    user = User(
        email="mc_strategy_guard@example.com",
        username="mc_strategy_guard",
        password_hash="dummy",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    # Monte Carlo is gated to QUANT_DESK in the Ladder 3 catalog.
    EntitlementService.manual_set_tier(
        db_session,
        user=user,
        new_tier=SubscriptionTier.QUANT_DESK,
        actor="pytest_monte_carlo_api",
    )
    db_session.commit()

    def _get_db():
        yield db_session

    def _get_user():
        return user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    app.dependency_overrides[get_optional_user] = _get_user
    body = _mc_json_body()
    body["strategy_id"] = 123
    try:
        r = client.post("/api/v1/backtest/monte-carlo", json=body)
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_optional_user, None)
