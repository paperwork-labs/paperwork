"""Tests for :class:`CoinbaseSyncService` (injected fake client, no HTTP)."""

from __future__ import annotations

from datetime import timezone
from decimal import Decimal
from typing import Any, Dict, FrozenSet, List, Optional

import pytest

from backend.models.broker_account import AccountType, BrokerAccount, BrokerType
from backend.models.broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from backend.models.position import Position
from backend.models.trade import Trade
from backend.models.user import User
from backend.services.bronze.coinbase.sync_service import CoinbaseSyncService
from backend.services.oauth.encryption import encrypt


class FakeCoinbaseClient:
    """Minimal stand-in matching methods ``CoinbaseSyncService`` calls."""

    def __init__(
        self,
        *,
        user: Dict[str, Any],
        accounts: List[Dict[str, Any]],
        transactions_by_account: Dict[str, List[Dict[str, Any]]],
        fail_list_accounts: bool = False,
        fail_txn_account_ids: Optional[FrozenSet[str]] = None,
    ) -> None:
        self._user = user
        self._accounts = accounts
        self._tx = transactions_by_account
        self.fail_list_accounts = fail_list_accounts
        self._fail_txn_account_ids = fail_txn_account_ids or frozenset()

    def get_user(self) -> Dict[str, Any]:
        return dict(self._user)

    def list_all_accounts(self) -> List[Dict[str, Any]]:
        if self.fail_list_accounts:
            from backend.services.bronze.coinbase.client import CoinbaseAPIError

            raise CoinbaseAPIError("forced", permanent=True, status=500)
        return [dict(a) for a in self._accounts]

    def list_transactions_for_account(self, account_id: str) -> List[Dict[str, Any]]:
        if account_id in self._fail_txn_account_ids:
            from backend.services.bronze.coinbase.client import CoinbaseAPIError

            raise CoinbaseAPIError(
                "forced txn list failure",
                permanent=False,
                status=500,
            )
        rows = self._tx.get(account_id, [])
        return [dict(t) for t in rows]


def _make_user(session, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def _make_coinbase_account(
    session,
    user: User,
    account_number: str = "COINBASE_OAUTH",
) -> BrokerAccount:
    acct = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.COINBASE,
        account_number=account_number,
        account_name=f"Coinbase {user.username}",
        account_type=AccountType.TAXABLE,
        currency="USD",
    )
    session.add(acct)
    session.flush()
    return acct


def _make_oauth(session, user: User) -> BrokerOAuthConnection:
    conn = BrokerOAuthConnection(
        user_id=user.id,
        broker="coinbase",
        status=OAuthConnectionStatus.ACTIVE.value,
        access_token_encrypted=encrypt("fake-coinbase-access"),
        refresh_token_encrypted=encrypt("fake-coinbase-refresh"),
        environment="live",
    )
    session.add(conn)
    session.flush()
    return conn


def _btc_wallet() -> Dict[str, Any]:
    return {
        "id": "wallet-btc",
        "type": "wallet",
        "currency": {"code": "BTC", "name": "Bitcoin"},
        "balance": {"amount": "0.30", "currency": "BTC"},
    }


def _usd_fiat() -> Dict[str, Any]:
    return {
        "id": "wallet-usd",
        "type": "fiat",
        "currency": {"code": "USD", "name": "USD"},
        "balance": {"amount": "1000.00", "currency": "USD"},
    }


def _eth_wallet() -> Dict[str, Any]:
    return {
        "id": "wallet-eth",
        "type": "wallet",
        "currency": {"code": "ETH", "name": "Ethereum"},
        "balance": {"amount": "1.0", "currency": "ETH"},
    }


def _buy_txn() -> Dict[str, Any]:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "type": "buy",
        "status": "completed",
        "created_at": "2024-01-01T12:00:00+00:00",
        "amount": {"amount": "0.50", "currency": "BTC"},
        "native_amount": {"amount": "-25000.00", "currency": "USD"},
        "description": "Bought BTC",
        "buy": {"fee": {"amount": "2.00", "currency": "USD"}},
    }


