"""Unit tests for detect_kell_patterns (C4 chart initiative)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.silver.indicators.indicator_engine import detect_kell_patterns

pytestmark = pytest.mark.no_db


def _idx(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")


def test_kell_empty_ohlcv() -> None:
    out = detect_kell_patterns(pd.DataFrame(), pd.Series([], dtype=object))
    assert len(out) == 0


def test_ebc_reclaim_after_climax() -> None:
    """Bearish wide bar + high vol, next day reclaims above midpoint (bullish close)."""
    n = 40
    idx = _idx(n)
    c = np.full(n, 100.0)
    o = np.full(n, 100.0)
    h = np.full(n, 101.0)
    lo = np.full(n, 99.0)
    v = np.full(n, 1_000_000.0)
    i = 25
    # Bearish + wide range
    o[i] = 102.0
    c[i] = 90.0
    h[i] = 102.0
    lo[i] = 88.0
    v[i] = 3_000_000.0
    # Reclaim day
    o[i + 1] = 90.0
    c[i + 1] = 96.0
    h[i + 1] = 97.0
    lo[i + 1] = 89.0
    v[i + 1] = 1_200_000.0

    ohlc = pd.DataFrame(
        {"Open": o, "High": h, "Low": lo, "Close": c, "Volume": v},
        index=idx,
    )
    st = pd.Series([None] * n, index=idx)
    st.iloc[i] = "3A"
    out = detect_kell_patterns(ohlc, st)
    assert out.loc[idx[i + 1], "pattern"] == "EBC"
    assert np.isfinite(out.loc[idx[i + 1], "confidence"])


def test_krc_gap_up() -> None:
    n = 30
    idx = _idx(n)
    c = np.full(n, 100.0)
    o = np.full(n, 100.0)
    h = np.full(n, 100.2)
    lo = np.full(n, 99.8)
    v = np.full(n, 1_500_000.0)
    j = 22
    h[j - 1] = 100.0
    o[j] = 101.0
    c[j] = 102.0
    h[j] = 102.5
    lo[j] = 100.5
    v[j] = 2_500_000.0
    ohlc = pd.DataFrame(
        {"Open": o, "High": h, "Low": lo, "Close": c, "Volume": v},
        index=idx,
    )
    st = pd.Series("2A", index=idx)
    out = detect_kell_patterns(ohlc, st)
    assert out.loc[idx[j], "pattern"] == "KRC"
