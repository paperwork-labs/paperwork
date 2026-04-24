"""Tests for RS Mansfield: daily_rs = stock/SPY, rs_ma = SMA(daily_rs, 252), pct = (daily_rs/rs_ma - 1)*100."""

from __future__ import annotations

import numpy as np
import pytest
import pandas as pd

from app.services.silver.indicators.indicator_engine import (
    compute_rs_mansfield,
    compute_weinstein_stage_from_daily,
)

pytestmark = pytest.mark.no_db


def _ohlcv_nf(
    close: np.ndarray,
    *,
    volume: float = 1_000_000.0,
) -> pd.DataFrame:
    """Build newest-first OHLCV aligned to business-day index (length = len(close))."""
    n = len(close)
    dates = pd.date_range(end=pd.Timestamp("2024-12-31"), periods=n, freq="B")
    c = np.asarray(close, dtype=float)
    df = pd.DataFrame(
        {
            "Open": c,
            "High": c * 1.01,
            "Low": c * 0.99,
            "Close": c,
            "Volume": volume,
        },
        index=dates,
    )
    return df.iloc[::-1]


def test_rs_mansfield_outperforming():
    """Stock doubles vs SPY on the latest bar while history was flat 1:1 -> positive Mansfield."""
    n = 300
    stock = np.ones(n) * 100.0
    stock[-1] = 200.0
    spy = np.ones(n) * 100.0
    sym = _ohlcv_nf(stock)
    bm = _ohlcv_nf(spy)
    out = compute_weinstein_stage_from_daily(sym, bm)
    rm = out.get("rs_mansfield_pct")
    assert rm is not None
    assert rm > 0


def test_rs_mansfield_matching_spy():
    """Stock tracks SPY exactly -> Mansfield near 0 once 252-day window is full."""
    n = 300
    stock = np.linspace(100.0, 120.0, n)
    spy = stock.copy()
    sym = _ohlcv_nf(stock)
    bm = _ohlcv_nf(spy)
    out = compute_weinstein_stage_from_daily(sym, bm)
    rm = out.get("rs_mansfield_pct")
    assert rm is not None
    assert abs(rm) < 1e-6


def test_rs_mansfield_underperforming():
    """SPY doubles vs stock on latest bar while history was flat 1:1 -> negative Mansfield."""
    n = 300
    stock = np.ones(n) * 100.0
    spy = np.ones(n) * 100.0
    spy[-1] = 200.0
    sym = _ohlcv_nf(stock)
    bm = _ohlcv_nf(spy)
    out = compute_weinstein_stage_from_daily(sym, bm)
    rm = out.get("rs_mansfield_pct")
    assert rm is not None
    assert rm < 0


def test_rs_mansfield_insufficient_data():
    """Fewer than 252 RS observations -> Mansfield not available (None)."""
    n = 200
    stock = np.ones(n) * 100.0
    spy = np.ones(n) * 100.0
    sym = _ohlcv_nf(stock)
    bm = _ohlcv_nf(spy)
    out = compute_weinstein_stage_from_daily(sym, bm)
    assert out["rs_mansfield_pct"] is None


def _date_index(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2020-01-01", periods=n, freq="B")


def test_compute_rs_mansfield_pure_correlation_flat_after_warmup():
    """Scaled benchmark path → RS ratio constant → Mansfield ~ 0 after full window."""
    n = 300
    idx = _date_index(n)
    bench = pd.Series(np.linspace(100.0, 150.0, n), index=idx)
    sym = bench * 1.03
    out = compute_rs_mansfield(sym, bench, ma_window=252)
    valid = out.dropna()
    assert len(valid) == n - 252 + 1
    assert np.allclose(valid.values, 0.0, atol=1e-9)


def test_compute_rs_mansfield_outperformance_positive():
    """Faster-rising symbol vs benchmark → positive tail values."""
    n = 280
    idx = _date_index(n)
    bench = pd.Series(np.linspace(100.0, 110.0, n), index=idx)
    sym = pd.Series(np.linspace(100.0, 130.0, n), index=idx)
    tail = compute_rs_mansfield(sym, bench, ma_window=52).dropna().iloc[-5:]
    assert len(tail) >= 1
    assert float(tail.iloc[-1]) > 1.0


def test_compute_rs_mansfield_empty_series():
    assert compute_rs_mansfield(pd.Series(dtype=float), pd.Series(dtype=float)).empty


def test_compute_rs_mansfield_short_window_all_nan():
    idx = _date_index(30)
    sym = pd.Series(1.0, index=idx)
    bench = pd.Series(1.0, index=idx)
    out = compute_rs_mansfield(sym, bench, ma_window=252)
    assert bool(out.isna().all())


def test_compute_rs_mansfield_none_inputs_empty():
    bench = pd.Series([1.0, 2.0])
    assert compute_rs_mansfield(None, bench).empty  # type: ignore[arg-type]
    sym = pd.Series([1.0, 2.0])
    assert compute_rs_mansfield(sym, None).empty  # type: ignore[arg-type]
