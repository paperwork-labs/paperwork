"""Tests for Stage Analysis sub-stage classification.

Tests :func:`classify_stage_for_timeframe` (scalar rules),
:func:`classify_stage_full` (scalar + state tracking), and
:func:`classify_stage_series` (vectorized rules + ATRE / RS post-steps).
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.market.indicator_engine import (
    classify_stage_for_timeframe,
    classify_stage_full,
    classify_stage_series,
)

pytestmark = pytest.mark.no_db


def _tf(
    price: float,
    sma150: float,
    sma50: float,
    ema10: float,
    *,
    sma21: float = 0.0,
    sma150_slope: float | None,
    sma50_slope: float | None,
    ext_pct: float | None = None,
    vol_ratio: float = 0.0,
    prev_stage: str | None = None,
) -> str:
    """Thin wrapper matching production argument order after *price*."""
    return classify_stage_for_timeframe(
        price,
        sma150,
        sma50,
        ema10,
        prev_stage,
        sma21=sma21,
        sma150_slope=sma150_slope,
        sma50_slope=sma50_slope,
        ext_pct=ext_pct,
        vol_ratio=vol_ratio,
    )


def _series_pack(
    close: float,
    sma150: float,
    sma50: float,
    sma21: float,
    ema10: float,
    sma150_slope: float,
    sma50_slope: float,
    ext_pct: float,
    atre_150: float,
    vol_ratio: float,
    rs_mansfield: float,
) -> dict[str, pd.Series]:
    idx = pd.RangeIndex(1)
    return {
        "close": pd.Series([close], index=idx),
        "sma150": pd.Series([sma150], index=idx),
        "sma50": pd.Series([sma50], index=idx),
        "sma21": pd.Series([sma21], index=idx),
        "ema10": pd.Series([ema10], index=idx),
        "sma150_slope": pd.Series([sma150_slope], index=idx),
        "sma50_slope": pd.Series([sma50_slope], index=idx),
        "ext_pct": pd.Series([ext_pct], index=idx),
        "atre_150": pd.Series([atre_150], index=idx),
        "vol_ratio": pd.Series([vol_ratio], index=idx),
        "rs_mansfield": pd.Series([rs_mansfield], index=idx),
    }


# ── Ext% band boundary tests ──


class TestStage4:
    def test_4c_deep_capitulation(self) -> None:
        """4C: below SMA150, slope strongly down, ext <= -30%"""
        assert (
            _tf(70.0, 100.0, 85.0, 68.0, sma150_slope=-0.5, sma50_slope=-0.4, ext_pct=-30.0) == "4C"
        )
        assert (
            _tf(65.0, 100.0, 85.0, 63.0, sma150_slope=-0.8, sma50_slope=-0.6, ext_pct=-35.0) == "4C"
        )

    def test_4b_accelerating_decline(self) -> None:
        """4B: below, slope strongly down, ext in (-30, -15], SMA50 < SMA150"""
        assert (
            _tf(85.0, 100.0, 95.0, 84.0, sma150_slope=-0.5, sma50_slope=-0.3, ext_pct=-15.0) == "4B"
        )
        assert (
            _tf(80.0, 100.0, 90.0, 78.0, sma150_slope=-0.5, sma50_slope=-0.3, ext_pct=-20.0) == "4B"
        )

    def test_4b_requires_sma50_below(self) -> None:
        """4B needs SMA50 < SMA150; with SMA50 > SMA150 it shouldn't match 4B."""
        result = _tf(85.0, 100.0, 105.0, 84.0, sma150_slope=-0.5, sma50_slope=-0.3, ext_pct=-15.0)
        assert result != "4B"

    def test_4a_early_decline(self) -> None:
        """4A: below, slope strongly down or flat+SMA50 weak, ext in (-15, -5]"""
        assert (
            _tf(92.0, 100.0, 97.0, 91.0, sma150_slope=-0.5, sma50_slope=-0.3, ext_pct=-8.0) == "4A"
        )
        assert (
            _tf(95.0, 100.0, 97.0, 94.0, sma150_slope=-0.5, sma50_slope=-0.3, ext_pct=-5.0) == "4A"
        )

    def test_4a_flat_slope_with_weak_sma50(self) -> None:
        """4A via flat SMA150 slope + SMA50 slope < -0.35%"""
        assert (
            _tf(93.0, 100.0, 97.0, 92.0, sma150_slope=-0.1, sma50_slope=-0.5, ext_pct=-7.0) == "4A"
        )


