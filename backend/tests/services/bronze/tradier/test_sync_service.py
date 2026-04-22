"""Happy-path tests for :class:`TradierSyncService`.

These tests drive the sync service end-to-end against an injected fake
Tradier client — no network, no HTTP, no real OAuth 2.0 token exchange.
Credentials are satisfied by inserting a synthetic
:class:`BrokerOAuthConnection` row with encrypted tokens. We still use
the real ``db_session`` fixture so Postgres enum casting, unique
constraints, and ``options_enabled`` updates are exercised for real.

Mirrors ``backend/tests/services/bronze/etrade/test_sync_service.py``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

import pytest

from backend.models.broker_account import AccountType, BrokerAccount, BrokerType
from backend.models.broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from backend.models.options import Option
from backend.models.position import Position, PositionStatus, PositionType
from backend.models.trade import Trade
from backend.models.transaction import Dividend, Transaction, TransactionType
from backend.models.user import User
from backend.services.bronze.tradier.sync_service import TradierSyncService
from backend.services.oauth.encryption import encrypt


class FakeTradierClient:
    """In-memory stand-in for :class:`TradierBronzeClient`."""

    def __init__(
        self,
        *,
        accounts: List[Dict[str, Any]],
        positions: List[Dict[str, Any]],
        history: List[Dict[str, Any]],
        balances: Dict[str, Any],
        gainloss: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self._accounts = accounts
        self._positions = positions
        self._history = history
        self._balances = balances
        self._gainloss = gainloss or []
        self.calls: List[str] = []

    def get_accounts(self) -> List[Dict[str, Any]]:
        self.calls.append("get_accounts")
        return list(self._accounts)

    def get_positions(self, account_id: str) -> List[Dict[str, Any]]:
        self.calls.append(f"get_positions:{account_id}")
        return list(self._positions)

    def get_history(
        self,
        account_id: str,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
        history_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        self.calls.append(f"get_history:{account_id}")
        return list(self._history)

    def get_balances(self, account_id: str) -> Dict[str, Any]:
        self.calls.append(f"get_balances:{account_id}")
        return dict(self._balances)

    def get_gainloss(
        self,
        account_id: str,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        self.calls.append(f"get_gainloss:{account_id}")
        return list(self._gainloss)


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


def _make_tradier_account(
    session,
    user: User,
    account_number: str = "TRADIER_OAUTH",
    *,
    broker: BrokerType = BrokerType.TRADIER_SANDBOX,
) -> BrokerAccount:
    acct = BrokerAccount(
        user_id=user.id,
        broker=broker,
        account_number=account_number,
        account_name=f"Tradier {user.username}",
        account_type=AccountType.TAXABLE,
        currency="USD",
    )
    session.add(acct)
    session.flush()
    return acct


def _make_oauth_connection(
    session, user: User, broker: str = "tradier_sandbox"
) -> BrokerOAuthConnection:
    conn = BrokerOAuthConnection(
        user_id=user.id,
        broker=broker,
        status=OAuthConnectionStatus.ACTIVE.value,
        access_token_encrypted=encrypt("fake-tradier-access-token"),
        refresh_token_encrypted=encrypt("fake-tradier-refresh-token"),
        environment="sandbox" if "sandbox" in broker else "live",
    )
    session.add(conn)
    session.flush()
    return conn


def _default_payload() -> Dict[str, Any]:
    """Canonical minimal payload covering balances/positions/history."""

    return {
        "accounts": [
            {"account_number": "987654321", "status": "ACTIVE", "type": "margin"},
        ],
        "positions": [
            # Stock — AAPL long.
            {
                "symbol": "AAPL",
                "quantity": 10,
                "cost_basis": 1500.0,
                "date_acquired": "2024-01-15T00:00:00",
                "id": 1001,
            },
            # Option — MSFT call (19-char OSI symbol: 4-letter root + OCC tail).
            {
                "symbol": "MSFT240119C00400000",
                "quantity": 2,
                "cost_basis": 500.0,
                "date_acquired": "2024-01-10T00:00:00",
                "id": 1002,
            },
        ],
        "history": [
            {
                "amount": -1500.0,
                "date": "2024-01-15T09:30:00-05:00",
                "type": "trade",
                "trade": {
                    "commission": 1.0,
                    "description": "BOUGHT AAPL @ 150",
                    "price": 150.0,
                    "quantity": 10,
                    "symbol": "AAPL",
                    "trade_type": "Equity",
                    "transaction_type": "buy",
                },
            },
            {
                "amount": 42.50,
                "date": "2024-02-15T00:00:00-05:00",
                "type": "dividend",
                "dividend": {
                    "description": "AAPL CASH DIVIDEND",
                    "symbol": "AAPL",
                    "quantity": 10,
                    "dividend_type": "cash_dividend",
                },
            },
        ],
        "balances": {
            "total_cash": 2500.0,
            "total_equity": 12345.67,
            "cash": {"cash_available": 2400.0},
            "margin": {"stock_buying_power": 5000.0},
        },
    }


def test_sync_comprehensive_happy_path(db_session) -> None:
    payload = _default_payload()
    user = _make_user(db_session, "tradier_happy")
    account = _make_tradier_account(db_session, user)
    _make_oauth_connection(db_session, user)

    fake = FakeTradierClient(
        accounts=payload["accounts"],
        positions=payload["positions"],
        history=payload["history"],
        balances=payload["balances"],
    )
    service = TradierSyncService(client=fake)

    result = service.sync_account_comprehensive(
        account_number=account.account_number, session=db_session
    )

    assert result["status"] == "success"
    # Stock + option both land from the /positions payload.
    assert result["positions_synced"] == 1
    assert result["options_synced"] == 1
    # History: 1 trade + 1 dividend.
    assert result["transactions_synced"] == 2
    assert result["trades_synced"] == 1
    assert result["dividends_synced"] == 1
    assert result["balances_synced"] == 1

    db_session.refresh(account)
    assert account.account_number == "987654321"
    assert account.options_enabled is True

    pos = (
        db_session.query(Position)
        .filter(Position.user_id == user.id, Position.account_id == account.id)
        .one()
    )
    assert pos.symbol == "AAPL"
    assert pos.status == PositionStatus.OPEN
    assert pos.position_type == PositionType.LONG
    assert Decimal(pos.quantity) == Decimal("10")

    opt = (
        db_session.query(Option)
        .filter(Option.user_id == user.id, Option.account_id == account.id)
        .one()
    )
    assert opt.underlying_symbol == "MSFT"
    assert opt.option_type == "CALL"
    assert opt.strike_price == pytest.approx(400.0)
    assert opt.open_quantity == 2

    txns = (
        db_session.query(Transaction)
        .filter(Transaction.account_id == account.id)
        .order_by(Transaction.transaction_date)
        .all()
    )
    assert len(txns) == 2
    assert any(t.transaction_type == TransactionType.DIVIDEND for t in txns)
    assert any(t.transaction_type == TransactionType.BUY for t in txns)


def test_sync_trades_populate_closing_lot_fields(db_session) -> None:
    """``_sync_trades`` must populate ``execution_time``, ``is_opening``,
    and ``status='FILLED'`` so the closing-lot matcher can pair them.
    """

    payload = _default_payload()
    # Add a closing sell so we exercise both opening and closing trades.
    payload["history"].append({
        "amount": 1800.0,
        "date": "2024-03-01T10:15:00-05:00",
        "type": "trade",
        "trade": {
            "commission": 1.0,
            "description": "SOLD AAPL @ 180",
            "price": 180.0,
            "quantity": 10,
            "symbol": "AAPL",
            "trade_type": "Equity",
            "transaction_type": "sell",
        },
    })

    user = _make_user(db_session, "tradier_trades")
    account = _make_tradier_account(db_session, user)
    _make_oauth_connection(db_session, user)

    fake = FakeTradierClient(
        accounts=payload["accounts"],
        positions=payload["positions"],
        history=payload["history"],
        balances=payload["balances"],
    )
    service = TradierSyncService(client=fake)
    result = service.sync_account_comprehensive(
        account_number=account.account_number, session=db_session
    )
    assert result["status"] == "success"
    assert result["trades_synced"] == 2

    # Closing-lot reconciliation adds synthetic ``CLOSED_LOT`` rows; this
    # test targets broker executions from ``_sync_trades`` only.
    trades = (
        db_session.query(Trade)
        .filter(Trade.account_id == account.id, Trade.status == "FILLED")
        .order_by(Trade.execution_time)
        .all()
    )
    assert len(trades) == 2
    buy, sell = trades
    assert buy.side == "BUY"
    assert buy.is_opening is True
    assert buy.status == "FILLED"
    assert buy.execution_time is not None
    assert sell.side == "SELL"
    assert sell.is_opening is False  # bare ``sell`` is a closing action.
    assert sell.status == "FILLED"
    assert sell.execution_time is not None


def test_sync_is_idempotent_on_second_run(db_session) -> None:
    payload = _default_payload()
    user = _make_user(db_session, "tradier_idem")
    account = _make_tradier_account(db_session, user)
    _make_oauth_connection(db_session, user)

    fake = FakeTradierClient(
        accounts=payload["accounts"],
        positions=payload["positions"],
        history=payload["history"],
        balances=payload["balances"],
    )
    service = TradierSyncService(client=fake)
    service.sync_account_comprehensive(
        account_number=account.account_number, session=db_session
    )
    # Second pass against the auto-corrected real account number.
    result2 = service.sync_account_comprehensive(
        account_number="987654321", session=db_session
    )
    assert result2["status"] == "success"
    # Transactions are external_id-keyed, so re-ingest is a skip.
    assert result2["transactions_synced"] == 0
    assert result2["transactions_skipped"] >= 2

    pos_count = (
        db_session.query(Position)
        .filter(Position.account_id == account.id)
        .count()
    )
    assert pos_count == 1


def test_sync_fails_cleanly_when_oauth_missing(db_session) -> None:
    user = _make_user(db_session, "tradier_no_conn")
    account = _make_tradier_account(
        db_session, user, account_number="TRADIER_OAUTH", broker=BrokerType.TRADIER
    )
    # No BrokerOAuthConnection on purpose — sync must raise loudly.
    service = TradierSyncService()
    with pytest.raises(ConnectionError) as exc:
        service.sync_account_comprehensive(
            account_number=account.account_number, session=db_session
        )
    assert "OAuth connection" in str(exc.value)


def test_sync_requires_user_id_when_account_number_collides(db_session) -> None:
    """Multi-tenancy guard: same ``account_number`` across two tenants
    must refuse to guess rather than silently write under the wrong user.
    """

    user_a = _make_user(db_session, "tradier_userA")
    user_b = _make_user(db_session, "tradier_userB")
    _make_tradier_account(db_session, user_a, account_number="SHARED_NUM")
    _make_tradier_account(db_session, user_b, account_number="SHARED_NUM")
    _make_oauth_connection(db_session, user_a)
    _make_oauth_connection(db_session, user_b)

    service = TradierSyncService(
        client=FakeTradierClient(
            accounts=[], positions=[], history=[], balances={}
        )
    )
    with pytest.raises(ValueError) as exc:
        service.sync_account_comprehensive(
            account_number="SHARED_NUM", session=db_session
        )
    assert "multi-tenancy" in str(exc.value).lower()


def test_sync_scopes_to_user_id_kwarg(db_session) -> None:
    """When ``user_id`` is passed (the BrokerSyncService path), the lookup
    is pinned to that tenant even when another user holds the same number.
    """

    user_a = _make_user(db_session, "tradier_scope_a")
    user_b = _make_user(db_session, "tradier_scope_b")
    acct_a = _make_tradier_account(db_session, user_a, account_number="SCOPED_NUM")
    _make_tradier_account(db_session, user_b, account_number="SCOPED_NUM")
    _make_oauth_connection(db_session, user_a)
    _make_oauth_connection(db_session, user_b)

    payload = _default_payload()
    payload["accounts"] = [{"account_number": "SCOPED_NUM", "status": "ACTIVE"}]
    fake = FakeTradierClient(
        accounts=payload["accounts"],
        positions=payload["positions"],
        history=payload["history"],
        balances=payload["balances"],
    )
    service = TradierSyncService(client=fake)
    result = service.sync_account_comprehensive(
        account_number="SCOPED_NUM", session=db_session, user_id=user_a.id
    )
    assert result["status"] == "success"

    user_a_positions = (
        db_session.query(Position)
        .filter(Position.user_id == user_a.id, Position.account_id == acct_a.id)
        .count()
    )
    user_b_positions = (
        db_session.query(Position)
        .filter(Position.user_id == user_b.id)
        .count()
    )
    assert user_a_positions == 1
    assert user_b_positions == 0


def test_sync_returns_error_on_permanent_api_failure(db_session) -> None:
    from backend.services.bronze.tradier.client import TradierAPIError

    user = _make_user(db_session, "tradier_perm_err")
    account = _make_tradier_account(db_session, user)
    _make_oauth_connection(db_session, user)

    class FlakyClient(FakeTradierClient):
        def get_history(  # type: ignore[override]
            self,
            account_id: str,
            *,
            start: Optional[str] = None,
            end: Optional[str] = None,
            history_type: Optional[str] = None,
        ) -> List[Dict[str, Any]]:
            raise TradierAPIError("401 unauthorized", permanent=True, status=401)

    payload = _default_payload()
    fake = FlakyClient(
        accounts=payload["accounts"],
        positions=payload["positions"],
        history=payload["history"],
        balances=payload["balances"],
    )
    service = TradierSyncService(client=fake)
    result = service.sync_account_comprehensive(
        account_number=account.account_number, session=db_session
    )
    assert result["status"] == "error"
    assert result["permanent"] is True


def test_sync_dividends_populate_correctly(db_session) -> None:
    payload = _default_payload()
    user = _make_user(db_session, "tradier_divs")
    account = _make_tradier_account(db_session, user)
    _make_oauth_connection(db_session, user)

    fake = FakeTradierClient(
        accounts=payload["accounts"],
        positions=payload["positions"],
        history=payload["history"],
        balances=payload["balances"],
    )
    service = TradierSyncService(client=fake)
    service.sync_account_comprehensive(
        account_number=account.account_number, session=db_session
    )

    divs = (
        db_session.query(Dividend)
        .filter(Dividend.account_id == account.id)
        .all()
    )
    assert len(divs) == 1
    assert divs[0].symbol == "AAPL"
    assert divs[0].total_dividend == pytest.approx(42.50)


def test_history_external_id_fits_trade_execution_id_limit() -> None:
    """Long/verbose Tradier history rows must hash to a short ``tra_*`` id."""

    long_event: Dict[str, Any] = {
        "date": "2024-01-15T10:00:00-05:00",
        "type": "trade",
        "amount": -500.0,
        "trade": {
            "symbol": "AAPL",
            "description": "BOUGHT" + ("AAPL" * 50),
        },
    }
    one = TradierSyncService._history_external_id(long_event)
    two = TradierSyncService._history_external_id(long_event)
    assert len(one) <= 50
    assert one == two
    assert one.startswith("tra_")


def test_load_connection_filters_by_broker_id_not_last_updated(
    db_session,
) -> None:
    """Sandbox ``BrokerAccount`` must pair with ``tradier_sandbox`` OAuth.

    A user with both live and sandbox links must not get whichever row was
    updated most recently.
    """

    user = _make_user(db_session, "tradier_conn_slug")
    account = _make_tradier_account(
        db_session, user, account_number="TRADIER_OAUTH", broker=BrokerType.TRADIER_SANDBOX
    )
    _make_oauth_connection(db_session, user, broker="tradier")
    _make_oauth_connection(db_session, user, broker="tradier_sandbox")
    service = TradierSyncService()
    conn = service._load_connection(account, db_session)
    assert conn.broker == "tradier_sandbox"
