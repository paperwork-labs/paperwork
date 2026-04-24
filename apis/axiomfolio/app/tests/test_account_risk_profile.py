"""Tests for per-account risk-profile service + route.

The rule encoded in every test below: **firm caps are never loosened**.
Per-account overrides can only tighten; any value stricter-than-or-equal
to the firm cap is honoured, anything looser is rejected at write time
and overridden at read time.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

try:
    from app.api.main import app
    from app.api.dependencies import get_current_user
    from app.database import get_db
    from app.models import User, BrokerAccount
    from app.models.account_risk_profile import BrokerAccountRiskProfile
    from app.models.user import UserRole
    from app.models.broker_account import AccountType, BrokerType, SyncStatus
    from app.services.gold.risk.account_risk_profile import (
        AccountNotFoundError,
        apply_override,
        get_effective_limits,
    )
    from app.services.gold.risk.firm_caps import get_firm_caps

    AVAILABLE = True
except Exception:
    AVAILABLE = False


pytestmark = pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except TypeError:
        pytest.skip("TestClient not available")


def _make_user(db_session, *, email: str, username: str) -> User:
    user = User(
        email=email,
        username=username,
        password_hash="dummy",
        role=UserRole.OWNER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_account(db_session, owner: User, *, account_number: str) -> BrokerAccount:
    account = BrokerAccount(
        user_id=owner.id,
        broker=BrokerType.IBKR,
        account_number=account_number,
        account_name="Test IBKR",
        account_type=AccountType.TAXABLE,
        sync_status=SyncStatus.NEVER_SYNCED,
        is_enabled=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def user_a(db_session):
    return _make_user(db_session, email="risk_a@example.com", username="risk_a")


@pytest.fixture
def user_b(db_session):
    return _make_user(db_session, email="risk_b@example.com", username="risk_b")


@pytest.fixture
def account_a(db_session, user_a):
    return _make_account(db_session, user_a, account_number="U_A_01")


@pytest.fixture
def account_b(db_session, user_b):
    return _make_account(db_session, user_b, account_number="U_B_01")


# ---------------------------------------------------------------------------
# Service layer: min() merge + validation
# ---------------------------------------------------------------------------


def test_firm_wins_when_per_account_override_is_looser(db_session, user_a, account_a):
    """A per-account value LOOSER than the firm cap must be rejected at
    write time — loosening is forbidden."""
    firm = get_firm_caps()
    looser = firm.max_position_pct + Decimal("0.01")

    with pytest.raises(ValueError) as exc:
        apply_override(
            db=db_session,
            user_id=user_a.id,
            account_id=account_a.id,
            new_limits={"max_position_pct": looser},
        )
    assert "loosen" in str(exc.value).lower() or "firm cap" in str(exc.value).lower()

    # And the DB stays clean — no row was created for a rejected PUT.
    row = (
        db_session.query(BrokerAccountRiskProfile)
        .filter(BrokerAccountRiskProfile.account_id == account_a.id)
        .one_or_none()
    )
    assert row is None


def test_per_account_wins_when_tighter(db_session, user_a, account_a):
    """A per-account value STRICTER than the firm cap must win at read time."""
    firm = get_firm_caps()
    tighter = firm.max_position_pct / Decimal("2")

    result = apply_override(
        db=db_session,
        user_id=user_a.id,
        account_id=account_a.id,
        new_limits={"max_position_pct": tighter},
    )

    assert result.firm["max_position_pct"] == firm.max_position_pct
    assert result.per_account["max_position_pct"] == tighter
    assert result.effective["max_position_pct"] == tighter

    # Untouched fields inherit the firm cap.
    assert result.effective["max_options_pct"] == firm.max_options_pct
    assert result.per_account["max_options_pct"] is None


def test_invalid_negative_is_rejected(db_session, user_a, account_a):
    """Negative per-account caps are invalid (use 0 for 'block entirely')."""
    with pytest.raises(ValueError) as exc:
        apply_override(
            db=db_session,
            user_id=user_a.id,
            account_id=account_a.id,
            new_limits={"max_position_pct": Decimal("-0.01")},
        )
    assert "negative" in str(exc.value).lower()


def test_cross_tenant_access_is_blocked(db_session, user_a, user_b, account_b):
    """User A cannot see or edit User B's account risk profile."""
    with pytest.raises(AccountNotFoundError):
        get_effective_limits(
            db=db_session, user_id=user_a.id, account_id=account_b.id
        )

    with pytest.raises(AccountNotFoundError):
        apply_override(
            db=db_session,
            user_id=user_a.id,
            account_id=account_b.id,
            new_limits={"max_position_pct": Decimal("0.01")},
        )


def test_put_is_idempotent(db_session, user_a, account_a):
    """Applying the same override twice yields the same state and keeps one row."""
    firm = get_firm_caps()
    payload = {"max_options_pct": firm.max_options_pct / Decimal("2")}

    first = apply_override(
        db=db_session, user_id=user_a.id, account_id=account_a.id, new_limits=payload
    )
    second = apply_override(
        db=db_session, user_id=user_a.id, account_id=account_a.id, new_limits=payload
    )
    assert first.effective == second.effective
    assert first.per_account == second.per_account

    rows = (
        db_session.query(BrokerAccountRiskProfile)
        .filter(BrokerAccountRiskProfile.account_id == account_a.id)
        .all()
    )
    assert len(rows) == 1


def test_unknown_field_rejected(db_session, user_a, account_a):
    with pytest.raises(ValueError) as exc:
        apply_override(
            db=db_session,
            user_id=user_a.id,
            account_id=account_a.id,
            new_limits={"max_position_pct": Decimal("0.01"), "not_a_field": "0.5"},
        )
    assert "unknown" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# Route layer
# ---------------------------------------------------------------------------


def _override_deps(user: User, db_session):
    def _get_db():
        yield db_session

    def _get_user():
        return user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user


def _clear_overrides():
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_get_route_returns_firm_and_effective(client, db_session, user_a, account_a):
    _override_deps(user_a, db_session)
    try:
        resp = client.get(f"/api/v1/accounts/{account_a.id}/risk-profile")
        assert resp.status_code == 200, resp.text
        payload = resp.json()["data"]
        assert payload["account_id"] == account_a.id
        firm = get_firm_caps()
        assert Decimal(payload["firm"]["max_position_pct"]) == firm.max_position_pct
        assert payload["per_account"]["max_position_pct"] is None
        assert Decimal(payload["effective"]["max_position_pct"]) == firm.max_position_pct
    finally:
        _clear_overrides()


def test_put_route_rejects_loosening_with_400(client, db_session, user_a, account_a):
    _override_deps(user_a, db_session)
    try:
        firm = get_firm_caps()
        looser = str(firm.max_position_pct + Decimal("0.01"))
        resp = client.put(
            f"/api/v1/accounts/{account_a.id}/risk-profile",
            json={"max_position_pct": looser},
        )
        assert resp.status_code == 400, resp.text
        detail = resp.json().get("detail", "").lower()
        assert "loosen" in detail or "firm cap" in detail
    finally:
        _clear_overrides()


def test_put_route_blocks_cross_tenant(client, db_session, user_a, user_b, account_b):
    _override_deps(user_a, db_session)
    try:
        resp = client.put(
            f"/api/v1/accounts/{account_b.id}/risk-profile",
            json={"max_position_pct": "0.01"},
        )
        assert resp.status_code == 404, resp.text
    finally:
        _clear_overrides()
