"""Tests for :meth:`OrderManager.list_orders` union of in-app orders and broker trades."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.models.broker_account import AccountStatus, AccountType, BrokerAccount, BrokerType
from backend.models.order import Order
from backend.models.trade import Trade
from backend.models.user import User, UserRole
from backend.services.execution.order_manager import OrderManager


def _make_user(db_session, *, prefix: str = "u") -> User:
    suffix = uuid.uuid4().hex[:10]
    u = User(
        email=f"{prefix}_{suffix}@example.com",
        username=f"{prefix}_{suffix}",
        password_hash="x" * 32,
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(u)
    db_session.flush()
    return u


def _make_account(db_session, user: User, *, enabled: bool = True) -> BrokerAccount:
    acc = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.SCHWAB,
        account_number=f"SCH-{uuid.uuid4().hex[:8]}",
        account_name="Test",
        account_type=AccountType.TAXABLE,
        status=AccountStatus.ACTIVE,
        is_enabled=enabled,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


@pytest.mark.usefixtures("db_session")
def test_list_orders_unions_trades_newest_first(db_session):
    if db_session is None:
        pytest.skip("database not configured")

    user = _make_user(db_session)
    acct = _make_account(db_session, user)
    now = datetime.now(timezone.utc)

    t_old = Trade(
        account_id=acct.id,
        symbol="OLD",
        side="BUY",
        quantity=Decimal("1"),
        price=Decimal("10"),
        status="FILLED",
        order_type="MARKET",
        execution_id=f"ex-old-{uuid.uuid4().hex[:8]}",
        execution_time=now - timedelta(hours=3),
    )
    t_new = Trade(
        account_id=acct.id,
        symbol="NEW",
        side="SELL",
        quantity=Decimal("2"),
        price=Decimal("20"),
        status="FILLED",
        order_type="MARKET",
        execution_id=f"ex-new-{uuid.uuid4().hex[:8]}",
        execution_time=now,
    )
    db_session.add_all([t_old, t_new])
    db_session.flush()

    o = Order(
        symbol="MID",
        side="buy",
        order_type="market",
        status="filled",
        quantity=5.0,
        filled_quantity=5.0,
        filled_avg_price=100.0,
        broker_type="schwab",
        source="manual",
        user_id=user.id,
        created_at=now - timedelta(hours=1),
        submitted_at=now - timedelta(hours=1),
        filled_at=now - timedelta(hours=1),
    )
    db_session.add(o)
    db_session.flush()

    mgr = OrderManager()
    rows = mgr.list_orders(db_session, user.id, limit=10)
    assert len(rows) == 3
    assert rows[0]["symbol"] == "NEW"
    assert rows[0]["provenance"] == "broker_sync"
    assert rows[1]["symbol"] == "MID"
    assert rows[1]["provenance"] == "app"
    assert rows[2]["symbol"] == "OLD"
    assert rows[2]["provenance"] == "broker_sync"


@pytest.mark.usefixtures("db_session")
def test_list_source_app_only_orders(db_session):
    if db_session is None:
        pytest.skip("database not configured")

    user = _make_user(db_session)
    acct = _make_account(db_session, user)
    now = datetime.now(timezone.utc)
    ex = f"ex-{uuid.uuid4().hex[:8]}"
    db_session.add(
        Trade(
            account_id=acct.id,
            symbol="T1",
            side="BUY",
            quantity=Decimal("1"),
            price=Decimal("5"),
            status="FILLED",
            order_type="MARKET",
            execution_id=ex,
            execution_time=now,
        )
    )
    db_session.add(
        Order(
            symbol="O1",
            side="buy",
            order_type="market",
            status="filled",
            quantity=1.0,
            filled_quantity=1.0,
            filled_avg_price=10.0,
            broker_type="schwab",
            source="manual",
            user_id=user.id,
            filled_at=now - timedelta(hours=1),
        )
    )
    db_session.flush()

    mgr = OrderManager()
    rows = mgr.list_orders(db_session, user.id, limit=10, list_source="app")
    assert len(rows) == 1
    assert rows[0]["symbol"] == "O1"
    assert rows[0]["provenance"] == "app"


@pytest.mark.usefixtures("db_session")
def test_list_source_broker_only_trades(db_session):
    if db_session is None:
        pytest.skip("database not configured")

    user = _make_user(db_session)
    acct = _make_account(db_session, user)
    now = datetime.now(timezone.utc)
    ex = f"ex-{uuid.uuid4().hex[:8]}"
    db_session.add(
        Trade(
            account_id=acct.id,
            symbol="T1",
            side="BUY",
            quantity=Decimal("1"),
            price=Decimal("5"),
            status="FILLED",
            order_type="MARKET",
            execution_id=ex,
            execution_time=now,
        )
    )
    db_session.add(
        Order(
            symbol="O1",
            side="buy",
            order_type="market",
            status="filled",
            quantity=1.0,
            filled_quantity=1.0,
            filled_avg_price=10.0,
            broker_type="schwab",
            source="manual",
            user_id=user.id,
            filled_at=now - timedelta(hours=1),
        )
    )
    db_session.flush()

    mgr = OrderManager()
    rows = mgr.list_orders(db_session, user.id, limit=10, list_source="broker")
    assert len(rows) == 1
    assert rows[0]["symbol"] == "T1"
    assert rows[0]["provenance"] == "broker_sync"


@pytest.mark.usefixtures("db_session")
def test_pagination_limit_offset(db_session):
    if db_session is None:
        pytest.skip("database not configured")

    user = _make_user(db_session)
    now = datetime.now(timezone.utc)
    for i in range(3):
        db_session.add(
            Order(
                symbol=f"S{i}",
                side="buy",
                order_type="market",
                status="filled",
                quantity=1.0,
                filled_quantity=1.0,
                filled_avg_price=10.0,
                broker_type="schwab",
                source="manual",
                user_id=user.id,
                filled_at=now - timedelta(hours=i),
            )
        )
    db_session.flush()

    mgr = OrderManager()
    p0 = mgr.list_orders(db_session, user.id, limit=1, offset=0, list_source="app")
    p1 = mgr.list_orders(db_session, user.id, limit=1, offset=1, list_source="app")
    assert len(p0) == 1
    assert len(p1) == 1
    assert p0[0]["symbol"] != p1[0]["symbol"]


@pytest.mark.usefixtures("db_session")
def test_user_isolation(db_session):
    if db_session is None:
        pytest.skip("database not configured")

    ua = _make_user(db_session, prefix="a")
    ub = _make_user(db_session, prefix="b")
    acct_a = _make_account(db_session, ua)
    acct_b = _make_account(db_session, ub)
    now = datetime.now(timezone.utc)

    db_session.add(
        Order(
            symbol="ONLYA",
            side="buy",
            order_type="market",
            status="filled",
            quantity=1.0,
            filled_quantity=1.0,
            filled_avg_price=1.0,
            broker_type="schwab",
            source="manual",
            user_id=ua.id,
            filled_at=now,
        )
    )
    db_session.add(
        Trade(
            account_id=acct_b.id,
            symbol="ONLYB",
            side="BUY",
            quantity=Decimal("1"),
            price=Decimal("1"),
            status="FILLED",
            order_type="MARKET",
            execution_id=f"ex-b-{uuid.uuid4().hex[:8]}",
            execution_time=now,
        )
    )
    db_session.flush()

    mgr = OrderManager()
    for_b = mgr.list_orders(db_session, ub.id, limit=50)
    assert len(for_b) == 1
    assert for_b[0]["symbol"] == "ONLYB"

    for_a = mgr.list_orders(db_session, ua.id, limit=50)
    assert len(for_a) == 1
    assert for_a[0]["symbol"] == "ONLYA"


@pytest.mark.usefixtures("db_session")
def test_include_broker_fills_false_is_app_only(db_session):
    if db_session is None:
        pytest.skip("database not configured")

    user = _make_user(db_session)
    acct = _make_account(db_session, user)
    now = datetime.now(timezone.utc)
    db_session.add(
        Trade(
            account_id=acct.id,
            symbol="T1",
            side="BUY",
            quantity=Decimal("1"),
            price=Decimal("5"),
            status="FILLED",
            order_type="MARKET",
            execution_id=f"ex-{uuid.uuid4().hex[:8]}",
            execution_time=now,
        )
    )
    db_session.add(
        Order(
            symbol="O1",
            side="buy",
            order_type="market",
            status="filled",
            quantity=1.0,
            filled_quantity=1.0,
            filled_avg_price=10.0,
            broker_type="schwab",
            source="manual",
            user_id=user.id,
            filled_at=now - timedelta(hours=1),
        )
    )
    db_session.flush()

    mgr = OrderManager()
    rows = mgr.list_orders(
        db_session, user.id, limit=10, list_source="all", include_broker_fills=False
    )
    assert len(rows) == 1
    assert rows[0]["symbol"] == "O1"


@pytest.mark.usefixtures("db_session")
def test_disabled_broker_account_excludes_trades(db_session):
    if db_session is None:
        pytest.skip("database not configured")

    user = _make_user(db_session)
    acct = _make_account(db_session, user, enabled=False)
    now = datetime.now(timezone.utc)
    db_session.add(
        Trade(
            account_id=acct.id,
            symbol="HID",
            side="BUY",
            quantity=Decimal("1"),
            price=Decimal("5"),
            status="FILLED",
            order_type="MARKET",
            execution_id=f"ex-{uuid.uuid4().hex[:8]}",
            execution_time=now,
        )
    )
    db_session.flush()

    mgr = OrderManager()
    rows = mgr.list_orders(db_session, user.id, limit=10, list_source="all")
    assert rows == []
