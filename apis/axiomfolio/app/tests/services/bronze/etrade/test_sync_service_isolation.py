"""Cross-tenant isolation pin for :class:`ETradeSyncService`.

Regression pin for the multi-tenancy contract in ``AGENTS.md`` / ``engineering.mdc``:
running an E*TRADE sync for User A must never read, write, mutate, or overwrite
any row belonging to User B — not positions, options, transactions, trades,
dividends, balances, broker accounts, nor OAuth connections.

The test seeds User B with pre-existing rows that look *exactly* like what a
contaminated sync would try to upsert (same symbol, same external_id,
same account_number) and then runs User A's sync against a fake client. If
any query missed its ``user_id`` / ``account_id`` filter, User B's data
would be mutated and the assertion that User B's rows are byte-identical
would fail.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from app.models.account_balance import AccountBalance
from app.models.broker_account import AccountType, BrokerAccount, BrokerType
from app.models.broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from app.models.position import Position, PositionStatus, PositionType
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.bronze.etrade.sync_service import ETradeSyncService
from app.services.oauth.encryption import encrypt


class _FakeClient:
    def __init__(self) -> None:
        self._account_id = "111"
        self._account_key = "keyA"

    def list_accounts(self) -> list[dict[str, Any]]:
        return [
            {
                "accountId": self._account_id,
                "accountIdKey": self._account_key,
                "accountStatus": "ACTIVE",
            }
        ]

    def get_portfolio(self, key: str) -> list[dict[str, Any]]:
        assert key == self._account_key
        return [
            {
                "Product": {"symbol": "AAPL", "securityType": "EQ"},
                "quantity": 5,
                "costPerShare": 100.0,
                "totalCost": 500.0,
                "marketValue": 550.0,
            }
        ]

    def get_transactions(self, key: str) -> list[dict[str, Any]]:
        return [
            {
                "transactionId": "SHARED_TX_ID",
                "transactionType": "BUY",
                "transactionDate": 1_700_000_000_000,
                "amount": -500.0,
                "brokerage": {
                    "product": {"symbol": "AAPL"},
                    "quantity": 5,
                    "price": 100.0,
                    "fee": 0.0,
                },
            }
        ]

    def get_balance(self, key: str) -> dict[str, Any]:
        return {
            "Computed": {"cashBalance": 1000.0},
            "RealTimeValues": {"totalAccountValue": 1550.0},
        }


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


def _etrade_account(session, user: User, account_number: str) -> BrokerAccount:
    a = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.ETRADE,
        account_number=account_number,
        account_name=f"E*TRADE {user.username}",
        account_type=AccountType.TAXABLE,
        currency="USD",
    )
    session.add(a)
    session.flush()
    return a


def _oauth_conn(session, user: User, token: str = "T") -> BrokerOAuthConnection:
    c = BrokerOAuthConnection(
        user_id=user.id,
        broker="etrade_sandbox",
        status=OAuthConnectionStatus.ACTIVE.value,
        access_token_encrypted=encrypt(f"access-{token}"),
        refresh_token_encrypted=encrypt(f"secret-{token}"),
        environment="sandbox",
    )
    session.add(c)
    session.flush()
    return c


def test_sync_does_not_touch_other_users_rows(db_session) -> None:
    # Arrange — two users, both with an E*TRADE account and matching OAuth.
    user_a = _user(db_session, "etrade_isolation_a")
    user_b = _user(db_session, "etrade_isolation_b")
    acct_a = _etrade_account(db_session, user_a, "ETRADE_OAUTH")
    # User B's account deliberately uses the SAME "real" accountId that
    # User A's sync will auto-correct to. If ``_resolve_or_discover``
    # forgot to filter by ``user_id`` it would repoint User A's account
    # onto User B's row.
    acct_b = _etrade_account(db_session, user_b, "111")
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
    txn_b = Transaction(
        account_id=acct_b.id,
        external_id="SHARED_TX_ID",
        symbol="AAPL",
        transaction_type=TransactionType.BUY,
        action="BUY",
        quantity=999,
        trade_price=42.0,
        amount=-41958.0,
        net_amount=-41958.0,
        commission=0,
        currency="USD",
        transaction_date=__import__("datetime").datetime(
            2020, 1, 1, tzinfo=__import__("datetime").timezone.utc
        ),
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
    service = ETradeSyncService(client=_FakeClient())
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

    # User B still has exactly one position, one transaction, zero balances
    # from User A's sync.
    user_b_positions = db_session.query(Position).filter(Position.user_id == user_b.id).all()
    user_b_txns = db_session.query(Transaction).filter(Transaction.account_id == acct_b.id).all()
    user_b_balances = (
        db_session.query(AccountBalance).filter(AccountBalance.user_id == user_b.id).all()
    )
    assert len(user_b_positions) == 1
    assert len(user_b_txns) == 1
    assert len(user_b_balances) == 0

    # User A got the expected new rows under their own user_id.
    user_a_positions = db_session.query(Position).filter(Position.user_id == user_a.id).all()
    assert len(user_a_positions) == 1
    assert user_a_positions[0].account_id == acct_a.id
    user_a_balances = (
        db_session.query(AccountBalance).filter(AccountBalance.user_id == user_a.id).all()
    )
    assert len(user_a_balances) == 1

    # Placeholder auto-correction must NOT have collided with User B's
    # account_number; User A either got a new account_number or remained
    # on the placeholder — but it must still belong to user_a.
    db_session.refresh(acct_a)
    assert acct_a.user_id == user_a.id


def test_load_connection_ignores_other_users_oauth(db_session) -> None:
    """Even if only User B has an ACTIVE E*TRADE connection, a sync for
    User A must fail loudly rather than pick up B's tokens."""

    user_a = _user(db_session, "etrade_conn_iso_a")
    user_b = _user(db_session, "etrade_conn_iso_b")
    acct_a = _etrade_account(db_session, user_a, "ETRADE_OAUTH")
    _oauth_conn(db_session, user_b)  # only User B has a connection

    service = ETradeSyncService()
    with pytest.raises(ConnectionError):
        service.sync_account_comprehensive(account_number=acct_a.account_number, session=db_session)
