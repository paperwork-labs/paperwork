"""Cross-tenant isolation for :class:`CoinbaseSyncService`."""

from __future__ import annotations

import copy
from decimal import Decimal
from typing import Any, Dict, List

import pytest

from backend.models.broker_account import AccountType, BrokerAccount, BrokerType
from backend.models.broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from backend.models.position import Position
from backend.models.transaction import Transaction
from backend.models.user import User
from backend.services.bronze.coinbase.sync_service import CoinbaseSyncService
from backend.services.oauth.encryption import encrypt


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


def _cb_acct(session, user: User, num: str) -> BrokerAccount:
    a = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.COINBASE,
        account_number=num,
        account_name="CB",
        account_type=AccountType.TAXABLE,
        currency="USD",
    )
    session.add(a)
    session.flush()
    return a


def _conn(session, user: User) -> None:
    session.add(
        BrokerOAuthConnection(
            user_id=user.id,
            broker="coinbase",
            status=OAuthConnectionStatus.ACTIVE.value,
            access_token_encrypted=encrypt("tok"),
            refresh_token_encrypted=encrypt("ref"),
            environment="live",
        )
    )
    session.flush()


class _Fake:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = payload

    def get_user(self) -> Dict[str, Any]:
        return copy.deepcopy(self._payload["user"])

    def list_all_accounts(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self._payload["accounts"])

    def list_transactions_for_account(self, account_id: str) -> List[Dict[str, Any]]:
        return copy.deepcopy(self._payload["tx"].get(account_id, []))


@pytest.fixture
def payload_a() -> Dict[str, Any]:
    return {
        "user": {"id": "user-a-cb", "name": "A"},
        "accounts": [
            {
                "id": "w-a",
                "type": "wallet",
                "currency": {"code": "BTC"},
                "balance": {"amount": "1", "currency": "BTC"},
            },
            {
                "id": "f-a",
                "type": "fiat",
                "currency": {"code": "USD"},
                "balance": {"amount": "100", "currency": "USD"},
            },
        ],
        "tx": {
            "w-a": [
                {
                    "id": "ta-1",
                    "type": "buy",
                    "status": "completed",
                    "created_at": "2024-01-02T00:00:00+00:00",
                    "amount": {"amount": "1", "currency": "BTC"},
                    "native_amount": {"amount": "-40000", "currency": "USD"},
                    "description": "x",
                }
            ]
        },
    }


def test_user_b_rows_untouched_after_user_a_sync(db_session, payload_a) -> None:
    ua = _user(db_session, "cb_iso_a")
    ub = _user(db_session, "cb_iso_b")
    acct_a = _cb_acct(db_session, ua, "COINBASE_OAUTH")
    acct_b = _cb_acct(db_session, ub, "COINBASE_OAUTH")
    _conn(db_session, ua)
    _conn(db_session, ub)

    b_pos_before = (
        db_session.query(Position)
        .filter(Position.user_id == ub.id, Position.account_id == acct_b.id)
        .all()
    )
    b_tx_before = (
        db_session.query(Transaction)
        .filter(Transaction.account_id == acct_b.id)
        .all()
    )
    snap_b_pos = [(p.symbol, Decimal(p.quantity)) for p in b_pos_before]
    snap_b_tx = [t.external_id for t in b_tx_before]

    svc = CoinbaseSyncService(client=_Fake(payload_a))
    svc.sync_account_comprehensive(
        account_number=acct_a.account_number,
        session=db_session,
        user_id=ua.id,
    )

    b_pos_after = (
        db_session.query(Position)
        .filter(Position.user_id == ub.id, Position.account_id == acct_b.id)
        .all()
    )
    b_tx_after = (
        db_session.query(Transaction)
        .filter(Transaction.account_id == acct_b.id)
        .all()
    )
    assert [(p.symbol, Decimal(p.quantity)) for p in b_pos_after] == snap_b_pos
    assert [t.external_id for t in b_tx_after] == snap_b_tx
