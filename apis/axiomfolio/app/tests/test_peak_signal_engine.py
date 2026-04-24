"""Unit tests for ``PeakSignalEngine``.

These tests do not touch the database -- the engine is pure and reads a
``MarketSnapshot`` instance passed in by the caller. We construct snapshots
in-memory via the ORM constructor and never commit them.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.market_data import MarketSnapshot
from app.services.gold.peak_signal_engine import PeakSignal, PeakSignalEngine

pytestmark = pytest.mark.no_db


def _snap(**kw) -> MarketSnapshot:
    """Build a snapshot with only the fields the engine actually reads.

    Unset fields default to ``None`` which the engine tolerates.
    """
    return MarketSnapshot(
        symbol=kw.pop("symbol", "TEST"),
        analysis_type=kw.pop("analysis_type", "technical_snapshot"),
        **kw,
    )


def test_happy_path_cool_stage_2a_low_severity():
    row = _snap(
        stage_label="2A",
        previous_stage_label="2A",
        rs_mansfield_pct=40.0,
        ext_pct=4.0,
        atr_dist_ema21=1.0,
        range_pos_52w=60.0,
        vol_ratio=1.0,
        perf_1d=0.5,
        td_sell_setup=2,
        action_label="HOLD",
    )
    out = PeakSignalEngine().evaluate("TEST", row)
    assert isinstance(out, PeakSignal)
    assert out.composite_severity == "low"
    assert out.td_exhaustion_flag is False
    # Parabolic should not fire at 4% above SMA150 or 1 ATR above EMA21.
    assert out.parabolic_score == Decimal("0")


def test_boundary_parabolic_climax_td_all_fire_high_severity():
    row = _snap(
        stage_label="3A",
        previous_stage_label="2C",
        rs_mansfield_pct=-5.0,
        ext_pct=22.0,  # past PARABOLIC_EXT_PCT_DANGER
        atr_dist_ema21=8.0,  # past PARABOLIC_ATR_DIST_DANGER
        atrx_sma_150=6.0,
        range_pos_52w=97.0,
        vol_ratio=3.0,  # past CLIMAX_VOL_RATIO_DANGER
        perf_1d=7.0,
        td_sell_setup=9,  # exhaustion
        td_sell_complete=True,
        action_label="REDUCE",
    )
    out = PeakSignalEngine().evaluate("TEST", row)
    assert out.composite_severity == "high"
    assert out.parabolic_score >= Decimal("0.80")
    assert out.climax_volume_score >= Decimal("0.80")
    assert out.distribution_score >= Decimal("0.70")
    assert out.td_exhaustion_flag is True
    assert any("Stage" in r for r in out.reasons)


def test_empty_snapshot_returns_neutral_signal():
    out = PeakSignalEngine().evaluate("TEST", None)
    assert out.symbol == "TEST"
    assert out.composite_severity == "low"
    assert out.parabolic_score == Decimal("0")
    assert out.climax_volume_score == Decimal("0")
    assert out.distribution_score == Decimal("0")
    assert out.td_exhaustion_flag is False
    assert "snapshot data not available" in out.reasons


def test_symbol_is_normalized_upper_stripped():
    row = _snap(stage_label="2A")
    out = PeakSignalEngine().evaluate("  aapl ", row)
    assert out.symbol == "AAPL"


def test_stage_transition_2_to_3_elevates_distribution_score():
    row = _snap(
        stage_label="3A",
        previous_stage_label="2B",
        rs_mansfield_pct=10.0,
        ext_pct=2.0,
    )
    out = PeakSignalEngine().evaluate("TEST", row)
    assert out.distribution_score >= Decimal("0.55")
    assert any("transition" in r.lower() for r in out.reasons)


def test_climax_without_range_position_still_scores_but_lower():
    # Elevated volume in the middle of the range earns the base score but
    # no top-of-range boost.
    row_mid = _snap(
        vol_ratio=3.0,
        perf_1d=1.0,
        range_pos_52w=40.0,
    )
    row_top = _snap(
        vol_ratio=3.0,
        perf_1d=6.0,
        range_pos_52w=95.0,
    )
    mid = PeakSignalEngine().evaluate("TEST", row_mid)
    top = PeakSignalEngine().evaluate("TEST", row_top)
    assert top.climax_volume_score > mid.climax_volume_score


def test_payload_is_json_serialisable_floats():
    row = _snap(stage_label="2A", ext_pct=3.0)
    payload = PeakSignalEngine().evaluate("TEST", row).to_payload()
    for key in (
        "parabolic_score",
        "climax_volume_score",
        "distribution_score",
    ):
        assert isinstance(payload[key], float)
    assert isinstance(payload["td_exhaustion_flag"], bool)
    assert payload["composite_severity"] in {"low", "med", "high"}
