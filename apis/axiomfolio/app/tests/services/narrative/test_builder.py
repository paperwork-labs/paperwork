"""Tests for portfolio narrative summary assembly."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.models.broker_account import AccountType, BrokerAccount, BrokerType
from app.models.instrument import Instrument, InstrumentType
from app.models.market_data import MarketRegime, MarketSnapshotHistory
from app.models.portfolio import PortfolioHistory
from app.models.position import Position, PositionStatus, PositionType
from app.models.user import User
from app.services.gold.narrative.builder import build_portfolio_summary


def test_build_portfolio_summary_shape(db_session):
    suffix = uuid.uuid4().hex[:10]
    u = User(
        email=f"narr_builder_{suffix}@example.com",
        username=f"narr_builder_{suffix}",
        password_hash="x",
    )
    db_session.add(u)
    db_session.flush()

    ba = BrokerAccount(
        user_id=u.id,
        broker=BrokerType.IBKR,
        account_number=f"NARR_{suffix}",
        account_type=AccountType.TAXABLE,
    )
    sym = f"Z{suffix}"[:8]
    instr = Instrument(symbol=sym, instrument_type=InstrumentType.STOCK)
    db_session.add_all([ba, instr])
    db_session.flush()

    pos = Position(
        user_id=u.id,
        account_id=ba.id,
        instrument_id=instr.id,
        symbol=sym,
        quantity=Decimal("10"),
        average_cost=Decimal("100"),
        total_cost_basis=Decimal("1000"),
        position_type=PositionType.LONG,
        status=PositionStatus.OPEN,
        instrument_type="STOCK",
        day_pnl_pct=Decimal("3.25"),
    )
    db_session.add(pos)

    d = date(2026, 4, 15)
    db_session.add(
        PortfolioHistory(
            user_id=u.id,
            account_id=ba.id,
            as_of_date=d,
            total_value=Decimal("10000"),
            cash_value=Decimal("0"),
            positions_value=Decimal("10000"),
        )
    )
    db_session.add(
        PortfolioHistory(
            user_id=u.id,
            account_id=ba.id,
            as_of_date=date(2026, 4, 14),
            total_value=Decimal("9900"),
            cash_value=Decimal("0"),
            positions_value=Decimal("9900"),
        )
    )

    hist_prev = MarketSnapshotHistory(
        symbol=sym,
        analysis_type="technical_snapshot",
        as_of_date=datetime(2026, 4, 14, 0, 0, 0, tzinfo=UTC),
        stage_label="2A",
        perf_1d=0.1,
    )
    hist_today = MarketSnapshotHistory(
        symbol=sym,
        analysis_type="technical_snapshot",
        as_of_date=datetime(2026, 4, 15, 0, 0, 0, tzinfo=UTC),
        stage_label="3A",
        vol_ratio=2.5,
        perf_1d=0.2,
    )
    spy = MarketSnapshotHistory(
        symbol="SPY",
        analysis_type="technical_snapshot",
        as_of_date=datetime(2026, 4, 15, 0, 0, 0, tzinfo=UTC),
        stage_label="3B",
        perf_1d=1.25,
    )
    db_session.add_all([hist_prev, hist_today, spy])

    db_session.add(
        MarketRegime(
            as_of_date=datetime(2026, 4, 15, 0, 0, 0, tzinfo=UTC),
            regime_state="R2",
            composite_score=2.0,
        )
    )
    db_session.commit()

    summary = build_portfolio_summary(db_session, u.id, d)
    assert summary["top_movers"]
    assert summary["top_movers"][0]["symbol"] == sym
    assert summary["stage_transitions"]
    assert summary["stage_transitions"][0]["from"] == "2A"
    assert summary["stage_transitions"][0]["to"] == "3A"
    assert summary["spy_return_pct"] == pytest.approx(1.25)
    assert summary["portfolio_return_pct"] is not None
    assert summary["regime_state"] == "R2"
