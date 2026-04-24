"""Earnings calendar refresh (Wave D).

Verifies that ``next_earnings`` on the persisted MarketSnapshot row reflects
the authoritative ``EarningsCalendarEvent`` for the symbol, end-to-end
through the build + persist pipeline.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from backend.models.market_data import EarningsCalendarEvent, MarketSnapshot
from backend.services.market.market_data_service import price_bars, snapshot_builder


@pytest.fixture(autouse=True)
def _stub_fundamentals(monkeypatch):
    monkeypatch.setattr(
        snapshot_builder._fundamentals,
        "get_fundamentals_info",
        lambda *a, **kw: {},
    )


def _seed_ohlcv(db_session, symbol: str, n: int = 260) -> None:
    rng = np.random.default_rng(1)
    start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=n + 10)
    idx = pd.DatetimeIndex([start + timedelta(days=i) for i in range(n)])
    close = 50.0 + np.cumsum(rng.normal(0, 0.2, n))
    vol = 200_000 + rng.integers(0, 50_000, n)
    df = pd.DataFrame(
        {"Open": close, "High": close + 0.1, "Low": close - 0.1, "Close": close, "Volume": vol},
        index=idx,
    )
    price_bars.persist_price_bars(
        db_session, symbol, df, interval="1d", data_source="unit_test", is_adjusted=True
    )


def test_earnings_calendar_event_flows_into_snapshot_next_earnings(db_session):
    """EarningsCalendarEvent(report_date=2026-05-15) -> MarketSnapshot.next_earnings."""
    sym = "EARNFLOW"
    _seed_ohlcv(db_session, sym)

    target = (datetime.now(timezone.utc) + timedelta(days=20)).date()
    db_session.add(
        EarningsCalendarEvent(
            symbol=sym,
            report_date=target,
            fiscal_period="Q2",
            source="unit_test",
        )
    )
    db_session.commit()

    snap = snapshot_builder.compute_snapshot_from_db(
        db_session, sym, skip_fundamentals=True
    )
    snapshot_builder.persist_snapshot(db_session, sym, snap)

    row = (
        db_session.query(MarketSnapshot)
        .filter(MarketSnapshot.symbol == sym)
        .one()
    )
    assert row.next_earnings is not None
    assert row.next_earnings.date() == target


def test_snapshot_next_earnings_clears_when_calendar_empty(db_session):
    """When there is no future earnings calendar row, next_earnings on the
    snapshot is explicitly None — not a silently-inherited stale value from
    a prior snapshot row (no-silent-fallback)."""
    sym = "EARNEMPTY"
    _seed_ohlcv(db_session, sym)

    snap = snapshot_builder.compute_snapshot_from_db(
        db_session, sym, skip_fundamentals=True
    )
    snapshot_builder.persist_snapshot(db_session, sym, snap)

    row = (
        db_session.query(MarketSnapshot)
        .filter(MarketSnapshot.symbol == sym)
        .one()
    )
    assert row.next_earnings is None
