"""Tests for GET /api/v1/portfolio/options/tax-summary."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.main import app
from app.database import get_db
from app.models import BrokerAccount, User
from app.models.broker_account import AccountType, BrokerType, SyncStatus
from app.models.options import Option
from app.models.user import UserRole


@pytest.fixture(scope="module")
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("FastAPI TestClient not available")


@pytest.fixture
def user_a(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"otax_a_{suffix}@example.com",
        username=f"otax_a_{suffix}",
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
def user_b(db_session):
    if db_session is None:
        pytest.skip("database not configured")
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"otax_b_{suffix}@example.com",
        username=f"otax_b_{suffix}",
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
def broker_account_a(db_session, user_a):
    suffix = uuid.uuid4().hex[:6]
    acc = BrokerAccount(
        user_id=user_a.id,
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


@pytest.fixture
def broker_account_b(db_session, user_b):
    suffix = uuid.uuid4().hex[:6]
    acc = BrokerAccount(
        user_id=user_b.id,
        broker=BrokerType.IBKR,
        account_number=f"V{suffix}",
        account_name="Other",
        account_type=AccountType.TAXABLE,
        sync_status=SyncStatus.NEVER_SYNCED,
        is_enabled=True,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


@pytest.fixture(autouse=True)
def _wire_overrides(db_session, user_a):
    if db_session is None:
        yield
        return

    def _get_db():
        yield db_session

    def _get_user():
        return user_a

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def _opt_long(**kwargs):
    return Option(
        symbol=kwargs.get("symbol", "AAPL  250620C00150000"),
        underlying_symbol=kwargs.get("underlying_symbol", "AAPL"),
        strike_price=150.0,
        expiry_date=kwargs.get("expiry_date", datetime.now(UTC).date() + timedelta(days=30)),
        option_type="CALL",
        multiplier=100.0,
        open_quantity=kwargs.get("open_quantity", 2),
        current_price=kwargs.get("current_price", Decimal("3")),
        total_cost=kwargs.get("total_cost", Decimal("500")),
        account_id=kwargs["account_id"],
        user_id=kwargs["user_id"],
    )


def _opt_short(**kwargs):
    return Option(
        symbol=kwargs.get("symbol", "XYZ   250620P00050000"),
        underlying_symbol=kwargs.get("underlying_symbol", "XYZ"),
        strike_price=50.0,
        expiry_date=kwargs.get("expiry_date", datetime.now(UTC).date() + timedelta(days=45)),
        option_type="PUT",
        multiplier=100.0,
        open_quantity=kwargs.get("open_quantity", -1),
        current_price=kwargs.get("current_price", Decimal("3")),
        total_cost=kwargs.get("total_cost", Decimal("-400")),
        account_id=kwargs["account_id"],
        user_id=kwargs["user_id"],
    )


def test_returns_long_and_short_unrealized_math(client, db_session, user_a, broker_account_a):
    if db_session is None:
        pytest.skip("database not configured")

    long_ago = datetime.now(timezone.utc) - timedelta(days=400)
    recent = datetime.now(timezone.utc) - timedelta(days=30)

    lo = _opt_long(
        user_id=user_a.id,
        account_id=broker_account_a.id,
        symbol="LONGSYM 250620C00001000",
        underlying_symbol="LONGSYM",
        open_quantity=2,
        current_price=Decimal("3"),
        total_cost=Decimal("500"),
    )
    lo.created_at = long_ago

    sh = _opt_short(
        user_id=user_a.id,
        account_id=broker_account_a.id,
        symbol="SHORTSYM 250620P00005000",
        underlying_symbol="SHORTSYM",
        open_quantity=-1,
        current_price=Decimal("3"),
        total_cost=Decimal("-400"),
    )
    sh.created_at = recent

    db_session.add_all([lo, sh])
    db_session.commit()

    res = client.get("/api/v1/portfolio/options/tax-summary")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["counts"]["longs"] == 1
    assert data["counts"]["shorts"] == 1
    items = {i["symbol"]: i for i in data["items"]}
    assert len(items) == 2

    long_row = items["LONGSYM 250620C00001000"]
    assert long_row["open_quantity"] == 2
    assert Decimal(str(long_row["unrealized_pnl"])) == Decimal("100")
    assert long_row["tax_holding_class"] == "long_term"

    short_row = items["SHORTSYM 250620P00005000"]
    assert short_row["open_quantity"] == -1
    assert Decimal(str(short_row["unrealized_pnl"])) == Decimal("100")
    assert short_row["tax_holding_class"] == "short_term"

    assert Decimal(str(data["total_unrealized_pnl"])) == Decimal("200")


def test_unrealized_null_when_mark_missing_not_zero(client, db_session, user_a, broker_account_a):
    if db_session is None:
        pytest.skip("database not configured")

    o = _opt_long(
        user_id=user_a.id,
        account_id=broker_account_a.id,
        symbol="NOMARK 250620C00001000",
        underlying_symbol="NOMARK",
        current_price=None,
        total_cost=Decimal("500"),
    )
    db_session.add(o)
    db_session.commit()

    res = client.get("/api/v1/portfolio/options/tax-summary")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["items"]) == 1
    row = data["items"][0]
    assert row["mark"] is None
    assert row["unrealized_pnl"] is None
    assert row["unrealized_pnl_pct"] is None


def test_total_unrealized_null_when_any_row_missing_pnl(client, db_session, user_a, broker_account_a):
    if db_session is None:
        pytest.skip("database not configured")

    has_mark = _opt_long(
        user_id=user_a.id,
        account_id=broker_account_a.id,
        symbol="HASMRK 250620C00001000",
        underlying_symbol="HASMRK",
        current_price=Decimal("3"),
        total_cost=Decimal("500"),
    )
    no_mark = _opt_long(
        user_id=user_a.id,
        account_id=broker_account_a.id,
        symbol="NOMRK2 250620C00001000",
        underlying_symbol="NOMRK2",
        current_price=None,
        total_cost=Decimal("300"),
    )
    db_session.add_all([has_mark, no_mark])
    db_session.commit()

    res = client.get("/api/v1/portfolio/options/tax-summary")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["items"]) == 2
    assert data["total_unrealized_pnl"] is None


def test_open_quantity_zero_excluded(client, db_session, user_a, broker_account_a):
    if db_session is None:
        pytest.skip("database not configured")

    open_pos = _opt_long(
        user_id=user_a.id,
        account_id=broker_account_a.id,
        symbol="OPENED 250620C00001000",
        underlying_symbol="OPENED",
        open_quantity=1,
    )
    flat = _opt_long(
        user_id=user_a.id,
        account_id=broker_account_a.id,
        symbol="FLAT 250620C00002000",
        underlying_symbol="FLAT",
        open_quantity=0,
    )
    db_session.add_all([open_pos, flat])
    db_session.commit()

    res = client.get("/api/v1/portfolio/options/tax-summary")
    assert res.status_code == 200
    syms = [i["symbol"] for i in res.json()["data"]["items"]]
    assert "OPENED 250620C00001000" in syms
    assert "FLAT 250620C00002000" not in syms


def test_user_cannot_see_other_users_options(client, db_session, user_a, user_b, broker_account_b):
    if db_session is None:
        pytest.skip("database not configured")

    other = _opt_long(
        user_id=user_b.id,
        account_id=broker_account_b.id,
        symbol="SECRET 250620C00002000",
        underlying_symbol="SECRET",
        open_quantity=5,
        current_price=Decimal("2"),
        total_cost=Decimal("800"),
    )
    db_session.add(other)
    db_session.commit()

    res = client.get("/api/v1/portfolio/options/tax-summary")
    assert res.status_code == 200
    syms = [i["symbol"] for i in res.json()["data"]["items"]]
    assert "SECRET 250620C00002000" not in syms