def _sell_txn() -> Dict[str, Any]:
    return {
        "id": "22222222-2222-2222-2222-222222222222",
        "type": "sell",
        "status": "completed",
        "created_at": "2024-02-01T12:00:00+00:00",
        "amount": {"amount": "-0.20", "currency": "BTC"},
        "native_amount": {"amount": "12000.00", "currency": "USD"},
        "description": "Sold BTC",
        "sell": {"fee": {"amount": "1.00", "currency": "USD"}},
    }


def test_sync_happy_path(db_session) -> None:
    user = _make_user(db_session, "cb_happy")
    account = _make_coinbase_account(db_session, user)
    _make_oauth(db_session, user)
    fake = FakeCoinbaseClient(
        user={"id": "coinbase-user-1", "name": "Test"},
        accounts=[_btc_wallet(), _usd_fiat()],
        transactions_by_account={
            "wallet-btc": [_buy_txn(), _sell_txn()],
        },
    )
    service = CoinbaseSyncService(client=fake)
    result = service.sync_account_comprehensive(
        account_number=account.account_number, session=db_session
    )
    assert result["status"] == "success"
    assert result["positions_synced"] == 1
    assert result["transactions_synced"] == 2
    assert result["trades_synced"] == 2
    assert result["balances_synced"] == 1

    db_session.refresh(account)
    assert account.account_number == "coinbase-user-1"

    pos = db_session.query(Position).filter(Position.account_id == account.id).one()
    assert pos.symbol == "BTC-USD"
    assert Decimal(pos.quantity) == Decimal("0.30")

    fills = (
        db_session.query(Trade)
        .filter(Trade.account_id == account.id, Trade.status == "FILLED")
        .order_by(Trade.execution_time)
        .all()
    )
    assert len(fills) == 2
    assert fills[0].side == "BUY" and fills[0].is_opening is True
    assert fills[1].side == "SELL" and fills[1].is_opening is False

    closed = (
        db_session.query(Trade)
        .filter(Trade.account_id == account.id, Trade.status == "CLOSED_LOT")
        .all()
    )
    assert len(closed) >= 1


def test_sync_idempotent_second_run(db_session) -> None:
    user = _make_user(db_session, "cb_idem")
    account = _make_coinbase_account(db_session, user)
    _make_oauth(db_session, user)
    fake = FakeCoinbaseClient(
        user={"id": "u2", "name": "T"},
        accounts=[_btc_wallet(), _usd_fiat()],
        transactions_by_account={"wallet-btc": [_buy_txn()]},
    )
    service = CoinbaseSyncService(client=fake)
    service.sync_account_comprehensive(
        account_number=account.account_number, session=db_session
    )
    r2 = service.sync_account_comprehensive(account_number="u2", session=db_session)
    assert r2["status"] == "success"
    assert r2["transactions_synced"] == 0
    assert r2["transactions_skipped"] >= 1


def test_sync_scopes_user_id_kwarg(db_session) -> None:
    user_a = _make_user(db_session, "cb_scope_a")
    user_b = _make_user(db_session, "cb_scope_b")
    acct_a = _make_coinbase_account(db_session, user_a, account_number="SHARED")
    _make_coinbase_account(db_session, user_b, account_number="SHARED")
    _make_oauth(db_session, user_a)
    _make_oauth(db_session, user_b)
    fake = FakeCoinbaseClient(
        user={"id": "scoped-user", "name": "S"},
        accounts=[_btc_wallet()],
        transactions_by_account={},
    )
    service = CoinbaseSyncService(client=fake)
    result = service.sync_account_comprehensive(
        account_number="SHARED", session=db_session, user_id=user_a.id
    )
    assert result["status"] == "success"
    n_a = (
        db_session.query(Position)
        .filter(Position.user_id == user_a.id, Position.account_id == acct_a.id)
        .count()
    )
    n_b = db_session.query(Position).filter(Position.user_id == user_b.id).count()
    assert n_a == 1
    assert n_b == 0


