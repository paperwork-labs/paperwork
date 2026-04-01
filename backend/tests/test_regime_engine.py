"""Tests for regime_engine scoring and composite mapping."""

from datetime import date

import pytest

from backend.services.market.regime_engine import (
    RegimeInputs,
    REGIME_R1,
    REGIME_R2,
    REGIME_R3,
    REGIME_R5,
    composite_to_regime,
    compute_composite,
    compute_regime,
    score_nh_nl,
    score_pct_above_200d,
    score_pct_above_50d,
    score_vix,
    score_vix3m_vix,
    score_vvix_vix,
)

pytestmark = pytest.mark.no_db


def test_score_vix_boundaries() -> None:
    assert score_vix(13.0) == 1.0
    assert score_vix(13.001) == 2.0
    assert score_vix(16.0) == 2.0
    assert score_vix(16.001) == 3.0
    assert score_vix(22.0) == 3.0
    assert score_vix(22.001) == 4.0
    assert score_vix(30.0) == 4.0
    assert score_vix(30.001) == 5.0


def test_score_vix_nan() -> None:
    assert score_vix(float("nan")) == 3.0


def test_score_vix_none() -> None:
    assert score_vix(None) == 3.0  # type: ignore[arg-type]


def test_score_vix_zero() -> None:
    assert score_vix(0) == 3.0


def test_score_vix_negative() -> None:
    assert score_vix(-5) == 3.0


def test_score_vix3m_vix_boundaries() -> None:
    assert score_vix3m_vix(1.10) == 1.0
    assert score_vix3m_vix(1.03) == 2.0
    assert score_vix3m_vix(0.97) == 3.0
    assert score_vix3m_vix(0.90) == 4.0
    assert score_vix3m_vix(0.89) == 5.0


def test_score_vvix_vix_boundaries() -> None:
    assert score_vvix_vix(4.0) == 1.0
    assert score_vvix_vix(5.5) == 2.0
    assert score_vvix_vix(7.0) == 3.0
    assert score_vvix_vix(9.0) == 4.0
    assert score_vvix_vix(9.01) == 5.0


def test_score_nh_nl_boundaries() -> None:
    assert score_nh_nl(100) == 1.0
    assert score_nh_nl(30) == 2.0
    assert score_nh_nl(-30) == 3.0
    assert score_nh_nl(-100) == 4.0
    assert score_nh_nl(-101) == 5.0


def test_score_pct_above_200d() -> None:
    assert score_pct_above_200d(70) == 1.0
    assert score_pct_above_200d(55) == 2.0
    assert score_pct_above_200d(40) == 3.0
    assert score_pct_above_200d(25) == 4.0
    assert score_pct_above_200d(24) == 5.0


def test_score_pct_above_50d() -> None:
    assert score_pct_above_50d(75) == 1.0
    assert score_pct_above_50d(60) == 2.0
    assert score_pct_above_50d(40) == 3.0
    assert score_pct_above_50d(25) == 4.0
    assert score_pct_above_50d(24) == 5.0


def test_composite_rounding_half_up() -> None:
    # Mean 2.25 -> floor(2.25*2 + 0.5)/2 = floor(5.0)/2 = 2.5
    scores = [1.5, 1.5, 2.5, 2.5, 2.5, 3.0]
    assert sum(scores) / 6 == pytest.approx(2.25)
    assert compute_composite(scores) == 2.5


def test_composite_to_regime_r1() -> None:
    assert composite_to_regime(1.75) == REGIME_R1


def test_composite_to_regime_r2() -> None:
    assert composite_to_regime(2.0) == REGIME_R2


def test_composite_to_regime_r5() -> None:
    assert composite_to_regime(5.0) == REGIME_R5


def test_all_nan_inputs() -> None:
    nan = float("nan")
    # nh_nl is typed int but score_nh_nl accepts float NaN
    inputs = RegimeInputs(
        vix_spot=nan,
        vix3m_vix_ratio=nan,
        vvix_vix_ratio=nan,
        nh_nl=float("nan"),  # type: ignore[arg-type]
        pct_above_200d=nan,
        pct_above_50d=nan,
    )
    result = compute_regime(inputs, date(2026, 1, 15))
    assert result.composite_score == 3.0
    assert result.regime_state == REGIME_R3
