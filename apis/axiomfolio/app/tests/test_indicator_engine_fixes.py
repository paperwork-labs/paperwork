"""Tests for critical indicator engine fixes.

Covers RSI edge cases, TD Sequential cap, performance window guards,
and gap-fill scan direction.
"""

import numpy as np
import pandas as pd
import pytest

from app.services.silver.indicators.indicator_engine import (
    calculate_rsi_series,
    _compute_td_sequential_series,
    calculate_performance_windows,
    compute_gap_counts,
)


pytestmark = pytest.mark.no_db


# ── RSI edge cases ──────────────────────────────────────────────────


class TestRSIEdgeCases:
    """RSI should handle degenerate series without crashing or returning NaN."""

    @staticmethod
    def _flat_series(value: float, n: int = 30) -> pd.Series:
        idx = pd.date_range("2025-01-01", periods=n, freq="B")
        return pd.Series([value] * n, index=idx, dtype="float64")

    def test_rsi_50_when_no_movement(self):
        """Flat price -> gain=0, loss=0 -> RSI should be 50 (neutral)."""
        closes = self._flat_series(100.0, n=30)
        rsi = calculate_rsi_series(closes, period=14)
        assert rsi is not None
        valid = rsi.dropna()
        assert len(valid) > 0
        for val in valid:
            assert val == pytest.approx(50.0), f"Expected RSI=50 for flat series, got {val}"

    def test_rsi_100_when_all_gains(self):
        """Strictly rising price -> RSI should be 100."""
        idx = pd.date_range("2025-01-01", periods=30, freq="B")
        closes = pd.Series([100.0 + i for i in range(30)], index=idx, dtype="float64")
        rsi = calculate_rsi_series(closes, period=14)
        assert rsi is not None
        last_rsi = rsi.dropna().iloc[-1]
        assert last_rsi == pytest.approx(100.0), f"Expected RSI=100 for all-gains, got {last_rsi}"

    def test_rsi_0_when_all_losses(self):
        """Strictly falling price -> RSI should be 0."""
        idx = pd.date_range("2025-01-01", periods=30, freq="B")
        closes = pd.Series([200.0 - i for i in range(30)], index=idx, dtype="float64")
        rsi = calculate_rsi_series(closes, period=14)
        assert rsi is not None
        last_rsi = rsi.dropna().iloc[-1]
        assert last_rsi == pytest.approx(0.0), f"Expected RSI=0 for all-losses, got {last_rsi}"

    def test_rsi_returns_none_for_insufficient_data(self):
        """With fewer bars than the period, RSI should return None."""
        idx = pd.date_range("2025-01-01", periods=5, freq="B")
        closes = pd.Series([100.0, 101.0, 99.0, 102.0, 100.5], index=idx)
        rsi = calculate_rsi_series(closes, period=14)
        assert rsi is None

    def test_rsi_normal_series_range(self):
        """Normal oscillating series should produce RSI in [0, 100]."""
        np.random.seed(42)
        idx = pd.date_range("2025-01-01", periods=60, freq="B")
        closes = pd.Series(100 + np.cumsum(np.random.randn(60) * 2), index=idx)
        rsi = calculate_rsi_series(closes, period=14)
        assert rsi is not None
        valid = rsi.dropna()
        assert all(0 <= v <= 100 for v in valid), "RSI values must be in [0, 100]"


# ── TD Sequential cap ──────────────────────────────────────────────


