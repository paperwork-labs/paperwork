"""API tests for `/api/v1/portfolio/dividends`.

Specifically pins down the SQL-level `symbol` and `account_id` filters
introduced when the per-holding chart's dividend overlay started asking
for a single ticker's dividends instead of pulling the entire account
payload and filtering client-side.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.main import app
from app.database import get_db
from app.models import BrokerAccount, User
from app.models.broker_account import AccountType, BrokerType, SyncStatus
from app.models.transaction import Dividend
from app.models.user import UserRole


@pytest.fixture(scope="module")
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("FastAPI TestClient not available")


@pytest.fixture
def auth_user(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"divs_{suffix}@example.com",
        username=f"divs_{suffix}",
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


@pytest.fixture
def broker_account(db_session, auth_user):
    """Primary account used by tests; additional accounts are created where needed."""
    suffix = uuid.uuid4().hex[:6]
    acc = BrokerAccount(
        user_id=auth_user.id,
        broker=BrokerType.IBKR,
        account_number=f"U{suffix}",
        account_name="Primary",
        account_type=AccountType.TAXABLE,
        sync_status=SyncStatus.NEVER_SYNCED,
        is_enabled=True,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


def _seed_div(db_session, account_id: int, symbol: str, ex_date: datetime, total: float = 12.34):
    div = Dividend(
        account_id=account_id,
        symbol=symbol,
        ex_date=ex_date,
        dividend_per_share=0.5,
        shares_held=10.0,
        total_dividend=total,
        net_dividend=total,
        currency="USD",
    )
    db_session.add(div)
    return div


@pytest.fixture(autouse=True)
def _wire_overrides(db_session, auth_user):
    if db_session is None:
        yield
        return

    def _get_db():
        yield db_session

    def _get_user():
        return auth_user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def test_no_filter_returns_all_user_dividends(client, db_session, broker_account):
    if db_session is None:
        pytest.skip("database not configured")
    now = datetime.now(UTC)
    _seed_div(db_session, broker_account.id, "AAPL", now)
    _seed_div(db_session, broker_account.id, "MSFT", now)
    db_session.commit()

    res = client.get("/api/v1/portfolio/dividends?days=365")
    assert res.status_code == 200
    rows = res.json()["data"]["dividends"]
    symbols = sorted(r["symbol"] for r in rows)
    assert symbols == ["AAPL", "MSFT"]


def test_symbol_filter_scopes_to_one_ticker(client, db_session, broker_account):
    if db_session is None:
        pytest.skip("database not configured")
    now = datetime.now(UTC)
    _seed_div(db_session, broker_account.id, "AAPL", now, total=24.0)
    _seed_div(db_session, broker_account.id, "MSFT", now, total=37.5)
    _seed_div(db_session, broker_account.id, "AAPL", now, total=24.0)
    db_session.commit()

    res = client.get("/api/v1/portfolio/dividends?days=365&symbol=AAPL")
    assert res.status_code == 200
    rows = res.json()["data"]["dividends"]
    assert len(rows) == 2
    assert {r["symbol"] for r in rows} == {"AAPL"}


def test_symbol_filter_is_case_insensitive(client, db_session, broker_account):
    if db_session is None:
        pytest.skip("database not configured")
    now = datetime.now(UTC)
    _seed_div(db_session, broker_account.id, "AAPL", now)
    db_session.commit()

    res = client.get("/api/v1/portfolio/dividends?days=365&symbol=aapl")
    assert res.status_code == 200
    rows = res.json()["data"]["dividends"]
    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAPL"


def test_symbol_filter_unknown_returns_empty(client, db_session, broker_account):
    if db_session is None:
        pytest.skip("database not configured")
    now = datetime.now(UTC)
    _seed_div(db_session, broker_account.id, "AAPL", now)
    db_session.commit()

    res = client.get("/api/v1/portfolio/dividends?days=365&symbol=ZZZZ")
    assert res.status_code == 200
    assert res.json()["data"]["dividends"] == []


def test_symbol_does_not_leak_other_users_dividends(client, db_session, auth_user, broker_account):
    """Authorization gate must come first: even when a malicious caller
    asks for the right symbol, dividends owned by another user must not
    appear in the response."""
    if db_session is None:
        pytest.skip("database not configured")

    other = User(
        email=f"other_{uuid.uuid4().hex[:6]}@example.com",
        username=f"other_{uuid.uuid4().hex[:6]}",
        password_hash="dummy",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    other_acc = BrokerAccount(
        user_id=other.id,
        broker=BrokerType.IBKR,
        account_number=f"U{uuid.uuid4().hex[:6]}",
        account_type=AccountType.TAXABLE,
        is_enabled=True,
    )
    db_session.add(other_acc)
    db_session.commit()
    db_session.refresh(other_acc)

    now = datetime.now(UTC)
    _seed_div(db_session, broker_account.id, "AAPL", now, total=10.0)
    _seed_div(db_session, other_acc.id, "AAPL", now, total=999.0)
    db_session.commit()

    res = client.get("/api/v1/portfolio/dividends?days=365&symbol=AAPL")
    assert res.status_code == 200
    rows = res.json()["data"]["dividends"]
    assert len(rows) == 1
    assert rows[0]["total_dividend"] == 10.0


def test_account_and_symbol_filters_compose(client, db_session, auth_user, broker_account):
    """account_id + symbol must AND together at the SQL layer."""
    if db_session is None:
        pytest.skip("database not configured")
    secondary = BrokerAccount(
        user_id=auth_user.id,
        broker=BrokerType.IBKR,
        account_number=f"U{uuid.uuid4().hex[:6]}",
        account_name="Secondary",
        account_type=AccountType.TAXABLE,
        is_enabled=True,
    )
    db_session.add(secondary)
    db_session.commit()
    db_session.refresh(secondary)

    now = datetime.now(UTC)
    _seed_div(db_session, broker_account.id, "AAPL", now, total=11.11)
    _seed_div(db_session, secondary.id, "AAPL", now, total=22.22)
    db_session.commit()

    res = client.get(
        "/api/v1/portfolio/dividends",
        params={
            "days": 365,
            "symbol": "AAPL",
            "account_id": broker_account.account_number,
        },
    )
    assert res.status_code == 200
    rows = res.json()["data"]["dividends"]
    assert len(rows) == 1
    assert rows[0]["total_dividend"] == 11.11