class TestStage1:
    def test_1a_deep_base(self) -> None:
        """1A: flat slope, SMA50 <= SMA150, ext in (-5, 0]"""
        assert (
            _tf(98.0, 100.0, 99.0, 97.5, sma150_slope=-0.1, sma50_slope=0.1, ext_pct=-2.0) == "1A"
        )
        assert _tf(100.0, 100.0, 98.0, 99.0, sma150_slope=0.0, sma50_slope=0.0, ext_pct=0.0) == "1A"

    def test_1a_sma50_above_becomes_3a_or_1b(self) -> None:
        """With SMA50 > SMA150, 1A doesn't match (disambiguation to 3A)."""
        result = _tf(98.0, 100.0, 101.0, 97.5, sma150_slope=0.1, sma50_slope=0.1, ext_pct=-2.0)
        assert result != "1A"

    def test_1b_late_base(self) -> None:
        """1B: flat slope, ext in (-5, 0], Close > SMA21, EMA10 > SMA21.
        SMA50 > SMA150 to skip 1A disambiguation."""
        assert (
            _tf(
                99.0,
                100.0,
                101.0,
                99.5,
                sma21=98.0,
                sma150_slope=0.1,
                sma50_slope=0.1,
                ext_pct=-1.0,
            )
            == "1B"
        )

    def test_1b_breakout_captured_by_2a(self) -> None:
        """When price breaks above SMA150, ext becomes positive → 2A captures it."""
        assert (
            _tf(
                101.0,
                100.0,
                95.0,
                102.0,
                sma21=97.0,
                sma150_slope=0.2,
                sma50_slope=0.2,
                ext_pct=1.0,
                vol_ratio=2.0,
            )
            == "2A"
        )


class TestStage2:
    def test_2a_early_advance(self) -> None:
        """2A: above, slope >= 0, ext 0-8%, EMA stack (ema10 > sma21 > sma50)"""
        assert (
            _tf(
                105.0,
                100.0,
                102.0,
                106.0,
                sma21=104.0,
                sma150_slope=0.2,
                sma50_slope=0.3,
                ext_pct=5.0,
            )
            == "2A"
        )

    def test_2a_boundary_8_pct(self) -> None:
        """ext_pct = 8.0 is still 2A (boundary inclusive)."""
        assert (
            _tf(
                108.0,
                100.0,
                103.0,
                109.0,
                sma21=106.0,
                sma150_slope=0.3,
                sma50_slope=0.3,
                ext_pct=8.0,
            )
            == "2A"
        )

    def test_2a_requires_ema_stack(self) -> None:
        """2A needs EMA10 > SMA21 > SMA50; without it, falls through."""
        result = _tf(
            105.0,
            100.0,
            104.0,
            103.0,
            sma21=102.0,
            sma150_slope=0.2,
            sma50_slope=0.3,
            ext_pct=5.0,
        )
        assert result != "2A"

    def test_2b_confirmed_advance(self) -> None:
        """2B: above, slope > 0.35%, ext in (8, 20], SMA50 > SMA150, SMA50 slope > 0.35%"""
        assert (
            _tf(
                115.0,
                100.0,
                108.0,
                116.0,
                sma21=113.0,
                sma150_slope=0.5,
                sma50_slope=0.5,
                ext_pct=15.0,
            )
            == "2B"
        )

    def test_2b_boundary_20_pct(self) -> None:
        """ext_pct = 20.0 is still 2B (boundary inclusive)."""
        assert (
            _tf(
                120.0,
                100.0,
                110.0,
                121.0,
                sma21=118.0,
                sma150_slope=0.6,
                sma50_slope=0.6,
                ext_pct=20.0,
            )
            == "2B"
        )

    def test_2c_extended(self) -> None:
        """2C: above, slope > 0.35%, ext > 20%"""
        assert (
            _tf(
                125.0,
                100.0,
                112.0,
                126.0,
                sma21=120.0,
                sma150_slope=0.7,
                sma50_slope=0.6,
                ext_pct=25.0,
            )
            == "2C"
        )

    def test_2c_via_atre_promoted(self) -> None:
        """2C via ATRE sticky is a post-step in classify_stage_full, not raw."""
        r = classify_stage_full(
            close=110.0,
            sma150=100.0,
            sma50=105.0,
            sma21=108.0,
            ema10=111.0,
            sma150_slope=0.5,
            sma50_slope=0.5,
            ext_pct=10.0,
            atre_150=5.0,
            vol_ratio=1.0,
            prior_atre_promoted=True,
        )
        assert r.stage_label == "2C"
        assert r.atre_promoted is True


