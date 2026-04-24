"""Tests for regime_engine scoring and composite mapping."""

from datetime import date

import pytest

from app.services.silver.regime.regime_engine import (
    REGIME_R1,
    REGIME_R2,
    REGIME_R3,
    REGIME_R4,
    REGIME_R5,
    WEIGHTS,
    WEIGHT_SUM,
    RegimeInputs,
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


# ── VIX scoring: <17 / 17–20 / 20–27 / 27–35 / ≥35 ──

class TestScoreVix:
    def test_deep_bull(self) -> None:
        assert score_vix(10.0) == 1.0
        assert score_vix(16.99) == 1.0

    def test_boundary_17_is_bearish(self) -> None:
        assert score_vix(17.0) == 2.0

    def test_mid_ranges(self) -> None:
        assert score_vix(18.5) == 2.0
        assert score_vix(20.0) == 3.0
        assert score_vix(25.0) == 3.0
        assert score_vix(27.0) == 4.0
        assert score_vix(32.0) == 4.0

    def test_boundary_35_is_bearish(self) -> None:
        assert score_vix(35.0) == 5.0
        assert score_vix(50.0) == 5.0

    def test_invalid_inputs(self) -> None:
        assert score_vix(None) == 3.0  # type: ignore[arg-type]
        assert score_vix(float("nan")) == 3.0
        assert score_vix(0) == 3.0
        assert score_vix(-5) == 3.0


# ── VIX3M/VIX scoring: >1.10 / (1.05,1.10] / (1.00,1.05] / (0.90,1.00] / ≤0.90 ──

class TestScoreVix3mVix:
    def test_strong_contango(self) -> None:
        assert score_vix3m_vix(1.15) == 1.0
        assert score_vix3m_vix(1.11) == 1.0

    def test_boundary_1_10_is_bearish(self) -> None:
        assert score_vix3m_vix(1.10) == 2.0

    def test_mid_ranges(self) -> None:
        assert score_vix3m_vix(1.07) == 2.0
        assert score_vix3m_vix(1.05) == 3.0
        assert score_vix3m_vix(1.02) == 3.0
        assert score_vix3m_vix(1.00) == 4.0
        assert score_vix3m_vix(0.95) == 4.0

    def test_boundary_0_90_is_bearish(self) -> None:
        assert score_vix3m_vix(0.90) == 5.0
        assert score_vix3m_vix(0.80) == 5.0

    def test_invalid(self) -> None:
        assert score_vix3m_vix(None) == 3.0  # type: ignore[arg-type]
        assert score_vix3m_vix(float("nan")) == 3.0


# ── VVIX/VIX scoring (non-monotonic): ≥7.0→5 / (5.5,7.0)→1 / (4.5,5.5]→2 / etc. ──

class TestScoreVvixVix:
    def test_optimal_range(self) -> None:
        assert score_vvix_vix(6.0) == 1.0
        assert score_vvix_vix(5.51) == 1.0
        assert score_vvix_vix(6.99) == 1.0

    def test_boundary_5_5_is_bearish(self) -> None:
        assert score_vvix_vix(5.5) == 2.0

    def test_mid_ranges(self) -> None:
        assert score_vvix_vix(5.0) == 2.0
        assert score_vvix_vix(4.5) == 3.0
        assert score_vvix_vix(4.0) == 3.0
        assert score_vvix_vix(3.5) == 4.0
        assert score_vvix_vix(3.0) == 4.0

    def test_extreme_high_is_bearish(self) -> None:
        assert score_vvix_vix(7.0) == 5.0
        assert score_vvix_vix(10.0) == 5.0

    def test_collapsed_ratio_is_bearish(self) -> None:
        assert score_vvix_vix(2.5) == 5.0
        assert score_vvix_vix(2.0) == 5.0
        assert score_vvix_vix(1.0) == 5.0

    def test_invalid(self) -> None:
        assert score_vvix_vix(None) == 3.0  # type: ignore[arg-type]
        assert score_vvix_vix(float("nan")) == 3.0


# ── NH-NL scoring: >100 / (20,100] / (-50,20] / (-150,-50] / ≤-150 ──

class TestScoreNhNl:
    def test_strong_breadth(self) -> None:
        assert score_nh_nl(200) == 1.0
        assert score_nh_nl(101) == 1.0

    def test_boundary_100_is_bearish(self) -> None:
        assert score_nh_nl(100) == 2.0

    def test_mid_ranges(self) -> None:
        assert score_nh_nl(50) == 2.0
        assert score_nh_nl(20) == 3.0
        assert score_nh_nl(0) == 3.0
        assert score_nh_nl(-50) == 4.0
        assert score_nh_nl(-100) == 4.0

    def test_boundary_negative_150_is_bearish(self) -> None:
        assert score_nh_nl(-150) == 5.0
        assert score_nh_nl(-200) == 5.0

    def test_invalid(self) -> None:
        assert score_nh_nl(None) == 3.0
        assert score_nh_nl(float("nan")) == 3.0


# ── % above 200D scoring: >65 / (55,65] / (45,55] / (30,45] / ≤30 ──

class TestScorePctAbove200d:
    def test_healthy(self) -> None:
        assert score_pct_above_200d(80) == 1.0
        assert score_pct_above_200d(66) == 1.0

    def test_boundary_65_is_bearish(self) -> None:
        assert score_pct_above_200d(65) == 2.0

    def test_mid_ranges(self) -> None:
        assert score_pct_above_200d(60) == 2.0
        assert score_pct_above_200d(55) == 3.0
        assert score_pct_above_200d(50) == 3.0
        assert score_pct_above_200d(45) == 4.0
        assert score_pct_above_200d(35) == 4.0

    def test_boundary_30_is_bearish(self) -> None:
        assert score_pct_above_200d(30) == 5.0
        assert score_pct_above_200d(20) == 5.0

    def test_invalid(self) -> None:
        assert score_pct_above_200d(None) == 3.0  # type: ignore[arg-type]


# ── % above 50D scoring: >65 / (50,65] / (35,50] / (15,35] / ≤15 ──

class TestScorePctAbove50d:
    def test_healthy(self) -> None:
        assert score_pct_above_50d(80) == 1.0
        assert score_pct_above_50d(66) == 1.0

    def test_boundary_65_is_bearish(self) -> None:
        assert score_pct_above_50d(65) == 2.0

    def test_mid_ranges(self) -> None:
        assert score_pct_above_50d(55) == 2.0
        assert score_pct_above_50d(50) == 3.0
        assert score_pct_above_50d(40) == 3.0
        assert score_pct_above_50d(35) == 4.0
        assert score_pct_above_50d(20) == 4.0

    def test_boundary_15_is_bearish(self) -> None:
        assert score_pct_above_50d(15) == 5.0
        assert score_pct_above_50d(10) == 5.0


# ── Weighted composite ──

class TestComputeComposite:
    def test_weights_constant(self) -> None:
        assert WEIGHTS == [1.00, 1.25, 0.75, 1.00, 1.00, 0.75]
        assert WEIGHT_SUM == pytest.approx(5.75)

    def test_all_ones(self) -> None:
        assert compute_composite([1, 1, 1, 1, 1, 1]) == 1.0

    def test_all_fives(self) -> None:
        assert compute_composite([5, 5, 5, 5, 5, 5]) == 5.0

    def test_all_threes(self) -> None:
        assert compute_composite([3, 3, 3, 3, 3, 3]) == 3.0

    def test_weighted_average(self) -> None:
        scores = [1, 2, 3, 2, 2, 3]
        expected = (1*1.0 + 2*1.25 + 3*0.75 + 2*1.0 + 2*1.0 + 3*0.75) / 5.75
        rounded = round(expected * 4) / 4
        assert compute_composite(scores) == rounded

    def test_rounds_to_nearest_quarter(self) -> None:
        scores = [2, 2, 3, 2, 2, 3]
        result = compute_composite(scores)
        assert result * 4 == round(result * 4)

    def test_vix_term_structure_weight_dominance(self) -> None:
        base = [3, 3, 3, 3, 3, 3]
        term_bull = list(base)
        term_bull[1] = 1  # VIX3M/VIX gets weight 1.25
        vol_bull = list(base)
        vol_bull[2] = 1   # VVIX/VIX gets weight 0.75
        assert compute_composite(term_bull) < compute_composite(vol_bull)


# ── Regime mapping with boundary rule ──

class TestCompositeToRegime:
    def test_r1_range(self) -> None:
        assert composite_to_regime(1.0) == REGIME_R1
        assert composite_to_regime(1.25) == REGIME_R1
        assert composite_to_regime(1.5) == REGIME_R1
        assert composite_to_regime(1.75) == REGIME_R1

    def test_r2_range(self) -> None:
        assert composite_to_regime(2.0) == REGIME_R2
        assert composite_to_regime(2.25) == REGIME_R2

    def test_boundary_2_50_is_r3(self) -> None:
        assert composite_to_regime(2.50) == REGIME_R3

    def test_r3_range(self) -> None:
        assert composite_to_regime(2.75) == REGIME_R3
        assert composite_to_regime(3.0) == REGIME_R3
        assert composite_to_regime(3.25) == REGIME_R3

    def test_boundary_3_50_is_r4(self) -> None:
        assert composite_to_regime(3.50) == REGIME_R4

    def test_r4_range(self) -> None:
        assert composite_to_regime(3.75) == REGIME_R4
        assert composite_to_regime(4.0) == REGIME_R4
        assert composite_to_regime(4.25) == REGIME_R4

    def test_boundary_4_50_is_r5(self) -> None:
        assert composite_to_regime(4.50) == REGIME_R5

    def test_r5_range(self) -> None:
        assert composite_to_regime(4.75) == REGIME_R5
        assert composite_to_regime(5.0) == REGIME_R5


# ── End-to-end compute_regime ──

class TestComputeRegime:
    def test_bull_market(self) -> None:
        inputs = RegimeInputs(
            vix_spot=12.0,
            vix3m_vix_ratio=1.15,
            vvix_vix_ratio=6.0,
            nh_nl=150,
            pct_above_200d=75,
            pct_above_50d=70,
        )
        result = compute_regime(inputs, date(2026, 4, 6))
        assert result.regime_state == REGIME_R1
        assert result.composite_score == 1.0
        assert result.regime_multiplier == 1.0
        assert result.cash_floor_pct == 5.0
        assert result.max_equity_exposure_pct == 90.0
        assert result.weights_used == WEIGHTS

    def test_bear_market(self) -> None:
        inputs = RegimeInputs(
            vix_spot=40.0,
            vix3m_vix_ratio=0.85,
            vvix_vix_ratio=2.0,
            nh_nl=-200,
            pct_above_200d=20,
            pct_above_50d=10,
        )
        result = compute_regime(inputs, date(2026, 4, 6))
        assert result.regime_state == REGIME_R5
        assert result.composite_score == 5.0
        assert result.regime_multiplier == 0.0
        assert result.cash_floor_pct == 70.0
        assert result.max_equity_exposure_pct == 10.0

    def test_all_nan_inputs_neutral(self) -> None:
        nan = float("nan")
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

    def test_r5_multiplier_blocks_longs(self) -> None:
        inputs = RegimeInputs(
            vix_spot=40.0,
            vix3m_vix_ratio=0.85,
            vvix_vix_ratio=2.0,
            nh_nl=-200,
            pct_above_200d=20,
            pct_above_50d=10,
        )
        result = compute_regime(inputs, date(2026, 4, 6))
        assert result.regime_multiplier == 0.0

    def test_weights_returned(self) -> None:
        inputs = RegimeInputs(
            vix_spot=15.0,
            vix3m_vix_ratio=1.08,
            vvix_vix_ratio=5.0,
            nh_nl=50,
            pct_above_200d=60,
            pct_above_50d=55,
        )
        result = compute_regime(inputs, date(2026, 4, 6))
        assert result.weights_used == [1.0, 1.25, 0.75, 1.0, 1.0, 0.75]
        assert len(result.weights_used) == 6
