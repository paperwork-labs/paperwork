"""Edge-case tests for indicator_engine.compute_full_indicator_series and Weinstein stage."""

from __future__ import annotations

import numpy as np
import pytest
import pandas as pd

from app.services.silver.indicators.indicator_engine import (
    calculate_atr_series,
    compute_full_indicator_series,
    compute_weinstein_stage_from_daily,
)

pytestmark = pytest.mark.no_db


def test_empty_dataframe():
    empty = pd.DataFrame()
    out = compute_full_indicator_series(empty)
    assert isinstance(out, pd.DataFrame)
    assert len(out) == 0

    empty_close = pd.DataFrame(columns=["Close"])
    out2 = compute_full_indicator_series(empty_close)
    assert isinstance(out2, pd.DataFrame)
    assert len(out2) == 0


def test_single_bar():
    idx = pd.DatetimeIndex([pd.Timestamp("2024-06-03")])
    one = pd.DataFrame(
        {
            "Open": [10.0],
            "High": [11.0],
            "Low": [9.0],
            "Close": [10.0],
            "Volume": [1000.0],
        },
        index=idx,
    )
    out = compute_full_indicator_series(one)
    assert len(out) == 1
    assert pd.isna(out["sma_150"].iloc[0])


def test_nan_in_close():
    idx = pd.date_range(end=pd.Timestamp("2024-12-31"), periods=50, freq="B")
    close = pd.Series(np.linspace(100.0, 110.0, len(idx)), index=idx)
    close.iloc[25] = np.nan
    df = pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": 1_000_000.0,
        },
        index=idx,
    )
    out = compute_full_indicator_series(df)
    assert len(out) == len(df)
    assert pd.isna(close.iloc[25])
    assert pd.isna(out["sma_50"].iloc[25])


def test_zero_price():
    idx = pd.date_range(end=pd.Timestamp("2024-12-31"), periods=30, freq="B")
    close = pd.Series(100.0, index=idx)
    close.iloc[-1] = 0.0
    df = pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": 1_000_000.0,
        },
        index=idx,
    )
    out = compute_full_indicator_series(df)
    assert len(out) == len(df)
    assert not np.isinf(out["atrp_14"].iloc[-1])


def test_insufficient_bars_for_stage():
    n = 174
    dates = pd.date_range(end=pd.Timestamp("2024-12-31"), periods=n, freq="B")
    close = np.linspace(100.0, 120.0, n)
    sym = pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": 1_000_000.0,
        },
        index=dates,
    ).iloc[::-1]
    bm = sym.copy()
    out = compute_weinstein_stage_from_daily(sym, bm)
    assert out["stage_label"] == "UNKNOWN"


def test_missing_high_low():
    idx = pd.date_range(end=pd.Timestamp("2024-12-31"), periods=80, freq="B")
    close = pd.Series(np.linspace(100.0, 105.0, len(idx)), index=idx)
    df = pd.DataFrame({"Close": close}, index=idx)
    out = compute_full_indicator_series(df)
    assert len(out) == len(df)
    assert out["sma_21"].notna().any()
    assert pd.isna(out["atr_14"].iloc[-1])


def test_atr_series_close_only_returns_none():
    idx = pd.date_range(end=pd.Timestamp("2024-12-31"), periods=40, freq="B")
    df = pd.DataFrame({"Close": np.linspace(100.0, 102.0, len(idx))}, index=idx)
    atr = calculate_atr_series(df, 14)
    assert atr is None


def test_volume_overflow():
    idx = pd.date_range(end=pd.Timestamp("2024-12-31"), periods=60, freq="B")
    close = pd.Series(100.0, index=idx)
    vol = pd.Series(1e308, index=idx)
    df = pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": vol,
        },
        index=idx,
    )
    out = compute_full_indicator_series(df)
    assert len(out) == len(df)
