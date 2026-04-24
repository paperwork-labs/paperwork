"""End-to-end pipeline checks: synthetic OHLCV through indicator and stage utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.market.indicator_engine import (
    calculate_atr_series,
    compute_full_indicator_series,
    compute_weinstein_stage_from_daily,
)
from app.services.market.stage_utils import compute_stage_run_lengths

pytestmark = pytest.mark.no_db

VALID_STAGE_LABELS = frozenset(
    {
        "1A",
        "1B",
        "2A",
        "2B",
        "2B(RS-)",
        "2C",
        "3A",
        "3B",
        "4A",
        "4B",
        "4C",
    }
)

# Core columns always produced by compute_full_indicator_series (OHLCV present; spy optional).
EXPECTED_INDICATOR_COLUMNS = frozenset(
    {
        "sma_5",
        "sma_8",
        "sma_10",
        "sma_14",
        "sma_21",
        "sma_50",
        "sma_100",
        "sma_150",
        "sma_200",
        "ema_8",
        "ema_10",
        "ema_21",
        "ema_200",
        "rsi",
        "atr_14",
        "atr_30",
        "macd",
        "macd_signal",
        "macd_histogram",
        "plus_di",
        "minus_di",
        "adx",
        "bollinger_upper",
        "bollinger_lower",
        "bollinger_width",
        "keltner_upper",
        "keltner_lower",
        "stoch_rsi",
        "high_52w",
        "low_52w",
        "volume_avg_20d",
        "current_price",
        "atrp_14",
        "atrp_30",
    }
)


def _true_range_series(df: pd.DataFrame) -> pd.Series:
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    return pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)


@pytest.fixture
def synthetic_stock_spy() -> tuple[pd.DataFrame, pd.DataFrame]:
    """300 business days: stock (uptrend, consolidation, decline) + SPY slow uptrend."""
    rng = np.random.default_rng(42)
    n = 300
    idx = pd.date_range("2020-06-01", periods=n, freq="B")

    close = np.empty(n, dtype=np.float64)
    close[:150] = np.linspace(50.0, 120.0, 150)
    consol = 120.0 + rng.normal(0.0, 2.5, size=70)
    close[150:220] = np.clip(consol, 115.0, 125.0)
    close[220:] = np.linspace(float(close[219]), 80.0, n - 220)
    close = close + rng.normal(0.0, 0.15, size=n)

    spread = rng.uniform(0.3, 1.2, size=n)
    high = close + spread
    low = close - spread * rng.uniform(0.5, 1.0, size=n)
    open_ = np.empty(n, dtype=np.float64)
    open_[0] = float(close[0])
    open_[1:] = close[:-1] + rng.normal(0.0, 0.05, size=n - 1)
    volume = rng.integers(800_000, 2_000_000, size=n).astype(np.float64)

    stock = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )

    spy_close = np.linspace(400.0, 500.0, n) + rng.normal(0.0, 0.2, size=n)
    spy_spread = rng.uniform(0.2, 0.8, size=n)
    spy_high = spy_close + spy_spread
    spy_low = spy_close - spy_spread * rng.uniform(0.5, 1.0, size=n)
    spy_open = np.empty(n, dtype=np.float64)
    spy_open[0] = float(spy_close[0])
    spy_open[1:] = spy_close[:-1] + rng.normal(0.0, 0.03, size=n - 1)
    spy_vol = rng.integers(5_000_000, 15_000_000, size=n).astype(np.float64)

    spy = pd.DataFrame(
        {
            "Open": spy_open,
            "High": spy_high,
            "Low": spy_low,
            "Close": spy_close,
            "Volume": spy_vol,
        },
        index=idx,
    )

    return stock, spy


def test_e2e_full_indicator_series(synthetic_stock_spy: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    ohlcv_df, _ = synthetic_stock_spy
    result = compute_full_indicator_series(ohlcv_df)

    assert isinstance(result, pd.DataFrame)
    assert result.index.equals(ohlcv_df.index)
    missing = EXPECTED_INDICATOR_COLUMNS - set(result.columns)
    assert not missing, f"Missing indicator columns: {sorted(missing)}"

    warmup = 252
    tail = result.iloc[warmup:]
    close = ohlcv_df["Close"]

    for col in ("rsi", "atr_14", "sma_150", "macd", "adx"):
        series = tail[col]
        valid = series.dropna()
        assert len(valid) > 0, f"{col} all NaN after warmup"
        assert not valid.isna().all()

    rsi_tail = tail["rsi"].dropna()
    assert (rsi_tail >= 0.0).all() and (rsi_tail <= 100.0).all()
    atr_tail = tail["atr_14"].dropna()
    assert (atr_tail > 0.0).all()
    assert (atr_tail < float(close.iloc[-1]) * 2.0).all()

    for i in (200, 220, 280):
        win = close.iloc[i - 149 : i + 1]
        exp_sma150 = float(win.mean())
        np.testing.assert_allclose(
            float(result["sma_150"].iloc[i]), exp_sma150, rtol=1e-9, atol=1e-6
        )

    exp_sma50_280 = float(close.iloc[280 - 49 : 281].mean())
    np.testing.assert_allclose(
        float(result["sma_50"].iloc[280]), exp_sma50_280, rtol=1e-9, atol=1e-6
    )


def test_e2e_stage_classification(synthetic_stock_spy: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    stock, spy = synthetic_stock_spy
    sym_nf = stock.iloc[::-1]
    bm_nf = spy.iloc[::-1]

    out = compute_weinstein_stage_from_daily(sym_nf, bm_nf)

    assert isinstance(out, dict)
    assert "stage_label" in out
    label = out["stage_label"]
    assert isinstance(label, str)
    assert label != "UNKNOWN"
    assert label in VALID_STAGE_LABELS

    assert "rs_mansfield_pct" in out
    rm = out["rs_mansfield_pct"]
    assert rm is not None
    assert isinstance(rm, (int, float))
    assert np.isfinite(float(rm))


def test_e2e_indicator_consistency(synthetic_stock_spy: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    ohlcv_df, _ = synthetic_stock_spy
    period = 14
    atr = calculate_atr_series(ohlcv_df, period=period)
    assert atr is not None

    tr = _true_range_series(ohlcv_df)
    first_valid = tr.first_valid_index()
    assert first_valid is not None
    start = ohlcv_df.index.get_loc(first_valid)
    if isinstance(start, slice):
        start = start.start
    start = int(start)
    seed_end = start + period
    assert seed_end <= len(ohlcv_df)
    seed_idx = seed_end - 1

    expected_seed = float(tr.iloc[start:seed_end].mean())
    np.testing.assert_allclose(float(atr.iloc[seed_idx]), expected_seed, rtol=1e-9, atol=1e-9)

    prev = float(atr.iloc[seed_idx])
    for i in range(seed_idx + 1, len(ohlcv_df)):
        tr_i = float(tr.iloc[i])
        exp = (prev * (period - 1) + tr_i) / period
        np.testing.assert_allclose(float(atr.iloc[i]), exp, rtol=1e-9, atol=1e-9)
        prev = exp

    full = compute_full_indicator_series(ohlcv_df)
    np.testing.assert_allclose(
        full["atr_14"].astype(float).values,
        atr.astype(float).values,
        rtol=1e-9,
        atol=1e-9,
        equal_nan=True,
    )

    wrong_sma_tr = tr.rolling(window=period, min_periods=period).mean()
    j = min(len(ohlcv_df) - 1, seed_idx + 25)
    assert not np.isnan(float(atr.iloc[j]))
    assert not np.isnan(float(wrong_sma_tr.iloc[j]))
    assert not np.isclose(float(atr.iloc[j]), float(wrong_sma_tr.iloc[j]), rtol=1e-6, atol=1e-6)


def test_e2e_no_unknown_propagation() -> None:
    labels = ["2A", "UNKNOWN", "2A", "2A", "3B"]
    rows = compute_stage_run_lengths(labels)

    assert rows[0]["current_stage_days"] == 1
    assert rows[1]["current_stage_days"] is None
    assert rows[1]["previous_stage_label"] is None

    assert rows[2]["current_stage_days"] == 1
    assert rows[2]["previous_stage_label"] is None

    assert rows[3]["current_stage_days"] == 2

    assert rows[4]["current_stage_days"] == 1
    assert rows[4]["previous_stage_label"] == "2A"
    # Only the two 2A bars after UNKNOWN form the prior run (UNKNOWN resets counting).
    assert rows[4]["previous_stage_days"] == 2