class TestStage3:
    def test_3a_early_distribution(self) -> None:
        """3A: slope gently positive, ext in (-5, 0], SMA50 > SMA150"""
        assert (
            _tf(
                99.0,
                100.0,
                102.0,
                98.5,
                sma21=100.0,
                sma150_slope=0.2,
                sma50_slope=0.1,
                ext_pct=-1.0,
            )
            == "3A"
        )

    def test_3b_late_distribution(self) -> None:
        """3B: flat slope, Close < SMA50, SMA50 slope < 0, EMA < SMA21 < SMA50.
        SMA50 > SMA150 to skip 1A disambiguation."""
        assert (
            _tf(
                96.0,
                100.0,
                101.0,
                95.0,
                sma21=97.0,
                sma150_slope=-0.1,
                sma50_slope=-0.2,
                ext_pct=-4.0,
            )
            == "3B"
        )


class TestFallback:
    def test_no_match_returns_3a(self) -> None:
        """Fallback: no rule match → 3A. (above SMA150, slope up, no EMA stack)"""
        result = _tf(
            105.0,
            100.0,
            104.0,
            103.0,
            sma21=103.5,
            sma150_slope=0.5,
            sma50_slope=0.2,
            ext_pct=5.0,
        )
        assert result == "3A"

    def test_missing_slopes_returns_prev_stage(self) -> None:
        """Missing slopes → returns prev_stage."""
        assert (
            _tf(100.0, 100.0, 100.0, 100.0, sma150_slope=None, sma50_slope=None, prev_stage="2B")
            == "2B"
        )

    def test_missing_slopes_returns_unknown(self) -> None:
        assert _tf(100.0, 100.0, 100.0, 100.0, sma150_slope=None, sma50_slope=None) == "UNKNOWN"


# ── classify_stage_full: state management ──


