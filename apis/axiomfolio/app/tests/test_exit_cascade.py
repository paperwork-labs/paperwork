"""Tests for exit_cascade tier logic and full cascade evaluation."""

import pytest

from app.services.execution.exit_cascade import (
    ExitAction,
    PositionContext,
    _short_s4_target,
    _tier1_stop_loss,
    _tier2_trailing_stop,
    _tier3_stage_deterioration,
    _tier6_regime_transition,
    _tier7_regime_trail,
    evaluate_exit_cascade,
)
from app.services.market.regime_engine import REGIME_R1, REGIME_R3, REGIME_R4

pytestmark = pytest.mark.no_db


def _long_base(**overrides) -> PositionContext:
    """Defaults: profitable long, above hard stop, R3 stable, no time/stage pressure."""
    fields = {
        "symbol": "TEST",
        "side": "LONG",
        "entry_price": 100.0,
        "current_price": 105.0,
        "atr_14": 3.0,
        "atrp_14": 3.0,
        "stage_label": "2A",
        "previous_stage_label": "2A",
        "current_stage_days": 5,
        "ext_pct": 10.0,
        "sma150_slope": 0.1,
        "ema10_dist_n": 0.5,
        "rs_mansfield": 5.0,
        "regime_state": REGIME_R3,
        "previous_regime_state": REGIME_R3,
        "days_held": 10,
        "pnl_pct": 5.0,
        "high_water_price": 108.0,
    }
    fields.update(overrides)
    return PositionContext(**fields)


def _short_base(**overrides) -> PositionContext:
    fields = {
        "symbol": "SHORT1",
        "side": "SHORT",
        "entry_price": 100.0,
        "current_price": 95.0,
        "atr_14": 2.0,
        "atrp_14": 3.0,
        "stage_label": "4A",
        "previous_stage_label": "4B",
        "current_stage_days": 3,
        "ext_pct": -5.0,
        "sma150_slope": -0.1,
        "ema10_dist_n": -0.5,
        "rs_mansfield": -2.0,
        "regime_state": REGIME_R4,
        "previous_regime_state": REGIME_R4,
        "days_held": 5,
        "pnl_pct": 5.0,
        "high_water_price": None,
    }
    fields.update(overrides)
    return PositionContext(**fields)


def test_t1_stop_loss_fires() -> None:
    ctx = _long_base(entry_price=100.0, current_price=94.0, atr_14=3.0)
    sig = _tier1_stop_loss(ctx)
    assert sig.action == ExitAction.EXIT
    assert "stop" in sig.reason.lower()


def test_t1_stop_loss_no_fire() -> None:
    ctx = _long_base(entry_price=100.0, current_price=95.0, atr_14=3.0)
    sig = _tier1_stop_loss(ctx)
    assert sig.action == ExitAction.HOLD


def test_t2_trailing_fires() -> None:
    # 2A: 1.5× ATR = 4.5; hwm 120 -> trigger 115.5; pnl>0 required
    ctx = _long_base(
        entry_price=100.0,
        current_price=110.0,
        atr_14=3.0,
        atrp_14=3.0,
        stage_label="2A",
        regime_state=REGIME_R1,
        previous_regime_state=REGIME_R1,
        pnl_pct=10.0,
        high_water_price=120.0,
    )
    sig = _tier2_trailing_stop(ctx)
    assert sig.action == ExitAction.EXIT


def test_t2_trailing_no_fire() -> None:
    ctx = _long_base(
        entry_price=100.0,
        current_price=116.0,
        atr_14=3.0,
        atrp_14=3.0,
        stage_label="2A",
        regime_state=REGIME_R1,
        previous_regime_state=REGIME_R1,
        pnl_pct=16.0,
        high_water_price=120.0,
    )
    sig = _tier2_trailing_stop(ctx)
    assert sig.action == ExitAction.HOLD


def test_t3_stage_deterioration() -> None:
    ctx = _long_base(previous_stage_label="2B", stage_label="4A")
    sig = _tier3_stage_deterioration(ctx)
    assert sig.action == ExitAction.EXIT
    assert "4A" in sig.reason


def test_t6_regime_transition_fires() -> None:
    ctx = _long_base(
        regime_state=REGIME_R4,
        previous_regime_state=REGIME_R1,
    )
    sig = _tier6_regime_transition(ctx)
    assert sig is not None
    assert sig.action == ExitAction.EXIT
    assert sig.tier == "T6"


def test_t6_no_previous_regime() -> None:
    ctx = _long_base(previous_regime_state=None)
    assert _tier6_regime_transition(ctx) is None


def test_t7_regime_trail_fires() -> None:
    # R4: 0.75× ATR = 2.25; hwm 120 -> trigger 117.75
    ctx = _long_base(
        regime_state=REGIME_R4,
        previous_regime_state=REGIME_R4,
        atr_14=3.0,
        current_price=115.0,
        pnl_pct=10.0,
        high_water_price=120.0,
        entry_price=100.0,
    )
    sig = _tier7_regime_trail(ctx)
    assert sig.action == ExitAction.EXIT
    assert sig.tier == "T7"


def test_s4_35_percent_reachable() -> None:
    ctx = _short_base(pnl_pct=40.0)
    sig = _short_s4_target(ctx)
    assert sig.action == ExitAction.EXIT


def test_s4_20_percent() -> None:
    ctx = _short_base(pnl_pct=25.0)
    sig = _short_s4_target(ctx)
    assert sig.action == ExitAction.REDUCE_50


def test_evaluate_cascade_basic() -> None:
    ctx = _long_base()
    result = evaluate_exit_cascade(ctx)
    assert result.symbol == "TEST"
    assert result.final_action == ExitAction.HOLD
    assert result.final_reason == "All tiers clear"
    assert result.final_tier == ""
