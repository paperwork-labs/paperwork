"""list_orders merges Axiom Order rows with broker Trade ledger rows."""

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


def _make_user(db_session) -> User:
    suffix = uuid.uuid4().hex[:10]
    u = User(
        email=f"lo_{suffix}@example.com",
        username=f"lo_{suffix}",
        password_hash="x" * 32,
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(u)
    db_session.flush()
    return u


def _make_account(db_session, user: User) -> BrokerAccount:
    acc = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.SCHWAB,
        account_number=f"SCH-{uuid.uuid4().hex[:8]}",
        account_name="Test",
        account_type=AccountType.TAXABLE,
        status=AccountStatus.ACTIVE,
        is_enabled=True,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


@pytest.mark.usefixtures("db_session")
def test_list_orders_merges_trades_newest_first(db_session):
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
    # Newest first: t_new, then order, then t_old
    assert rows[0]["symbol"] == "NEW"
    assert rows[0]["ledger"] == "trade"
    assert rows[1]["symbol"] == "MID"
    assert rows[1]["ledger"] == "order"
    assert rows[2]["symbol"] == "OLD"
    assert rows[2]["ledger"] == "trade"
