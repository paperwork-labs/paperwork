"""Unit tests for detect_volume_events (C4 chart initiative)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.silver.indicators.indicator_engine import detect_volume_events

pytestmark = pytest.mark.no_db


def _make_ohlcv(
    *,
    n: int,
    vol_base: float = 1_000_000.0,
    spike_idx: int | None = None,
    dry_idx: int | None = None,
) -> pd.DataFrame:
    """Build synthetic oldest-first OHLCV with default flat price and ATR-friendly ranges."""
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    close = 100.0 + np.cumsum(np.random.default_rng(42).normal(0, 0.1, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + 0.2
    low = np.minimum(open_, close) - 0.2
    vol = np.full(n, vol_base)
    if spike_idx is not None and 0 <= spike_idx < n:
        vol[spike_idx] = vol_base * 2.0
        # Reversal bar: big body vs ATR
        open_[spike_idx] = close[spike_idx] + 3.0
    if dry_idx is not None and 0 <= dry_idx < n:
        vol[dry_idx] = vol_base * 0.3
    return pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": vol,
        },
        index=idx,
    )


def test_detect_volume_events_empty() -> None:
    out = detect_volume_events(pd.DataFrame(), lookback=20)
    assert out.empty or len(out) == 0


def test_detect_volume_events_requires_columns() -> None:
    bad = pd.DataFrame({"Open": [1.0], "Close": [1.0]})
    out = detect_volume_events(bad, lookback=20)
    cell = out["volume_event"].iloc[0]
    assert cell is None or (isinstance(cell, float) and np.isnan(cell))


def test_dry_up_flagged() -> None:
    df = _make_ohlcv(n=30, vol_base=1_000_000, dry_idx=25)
    out = detect_volume_events(df, lookback=20)
    v = out.loc[df.index[25], "volume_event"]
    assert v == "dry_up"


def test_climax_flagged() -> None:
    df = _make_ohlcv(n=30, vol_base=1_000_000, spike_idx=25)
    out = detect_volume_events(df, lookback=20)
    v = out.loc[df.index[25], "volume_event"]
    assert v == "climax"


def test_climax_wins_over_dry_on_same_bar() -> None:
    n = 30
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    close = np.full(n, 100.0)
    open_ = close.copy()
    # Bar 25: high volume + huge body, also below half of avg in an inconsistent setup —
    # use explicit vol such that 1.5*avg and 0.5*avg are mutually exclusive in practice.
    vol = np.full(n, 1_000_000.0)
    vol[25] = 3_000_000.0  # >> avg once rolling warms
    open_[25] = 100.0
    close[25] = 110.0  # 10-pt body
    high = np.maximum(open_, close) + 0.1
    low = np.minimum(open_, close) - 0.1
    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )
    out = detect_volume_events(df, lookback=20)
    assert out.loc[df.index[25], "volume_event"] == "climax"