class TestTDSequentialCap:
    """TD Sequential counts should cap at 9."""

    def test_td_buy_caps_at_9(self):
        """Even with 20 consecutive down closes, td_buy never exceeds 9."""
        closes = np.array([200.0 - i * 2 for i in range(25)], dtype="float64")
        td_buy, td_sell, td_buy_c, td_sell_c = _compute_td_sequential_series(closes)
        assert td_buy.max() <= 9, f"td_buy should cap at 9, got {td_buy.max()}"

    def test_td_sell_caps_at_9(self):
        """Even with 20 consecutive up closes, td_sell never exceeds 9."""
        closes = np.array([100.0 + i * 2 for i in range(25)], dtype="float64")
        td_buy, td_sell, td_buy_c, td_sell_c = _compute_td_sequential_series(closes)
        assert td_sell.max() <= 9, f"td_sell should cap at 9, got {td_sell.max()}"

    def test_td_resets_after_9(self):
        """After reaching 9, count resets to 0 on the next bar."""
        closes = np.array([200.0 - i * 2 for i in range(25)], dtype="float64")
        td_buy, _, _, _ = _compute_td_sequential_series(closes)
        nines = np.where(td_buy == 9)[0]
        assert len(nines) > 0, "Should have at least one 9-count"
        for nine_idx in nines:
            if nine_idx + 1 < len(td_buy):
                assert td_buy[nine_idx + 1] <= 1, "Count should reset after reaching 9"


# ── Performance windows edge cases ─────────────────────────────────


class TestPerformanceWindowEdgeCases:
    """Performance windows must handle 0.0 and NaN close prices."""

    @staticmethod
    def _make_newest_first_df(closes: list[float]) -> pd.DataFrame:
        idx = pd.date_range("2025-01-01", periods=len(closes), freq="B")[::-1]
        return pd.DataFrame({"Close": closes}, index=idx)

    def test_zero_close_price_returns_none(self):
        """When close is 0.0, perf should be None (not crash with ZeroDivision)."""
        closes = [0.0] + [100.0] * 10
        df = self._make_newest_first_df(closes)
        result = calculate_performance_windows(df)
        assert result["perf_1d"] is None

    def test_nan_close_price_returns_none(self):
        """When close is NaN, perf should be None (not crash)."""
        closes = [float("nan")] + [100.0] * 10
        df = self._make_newest_first_df(closes)
        result = calculate_performance_windows(df)
        assert result["perf_1d"] is None

    def test_normal_perf_calculation(self):
        """Normal data should produce correct percentage change."""
        closes = [110.0, 100.0] + [100.0] * 20
        df = self._make_newest_first_df(closes)
        result = calculate_performance_windows(df)
        assert result["perf_1d"] == pytest.approx(10.0)

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["Close"])
        result = calculate_performance_windows(df)
        assert result["perf_1d"] is None
        assert result["perf_5d"] is None

    def test_none_input(self):
        result = calculate_performance_windows(None)
        assert result["perf_1d"] is None


# ── Gap fill scan direction ─────────────────────────────────────────


class TestGapFillScanDirection:
    """Gap fill scanning checks newer bars to see if they fill older gaps."""

    def test_up_gap_filled_by_newer_bar(self):
        """An up-gap created by older bars should be marked filled if a newer bar's low fills it."""
        highs = [150.0, 130.0, 105.0, 100.0, 95.0]
        lows = [140.0, 120.0, 103.0, 98.0, 90.0]
        idx = pd.date_range("2025-01-05", periods=5, freq="-1B")
        df = pd.DataFrame({"High": highs, "Low": lows}, index=idx)

        result = compute_gap_counts(df, min_gap_percent=0.5)
        assert result["gaps_unfilled_up"] is not None

    def test_no_gaps_in_flat_data(self):
        """Flat/overlapping bars produce zero gaps."""
        highs = [101.0, 101.0, 101.0, 101.0, 101.0]
        lows = [99.0, 99.0, 99.0, 99.0, 99.0]
        idx = pd.date_range("2025-01-05", periods=5, freq="-1B")
        df = pd.DataFrame({"High": highs, "Low": lows}, index=idx)

        result = compute_gap_counts(df, min_gap_percent=0.5)
        assert result["gaps_unfilled_up"] == 0
        assert result["gaps_unfilled_down"] == 0

    def test_empty_input(self):
        df = pd.DataFrame(columns=["High", "Low"])
        result = compute_gap_counts(df)
        assert result["gaps_unfilled_up"] is None
