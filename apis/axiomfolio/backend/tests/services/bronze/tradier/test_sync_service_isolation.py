"""Cross-tenant isolation pin for :class:`TradierSyncService`.

Mirrors ``backend/tests/services/bronze/etrade/test_sync_service_isolation.py``:
running a Tradier sync for User A must never read, write, mutate, or
overwrite any row belonging to User B — not positions, options,
transactions, trades, dividends, balances, broker accounts, nor OAuth
connections.

The test seeds User B with pre-existing rows that look *exactly* like
what a contaminated sync would try to upsert (same symbol, same
external_id, same account_number) and then runs User A's sync against a
fake client. If any query missed its ``user_id`` / ``account_id``
filter, User B's data would be mutated and the assertion that User B's
rows are byte-identical would fail.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pytest

from backend.models.account_balance import AccountBalance
from backend.models.broker_account import AccountType, BrokerAccount, BrokerType
from backend.models.broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from backend.models.position import Position, PositionStatus, PositionType
from backend.models.transaction import Transaction, TransactionType
from backend.models.user import User
from backend.services.bronze.tradier.sync_service import TradierSyncService
from backend.services.oauth.encryption import encrypt


class _FakeClient:
    """Returns the same payload regardless of which account_id is asked —
    the sync service is responsible for scoping writes correctly."""

    def __init__(self) -> None:
        self._account_id = "111"

    def get_accounts(self) -> List[Dict[str, Any]]:
        return [{"account_number": self._account_id, "status": "ACTIVE"}]

    def get_positions(self, account_id: str) -> List[Dict[str, Any]]:
        assert account_id == self._account_id
        return [
            {
                "symbol": "AAPL",
                "quantity": 5,
                "cost_basis": 500.0,
                "date_acquired": "2024-01-15T00:00:00",
                "id": 1,
            }
        ]

    def get_history(
        self,
        account_id: str,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
        history_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return [
            {
                "amount": -500.0,
                "date": "2024-01-15T10:00:00-05:00",
                "type": "trade",
                "trade": {
                    "commission": 0.0,
                    "description": "BOUGHT AAPL @ 100",
                    "price": 100.0,
                    "quantity": 5,
                    "symbol": "AAPL",
                    "trade_type": "Equity",
                    "transaction_type": "buy",
                },
            }
        ]

    def get_balances(self, account_id: str) -> Dict[str, Any]:
        return {
            "total_cash": 1000.0,
            "total_equity": 1550.0,
            "cash": {"cash_available": 1000.0},
            "margin": {"stock_buying_power": 2000.0},
        }

    def get_gainloss(
        self,
        account_id: str,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return []


def _user(session, name: str) -> User:
    u = User(
        username=name,
        email=f"{name}@example.com",
        password_hash="x",
        is_active=True,
    )
    session.add(u)
    session.flush()
    return u


def _tradier_account(
    session, user: User, account_number: str
) -> BrokerAccount:
    a = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.TRADIER_SANDBOX,
        account_number=account_number,
        account_name=f"Tradier {user.username}",
        account_type=AccountType.TAXABLE,
        currency="USD",
    )
    session.add(a)
    session.flush()
    return a


def _oauth_conn(
    session, user: User, token: str = "T", broker: str = "tradier_sandbox"
) -> BrokerOAuthConnection:
    c = BrokerOAuthConnection(
        user_id=user.id,
        broker=broker,
        status=OAuthConnectionStatus.ACTIVE.value,
        access_token_encrypted=encrypt(f"access-{token}"),
        refresh_token_encrypted=encrypt(f"refresh-{token}"),
        environment="sandbox" if "sandbox" in broker else "live",
    )
    session.add(c)
    session.flush()
    return c


def test_sync_does_not_touch_other_users_rows(db_session) -> None:
    user_a = _user(db_session, "tradier_isolation_a")
    user_b = _user(db_session, "tradier_isolation_b")
    acct_a = _tradier_account(db_session, user_a, "TRADIER_OAUTH")
    # User B's account uses the SAME "real" account_number that User A's
    # sync will auto-correct to. If ``_resolve_or_discover`` forgot to
    # filter by ``user_id`` it would repoint User A's account onto User
    # B's row.
    acct_b = _tradier_account(db_session, user_b, "111")
    _oauth_conn(db_session, user_a, token="A")
    _oauth_conn(db_session, user_b, token="B")

    # User B has pre-existing rows with the same symbols + ids the sync
    # payload uses. These must remain byte-identical after the sync.
    pos_b = Position(
        user_id=user_b.id,
        account_id=acct_b.id,
        symbol="AAPL",
        currency="USD",
        quantity=Decimal("999"),
        instrument_type="STOCK",
        position_type=PositionType.LONG,
        status=PositionStatus.OPEN,
        average_cost=Decimal("42.00"),
        total_cost_basis=Decimal("41958.00"),
    )
    db_session.add(pos_b)
    # A transaction whose external_id could collide if our query lost
    # the account_id filter. The external_id is derived from the fake
    # payload's (date|type|amount|symbol|description) tuple.
    txn_b = Transaction(
        account_id=acct_b.id,
        external_id="2024-01-15T10:00:00-05:00|trade|-500.0|AAPL|BOUGHT AAPL @ 100",
        symbol="AAPL",
        transaction_type=TransactionType.BUY,
        action="buy",
        quantity=5,
        trade_price=100.0,
        amount=-500.0,
        net_amount=-500.0,
        commission=0,
        currency="USD",
        transaction_date=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc),
        description="USER_B_SENTINEL",
        source="SEED",
    )
    db_session.add(txn_b)
    db_session.flush()

    pos_b_id = pos_b.id
    pos_b_qty_before = Decimal(pos_b.quantity)
    pos_b_avg_before = Decimal(pos_b.average_cost)
    txn_b_id = txn_b.id
    txn_b_desc_before = txn_b.description
    txn_b_qty_before = txn_b.quantity
    acct_b_number_before = acct_b.account_number

    # Act — run sync for User A only.
    service = TradierSyncService(client=_FakeClient())
    result = service.sync_account_comprehensive(
        account_number=acct_a.account_number, session=db_session
    )
    assert result["status"] == "success"

    # Assert — User B's rows are untouched.
    db_session.refresh(pos_b)
    db_session.refresh(txn_b)
    db_session.refresh(acct_b)

    assert pos_b.id == pos_b_id, "User B's position row was replaced"
    assert Decimal(pos_b.quantity) == pos_b_qty_before
    assert Decimal(pos_b.average_cost) == pos_b_avg_before
    assert txn_b.id == txn_b_id
    assert txn_b.description == txn_b_desc_before
    assert txn_b.quantity == txn_b_qty_before
    assert acct_b.account_number == acct_b_number_before
    assert acct_b.user_id == user_b.id

    # User B still has exactly one position, one transaction, zero
    # balances from User A's sync.
    user_b_positions = (
        db_session.query(Position).filter(Position.user_id == user_b.id).all()
    )
    user_b_txns = (
        db_session.query(Transaction)
        .filter(Transaction.account_id == acct_b.id)
        .all()
    )
    user_b_balances = (
        db_session.query(AccountBalance)
        .filter(AccountBalance.user_id == user_b.id)
        .all()
    )
    assert len(user_b_positions) == 1
    assert len(user_b_txns) == 1
    assert len(user_b_balances) == 0

    # User A got the expected new rows under their own user_id.
    user_a_positions = (
        db_session.query(Position).filter(Position.user_id == user_a.id).all()
    )
    assert len(user_a_positions) == 1
    assert user_a_positions[0].account_id == acct_a.id
    user_a_balances = (
        db_session.query(AccountBalance)
        .filter(AccountBalance.user_id == user_a.id)
        .all()
    )
    assert len(user_a_balances) == 1

    db_session.refresh(acct_a)
    assert acct_a.user_id == user_a.id


def test_load_connection_ignores_other_users_oauth(db_session) -> None:
    """Even if only User B has an ACTIVE Tradier connection, a sync for
    User A must fail loudly rather than pick up B's tokens.
    """

    user_a = _user(db_session, "tradier_conn_iso_a")
    user_b = _user(db_session, "tradier_conn_iso_b")
    acct_a = _tradier_account(db_session, user_a, "TRADIER_OAUTH")
    _oauth_conn(db_session, user_b)  # only User B has a connection

    service = TradierSyncService()
    with pytest.raises(ConnectionError):
        service.sync_account_comprehensive(
            account_number=acct_a.account_number, session=db_session
        )
