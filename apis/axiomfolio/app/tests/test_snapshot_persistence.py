"""Snapshot persistence wire-up (Wave D).

These tests verify that the five target columns on ``MarketSnapshot`` —
``volume_avg_20d``, ``vol_ratio``, ``regime_state``, ``previous_stage_label``,
``next_earnings`` — are actually written when the snapshot build path runs,
rather than being computed and dropped on the floor.

The columns already existed on the model and the math already produced the
values; the gap (especially for ``regime_state``) was purely in the
snapshot write path's dict-to-row mapping. See D## in KNOWLEDGE.md.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from app.models.market_data import (
    EarningsCalendarEvent,
    MarketRegime,
    MarketSnapshot,
    MarketSnapshotHistory,
)
from app.services.silver.market.market_data_service import (
    price_bars,
    snapshot_builder,
)


@pytest.fixture(autouse=True)
def _stub_fundamentals(monkeypatch):
    monkeypatch.setattr(
        snapshot_builder._fundamentals,
        "get_fundamentals_info",
        lambda *a, **kw: {},
    )


def _make_ohlcv_df(n: int, base: float = 100.0, vol: int = 1_000_000) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=n + 10)
    idx = [start + timedelta(days=i) for i in range(n)]
    close = base + np.cumsum(rng.normal(0, 0.2, n))
    volume = vol + rng.integers(0, 100_000, n)
    return pd.DataFrame(
        {
            "Open": close,
            "High": close + 0.1,
            "Low": close - 0.1,
            "Close": close,
            "Volume": volume,
        },
        index=pd.DatetimeIndex(idx),
    )


def _seed_prices(db_session, symbol: str, n: int = 260) -> None:
    df = _make_ohlcv_df(n)
    price_bars.persist_price_bars(
        db_session, symbol, df, interval="1d", data_source="unit_test", is_adjusted=True
    )
    # Benchmark for RS / stage computation
    price_bars.persist_price_bars(
        db_session,
        "SPY",
        _make_ohlcv_df(n, base=450.0),
        interval="1d",
        data_source="unit_test",
        is_adjusted=True,
    )


def test_persist_snapshot_writes_volume_avg_and_vol_ratio(db_session):
    """volume_avg_20d and vol_ratio are computed in indicator_engine and must
    reach the MarketSnapshot row, not just the raw_analysis JSON blob."""
    sym = "VOLPERS"
    _seed_prices(db_session, sym)

    snap = snapshot_builder.compute_snapshot_from_db(
        db_session, sym, skip_fundamentals=True
    )
    assert snap, "snapshot build should succeed"
    assert snap.get("volume_avg_20d") is not None
    assert snap.get("vol_ratio") is not None

    snapshot_builder.persist_snapshot(db_session, sym, snap)

    row = (
        db_session.query(MarketSnapshot)
        .filter(MarketSnapshot.symbol == sym)
        .one()
    )
    assert row.volume_avg_20d is not None and float(row.volume_avg_20d) > 0
    assert row.vol_ratio is not None


def test_persist_snapshot_writes_regime_state_from_market_regime(db_session):
    """regime_state must come from the canonical MarketRegime row at snapshot
    build time, not be inherited from a prior stale MarketSnapshot row."""
    sym = "REGPERS"
    _seed_prices(db_session, sym)

    # Seed a fresh regime. compute_snapshot_from_db should pick this up.
    now = datetime.now(timezone.utc)
    db_session.add(
        MarketRegime(
            as_of_date=now,
            composite_score=1.5,
            regime_state="R2",
        )
    )
    db_session.commit()

    snap = snapshot_builder.compute_snapshot_from_db(
        db_session, sym, skip_fundamentals=True
    )
    assert snap.get("regime_state") == "R2"

    snapshot_builder.persist_snapshot(db_session, sym, snap)
    row = (
        db_session.query(MarketSnapshot)
        .filter(MarketSnapshot.symbol == sym)
        .one()
    )
    assert row.regime_state == "R2"


def test_regime_state_refresh_overrides_prior_stale_row(db_session):
    """Regression: older code read regime_state from the prior MarketSnapshot
    row for stage input only; the current row's regime_state column was
    effectively whatever the last scan_overlay tick set. Now the snapshot
    pipeline stamps regime_state from the canonical MarketRegime, so a fresh
    regime transition is reflected on the very next snapshot build."""
    sym = "REGREF"
    _seed_prices(db_session, sym)

    now = datetime.now(timezone.utc)
    # Prior snapshot row carries a stale regime_state.
    db_session.add(
        MarketSnapshot(
            symbol=sym,
            analysis_type="technical_snapshot",
            analysis_timestamp=now - timedelta(days=1),
            expiry_timestamp=now + timedelta(days=1),
            is_valid=True,
            regime_state="R1",
        )
    )
    # Regime engine has since moved to R4.
    db_session.add(
        MarketRegime(
            as_of_date=now,
            composite_score=2.7,
            regime_state="R4",
        )
    )
    db_session.commit()

    metrics: dict[str, int] = {}
    snap = snapshot_builder.compute_snapshot_from_db(
        db_session, sym, skip_fundamentals=True, recompute_metrics=metrics
    )
    assert snap.get("regime_state") == "R4"
    assert metrics.get("regime_state_written", 0) == 1

    snapshot_builder.persist_snapshot(db_session, sym, snap)
    row = (
        db_session.query(MarketSnapshot)
        .filter(MarketSnapshot.symbol == sym)
        .one()
    )
    assert row.regime_state == "R4"


def test_persist_snapshot_populates_previous_stage_label_from_history(db_session):
    """When history supports it, previous_stage_label is derived and persisted."""
    sym = "PREVST"
    _seed_prices(db_session, sym)

    # Seed history with two older rows establishing a stage transition 2A -> 2B.
    base_date = datetime.now(timezone.utc) - timedelta(days=10)
    for i, lbl in enumerate(["2A", "2A", "2B"]):
        db_session.add(
            MarketSnapshotHistory(
                symbol=sym,
                analysis_type="technical_snapshot",
                as_of_date=base_date + timedelta(days=i),
                stage_label=lbl,
                current_stage_days=(i + 1) if lbl == "2A" else 1,
                previous_stage_label=None if lbl == "2A" else "2A",
                previous_stage_days=None if lbl == "2A" else 2,
            )
        )
    db_session.commit()

    out = snapshot_builder._derive_stage_run_fields(
        current_stage_label="2B",
        prior_stage_labels=["2A", "2A", "2B"],
        latest_history_row=(
            db_session.query(MarketSnapshotHistory)
            .filter(MarketSnapshotHistory.symbol == sym)
            .order_by(MarketSnapshotHistory.as_of_date.desc())
            .first()
        ),
    )
    assert out["previous_stage_label"] == "2A"
    assert out["current_stage_days"] is not None


def test_persist_snapshot_writes_next_earnings_from_calendar(db_session):
    """next_earnings must be pulled from earnings_calendar (authoritative) and
    written to MarketSnapshot.next_earnings on every snapshot build."""
    sym = "EARNPERS"
    _seed_prices(db_session, sym)

    target_date = (datetime.now(timezone.utc) + timedelta(days=7)).date()
    db_session.add(
        EarningsCalendarEvent(
            symbol=sym,
            report_date=target_date,
            fiscal_period="Q1",
            source="unit_test",
        )
    )
    db_session.commit()

    snap = snapshot_builder.compute_snapshot_from_db(
        db_session, sym, skip_fundamentals=True
    )
    assert snap.get("next_earnings") is not None
    assert snap["next_earnings"].date() == target_date

    snapshot_builder.persist_snapshot(db_session, sym, snap)
    row = (
        db_session.query(MarketSnapshot)
        .filter(MarketSnapshot.symbol == sym)
        .one()
    )
    assert row.next_earnings is not None
    assert row.next_earnings.date() == target_date
