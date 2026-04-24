"""IBKR pipeline invokes the FIFO matcher and populates OptionTaxLot.

Where Schwab ships ``positionEffect`` on transactions, IBKR FlexQuery
ships ``openCloseIndicator`` on each Trade row and already populates
``trade_metadata.asset_category = "OPT"`` for option executions. So the
closing_lot_matcher's option branch already has everything it needs —
this test asserts the pipeline wires the call through.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models import BrokerAccount, Trade
from app.models.broker_account import AccountType, BrokerType
from app.models.option_tax_lot import OptionTaxLot
from app.models.user import User
from app.services.portfolio.ibkr.pipeline import (
    _run_closing_lot_reconciliation,
)

OPT = "AAPL  250117C00200000"


def _user_and_account(db_session) -> BrokerAccount:
    suffix = uuid.uuid4().hex[:8]
    u = User(
        username=f"ibkr_opt_{suffix}",
        email=f"ibkr_opt_{suffix}@example.test",
        password_hash="x",
        is_active=True,
    )
    db_session.add(u)
    db_session.flush()
    acct = BrokerAccount(
        user_id=u.id,
        broker=BrokerType.IBKR,
        account_number=f"U{suffix}",
        account_name="IBKR opt test",
        account_type=AccountType.TAXABLE,
        currency="USD",
    )
    db_session.add(acct)
    db_session.commit()
    db_session.refresh(acct)
    return acct


def _add_option_trade(
    db_session,
    account_id: int,
    *,
    exec_id: str,
    side: str,
    is_opening: bool,
    quantity: Decimal,
    price: Decimal,
    when: datetime,
    realized_pnl: Decimal | None = None,
) -> Trade:
    t = Trade(
        account_id=account_id,
        symbol=OPT,
        side=side,
        quantity=quantity,
        price=price,
        total_value=price * quantity,
        commission=Decimal("0.65"),
        execution_id=exec_id,
        execution_time=when,
        status="FILLED",
        is_opening=is_opening,
        is_paper_trade=False,
        realized_pnl=realized_pnl,
        trade_metadata={"asset_category": "OPT", "multiplier": 100},
    )
    db_session.add(t)
    db_session.flush()
    return t


def test_ibkr_reconciliation_creates_option_tax_lot(db_session) -> None:
    if db_session is None:
        pytest.skip("no db")
    acct = _user_and_account(db_session)
    t_open = datetime(2025, 1, 10, 16, 0, 0, tzinfo=UTC)
    t_close = datetime(2025, 3, 10, 16, 0, 0, tzinfo=UTC)

    _add_option_trade(
        db_session,
        acct.id,
        exec_id="ibkr-open-1",
        side="BUY",
        is_opening=True,
        quantity=Decimal("2"),
        price=Decimal("5.00"),
        when=t_open,
    )
    _add_option_trade(
        db_session,
        acct.id,
        exec_id="ibkr-close-1",
        side="SELL",
        is_opening=False,
        quantity=Decimal("2"),
        price=Decimal("8.00"),
        when=t_close,
        realized_pnl=Decimal("470.00"),
    )
    db_session.commit()

    results: dict = {}
    _run_closing_lot_reconciliation(db_session, acct, results)
    db_session.commit()

    assert results.get("option_tax_lots_created", 0) == 1
    rows = db_session.query(OptionTaxLot).filter(OptionTaxLot.broker_account_id == acct.id).all()
    assert len(rows) == 1
    r = rows[0]
    assert r.quantity_closed == Decimal("2")
    assert r.underlying == "AAPL"
    assert r.option_type == "call"
    assert r.realized_pnl == Decimal("470.0000")
    assert r.holding_class == "short_term"


def test_ibkr_reconciliation_idempotent(db_session) -> None:
    if db_session is None:
        pytest.skip("no db")
    acct = _user_and_account(db_session)
    t_open = datetime(2024, 2, 1, 16, 0, 0, tzinfo=UTC)
    t_close = t_open + timedelta(days=400)

    _add_option_trade(
        db_session,
        acct.id,
        exec_id="ibkr-open-lt",
        side="BUY",
        is_opening=True,
        quantity=Decimal("1"),
        price=Decimal("4.00"),
        when=t_open,
    )
    _add_option_trade(
        db_session,
        acct.id,
        exec_id="ibkr-close-lt",
        side="SELL",
        is_opening=False,
        quantity=Decimal("1"),
        price=Decimal("9.00"),
        when=t_close,
        realized_pnl=Decimal("500.00"),
    )
    db_session.commit()

    for _ in range(2):
        results: dict = {}
        _run_closing_lot_reconciliation(db_session, acct, results)
        db_session.commit()

    n = db_session.query(OptionTaxLot).filter(OptionTaxLot.broker_account_id == acct.id).count()
    assert n == 1
    r = db_session.query(OptionTaxLot).filter(OptionTaxLot.broker_account_id == acct.id).one()
    assert r.holding_class == "long_term"


def test_ibkr_reconciliation_pnl_drift_counter(db_session) -> None:
    """Broker-reported realized_pnl disagrees with matcher — counter increments, no raise."""
    if db_session is None:
        pytest.skip("no db")
    acct = _user_and_account(db_session)
    t_open = datetime(2025, 1, 10, 16, 0, 0, tzinfo=UTC)
    t_close = datetime(2025, 3, 10, 16, 0, 0, tzinfo=UTC)
    _add_option_trade(
        db_session,
        acct.id,
        exec_id="ibkr-open-drift",
        side="BUY",
        is_opening=True,
        quantity=Decimal("2"),
        price=Decimal("5.00"),
        when=t_open,
    )
    # Broker claims $999 realized; FIFO matcher will compute ~$470.
    _add_option_trade(
        db_session,
        acct.id,
        exec_id="ibkr-close-drift",
        side="SELL",
        is_opening=False,
        quantity=Decimal("2"),
        price=Decimal("8.00"),
        when=t_close,
        realized_pnl=Decimal("999.00"),
    )
    db_session.commit()

    results: dict = {}
    _run_closing_lot_reconciliation(db_session, acct, results)
    db_session.commit()

    assert results.get("option_tax_lots_created", 0) == 1
    assert results.get("option_pnl_discrepancies", 0) == 1
