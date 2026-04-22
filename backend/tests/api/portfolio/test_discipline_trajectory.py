"""Tests for GET /api/v1/portfolio/discipline-trajectory (C7)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_current_user, get_portfolio_user
from backend.api.main import app
from backend.database import get_db
from backend.models.account_balance import AccountBalance, AccountBalanceType
from backend.models import BrokerAccount, User
from backend.models.broker_account import AccountType, BrokerType
from backend.models.entitlement import SubscriptionTier
from backend.models.user import UserRole
from backend.services.billing.entitlement_service import EntitlementService


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


def _make_account(
    db_session,
    user: User,
    *,
    name: str = "Primary",
    broker: BrokerType = BrokerType.IBKR,
    is_primary: bool = False,
) -> BrokerAccount:
    suffix = uuid.uuid4().hex[:6]
    acc = BrokerAccount(
        user_id=user.id,
        broker=broker,
        account_number=f"U{suffix}",
        account_name=name,
        account_type=AccountType.TAXABLE,
        is_enabled=True,
        is_primary=is_primary,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


def _seed_balance(
    db_session,
    *,
    user_id: int,
    broker_account_id: int,
    when: datetime,
    nlv: float,
) -> None:
    row = AccountBalance(
        user_id=user_id,
        broker_account_id=broker_account_id,
        balance_date=when,
        balance_type=AccountBalanceType.DAILY_SNAPSHOT,
        base_currency="USD",
        net_liquidation=nlv,
        equity=nlv,
    )
    db_session.add(row)
    db_session.commit()


@pytest.fixture
def auth_user(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    return _make_user(db_session, "traj")


@pytest.fixture
def primary_account(db_session, auth_user):
    return _make_account(db_session, auth_user, name="Primary", is_primary=True)


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


def test_single_account_happy_path(client, db_session, auth_user, primary_account):
    if db_session is None:
        pytest.skip("database not configured")
    now = datetime.now(timezone.utc)
    y = now.year
    ytd_open = datetime(y, 1, 4, 12, 0, 0, tzinfo=timezone.utc)
    latest = now - timedelta(hours=3)

    _seed_balance(
        db_session,
        user_id=auth_user.id,
        broker_account_id=primary_account.id,
        when=ytd_open,
        nlv=100_000.0,
    )
    _seed_balance(
        db_session,
        user_id=auth_user.id,
        broker_account_id=primary_account.id,
        when=latest,
        nlv=110_000.0,
    )

    res = client.get(f"/api/v1/portfolio/discipline-trajectory?account_id={primary_account.id}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["aggregate"] is False
    assert body["account_id"] == str(primary_account.id)
    assert body["starting_equity"] == pytest.approx(100_000.0)
    assert body["current_equity"] == pytest.approx(110_000.0)
    assert body["anchors"]["unleveraged_ceiling"] == pytest.approx(150_000.0)
    assert body["anchors"]["leveraged_ceiling"] == pytest.approx(200_000.0)
    assert body["anchors"]["speculative_ceiling"] == pytest.approx(300_000.0)
    assert body["trend"] == "up"
    assert body["projected_year_end"] is not None
    assert body["by_account"] is None


def test_aggregate_happy_path(client, db_session, auth_user, primary_account):
    if db_session is None:
        pytest.skip("database not configured")
    EntitlementService.manual_set_tier(
        db_session,
        user=auth_user,
        new_tier=SubscriptionTier.PRO_PLUS,
        actor="test_discipline_trajectory",
        note="aggregate test",
    )
    db_session.commit()

    second = _make_account(db_session, auth_user, name="Second", broker=BrokerType.SCHWAB)
    now = datetime.now(timezone.utc)
    y = now.year
    ytd_open = datetime(y, 1, 5, 12, 0, 0, tzinfo=timezone.utc)
    latest = now - timedelta(hours=2)

    for acc, start_nlv, end_nlv in (
        (primary_account, 60_000.0, 66_000.0),
        (second, 40_000.0, 44_000.0),
    ):
        _seed_balance(
            db_session,
            user_id=auth_user.id,
            broker_account_id=acc.id,
            when=ytd_open,
            nlv=start_nlv,
        )
        _seed_balance(
            db_session,
            user_id=auth_user.id,
            broker_account_id=acc.id,
            when=latest,
            nlv=end_nlv,
        )

    res = client.get("/api/v1/portfolio/discipline-trajectory?aggregate=true")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["aggregate"] is True
    assert body["account_id"] is None
    assert body["starting_equity"] == pytest.approx(100_000.0)
    assert body["current_equity"] == pytest.approx(110_000.0)
    assert body["trend"] == "up"
    assert isinstance(body["by_account"], list)
    assert len(body["by_account"]) == 2


def test_aggregate_without_entitlement_returns_403(client, db_session, auth_user, primary_account):
    if db_session is None:
        pytest.skip("database not configured")
    res = client.get("/api/v1/portfolio/discipline-trajectory?aggregate=true")
    assert res.status_code == 403, res.text
    detail = res.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("error") == "feature_required"
    assert detail.get("feature") == "execution.multi_broker"


def test_cross_tenant_cannot_query_other_users_account(client, db_session, auth_user, primary_account):
    if db_session is None:
        pytest.skip("database not configured")
    other = _make_user(db_session, "traj_other")
    other_acc = _make_account(db_session, other, name="Victim")

    res = client.get(f"/api/v1/portfolio/discipline-trajectory?account_id={other_acc.id}")
    assert res.status_code == 404, res.text
