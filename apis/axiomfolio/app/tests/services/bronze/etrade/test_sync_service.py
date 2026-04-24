"""Happy-path tests for :class:`ETradeSyncService`.

These tests drive the sync service end-to-end against an injected fake
E*TRADE client — no network, no HMAC signing, and credentials are satisfied
by inserting a synthetic :class:`BrokerOAuthConnection` row with encrypted
tokens. We still use the real ``db_session`` fixture so Postgres enum
casting, unique constraints, and ``options_enabled`` updates are exercised
for real.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List

import pytest

from app.models.broker_account import AccountType, BrokerAccount, BrokerType
from app.models.broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from app.models.options import Option
from app.models.position import Position, PositionStatus, PositionType
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.bronze.etrade.sync_service import ETradeSyncService
from app.services.oauth.encryption import encrypt


class FakeETradeClient:
    """In-memory stand-in for :class:`ETradeBronzeClient`."""

    def __init__(
        self,
        *,
        accounts: List[Dict[str, Any]],
        portfolio: List[Dict[str, Any]],
        transactions: List[Dict[str, Any]],
        balance: Dict[str, Any],
    ) -> None:
        self._accounts = accounts
        self._portfolio = portfolio
        self._transactions = transactions
        self._balance = balance
        self.calls: List[str] = []

    def list_accounts(self) -> List[Dict[str, Any]]:
        self.calls.append("list_accounts")
        return list(self._accounts)

    def get_portfolio(self, key: str) -> List[Dict[str, Any]]:
        self.calls.append(f"get_portfolio:{key}")
        return list(self._portfolio)

    def get_transactions(self, key: str) -> List[Dict[str, Any]]:
        self.calls.append(f"get_transactions:{key}")
        return list(self._transactions)

    def get_balance(self, key: str) -> Dict[str, Any]:
        self.calls.append(f"get_balance:{key}")
        return dict(self._balance)


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


def _make_etrade_account(
    session, user: User, account_number: str = "ETRADE_OAUTH"
) -> BrokerAccount:
    acct = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.ETRADE,
        account_number=account_number,
        account_name=f"E*TRADE {user.username}",
        account_type=AccountType.TAXABLE,
        currency="USD",
    )
    session.add(acct)
    session.flush()
    return acct


def _make_oauth_connection(session, user: User) -> BrokerOAuthConnection:
    conn = BrokerOAuthConnection(
        user_id=user.id,
        broker="etrade_sandbox",
        status=OAuthConnectionStatus.ACTIVE.value,
        access_token_encrypted=encrypt("fake-access-token"),
        refresh_token_encrypted=encrypt("fake-access-token-secret"),
        environment="sandbox",
    )
    session.add(conn)
    session.flush()
    return conn


def _default_payload() -> Dict[str, Any]:
    """Canonical minimal payload covering positions, options, txns, balance."""
    return {
        "accounts": [
            {
                "accountId": "987654321",
                "accountIdKey": "keyABC",
                "accountStatus": "ACTIVE",
            }
        ],
        "portfolio": [
            {
                "Product": {"symbol": "AAPL", "securityType": "EQ"},
                "quantity": 10,
                "costPerShare": 150.0,
                "totalCost": 1500.0,
                "marketValue": 1800.0,
                "Quick": {"lastTrade": 180.0},
                "daysGain": 20.0,
                "daysGainPct": 1.11,
            },
            {
                "Product": {
                    "symbol": "MSFT",
                    "osiKey": "MSFT240119C00400000",
                    "securityType": "OPTN",
                    "strikePrice": 400.0,
                    "callPut": "CALL",
                    "expiryYear": 2024,
                    "expiryMonth": 1,
                    "expiryDay": 19,
                },
                "quantity": 2,
                "marketValue": 600.0,
                "costPerShare": 2.50,
            },
        ],
        "transactions": [
            {
                "transactionId": "TX1",
                "transactionType": "BUY",
                "transactionDate": 1_700_000_000_000,
                "amount": -1500.0,
                "description": "Bought AAPL",
                "brokerage": {
                    "product": {"symbol": "AAPL"},
                    "quantity": 10,
                    "price": 150.0,
                    "fee": 1.0,
                },
            },
            {
                "transactionId": "TX2",
                "transactionType": "DIVIDEND",
                "transactionDate": 1_700_100_000_000,
                "amount": 42.50,
                "description": "AAPL dividend",
                "brokerage": {
                    "product": {"symbol": "AAPL"},
                    "quantity": 0,
                    "price": 0,
                    "fee": 0,
                },
            },
        ],
        "balance": {
            "Computed": {
                "cashBalance": 2500.0,
                "cashAvailableForWithdrawal": 2400.0,
                "cashBuyingPower": 5000.0,
            },
            "RealTimeValues": {
                "totalAccountValue": 12345.67,
                "totalLongValue": 9845.67,
            },
        },
    }


def test_sync_comprehensive_happy_path(db_session) -> None:
    payload = _default_payload()
    user = _make_user(db_session, "etrade_happy")
    account = _make_etrade_account(db_session, user)
    _make_oauth_connection(db_session, user)

    fake = FakeETradeClient(
        accounts=payload["accounts"],
        portfolio=payload["portfolio"],
        transactions=payload["transactions"],
        balance=payload["balance"],
    )
    service = ETradeSyncService(client=fake)

    result = service.sync_account_comprehensive(
        account_number=account.account_number, session=db_session
    )

    assert result["status"] == "success"
    assert result["positions_synced"] == 1
    assert result["options_synced"] == 1
    assert result["transactions_synced"] == 2
    assert result["trades_synced"] == 1
    assert result["dividends_synced"] == 1
    assert result["balances_synced"] == 1

    # Placeholder ``account_number`` got auto-corrected to the real accountId.
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

    txns = (
        db_session.query(Transaction)
        .filter(Transaction.account_id == account.id)
        .order_by(Transaction.external_id)
        .all()
    )
    assert [t.external_id for t in txns] == ["TX1", "TX2"]
    assert any(t.transaction_type == TransactionType.DIVIDEND for t in txns)


def test_sync_is_idempotent_on_second_run(db_session) -> None:
    payload = _default_payload()
    user = _make_user(db_session, "etrade_idem")
    account = _make_etrade_account(db_session, user)
    _make_oauth_connection(db_session, user)

    fake = FakeETradeClient(
        accounts=payload["accounts"],
        portfolio=payload["portfolio"],
        transactions=payload["transactions"],
        balance=payload["balance"],
    )
    service = ETradeSyncService(client=fake)
    service.sync_account_comprehensive(
        account_number=account.account_number, session=db_session
    )
    # Second run: same payload shouldn't duplicate rows (idempotent on
    # external_id for transactions, symbol for positions).
    result2 = service.sync_account_comprehensive(
        account_number="987654321", session=db_session
    )
    assert result2["status"] == "success"
    assert result2["transactions_skipped"] == 2
    assert result2["transactions_synced"] == 0
    pos_count = (
        db_session.query(Position)
        .filter(Position.account_id == account.id)
        .count()
    )
    assert pos_count == 1


def test_sync_fails_cleanly_when_oauth_missing(db_session) -> None:
    user = _make_user(db_session, "etrade_no_conn")
    account = _make_etrade_account(db_session, user, account_number="ETRADE_OAUTH")
    # No BrokerOAuthConnection inserted on purpose.
    service = ETradeSyncService()
    with pytest.raises(ConnectionError) as exc:
        service.sync_account_comprehensive(
            account_number=account.account_number, session=db_session
        )
    assert "OAuth connection" in str(exc.value)


def test_sync_service_records_real_time_balance(db_session) -> None:
    """Regression (PR 395 follow-up): ``RealTimeValues`` lives at the top
    of E*TRADE's ``BalanceResponse`` envelope, not inside ``Computed``.
    Prior code silently recorded ``net_liquidation=None`` / ``equity=None``
    on well-formed payloads; pin the fix with an explicit value assert.
    """
    from app.models.account_balance import AccountBalance

    payload = _default_payload()
    user = _make_user(db_session, "etrade_balance")
    account = _make_etrade_account(db_session, user)
    _make_oauth_connection(db_session, user)

    fake = FakeETradeClient(
        accounts=payload["accounts"],
        portfolio=payload["portfolio"],
        transactions=payload["transactions"],
        balance=payload["balance"],
    )
    service = ETradeSyncService(client=fake)
    result = service.sync_account_comprehensive(
        account_number=account.account_number, session=db_session
    )
    assert result["status"] == "success"
    db_session.refresh(account)

    bal = (
        db_session.query(AccountBalance)
        .filter(AccountBalance.broker_account_id == account.id)
        .order_by(AccountBalance.id.desc())
        .first()
    )
    assert bal is not None, "ETradeSyncService did not persist AccountBalance"
    # ``AccountBalance`` stores monetary columns as SQLAlchemy ``Float`` (see
    # ``app/models/account_balance.py``), so even though the sync service
    # hands Decimal values to the ORM, round-tripping through the column
    # yields ``float``. Compare with pytest.approx to avoid IEEE-754
    # representation noise (e.g. 12345.67 ≈ 12345.6699999...).
    assert bal.net_liquidation == pytest.approx(12345.67)
    assert bal.equity == pytest.approx(9845.67)
    assert bal.cash_balance == pytest.approx(2500.0)
    assert bal.buying_power == pytest.approx(5000.0)


def test_sync_requires_user_id_when_account_number_collides(db_session) -> None:
    """Regression (PR 395 follow-up): ``account_number`` is not globally
    unique. If two tenants hold the same number, the sync must refuse to
    guess rather than silently write under the wrong user.
    """
    user_a = _make_user(db_session, "etrade_userA")
    user_b = _make_user(db_session, "etrade_userB")
    _make_etrade_account(db_session, user_a, account_number="SHARED_NUM")
    _make_etrade_account(db_session, user_b, account_number="SHARED_NUM")
    _make_oauth_connection(db_session, user_a)
    _make_oauth_connection(db_session, user_b)

    service = ETradeSyncService(client=FakeETradeClient(
        accounts=[], portfolio=[], transactions=[], balance={}
    ))
    with pytest.raises(ValueError) as exc:
        service.sync_account_comprehensive(
            account_number="SHARED_NUM", session=db_session
        )
    assert "multi-tenancy" in str(exc.value).lower()


def test_sync_scopes_to_user_id_kwarg(db_session) -> None:
    """When ``user_id`` is passed (the BrokerSyncService path), the lookup
    is pinned to that tenant even when another user holds the same number.
    """
    user_a = _make_user(db_session, "etrade_scope_a")
    user_b = _make_user(db_session, "etrade_scope_b")
    acct_a = _make_etrade_account(db_session, user_a, account_number="SCOPED_NUM")
    _make_etrade_account(db_session, user_b, account_number="SCOPED_NUM")
    _make_oauth_connection(db_session, user_a)
    _make_oauth_connection(db_session, user_b)

    payload = _default_payload()
    payload["accounts"] = [{
        "accountId": "SCOPED_NUM",
        "accountIdKey": "keyABC",
        "accountStatus": "ACTIVE",
    }]
    fake = FakeETradeClient(
        accounts=payload["accounts"],
        portfolio=payload["portfolio"],
        transactions=payload["transactions"],
        balance=payload["balance"],
    )
    service = ETradeSyncService(client=fake)
    result = service.sync_account_comprehensive(
        account_number="SCOPED_NUM", session=db_session, user_id=user_a.id
    )
    assert result["status"] == "success"
    # Positions must land under user_a's account_id, not user_b's.
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


def test_sync_fetches_portfolio_once_for_positions_and_options(db_session) -> None:
    """Regression (PR #395 Copilot follow-up): ``_sync_positions`` and
    ``_sync_options`` share one E*TRADE ``/portfolio`` payload; calling
    ``get_portfolio`` twice doubled latency and rate-limit pressure per
    account sync.
    """
    payload = _default_payload()
    user = _make_user(db_session, "etrade_portfolio_once")
    account = _make_etrade_account(db_session, user)
    _make_oauth_connection(db_session, user)

    fake = FakeETradeClient(
        accounts=payload["accounts"],
        portfolio=payload["portfolio"],
        transactions=payload["transactions"],
        balance=payload["balance"],
    )
    service = ETradeSyncService(client=fake)
    result = service.sync_account_comprehensive(
        account_number=account.account_number, session=db_session
    )
    assert result["status"] == "success"

    portfolio_calls = [c for c in fake.calls if c.startswith("get_portfolio:")]
    assert len(portfolio_calls) == 1, (
        f"Expected exactly one /portfolio fetch per sync; observed "
        f"{portfolio_calls}"
    )


def test_sync_skips_cleanly_on_placeholder_collision(db_session) -> None:
    """Regression (PR #395 Copilot follow-up): when a placeholder
    ``ETRADE_OAUTH`` row collides with a real account the same user
    already owns, ``sync_account_comprehensive`` must return a
    ``status='skipped'`` (not the generic ``status='error'``/
    please-re-link message) and disable the placeholder.
    """
    from app.models.broker_account import BrokerAccount

    user = _make_user(db_session, "etrade_collision_user")
    real = _make_etrade_account(
        db_session, user, account_number="REAL_ACCT_123"
    )
    placeholder = _make_etrade_account(
        db_session, user, account_number="ETRADE_OAUTH"
    )
    _make_oauth_connection(db_session, user)

    payload = _default_payload()
    payload["accounts"] = [{
        "accountId": "REAL_ACCT_123",
        "accountIdKey": "keyABC",
        "accountStatus": "ACTIVE",
    }]
    fake = FakeETradeClient(
        accounts=payload["accounts"],
        portfolio=payload["portfolio"],
        transactions=payload["transactions"],
        balance=payload["balance"],
    )
    service = ETradeSyncService(client=fake)
    result = service.sync_account_comprehensive(
        account_number="ETRADE_OAUTH", session=db_session, user_id=user.id
    )
    assert result["status"] == "skipped"
    assert "placeholder" in result["error"].lower()
    assert result["permanent"] is False

    # Placeholder is disabled; real account untouched.
    db_session.refresh(placeholder)
    db_session.refresh(real)
    refreshed_placeholder: BrokerAccount = placeholder
    refreshed_real: BrokerAccount = real
    assert refreshed_placeholder.is_enabled is False
    assert refreshed_real.is_enabled is True


def test_sync_returns_error_on_permanent_api_failure(db_session) -> None:
    from app.services.bronze.etrade.client import ETradeAPIError

    user = _make_user(db_session, "etrade_perm_err")
    account = _make_etrade_account(db_session, user)
    _make_oauth_connection(db_session, user)

    class FlakyClient(FakeETradeClient):
        def get_transactions(self, key: str) -> List[Dict[str, Any]]:
            raise ETradeAPIError("401 unauthorized", permanent=True, status=401)

    payload = _default_payload()
    fake = FlakyClient(
        accounts=payload["accounts"],
        portfolio=payload["portfolio"],
        transactions=payload["transactions"],
        balance=payload["balance"],
    )
    service = ETradeSyncService(client=fake)
    result = service.sync_account_comprehensive(
        account_number=account.account_number, session=db_session
    )
    assert result["status"] == "error"
    assert result["permanent"] is True
