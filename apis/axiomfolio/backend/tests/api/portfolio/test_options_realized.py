"""Tests for GET /api/v1/portfolio/options/realized."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_current_user
from backend.api.main import app
from backend.database import get_db
from backend.models import BrokerAccount, User
from backend.models.broker_account import AccountType, BrokerType, SyncStatus
from backend.models.option_tax_lot import OptionTaxLot
from backend.models.trade import Trade
from backend.models.user import UserRole


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
        email=f"oreal_a_{suffix}@example.com",
        username=f"oreal_a_{suffix}",
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
        email=f"oreal_b_{suffix}@example.com",
        username=f"oreal_b_{suffix}",
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
        account_number=f"R{suffix}",
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
        account_number=f"S{suffix}",
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


def _mk_trades(db_session, account: BrokerAccount) -> tuple[int, int]:
    t_open = Trade(
        account_id=account.id,
        symbol="AAPL  250117C00200000",
        side="BUY",
        quantity=Decimal("1"),
        price=Decimal("1"),
        total_value=Decimal("1"),
        execution_id=f"eo-{uuid.uuid4().hex[:8]}",
        execution_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        status="FILLED",
        is_opening=True,
        is_paper_trade=False,
        trade_metadata={"asset_category": "OPT"},
    )
    t_close = Trade(
        account_id=account.id,
        symbol="AAPL  250117C00200000",
        side="SELL",
        quantity=Decimal("1"),
        price=Decimal("2"),
        total_value=Decimal("2"),
        execution_id=f"ec-{uuid.uuid4().hex[:8]}",
        execution_time=datetime(2025, 6, 1, tzinfo=timezone.utc),
        status="FILLED",
        is_opening=False,
        is_paper_trade=False,
        trade_metadata={"asset_category": "OPT"},
    )
    db_session.add_all([t_open, t_close])
    db_session.commit()
    db_session.refresh(t_open)
    db_session.refresh(t_close)
    return t_open.id, t_close.id


def test_realized_groups_holding_class_and_totals(client, db_session, user_a, broker_account_a):
    if db_session is None:
        pytest.skip("no db")
    oid, cid = _mk_trades(db_session, broker_account_a)
    lot_st = OptionTaxLot(
        user_id=user_a.id,
        broker_account_id=broker_account_a.id,
        symbol="AAPL  250117C00200000",
        underlying="AAPL",
        option_type="call",
        strike=Decimal("200"),
        expiry=date(2025, 1, 17),
        multiplier=100,
        quantity_opened=Decimal("1"),
        cost_basis_per_contract=Decimal("1"),
        opened_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        closed_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        quantity_closed=Decimal("1"),
        proceeds_per_contract=Decimal("2"),
        realized_pnl=Decimal("100"),
        holding_class="short_term",
        opening_trade_id=oid,
        closing_trade_id=cid,
    )
    oid2, cid2 = _mk_trades(db_session, broker_account_a)
    lot_lt = OptionTaxLot(
        user_id=user_a.id,
        broker_account_id=broker_account_a.id,
        symbol="QQQ   250301C00400000",
        underlying="QQQ",
        option_type="call",
        strike=Decimal("400"),
        expiry=date(2025, 3, 1),
        multiplier=100,
        quantity_opened=Decimal("1"),
        cost_basis_per_contract=Decimal("1"),
        opened_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        closed_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        quantity_closed=Decimal("1"),
        proceeds_per_contract=Decimal("3"),
        realized_pnl=Decimal("200"),
        holding_class="long_term",
        opening_trade_id=oid2,
        closing_trade_id=cid2,
    )
    db_session.add_all([lot_st, lot_lt])
    db_session.commit()

    res = client.get("/api/v1/portfolio/options/realized", params={"year": 2025})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["counts"]["short_term"] >= 1
    assert Decimal(str(data["total_realized_pnl_short"])) >= Decimal("100")
    res25 = client.get("/api/v1/portfolio/options/realized", params={"year": 2024})
    assert res25.status_code == 200
    d24 = res25.json()["data"]
    assert d24["counts"]["long_term"] >= 1
    assert Decimal(str(d24["total_realized_pnl_long"])) >= Decimal("200")


def test_user_cannot_see_other_users_realized(client, db_session, user_a, user_b, broker_account_b):
    if db_session is None:
        pytest.skip("no db")
    oid, cid = _mk_trades(db_session, broker_account_b)
    secret = OptionTaxLot(
        user_id=user_b.id,
        broker_account_id=broker_account_b.id,
        symbol="SECRET 250117C00200000",
        underlying="SECRET",
        option_type="call",
        strike=Decimal("200"),
        expiry=date(2025, 1, 17),
        multiplier=100,
        quantity_opened=Decimal("1"),
        cost_basis_per_contract=Decimal("1"),
        opened_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        closed_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        quantity_closed=Decimal("1"),
        proceeds_per_contract=Decimal("2"),
        realized_pnl=Decimal("50"),
        holding_class="short_term",
        opening_trade_id=oid,
        closing_trade_id=cid,
    )
    db_session.add(secret)
    db_session.commit()

    res = client.get("/api/v1/portfolio/options/realized", params={"year": 2025})
    assert res.status_code == 200
    syms = [i["symbol"] for i in res.json()["data"]["items"]]
    assert "SECRET 250117C00200000" not in syms


def test_disabled_account_excluded(client, db_session, user_a):
    if db_session is None:
        pytest.skip("no db")
    suffix = uuid.uuid4().hex[:6]
    disabled_acct = BrokerAccount(
        user_id=user_a.id,
        broker=BrokerType.IBKR,
        account_number=f"DIS{suffix}",
        account_name="Disabled acct",
        account_type=AccountType.TAXABLE,
        sync_status=SyncStatus.NEVER_SYNCED,
        is_enabled=False,
    )
    db_session.add(disabled_acct)
    db_session.commit()
    db_session.refresh(disabled_acct)
    oid, cid = _mk_trades(db_session, disabled_acct)
    lot = OptionTaxLot(
        user_id=user_a.id,
        broker_account_id=disabled_acct.id,
        symbol="DIS   250117C00200000",
        underlying="DIS",
        option_type="call",
        strike=Decimal("200"),
        expiry=date(2025, 1, 17),
        multiplier=100,
        quantity_opened=Decimal("1"),
        cost_basis_per_contract=Decimal("1"),
        opened_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        closed_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        quantity_closed=Decimal("1"),
        proceeds_per_contract=Decimal("2"),
        realized_pnl=Decimal("77"),
        holding_class="short_term",
        opening_trade_id=oid,
        closing_trade_id=cid,
    )
    db_session.add(lot)
    db_session.commit()

    res = client.get("/api/v1/portfolio/options/realized", params={"year": 2025})
    assert res.status_code == 200
    syms = [i["symbol"] for i in res.json()["data"]["items"]]
    assert "DIS   250117C00200000" not in syms


def test_null_realized_pnl_nulls_group_total(client, db_session, user_a, broker_account_a):
    if db_session is None:
        pytest.skip("no db")
    oid, cid = _mk_trades(db_session, broker_account_a)
    oid2, cid2 = _mk_trades(db_session, broker_account_a)
    a = OptionTaxLot(
        user_id=user_a.id,
        broker_account_id=broker_account_a.id,
        symbol="NULL1 250117C00200000",
        underlying="NULL1",
        option_type="call",
        strike=Decimal("200"),
        expiry=date(2025, 1, 17),
        multiplier=100,
        quantity_opened=Decimal("1"),
        cost_basis_per_contract=Decimal("1"),
        opened_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        closed_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        quantity_closed=Decimal("1"),
        proceeds_per_contract=Decimal("2"),
        realized_pnl=None,
        holding_class="short_term",
        opening_trade_id=oid,
        closing_trade_id=cid,
    )
    b = OptionTaxLot(
        user_id=user_a.id,
        broker_account_id=broker_account_a.id,
        symbol="NULL2 250117C00200000",
        underlying="NULL2",
        option_type="call",
        strike=Decimal("200"),
        expiry=date(2025, 1, 17),
        multiplier=100,
        quantity_opened=Decimal("1"),
        cost_basis_per_contract=Decimal("1"),
        opened_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
        closed_at=datetime(2025, 6, 2, tzinfo=timezone.utc),
        quantity_closed=Decimal("1"),
        proceeds_per_contract=Decimal("2"),
        realized_pnl=Decimal("50"),
        holding_class="short_term",
        opening_trade_id=oid2,
        closing_trade_id=cid2,
    )
    db_session.add_all([a, b])
    db_session.commit()

    res = client.get("/api/v1/portfolio/options/realized", params={"year": 2025})
    assert res.status_code == 200
    assert res.json()["data"]["total_realized_pnl_short"] is None