def test_sync_empty_payload(db_session) -> None:
    user = _make_user(db_session, "cb_empty")
    account = _make_coinbase_account(db_session, user)
    _make_oauth(db_session, user)
    fake = FakeCoinbaseClient(
        user={"id": "empty-user", "name": "E"},
        accounts=[],
        transactions_by_account={},
    )
    service = CoinbaseSyncService(client=fake)
    result = service.sync_account_comprehensive(
        account_number=account.account_number, session=db_session
    )
    assert result["status"] == "success"
    assert result["positions_synced"] == 0
    assert result["transactions_synced"] == 0


def test_sync_partial_when_some_wallets_tx_fail(db_session) -> None:
    user = _make_user(db_session, "cb_partial_tx")
    account = _make_coinbase_account(db_session, user)
    _make_oauth(db_session, user)
    fake = FakeCoinbaseClient(
        user={"id": "coinbase-partial-1", "name": "P"},
        accounts=[_btc_wallet(), _eth_wallet(), _usd_fiat()],
        transactions_by_account={
            "wallet-eth": [_buy_txn()],
        },
        fail_txn_account_ids=frozenset({"wallet-btc"}),
    )
    service = CoinbaseSyncService(client=fake)
    result = service.sync_account_comprehensive(
        account_number=account.account_number, session=db_session
    )
    assert result["status"] == "partial"
    assert result.get("wallets_tx_failed", 0) >= 1
    assert result.get("wallets_tx_ok", 0) >= 1


def test_parse_iso_dt_naive_string_is_utc() -> None:
    from backend.services.bronze.coinbase.sync_service import _parse_iso_dt

    dt = _parse_iso_dt("2026-01-15T12:00:00")
    assert dt.tzinfo is not None
    assert dt.tzinfo == timezone.utc


def test_sync_api_error(db_session) -> None:
    user = _make_user(db_session, "cb_err")
    account = _make_coinbase_account(db_session, user)
    _make_oauth(db_session, user)
    fake = FakeCoinbaseClient(
        user={"id": "e1", "name": "E"},
        accounts=[],
        transactions_by_account={},
        fail_list_accounts=True,
    )
    service = CoinbaseSyncService(client=fake)
    result = service.sync_account_comprehensive(
        account_number=account.account_number, session=db_session
    )
    assert result["status"] == "error"


def test_sync_requires_user_id_on_collision(db_session) -> None:
    u1 = _make_user(db_session, "cb_col_a")
    u2 = _make_user(db_session, "cb_col_b")
    _make_coinbase_account(db_session, u1, "DUPE")
    _make_coinbase_account(db_session, u2, "DUPE")
    _make_oauth(db_session, u1)
    _make_oauth(db_session, u2)
    fake = FakeCoinbaseClient(
        user={"id": "x", "name": "X"}, accounts=[], transactions_by_account={}
    )
    service = CoinbaseSyncService(client=fake)
    with pytest.raises(ValueError) as exc:
        service.sync_account_comprehensive(account_number="DUPE", session=db_session)
    assert "user_id" in str(exc.value).lower()


def test_sync_fails_without_oauth(db_session) -> None:
    user = _make_user(db_session, "cb_no_oauth")
    account = _make_coinbase_account(db_session, user)
    service = CoinbaseSyncService()
    with pytest.raises(ConnectionError):
        service.sync_account_comprehensive(
            account_number=account.account_number, session=db_session
        )


def test_trade_execution_id_short_when_uuid(db_session) -> None:
    from backend.services.bronze.coinbase.sync_service import _trade_execution_id

    tid = "8250fe29-f5ef-5fc5-8302-0fbacf6be51e"
    eid = _trade_execution_id(tid)
    assert eid.startswith("cb_")
    assert len(eid) <= 50
