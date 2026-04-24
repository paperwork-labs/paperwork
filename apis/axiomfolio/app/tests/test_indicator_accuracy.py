"""Accuracy tests for core indicator math in indicator_engine (Wilder RSI/ATR/ADX, Bollinger, TD, MA)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.silver.indicators.indicator_engine import (
    _compute_td_sequential_series,
    calculate_atr_series,
    calculate_rsi_series,
    compute_full_indicator_series,
)


def _rsi_reference_series(closes: pd.Series, period: int = 14) -> np.ndarray:
    """Mirror calculate_rsi_series Wilder logic (including first_valid_index on gain)."""
    delta = closes.astype(float).diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    n = len(closes)
    out = np.full(n, np.nan)
    first_valid = gain.first_valid_index()
    if first_valid is None:
        return out
    start = closes.index.get_loc(first_valid)
    start = int(start.start if isinstance(start, slice) else start)
    seed_end = start + period
    if seed_end > n:
        return out
    ag = float(gain.iloc[start:seed_end].mean())
    al = float(loss.iloc[start:seed_end].mean())
    idx = seed_end - 1
    if al == 0.0:
        out[idx] = 100.0
    else:
        out[idx] = 100.0 - 100.0 / (1.0 + ag / al)
    for i in range(seed_end, n):
        ag = (ag * (period - 1) + float(gain.iloc[i])) / period
        al = (al * (period - 1) + float(loss.iloc[i])) / period
        if al == 0.0:
            out[i] = 100.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + ag / al)
    return out


def _true_range_series(df: pd.DataFrame) -> pd.Series:
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    return pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)


# ---------------------------------------------------------------------------
# RSI (Wilder's smoothing)
# ---------------------------------------------------------------------------


def test_rsi_basic() -> None:
    closes_list = [
        44,
        44.34,
        44.09,
        43.61,
        44.33,
        44.83,
        45.10,
        45.42,
        45.84,
        46.08,
        45.89,
        46.03,
        45.61,
        46.28,
        46.28,
        46.00,
        46.03,
        46.41,
        46.22,
        45.64,
    ]
    closes = pd.Series(closes_list, dtype=float)
    rsi = calculate_rsi_series(closes, period=14)
    assert rsi is not None
    exp_full = _rsi_reference_series(closes, period=14)
    # First seeded bar index follows engine (usually 13 when start=0, else 14)
    first_i = int(np.where(~np.isnan(exp_full))[0][0])
    np.testing.assert_allclose(float(rsi.iloc[first_i]), float(exp_full[first_i]), atol=0.01)
    np.testing.assert_allclose(
        rsi.values[~np.isnan(rsi.values)],
        exp_full[~np.isnan(exp_full)],
        atol=1e-9,
    )


def test_rsi_all_gains() -> None:
    closes = pd.Series(np.arange(1.0, 30.0), dtype=float)
    rsi = calculate_rsi_series(closes, period=14)
    assert rsi is not None
    last = float(rsi.dropna().iloc[-1])
    np.testing.assert_allclose(last, 100.0, atol=1e-9)


def test_rsi_all_losses() -> None:
    closes = pd.Series(np.arange(100.0, 70.0, -1.0), dtype=float)
    rsi = calculate_rsi_series(closes, period=14)
    assert rsi is not None
    last = float(rsi.dropna().iloc[-1])
    np.testing.assert_allclose(last, 0.0, atol=1e-9)


def test_rsi_insufficient_data() -> None:
    # Engine needs len(closes) >= start + period (start is 0 when first gain is non-NaN)
    closes = pd.Series(np.linspace(10, 11, 13), dtype=float)
    assert calculate_rsi_series(closes, period=14) is None


# ---------------------------------------------------------------------------
# ATR (Wilder's smoothing)
# ---------------------------------------------------------------------------


def test_atr_wilder_seed() -> None:
    rng = np.random.default_rng(42)
    n = 20
    base = np.cumsum(rng.normal(0, 0.5, size=n)) + 100.0
    high = base + rng.uniform(0.2, 1.0, size=n)
    low = base - rng.uniform(0.2, 1.0, size=n)
    close = base + rng.normal(0, 0.1, size=n)
    df = pd.DataFrame({"High": high, "Low": low, "Close": close})
    period = 14
    atr = calculate_atr_series(df, period=period)
    assert atr is not None
    tr = _true_range_series(df)
    seed_idx = period - 1
    expected_seed = float(tr.iloc[0:period].mean())
    np.testing.assert_allclose(float(atr.iloc[seed_idx]), expected_seed, atol=1e-9)


def test_atr_wilder_recursive() -> None:
    period = 14
    n = 22
    high = np.linspace(102.0, 110.0, n)
    low = np.linspace(98.0, 106.0, n)
    close = (high + low) / 2.0
    df = pd.DataFrame({"High": high, "Low": low, "Close": close})
    atr = calculate_atr_series(df, period=period)
    assert atr is not None
    tr = _true_range_series(df)
    seed_idx = period - 1
    prev = float(atr.iloc[seed_idx])
    for i in range(seed_idx + 1, min(seed_idx + 5, len(df))):
        tr_i = float(tr.iloc[i])
        expected = (prev * (period - 1) + tr_i) / period
        np.testing.assert_allclose(float(atr.iloc[i]), expected, atol=1e-9)
        prev = expected


def test_atr_single_bar() -> None:
    df = pd.DataFrame({"High": [10.0], "Low": [9.0], "Close": [9.5]})
    atr = calculate_atr_series(df, period=14)
    assert atr is not None
    assert bool(atr.isna().all())


# ---------------------------------------------------------------------------
# ADX (Wilder's) via compute_full_indicator_series
# ---------------------------------------------------------------------------


def _ohlcv_trending(n: int, up: bool) -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    if up:
        close = np.linspace(50.0, 50.0 + 2.5 * (n - 1), n)
    else:
        close = np.linspace(120.0, 120.0 - 2.5 * (n - 1), n)
    high = close + 1.0
    low = close - 1.0
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": np.full(n, 1_000_000.0),
        },
        index=idx,
    )


def test_adx_basic() -> None:
    df = _ohlcv_trending(40, up=True)
    out = compute_full_indicator_series(df)
    adx = out["adx"].dropna()
    pdi = out["plus_di"].dropna()
    mdi = out["minus_di"].dropna()
    assert len(adx) >= 1
    assert len(pdi) >= 1
    assert len(mdi) >= 1
    assert (adx >= 0).all() and (adx <= 100).all()
    assert (pdi >= 0).all() and (pdi <= 100).all()
    assert (mdi >= 0).all() and (mdi <= 100).all()


def test_adx_trend_up() -> None:
    df = _ohlcv_trending(80, up=True)
    out = compute_full_indicator_series(df)
    adx_last = float(out["adx"].iloc[-1])
    pdi_last = float(out["plus_di"].iloc[-1])
    mdi_last = float(out["minus_di"].iloc[-1])
    assert adx_last > 25.0
    assert pdi_last > mdi_last


def test_adx_trend_down() -> None:
    df = _ohlcv_trending(80, up=False)
    out = compute_full_indicator_series(df)
    adx_last = float(out["adx"].iloc[-1])
    pdi_last = float(out["plus_di"].iloc[-1])
    mdi_last = float(out["minus_di"].iloc[-1])
    assert adx_last > 25.0
    assert mdi_last > pdi_last


# ---------------------------------------------------------------------------
# Bollinger Bands (population std, ddof=0)
# ---------------------------------------------------------------------------


def test_bollinger_ddof0() -> None:
    prices = list(range(1, 21))
    idx = pd.date_range("2020-01-01", periods=20, freq="B")
    df = pd.DataFrame(
        {
            "Open": prices,
            "High": prices,
            "Low": prices,
            "Close": prices,
            "Volume": [1.0] * 20,
        },
        index=idx,
    )
    out = compute_full_indicator_series(df)
    mu = float(np.mean(prices))
    sigma = float(np.std(prices, ddof=0))
    upper_exp = mu + 2.0 * sigma
    lower_exp = mu - 2.0 * sigma
    np.testing.assert_allclose(float(out["bollinger_upper"].iloc[-1]), upper_exp, atol=1e-9)
    np.testing.assert_allclose(float(out["bollinger_lower"].iloc[-1]), lower_exp, atol=1e-9)


# ---------------------------------------------------------------------------
# TD Sequential
# ---------------------------------------------------------------------------


def test_td_cap_at_9() -> None:
    n = 25
    closes = np.array([100.0 - i for i in range(n)], dtype=float)
    td_buy, td_sell, _, _ = _compute_td_sequential_series(closes)
    assert int(td_buy.max()) == 9
    assert np.all(td_buy <= 9)


def test_td_reset_after_9() -> None:
    n = 25
    closes = np.array([100.0 - i for i in range(n)], dtype=float)
    td_buy, _, _, _ = _compute_td_sequential_series(closes)
    idx9 = int(np.where(td_buy == 9)[0][0])
    assert idx9 + 1 < len(td_buy)
    assert int(td_buy[idx9 + 1]) == 1


def test_td_buy_complete() -> None:
    n = 25
    closes = np.array([100.0 - i for i in range(n)], dtype=float)
    td_buy, _, td_buy_complete, _ = _compute_td_sequential_series(closes)
    idx9 = int(np.where(td_buy == 9)[0][0])
    assert bool(td_buy_complete[idx9])
    assert not bool(td_buy_complete[idx9 - 1])


# ---------------------------------------------------------------------------
# SMA / EMA
# ---------------------------------------------------------------------------


def test_sma_basic() -> None:
    prices = np.arange(1, 11, dtype=float)
    idx = pd.date_range("2020-01-01", periods=10, freq="B")
    df = pd.DataFrame(
        {
            "Open": prices,
            "High": prices,
            "Low": prices,
            "Close": prices,
            "Volume": np.ones(10),
        },
        index=idx,
    )
    out = compute_full_indicator_series(df)
    expected = float(np.mean(prices[-5:]))
    np.testing.assert_allclose(float(out["sma_5"].iloc[-1]), expected, atol=1e-9)


def test_ema_basic() -> None:
    # compute_full_indicator_series exposes ema_8 / ema_10 / ema_21 / ema_200 only
    closes_list = [10.0, 11.0, 12.0, 11.5, 13.0, 12.0, 14.0, 13.5]
    idx = pd.date_range("2020-01-01", periods=len(closes_list), freq="B")
    df = pd.DataFrame(
        {
            "Open": closes_list,
            "High": closes_list,
            "Low": closes_list,
            "Close": closes_list,
            "Volume": [1.0] * len(closes_list),
        },
        index=idx,
    )
    out = compute_full_indicator_series(df)
    span = 8
    alpha = 2.0 / (span + 1.0)
    ema = closes_list[0]
    for c in closes_list[1:]:
        ema = alpha * c + (1.0 - alpha) * ema
    np.testing.assert_allclose(float(out["ema_8"].iloc[-1]), ema, atol=1e-9)
