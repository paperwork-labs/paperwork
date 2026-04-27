"""Regression: /portfolio/performance/history must not mix naive/aware datetimes in SQL filters."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.main import app
from app.database import get_db
from app.models import BrokerAccount, PortfolioSnapshot, User
from app.models.broker_account import AccountType, BrokerType
from app.models.user import UserRole


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
    return _make_user(db_session, "perfhist")


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
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def _snapshot(account_id: int, snapshot_date: datetime, total_value: float = 10_000.0) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        account_id=account_id,
        snapshot_date=snapshot_date,
        total_value=total_value,
        total_cash=1_000.0,
        total_equity_value=total_value - 1_000.0,
        unrealized_pnl=0.0,
    )


def test_performance_history_naive_snapshots_period_1y_returns_200(client, db_session, primary_account):
    """Naive UTC snapshot_date vs aware window end must not raise (prod 500 on Performance tab)."""
    if db_session is None:
        pytest.skip("database not configured")

    snap_naive = (datetime.now(timezone.utc) - timedelta(days=10)).replace(tzinfo=None)
    assert snap_naive.tzinfo is None
    db_session.add(_snapshot(primary_account.id, snap_naive))
    db_session.commit()

    res = client.get("/api/v1/portfolio/performance/history?period=1y")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("status") == "success"
    data = body.get("data") or {}
    assert "series" in data
    assert isinstance(data["series"], list)
    assert len(data["series"]) >= 1


def test_performance_history_aware_snapshots_period_1y_returns_200(client, db_session, primary_account):
    if db_session is None:
        pytest.skip("database not configured")

    snap_aware = datetime.now(timezone.utc) - timedelta(days=5)
    db_session.add(_snapshot(primary_account.id, snap_aware, total_value=12_000.0))
    db_session.commit()

    res = client.get("/api/v1/portfolio/performance/history?period=1y")
    assert res.status_code == 200, res.text
    assert res.json().get("status") == "success"


def test_performance_history_not_shadowed_by_wildcard_account_route(
    client, db_session, primary_account
):
    """Regression: `/performance/history` must not be captured by
    `/performance/{account_id}` in portfolio/core.py. If the include order
    regresses, the request would route to the wildcard handler and 404
    (surfaced as 500 `{"detail":"404: Account not found"}` due to the
    bare `except Exception` there).
    """
    if db_session is None:
        pytest.skip("database not configured")

    # No snapshots, no account_id param — route must reach the dashboard
    # handler and return an empty series, not the wildcard 404.
    res = client.get("/api/v1/portfolio/performance/history")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("status") == "success"
    data = body.get("data") or {}
    assert isinstance(data.get("series"), list)


def test_performance_history_empty_accounts_returns_200(client, db_session, auth_user):
    """User with zero broker accounts is legitimate empty state, not 404/500."""
    if db_session is None:
        pytest.skip("database not configured")

    res = client.get("/api/v1/portfolio/performance/history?period=1y")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("status") == "success"
    assert (body.get("data") or {}).get("series") == []


def test_performance_history_period_all_naive_snapshots_returns_200(
    client, db_session, primary_account
):
    """`period=all` skips the lower-bound filter, so the tz fix still must hold."""
    if db_session is None:
        pytest.skip("database not configured")

    snap_naive = (datetime.now(timezone.utc) - timedelta(days=400)).replace(tzinfo=None)
    db_session.add(_snapshot(primary_account.id, snap_naive, total_value=9_000.0))
    db_session.commit()

    res = client.get("/api/v1/portfolio/performance/history?period=all")
    assert res.status_code == 200, res.text
    data = res.json().get("data") or {}
    assert isinstance(data.get("series"), list)
    assert len(data["series"]) >= 1