class TestClassifyFull:
    def test_atre_promote(self) -> None:
        """ATRE_150 > 6.0 promotes to 2C and sets atre_promoted."""
        r = classify_stage_full(
            close=106.0,
            sma150=100.0,
            sma50=103.0,
            sma21=104.0,
            ema10=105.0,
            sma150_slope=0.4,
            sma50_slope=0.4,
            ext_pct=6.0,
            atre_150=7.0,
            vol_ratio=1.0,
        )
        assert r.stage_label == "2C"
        assert r.atre_promoted is True

    def test_atre_hysteresis_stays_promoted(self) -> None:
        """ATRE_150 between 4.0 and 6.0 with prior promoted → stays promoted."""
        r = classify_stage_full(
            close=106.0,
            sma150=100.0,
            sma50=103.0,
            sma21=104.0,
            ema10=105.0,
            sma150_slope=0.4,
            sma50_slope=0.4,
            ext_pct=6.0,
            atre_150=5.0,
            vol_ratio=1.0,
            prior_atre_promoted=True,
        )
        assert r.atre_promoted is True
        assert r.stage_label == "2C"

    def test_atre_clears_below_4(self) -> None:
        """ATRE_150 < 4.0 clears the atre_promoted flag."""
        r = classify_stage_full(
            close=106.0,
            sma150=100.0,
            sma50=103.0,
            sma21=104.0,
            ema10=105.0,
            sma150_slope=0.4,
            sma50_slope=0.4,
            ext_pct=6.0,
            atre_150=3.5,
            vol_ratio=1.0,
            prior_atre_promoted=True,
        )
        assert r.atre_promoted is False
        assert r.stage_label != "2C"

    def test_pass_count_increments_on_2b_entry(self) -> None:
        """pass_count increments when entering 2B from non-2B."""
        r = classify_stage_full(
            close=115.0,
            sma150=100.0,
            sma50=108.0,
            sma21=110.0,
            ema10=112.0,
            sma150_slope=0.5,
            sma50_slope=0.5,
            ext_pct=15.0,
            atre_150=3.0,
            vol_ratio=1.0,
            prior_stage="2A",
            prior_pass_count=0,
        )
        assert r.stage_label == "2B"
        assert r.pass_count == 1

    def test_pass_count_no_increment_staying_2b(self) -> None:
        """pass_count doesn't increment if already in 2B."""
        r = classify_stage_full(
            close=115.0,
            sma150=100.0,
            sma50=108.0,
            sma21=110.0,
            ema10=112.0,
            sma150_slope=0.5,
            sma50_slope=0.5,
            ext_pct=15.0,
            atre_150=3.0,
            vol_ratio=1.0,
            prior_stage="2B",
            prior_pass_count=1,
        )
        assert r.pass_count == 1

    def test_pass_count_resets_on_stage_4(self) -> None:
        """pass_count resets to 0 when prior_stage is Stage 4."""
        r = classify_stage_full(
            close=115.0,
            sma150=100.0,
            sma50=108.0,
            sma21=110.0,
            ema10=112.0,
            sma150_slope=0.5,
            sma50_slope=0.5,
            ext_pct=15.0,
            atre_150=3.0,
            vol_ratio=1.0,
            prior_stage="4A",
            prior_pass_count=2,
        )
        assert r.pass_count == 1  # Reset to 0, then +1 for entering 2B

    def test_second_pass_tracking(self) -> None:
        """pass_count >= 2 identifies second-pass 2B."""
        r = classify_stage_full(
            close=115.0,
            sma150=100.0,
            sma50=108.0,
            sma21=110.0,
            ema10=112.0,
            sma150_slope=0.5,
            sma50_slope=0.5,
            ext_pct=15.0,
            atre_150=3.0,
            vol_ratio=1.0,
            prior_stage="2A",
            prior_pass_count=1,
        )
        assert r.pass_count == 2
        assert r.pass_count >= 2

    def test_action_override_2c_in_r4(self) -> None:
        """2C + R4 → action_override = '3A', stage stays 2C."""
        r = classify_stage_full(
            close=125.0,
            sma150=100.0,
            sma50=110.0,
            sma21=118.0,
            ema10=122.0,
            sma150_slope=0.8,
            sma50_slope=0.7,
            ext_pct=25.0,
            atre_150=4.0,
            vol_ratio=1.0,
            regime_state="R4",
        )
        assert r.stage_label == "2C"
        assert r.action_override == "3A"

    def test_no_action_override_2c_in_r1(self) -> None:
        """2C + R1 → no action_override."""
        r = classify_stage_full(
            close=125.0,
            sma150=100.0,
            sma50=110.0,
            sma21=118.0,
            ema10=122.0,
            sma150_slope=0.8,
            sma50_slope=0.7,
            ext_pct=25.0,
            atre_150=4.0,
            vol_ratio=1.0,
            regime_state="R1",
        )
        assert r.stage_label == "2C"
        assert r.action_override is None

    def test_manual_review_on_fallback(self) -> None:
        """Fallback 3A triggers manual_review. (above, slope up, no EMA stack)"""
        r = classify_stage_full(
            close=105.0,
            sma150=100.0,
            sma50=104.0,
            sma21=103.5,
            ema10=103.0,
            sma150_slope=0.5,
            sma50_slope=0.2,
            ext_pct=5.0,
            atre_150=2.0,
            vol_ratio=1.0,
        )
        assert r.stage_label == "3A"
        assert r.manual_review is True

    def test_genuine_3a_no_manual_review(self) -> None:
        """Genuine 3A match → manual_review = False."""
        r = classify_stage_full(
            close=99.0,
            sma150=100.0,
            sma50=102.0,
            sma21=100.0,
            ema10=98.5,
            sma150_slope=0.2,
            sma50_slope=0.1,
            ext_pct=-1.0,
            atre_150=2.0,
            vol_ratio=1.0,
        )
        assert r.stage_label == "3A"
        assert r.manual_review is False

    def test_rs_modifier_2b_rs_negative(self) -> None:
        """2B with RS < 0 → '2B(RS-)'."""
        r = classify_stage_full(
            close=115.0,
            sma150=100.0,
            sma50=108.0,
            sma21=110.0,
            ema10=112.0,
            sma150_slope=0.5,
            sma50_slope=0.5,
            ext_pct=15.0,
            atre_150=3.0,
            vol_ratio=1.0,
            rs_mansfield=-5.0,
        )
        assert r.stage_label == "2B(RS-)"


