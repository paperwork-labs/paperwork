"""Tests for portfolio options API routes (unified portfolio)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.main import app
from app.database import get_db
from app.models.broker_account import AccountStatus, AccountType, BrokerAccount, BrokerType
from app.models.options import Option
from app.models.user import User, UserRole


def _make_user(db_session) -> User:
    suffix = uuid.uuid4().hex[:10]
    u = User(
        email=f"op_{suffix}@example.com",
        username=f"op_{suffix}",
        password_hash="dummy",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _add_account(db_session, user: User) -> BrokerAccount:
    acc = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.SCHWAB,
        account_number=f"SCH-{uuid.uuid4().hex[:8]}",
        account_name="Opt test",
        account_type=AccountType.TAXABLE,
        status=AccountStatus.ACTIVE,
        is_enabled=True,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


@pytest.fixture(scope="module")
def client() -> TestClient:
    try:
        return TestClient(app, raise_server_exceptions=False)
    except Exception:  # pragma: no cover
        pytest.skip("TestClient not available")


def test_unified_portfolio_includes_long_and_short_open_quantity(
    db_session, client: TestClient
) -> None:
    if db_session is None:
        pytest.skip("database not configured")
    u = _make_user(db_session)
    acct = _add_account(db_session, u)
    exp = date(2026, 6, 20)

    long_o = Option(
        user_id=u.id,
        account_id=acct.id,
        symbol="AAPL  250620C00100000",
        underlying_symbol="AAPL",
        contract_id="c1",
        strike_price=100.0,
        expiry_date=exp,
        option_type="CALL",
        multiplier=100.0,
        open_quantity=2,
        data_source="BROKERAGE_API",
    )
    short_o = Option(
        user_id=u.id,
        account_id=acct.id,
        symbol="AAPL  250620P00200000",
        underlying_symbol="AAPL",
        contract_id="c2",
        strike_price=200.0,
        expiry_date=exp,
        option_type="PUT",
        multiplier=100.0,
        open_quantity=-1,
        data_source="BROKERAGE_API",
    )
    db_session.add_all([long_o, short_o])
    db_session.commit()

    def _get_db():
        yield db_session

    def _get_user() -> User:
        return u

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    app.dependency_overrides[get_current_user] = _get_user
    try:
        res = client.get("/api/v1/portfolio/options/unified/portfolio")
        assert res.status_code == 200, res.text
        payload = res.json()
        positions = payload.get("data", {}).get("positions", [])
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert len(positions) == 2
    quantities = sorted(int(p.get("quantity", 0)) for p in positions)
    assert quantities == [-1, 2]
