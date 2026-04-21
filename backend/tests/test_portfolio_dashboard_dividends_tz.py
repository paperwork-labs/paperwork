"""Regression: /portfolio/dividends/summary must not mix naive/aware datetimes."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_current_user, get_portfolio_user
from backend.api.main import app
from backend.database import get_db
from backend.models import BrokerAccount, Dividend, User
from backend.models.broker_account import AccountType, BrokerType
from backend.models.user import UserRole


@pytest.fixture(scope="module")
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("FastAPI TestClient not available")


def _make_user(db_session, label: str) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"{label}_{suffix}@example.com",
        username=f"{label}_{suffix}",
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


def _make_account(db_session, user: User) -> BrokerAccount:
    suffix = uuid.uuid4().hex[:6]
    acc = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.IBKR,
        account_number=f"U{suffix}",
        account_name="Primary",
        account_type=AccountType.TAXABLE,
        is_enabled=True,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


@pytest.fixture
def auth_user(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    return _make_user(db_session, "divtz")


@pytest.fixture
def primary_account(db_session, auth_user):
    return _make_account(db_session, auth_user)


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
    app.dependency_overrides[get_portfolio_user] = _get_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_portfolio_user, None)


def test_dividend_summary_naive_pay_date_returns_200(client, db_session, primary_account):
    """Naive DB datetimes vs aware ``one_year_ago`` must not raise TypeError."""
    if db_session is None:
        pytest.skip("database not configured")

    pay_naive = datetime.utcnow() - timedelta(days=30)
    assert pay_naive.tzinfo is None
    ex_naive = pay_naive - timedelta(days=7)

    db_session.add(
        Dividend(
            account_id=primary_account.id,
            symbol="TEST",
            ex_date=ex_naive,
            pay_date=pay_naive,
            dividend_per_share=0.5,
            shares_held=10.0,
            total_dividend=5.0,
            net_dividend=5.0,
        )
    )
    db_session.commit()

    res = client.get("/api/v1/portfolio/dividends/summary")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("status") == "success"
    assert "data" in body


def test_dividend_summary_aware_pay_date_returns_200(client, db_session, primary_account):
    if db_session is None:
        pytest.skip("database not configured")

    pay_aware = datetime.now(timezone.utc) - timedelta(days=30)
    ex_aware = pay_aware - timedelta(days=7)

    db_session.add(
        Dividend(
            account_id=primary_account.id,
            symbol="TST2",
            ex_date=ex_aware,
            pay_date=pay_aware,
            dividend_per_share=0.25,
            shares_held=8.0,
            total_dividend=2.0,
            net_dividend=2.0,
        )
    )
    db_session.commit()

    res = client.get("/api/v1/portfolio/dividends/summary")
    assert res.status_code == 200, res.text
    assert res.json().get("status") == "success"


def test_dividend_summary_two_ex_dates_upcoming_path(client, db_session, primary_account):
    """Exercise ex-date differencing with naive datetimes (upcoming block).

    Both dividend rows must land inside the trailing 12m window so they
    survive the ``trailing_divs`` filter that feeds the upcoming-ex-date
    projection. With a 90-day gap and the most recent ex-date ~50d old,
    the projected next ex-date lands ~40d in the future — inside the
    60d upcoming window the endpoint reports.
    """
    if db_session is None:
        pytest.skip("database not configured")

    base = datetime.utcnow() - timedelta(days=140)
    db_session.add(
        Dividend(
            account_id=primary_account.id,
            symbol="UPX",
            ex_date=base,
            pay_date=base + timedelta(days=3),
            dividend_per_share=1.0,
            shares_held=1.0,
            total_dividend=1.0,
            net_dividend=1.0,
        )
    )
    db_session.add(
        Dividend(
            account_id=primary_account.id,
            symbol="UPX",
            ex_date=base + timedelta(days=90),
            pay_date=base + timedelta(days=93),
            dividend_per_share=1.0,
            shares_held=1.0,
            total_dividend=1.0,
            net_dividend=1.0,
        )
    )
    db_session.commit()

    res = client.get("/api/v1/portfolio/dividends/summary")
    assert res.status_code == 200, res.text