# ── classify_stage_series: vectorized ──


class TestClassifyStageSeries:
    def _run(self, **kw) -> str:
        data = _series_pack(**kw)
        result = classify_stage_series(
            data["close"],
            data["sma150"],
            data["sma50"],
            data["sma21"],
            data["ema10"],
            data["sma150_slope"],
            data["sma50_slope"],
            data["ext_pct"],
            data["atre_150"],
            data["vol_ratio"],
            data["rs_mansfield"],
        )
        return result.iloc[0]

    def test_series_4c(self) -> None:
        assert (
            self._run(
                close=65.0,
                sma150=100.0,
                sma50=85.0,
                sma21=70.0,
                ema10=64.0,
                sma150_slope=-0.8,
                sma50_slope=-0.6,
                ext_pct=-35.0,
                atre_150=0.0,
                vol_ratio=1.0,
                rs_mansfield=-10.0,
            )
            == "4C"
        )

    def test_series_2a(self) -> None:
        assert (
            self._run(
                close=105.0,
                sma150=100.0,
                sma50=102.0,
                sma21=103.0,
                ema10=104.0,
                sma150_slope=0.3,
                sma50_slope=0.3,
                ext_pct=5.0,
                atre_150=2.0,
                vol_ratio=1.0,
                rs_mansfield=5.0,
            )
            == "2A"
        )

    def test_series_2b(self) -> None:
        assert (
            self._run(
                close=115.0,
                sma150=100.0,
                sma50=108.0,
                sma21=112.0,
                ema10=114.0,
                sma150_slope=0.5,
                sma50_slope=0.5,
                ext_pct=15.0,
                atre_150=3.0,
                vol_ratio=1.0,
                rs_mansfield=5.0,
            )
            == "2B"
        )

    def test_series_atre_override(self) -> None:
        """2A with ATRE_150 > 6 → promoted to 2C."""
        assert (
            self._run(
                close=106.0,
                sma150=100.0,
                sma50=103.0,
                sma21=104.0,
                ema10=105.0,
                sma150_slope=0.3,
                sma50_slope=0.3,
                ext_pct=6.0,
                atre_150=7.0,
                vol_ratio=1.0,
                rs_mansfield=5.0,
            )
            == "2C"
        )

    def test_series_rs_modifier(self) -> None:
        """2B with RS < 0 → 2B(RS-)."""
        assert (
            self._run(
                close=115.0,
                sma150=100.0,
                sma50=108.0,
                sma21=112.0,
                ema10=114.0,
                sma150_slope=0.5,
                sma50_slope=0.5,
                ext_pct=15.0,
                atre_150=3.0,
                vol_ratio=1.0,
                rs_mansfield=-5.0,
            )
            == "2B(RS-)"
        )

    def test_series_breakout_via_2a_rule(self) -> None:
        """Breakout is captured by 2A rule when above SMA150 with EMA stack."""
        assert (
            self._run(
                close=103.0,
                sma150=100.0,
                sma50=97.0,
                sma21=99.0,
                ema10=101.0,
                sma150_slope=0.2,
                sma50_slope=0.2,
                ext_pct=3.0,
                atre_150=1.0,
                vol_ratio=2.0,
                rs_mansfield=5.0,
            )
            == "2A"
        )


