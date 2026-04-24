"""Tests for :class:`app.services.portfolio.plaid.sync_service.PlaidSyncService`.

These are **integration** tests: they use the `db_session` fixture to
exercise SQLAlchemy models, but stub the Plaid SDK via a fake
``client_factory`` so no network calls are issued.

Coverage:
* ``sync_account_comprehensive`` returns ``status=success`` for a happy
  path, writing one ``Position`` and one aggregator-sourced ``TaxLot``.
* Plaid ``ITEM_LOGIN_REQUIRED`` flips the PlaidConnection to
  ``needs_reauth`` and returns ``status=error`` with ``error_code``.
* Cross-tenant protection: an ``account_number`` owned by user B cannot
  be synced when the caller passes ``user_id=userA.id``.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pytest

try:
    from app.models.broker_account import (
        AccountStatus,
        AccountType,
        BrokerAccount,
        BrokerType,
    )
    from app.models.plaid_connection import (
        PlaidConnection,
        PlaidConnectionStatus,
    )
    from app.models.position import Position
    from app.models.tax_lot import TaxLot, TaxLotSource
    from app.models.user import User, UserRole
    from app.services.portfolio.plaid.client import PlaidAPIError
    from app.services.portfolio.plaid.sync_service import PlaidSyncService
    AVAILABLE = True
except Exception:  # pragma: no cover
    AVAILABLE = False


pytestmark = pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mk_user(db_session, *, email: str, username: str) -> User:
    user = User(
        email=email,
        username=username,
        password_hash="x",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _mk_plaid_conn(
    db_session,
    *,
    user_id: int,
    item_id: str = "item-abc",
    status: str = PlaidConnectionStatus.ACTIVE.value,
) -> PlaidConnection:
    conn = PlaidConnection(
        user_id=user_id,
        item_id=item_id,
        access_token_encrypted="ciphertext-placeholder",
        institution_id="ins_1",
        institution_name="Test Bank",
        environment="sandbox",
        status=status,
    )
    db_session.add(conn)
    db_session.flush()
    return conn


def _mk_plaid_broker_account(
    db_session,
    *,
    user_id: int,
    plaid_account_id: str = "acct-1",
) -> BrokerAccount:
    acct = BrokerAccount(
        user_id=user_id,
        broker=BrokerType.UNKNOWN_BROKER,
        account_number=plaid_account_id,
        account_name="Test 401k",
        account_type=AccountType.IRA,
        auto_discovered=True,
        status=AccountStatus.ACTIVE,
        is_primary=False,
        is_enabled=True,
        connection_source="plaid",
    )
    db_session.add(acct)
    db_session.flush()
    return acct


# ---------------------------------------------------------------------------
# Fake Plaid client
# ---------------------------------------------------------------------------


class _FakeClientOK:
    """Happy-path stub — returns one holding with non-zero quantity."""

    def __init__(self, *, accounts: Optional[List[Dict]] = None) -> None:
        self._accounts = accounts or [{"account_id": "acct-1"}]
        self.closed = False

    def get_holdings(self, access_token_ct: str) -> Dict:
        assert access_token_ct == "ciphertext-placeholder"
        return {
            "accounts": self._accounts,
            "holdings": [
                {
                    "account_id": "acct-1",
                    "security_id": "sec-aapl",
                    "quantity": 10.0,
                    "institution_price": 180.0,
                    "institution_value": 1800.0,
                }
            ],
            "securities": [
                {
                    "security_id": "sec-aapl",
                    "ticker_symbol": "AAPL",
                    "type": "equity",
                    "name": "Apple Inc.",
                }
            ],
        }

    def close(self) -> None:
        self.closed = True


class _FakeClientReauth:
    def get_holdings(self, access_token_ct: str) -> Dict:
        raise PlaidAPIError(
            "login required",
            error_code="ITEM_LOGIN_REQUIRED",
            error_type="ITEM_ERROR",
            display_message="Please relink your account",
        )

    def close(self) -> None:  # noqa: D401
        return None


class _FakeClientTransient:
    def get_holdings(self, access_token_ct: str) -> Dict:
        raise PlaidAPIError(
            "rate limited",
            error_code="RATE_LIMIT_EXCEEDED",
            error_type="RATE_LIMIT_EXCEEDED",
        )

    def close(self) -> None:
        return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_sync_account_happy_path_writes_position_and_aggregator_lot(db_session):
    user = _mk_user(db_session, email="u1@example.com", username="u1")
    _mk_plaid_conn(db_session, user_id=user.id)
    acct = _mk_plaid_broker_account(db_session, user_id=user.id)

    service = PlaidSyncService(client_factory=_FakeClientOK)
    result = service.sync_account_comprehensive(
        acct.account_number, db_session, user_id=user.id
    )

    assert result["status"] == "success", result
    assert result["pipeline"]["written"] == 1
    assert result["pipeline"]["errors"] == 0

    position = (
        db_session.query(Position)
        .filter(Position.user_id == user.id, Position.symbol == "AAPL")
        .one()
    )
    assert float(position.quantity) == 10.0
    lot = (
        db_session.query(TaxLot)
        .filter(TaxLot.user_id == user.id, TaxLot.symbol == "AAPL")
        .one()
    )
    assert lot.source == TaxLotSource.AGGREGATOR
    assert lot.cost_per_share is None, "aggregator lots must NOT synthesize basis"
    assert lot.cost_basis is None
    assert lot.gain_loss_available is False


def test_sync_account_item_login_required_marks_needs_reauth(db_session):
    user = _mk_user(db_session, email="u2@example.com", username="u2")
    conn = _mk_plaid_conn(db_session, user_id=user.id, item_id="item-reauth")
    acct = _mk_plaid_broker_account(
        db_session, user_id=user.id, plaid_account_id="acct-reauth"
    )

    service = PlaidSyncService(client_factory=_FakeClientReauth)
    result = service.sync_account_comprehensive(
        acct.account_number, db_session, user_id=user.id
    )

    assert result["status"] == "error"
    assert result["error_code"] == "ITEM_LOGIN_REQUIRED"

    db_session.refresh(conn)
    assert conn.status == PlaidConnectionStatus.NEEDS_REAUTH.value
    assert "ITEM_LOGIN_REQUIRED" in (conn.last_error or "")


def test_sync_account_transient_error_marks_error_not_reauth(db_session):
    user = _mk_user(db_session, email="u3@example.com", username="u3")
    conn = _mk_plaid_conn(db_session, user_id=user.id, item_id="item-err")
    acct = _mk_plaid_broker_account(
        db_session, user_id=user.id, plaid_account_id="acct-err"
    )

    service = PlaidSyncService(client_factory=_FakeClientTransient)
    result = service.sync_account_comprehensive(
        acct.account_number, db_session, user_id=user.id
    )

    assert result["status"] == "error"
    assert result["error_code"] == "RATE_LIMIT_EXCEEDED"
    db_session.refresh(conn)
    assert conn.status == PlaidConnectionStatus.ERROR.value


def test_sync_rejects_cross_tenant_account_number(db_session):
    user_a = _mk_user(db_session, email="ua@example.com", username="ua")
    user_b = _mk_user(db_session, email="ub@example.com", username="ub")
    _mk_plaid_conn(db_session, user_id=user_b.id, item_id="item-b")
    acct_b = _mk_plaid_broker_account(
        db_session, user_id=user_b.id, plaid_account_id="acct-shared"
    )

    service = PlaidSyncService(client_factory=_FakeClientOK)
    # User A tries to sync user B's account — defensive scoping must refuse.
    result = service.sync_account_comprehensive(
        acct_b.account_number, db_session, user_id=user_a.id
    )

    assert result["status"] == "error"
    assert "not found" in result["error"].lower()
