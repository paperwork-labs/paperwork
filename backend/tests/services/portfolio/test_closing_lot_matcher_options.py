"""FIFO option closed-lot matcher (OptionTaxLot rows)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.models.broker_account import AccountType, BrokerAccount, BrokerType
from backend.models.option_tax_lot import OptionTaxLot
from backend.models.trade import Trade
from backend.models.user import User
from backend.services.portfolio.closing_lot_matcher import reconcile_closing_lots


def _user(session, name: str) -> User:
    u = User(username=name, email=f"{name}@example.test", password_hash="x", is_active=True)
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _acct(session, user: User, num: str) -> BrokerAccount:
    a = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.SCHWAB,
        account_number=num,
        account_name=f"acct {num}",
        account_type=AccountType.TAXABLE,
        currency="USD",
    )
    session.add(a)
    session.commit()
    session.refresh(a)
    return a


def _trade(
    session,
    account: BrokerAccount,
    *,
    symbol: str,
    side: str,
    qty: Decimal,
    price: Decimal,
    eid: str,
    t: datetime,
    opening: bool,
    meta: dict | None = None,
) -> Trade:
    tr = Trade(
        account_id=account.id,
        symbol=symbol,
        side=side,
        quantity=qty,
        price=price,
        total_value=qty * price,
        commission=Decimal("0"),
        execution_id=eid,
        execution_time=t,
        status="FILLED",
        is_opening=opening,
        is_paper_trade=False,
        trade_metadata=meta or {"asset_category": "OPT"},
    )
    session.add(tr)
    session.flush()
    return tr


OPT = "AAPL  250117C00200000"


def test_fifo_long_call_close(db_session):
    if db_session is None:
        pytest.skip("no db")
    u = _user(db_session, "optfifo1")
    a = _acct(db_session, u, "OF1")
    t0 = datetime(2025, 1, 10, tzinfo=timezone.utc)
    t1 = datetime(2025, 3, 10, tzinfo=timezone.utc)
    _trade(db_session, a, symbol=OPT, side="BUY", qty=Decimal("2"), price=Decimal("5"), eid="b1", t=t0, opening=True)
    _trade(db_session, a, symbol=OPT, side="SELL", qty=Decimal("2"), price=Decimal("8"), eid="s1", t=t1, opening=False)
    db_session.commit()

    reconcile_closing_lots(db_session, a)
    db_session.commit()

    rows = db_session.query(OptionTaxLot).filter(OptionTaxLot.broker_account_id == a.id).all()
    assert len(rows) == 1
    r = rows[0]
    assert r.quantity_closed == Decimal("2")
    assert r.option_type == "call"
    assert r.underlying == "AAPL"
    assert r.realized_pnl == (Decimal("8") - Decimal("5")) * Decimal("2") * Decimal("100")
    assert r.holding_class == "short_term"


def test_fifo_short_put_close(db_session):
    if db_session is None:
        pytest.skip("no db")
    sym = "XYZ   250220P00050000"
    u = _user(db_session, "optfifo2")
    a = _acct(db_session, u, "OF2")
    t0 = datetime(2025, 2, 1, tzinfo=timezone.utc)
    t1 = datetime(2025, 2, 15, tzinfo=timezone.utc)
    _trade(db_session, a, symbol=sym, side="SELL", qty=Decimal("3"), price=Decimal("4"), eid="os1", t=t0, opening=True)
    _trade(db_session, a, symbol=sym, side="BUY", qty=Decimal("3"), price=Decimal("2"), eid="cs1", t=t1, opening=False)
    db_session.commit()

    reconcile_closing_lots(db_session, a)
    db_session.commit()

    rows = db_session.query(OptionTaxLot).filter(OptionTaxLot.broker_account_id == a.id).all()
    assert len(rows) == 1
    r = rows[0]
    assert r.quantity_opened == Decimal("3")
    assert r.quantity_closed == Decimal("-3")
    assert r.option_type == "put"
    # (proceeds - cost) * qty_closed * mult = (2 - 4) * (-3) * 100 = 600
    assert r.realized_pnl == Decimal("600")


def test_partial_close_cascades_fifo(db_session):
    if db_session is None:
        pytest.skip("no db")
    u = _user(db_session, "optfifo3")
    a = _acct(db_session, u, "OF3")
    sym = "QQQ   250301C00400000"
    _trade(
        db_session, a, symbol=sym, side="BUY", qty=Decimal("2"), price=Decimal("3"),
        eid="b1", t=datetime(2025, 1, 1, tzinfo=timezone.utc), opening=True,
    )
    _trade(
        db_session, a, symbol=sym, side="BUY", qty=Decimal("3"), price=Decimal("4"),
        eid="b2", t=datetime(2025, 2, 1, tzinfo=timezone.utc), opening=True,
    )
    _trade(
        db_session, a, symbol=sym, side="SELL", qty=Decimal("4"), price=Decimal("6"),
        eid="s1", t=datetime(2025, 3, 1, tzinfo=timezone.utc), opening=False,
    )
    db_session.commit()

    reconcile_closing_lots(db_session, a)
    db_session.commit()

    rows = (
        db_session.query(OptionTaxLot)
        .filter(OptionTaxLot.broker_account_id == a.id)
        .order_by(OptionTaxLot.id.asc())
        .all()
    )
    assert len(rows) == 2
    assert rows[0].quantity_closed == Decimal("2")
    assert rows[0].opening_trade_id != rows[1].opening_trade_id
    assert rows[1].quantity_closed == Decimal("2")
    assert sum(r.realized_pnl or Decimal("0") for r in rows) == Decimal("1000")


def test_short_close_merges_multi_slice_same_lot(db_session):
    if db_session is None:
        pytest.skip("no db")
    sym = "IWM   250430C00200000"
    u = _user(db_session, "optfifo4")
    a = _acct(db_session, u, "OF4")
    _trade(
        db_session, a, symbol=sym, side="SELL", qty=Decimal("10"), price=Decimal("2"),
        eid="os", t=datetime(2025, 1, 1, tzinfo=timezone.utc), opening=True,
    )
    _trade(
        db_session, a, symbol=sym, side="BUY", qty=Decimal("10"), price=Decimal("1"),
        eid="cs", t=datetime(2025, 2, 1, tzinfo=timezone.utc), opening=False,
    )
    db_session.commit()

    reconcile_closing_lots(db_session, a)
    db_session.commit()

    rows = db_session.query(OptionTaxLot).filter(OptionTaxLot.broker_account_id == a.id).all()
    assert len(rows) == 1
    assert rows[0].quantity_closed == Decimal("-10")


def test_holding_class_long_term_at_365_calendar_days(db_session):
    if db_session is None:
        pytest.skip("no db")
    u = _user(db_session, "optfifo5")
    a = _acct(db_session, u, "OF5")
    opened = datetime(2023, 1, 1, tzinfo=timezone.utc)
    # Must exceed 365 calendar days (same rule as stock CLOSED_LOT is_long_term)
    closed = datetime(2024, 1, 2, tzinfo=timezone.utc)
    _trade(db_session, a, symbol=OPT, side="BUY", qty=Decimal("1"), price=Decimal("1"), eid="bl", t=opened, opening=True)
    _trade(db_session, a, symbol=OPT, side="SELL", qty=Decimal("1"), price=Decimal("2"), eid="sl", t=closed, opening=False)
    db_session.commit()

    reconcile_closing_lots(db_session, a)
    db_session.commit()

    r = db_session.query(OptionTaxLot).filter(OptionTaxLot.broker_account_id == a.id).one()
    assert r.holding_class == "long_term"


def test_holding_class_short_term_under_365_days(db_session):
    if db_session is None:
        pytest.skip("no db")
    u = _user(db_session, "optfifo6")
    a = _acct(db_session, u, "OF6")
    opened = datetime(2024, 1, 1, tzinfo=timezone.utc)
    closed = datetime(2024, 12, 31, tzinfo=timezone.utc)
    _trade(db_session, a, symbol=OPT, side="BUY", qty=Decimal("1"), price=Decimal("1"), eid="bs", t=opened, opening=True)
    _trade(db_session, a, symbol=OPT, side="SELL", qty=Decimal("1"), price=Decimal("2"), eid="ss", t=closed, opening=False)
    db_session.commit()

    reconcile_closing_lots(db_session, a)
    db_session.commit()

    r = db_session.query(OptionTaxLot).filter(OptionTaxLot.broker_account_id == a.id).one()
    assert r.holding_class == "short_term"
