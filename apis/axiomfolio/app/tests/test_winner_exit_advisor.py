"""Unit tests for ``WinnerExitAdvisor``."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.services.gold.peak_signal_engine import PeakSignal
from app.services.gold.tax_aware_exit_calculator import (
    ExitLot,
    TaxAwareExitCalculator,
    TaxAwareExitResult,
    TaxProfile,
)
from app.services.gold.winner_exit_advisor import (
    ACTION_EXIT,
    ACTION_HOLD,
    ACTION_SCALE,
    ACTION_TRIM,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MED,
    WinnerExitAdvice,
    WinnerExitAdvisor,
)

pytestmark = pytest.mark.no_db


TODAY = date(2026, 4, 21)


def _tax_result_neutral() -> TaxAwareExitResult:
    """A tax-advantaged account result: zero drag, no breakeven."""
    calc = TaxAwareExitCalculator(TaxProfile.conservative_default())
    return calc.evaluate(
        symbol="X",
        current_price=Decimal("100"),
        exit_shares=Decimal("10"),
        lots=[
            ExitLot(
                shares=Decimal("10"),
                cost_per_share=Decimal("50"),
                acquired_on=TODAY - timedelta(days=30),
            )
        ],
        as_of=TODAY,
        tax_advantaged=True,
    )


def _tax_result_st_winner() -> TaxAwareExitResult:
    """Short-term gainer with real federal+state+NIIT drag."""
    calc = TaxAwareExitCalculator(TaxProfile.conservative_default())
    return calc.evaluate(
        symbol="X",
        current_price=Decimal("150"),
        exit_shares=Decimal("100"),
        lots=[
            ExitLot(
                shares=Decimal("100"),
                cost_per_share=Decimal("100"),
                acquired_on=TODAY - timedelta(days=90),
            )
        ],
        as_of=TODAY,
        tax_advantaged=False,
    )


def test_happy_path_cool_peak_risk_advises_hold():
    peak = PeakSignal(
        symbol="X",
        parabolic_score=Decimal("0.1"),
        climax_volume_score=Decimal("0"),
        distribution_score=Decimal("0.1"),
        td_exhaustion_flag=False,
        composite_severity="low",
        reasons=["cool technicals"],
    )
    advisor = WinnerExitAdvisor()
    out = advisor.advise(
        symbol="X",
        peak=peak,
        tax=_tax_result_st_winner(),
        current_price=Decimal("150"),
        stop_price=Decimal("130"),
        atr_value=Decimal("5"),
        regime_state="R1",
    )
    assert isinstance(out, WinnerExitAdvice)
    assert out.action == ACTION_HOLD
    assert out.suggested_scale_pct == 0
    assert out.confidence in {CONFIDENCE_MED, CONFIDENCE_LOW}
    assert "Advisory only" in out.summary


def test_boundary_everything_firing_advises_full_exit():
    peak = PeakSignal(
        symbol="X",
        parabolic_score=Decimal("0.95"),
        climax_volume_score=Decimal("0.9"),
        distribution_score=Decimal("0.9"),
        td_exhaustion_flag=True,
        composite_severity="high",
        reasons=["parabolic", "climax", "distribution"],
    )
    advisor = WinnerExitAdvisor()
    out = advisor.advise(
        symbol="X",
        peak=peak,
        tax=_tax_result_neutral(),  # tax-advantaged: no drag
        current_price=Decimal("150"),
        stop_price=Decimal("148"),  # very tight stop
        atr_value=Decimal("5"),
        regime_state="R5",  # risk-off
    )
    assert out.action == ACTION_EXIT
    assert out.suggested_scale_pct == 100
    assert out.confidence == CONFIDENCE_HIGH
    assert "Full exit" in out.summary


def test_empty_neutral_inputs_advises_hold_at_med_confidence():
    peak = PeakSignal(
        symbol="X",
        parabolic_score=Decimal("0"),
        climax_volume_score=Decimal("0"),
        distribution_score=Decimal("0"),
        td_exhaustion_flag=False,
        composite_severity="low",
        reasons=[],
    )
    advisor = WinnerExitAdvisor()
    out = advisor.advise(
        symbol="X",
        peak=peak,
        tax=_tax_result_neutral(),
        current_price=Decimal("100"),
        stop_price=None,
        atr_value=None,
        regime_state=None,
    )
    assert out.action == ACTION_HOLD
    assert out.suggested_scale_pct == 0
    assert out.confidence == CONFIDENCE_MED


def test_medium_peak_plus_tight_stop_advises_scale():
    peak = PeakSignal(
        symbol="X",
        parabolic_score=Decimal("0.5"),
        climax_volume_score=Decimal("0.4"),
        distribution_score=Decimal("0.3"),
        td_exhaustion_flag=True,
        composite_severity="med",
        reasons=["mixed topping"],
    )
    advisor = WinnerExitAdvisor()
    out = advisor.advise(
        symbol="X",
        peak=peak,
        tax=_tax_result_neutral(),
        current_price=Decimal("100"),
        stop_price=Decimal("99"),  # <1 ATR
        atr_value=Decimal("2"),
        regime_state="R3",  # neutral
    )
    assert out.action in {ACTION_SCALE, ACTION_EXIT}
    assert out.suggested_scale_pct >= 33


def test_advice_payload_is_json_friendly():
    peak = PeakSignal(
        symbol="X",
        parabolic_score=Decimal("0.3"),
        climax_volume_score=Decimal("0.2"),
        distribution_score=Decimal("0.3"),
        td_exhaustion_flag=False,
        composite_severity="med",
        reasons=["warm"],
    )
    advisor = WinnerExitAdvisor()
    out = advisor.advise(
        symbol="X",
        peak=peak,
        tax=_tax_result_st_winner(),
        current_price=Decimal("150"),
        stop_price=Decimal("140"),
        atr_value=Decimal("5"),
        regime_state="R2",
    )
    payload = out.to_payload()
    assert set(payload.keys()) == {
        "symbol",
        "action",
        "suggested_scale_pct",
        "confidence",
        "summary",
        "reasons",
    }
    assert isinstance(payload["suggested_scale_pct"], int)
    assert payload["action"] in {
        ACTION_HOLD,
        ACTION_TRIM,
        ACTION_SCALE,
        ACTION_EXIT,
    }


def test_summary_mentions_tax_dollars_for_taxable_winner():
    peak = PeakSignal(
        symbol="X",
        parabolic_score=Decimal("0.4"),
        climax_volume_score=Decimal("0.4"),
        distribution_score=Decimal("0.4"),
        td_exhaustion_flag=False,
        composite_severity="med",
        reasons=[],
    )
    advisor = WinnerExitAdvisor()
    tax = _tax_result_st_winner()
    out = advisor.advise(
        symbol="X",
        peak=peak,
        tax=tax,
        current_price=Decimal("150"),
        stop_price=Decimal("140"),
        atr_value=Decimal("5"),
        regime_state="R2",
    )
    assert "Exit tax est. $" in out.summary
    assert "after-tax $" in out.summary