# ── Boundary precision tests ──


class TestExtPctBoundaries:
    def test_ext_neg5_is_4a_not_1a(self) -> None:
        """ext_pct = -5.0 should be in 4A zone, not 1A."""
        result = _tf(
            95.0,
            100.0,
            97.0,
            94.0,
            sma150_slope=-0.5,
            sma50_slope=-0.3,
            ext_pct=-5.0,
        )
        assert result == "4A"

    def test_ext_neg4_99_is_1a_zone(self) -> None:
        """ext_pct = -4.99 is in 1A zone (> -5)."""
        result = _tf(
            95.01,
            100.0,
            98.0,
            94.0,
            sma150_slope=-0.1,
            sma50_slope=0.1,
            ext_pct=-4.99,
        )
        assert result == "1A"

    def test_ext_0_is_1a_with_sma50_below(self) -> None:
        """ext_pct = 0.0, SMA50 <= SMA150 → 1A."""
        result = _tf(
            100.0,
            100.0,
            98.0,
            99.0,
            sma150_slope=0.0,
            sma50_slope=0.0,
            ext_pct=0.0,
        )
        assert result == "1A"

    def test_ext_8_boundary_is_2a(self) -> None:
        """ext_pct = 8.0 is in 2A range (inclusive boundary)."""
        result = _tf(
            108.0,
            100.0,
            103.0,
            109.0,
            sma21=106.0,
            sma150_slope=0.3,
            sma50_slope=0.3,
            ext_pct=8.0,
        )
        assert result == "2A"

    def test_ext_8_01_is_2b(self) -> None:
        """ext_pct = 8.01 is in 2B range."""
        result = _tf(
            108.01,
            100.0,
            105.0,
            109.0,
            sma21=107.0,
            sma150_slope=0.5,
            sma50_slope=0.5,
            ext_pct=8.01,
        )
        assert result == "2B"

    def test_ext_20_is_2b(self) -> None:
        """ext_pct = 20.0 is in 2B range (inclusive boundary)."""
        result = _tf(
            120.0,
            100.0,
            110.0,
            121.0,
            sma21=118.0,
            sma150_slope=0.6,
            sma50_slope=0.6,
            ext_pct=20.0,
        )
        assert result == "2B"

    def test_ext_20_01_is_2c(self) -> None:
        """ext_pct > 20 is 2C."""
        result = _tf(
            120.01,
            100.0,
            110.0,
            121.0,
            sma21=118.0,
            sma150_slope=0.6,
            sma50_slope=0.6,
            ext_pct=20.01,
        )
        assert result == "2C"

    def test_ext_neg30_is_4c(self) -> None:
        """ext_pct = -30.0 is 4C (inclusive boundary)."""
        result = _tf(
            70.0,
            100.0,
            85.0,
            68.0,
            sma150_slope=-0.5,
            sma50_slope=-0.4,
            ext_pct=-30.0,
        )
        assert result == "4C"

    def test_ext_neg29_99_is_4b(self) -> None:
        """ext_pct = -29.99 is in 4B range (> -30)."""
        result = _tf(
            70.01,
            100.0,
            90.0,
            68.0,
            sma150_slope=-0.5,
            sma50_slope=-0.3,
            ext_pct=-29.99,
        )
        assert result == "4B"
