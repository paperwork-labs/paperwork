"""Unit tests for Stage Analysis sub-stage classification (indicator_engine).

Uses :func:`classify_stage_for_timeframe` (scalar rules) and
:func:`classify_stage_series` (vectorized rules + ATRE / RS / breakout post-steps).
"""

from __future__ import annotations

import math
from typing import Dict, Optional

import pandas as pd

from backend.services.market.indicator_engine import (
    classify_stage_for_timeframe,
    classify_stage_scalar,
    classify_stage_series,
)


def _tf(
    price: float,
    sma150: float,
    sma50: float,
    ema10: float,
    *,
    sma21: float = 0.0,
    sma150_slope: Optional[float],
    sma50_slope: Optional[float],
    ext_pct: Optional[float] = None,
    vol_ratio: float = 0.0,
    prev_stage: Optional[str] = None,
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
) -> Dict[str, pd.Series]:
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


# ---------------------------------------------------------------------------
# Ten sub-stages (boundary-aligned inputs)
# ---------------------------------------------------------------------------


def test_stage_4c() -> None:
    assert (
        _tf(
            85.0,
            100.0,
            90.0,
            84.0,
            sma150_slope=-0.5,
            sma50_slope=-0.3,
            ext_pct=-15.1,
        )
        == "4C"
    )


def test_stage_4b() -> None:
    assert (
        _tf(
            90.0,
            100.0,
            92.0,
            89.0,
            sma150_slope=-0.5,
            sma50_slope=-0.3,
            ext_pct=-10.0,
        )
        == "4B"
    )


def test_stage_4a() -> None:
    assert (
        _tf(
            95.0,
            100.0,
            97.0,
            94.0,
            sma150_slope=-0.1,
            sma50_slope=-0.3,
            ext_pct=-5.0,
        )
        == "4A"
    )


def test_stage_1a() -> None:
    # Below SMA150: must skip 4A (sma50_slope >= 0) to reach 1A.
    assert (
        _tf(
            98.0,
            100.0,
            99.0,
            97.5,
            sma150_slope=-0.1,
            sma50_slope=0.1,
            ext_pct=-2.0,
        )
        == "1A"
    )


def test_stage_1b() -> None:
    assert (
        _tf(
            101.0,
            100.0,
            100.5,
            100.8,
            sma150_slope=0.2,
            sma50_slope=0.1,
            ext_pct=1.0,
        )
        == "1B"
    )


def test_stage_2a() -> None:
    # abs(ext) < 5 and slope_flat wins 1B before 2A; use slope > 0.35 so 1B does not match.
    assert (
        _tf(
            103.0,
            100.0,
            101.0,
            102.5,
            sma150_slope=0.4,
            sma50_slope=0.2,
            ext_pct=3.0,
        )
        == "2A"
    )


def test_stage_2b() -> None:
    assert (
        _tf(
            110.0,
            100.0,
            105.0,
            108.0,
            sma150_slope=0.5,
            sma50_slope=0.5,
            ext_pct=10.0,
        )
        == "2B"
    )


def test_stage_2c() -> None:
    assert (
        _tf(
            120.0,
            100.0,
            110.0,
            118.0,
            sma150_slope=0.5,
            sma50_slope=0.5,
            ext_pct=20.0,
        )
        == "2C"
    )


def test_stage_3a() -> None:
    assert (
        _tf(
            108.0,
            100.0,
            104.0,
            107.0,
            sma150_slope=0.2,
            sma50_slope=0.1,
            ext_pct=8.0,
        )
        == "3A"
    )


def test_stage_3b() -> None:
    """3B is the scalar/series catch-all for *above* bars after 2A–2C and 3A.

    With finite slopes and non-NaN inputs, every such bar is classified earlier
    (2A/2B/2C or 3A); this case asserts a strongly extended advance is **2C**,
    not mistaken for late distribution (3B).
    """
    # Above + strongly up + high extension => 2C, not 3B.
    assert (
        _tf(
            125.0,
            100.0,
            112.0,
            122.0,
            sma150_slope=0.6,
            sma50_slope=0.4,
            ext_pct=22.0,
        )
        == "2C"
    )


# ---------------------------------------------------------------------------
# classify_stage_scalar (atre_150 ignored; same core as timeframe)
# ---------------------------------------------------------------------------


def test_classify_stage_scalar_delegates_and_ignores_atre() -> None:
    base = dict(
        close=110.0,
        sma150=100.0,
        sma50=105.0,
        sma21=104.0,
        ema10=108.0,
        sma150_slope=0.5,
        sma50_slope=0.5,
        ext_pct=10.0,
        vol_ratio=1.0,
    )
    s_low = classify_stage_scalar(**base, atre_150=0.0)
    s_high = classify_stage_scalar(**base, atre_150=100.0)
    assert s_low == s_high == "2B"


# ---------------------------------------------------------------------------
# Missing data / NaN
# ---------------------------------------------------------------------------


def test_sma50_slope_none_returns_unknown() -> None:
    assert (
        _tf(
            100.0,
            100.0,
            100.0,
            100.0,
            sma150_slope=0.1,
            sma50_slope=None,
            ext_pct=0.0,
        )
        == "UNKNOWN"
    )


def test_sma150_slope_none_returns_unknown() -> None:
    assert (
        _tf(
            100.0,
            100.0,
            100.0,
            100.0,
            sma150_slope=None,
            sma50_slope=0.1,
            ext_pct=0.0,
        )
        == "UNKNOWN"
    )


def test_prev_stage_when_slopes_missing() -> None:
    assert (
        _tf(
            100.0,
            100.0,
            100.0,
            100.0,
            sma150_slope=None,
            sma50_slope=0.1,
            ext_pct=0.0,
            prev_stage="2B",
        )
        == "2B"
    )


def test_scalar_nan_slope_is_not_unknown() -> None:
    """``classify_stage_for_timeframe`` only treats *None* as missing, not NaN."""
    out = _tf(
        108.0,
        100.0,
        104.0,
        107.0,
        sma150_slope=0.2,
        sma50_slope=float("nan"),
        ext_pct=8.0,
    )
    assert out == "3A"


def test_series_sma50_nan_yields_unknown() -> None:
    p = _series_pack(
        108.0,
        100.0,
        104.0,
        103.0,
        107.0,
        0.2,
        0.1,
        8.0,
        0.0,
        1.0,
        1.0,
    )
    p["sma50_slope"] = pd.Series([float("nan")], index=p["close"].index)
    st = classify_stage_series(
        p["close"],
        p["sma150"],
        p["sma50"],
        p["sma21"],
        p["ema10"],
        p["sma150_slope"],
        p["sma50_slope"],
        p["ext_pct"],
        p["atre_150"],
        p["vol_ratio"],
        p["rs_mansfield"],
    )
    assert st.iloc[0] == "UNKNOWN"


# ---------------------------------------------------------------------------
# Post-classification (series only): ATRE, RS, breakout
# ---------------------------------------------------------------------------


def test_atre_override_promotes_2b_to_2c() -> None:
    p = _series_pack(
        110.0,
        100.0,
        105.0,
        104.0,
        108.0,
        0.5,
        0.5,
        10.0,
        6.1,
        1.0,
        1.0,
    )
    st = classify_stage_series(
        p["close"],
        p["sma150"],
        p["sma50"],
        p["sma21"],
        p["ema10"],
        p["sma150_slope"],
        p["sma50_slope"],
        p["ext_pct"],
        p["atre_150"],
        p["vol_ratio"],
        p["rs_mansfield"],
    )
    assert st.iloc[0] == "2C"


def test_atre_override_promotes_2a_to_2c() -> None:
    p = _series_pack(
        103.0,
        100.0,
        101.0,
        102.5,
        102.8,
        0.4,
        0.2,
        3.0,
        7.0,
        1.0,
        1.0,
    )
    st = classify_stage_series(
        p["close"],
        p["sma150"],
        p["sma50"],
        p["sma21"],
        p["ema10"],
        p["sma150_slope"],
        p["sma50_slope"],
        p["ext_pct"],
        p["atre_150"],
        p["vol_ratio"],
        p["rs_mansfield"],
    )
    assert st.iloc[0] == "2C"


def test_rs_modifier_on_2b() -> None:
    p = _series_pack(
        110.0,
        100.0,
        105.0,
        104.0,
        108.0,
        0.5,
        0.5,
        10.0,
        0.0,
        1.0,
        -0.5,
    )
    st = classify_stage_series(
        p["close"],
        p["sma150"],
        p["sma50"],
        p["sma21"],
        p["ema10"],
        p["sma150_slope"],
        p["sma50_slope"],
        p["ext_pct"],
        p["atre_150"],
        p["vol_ratio"],
        p["rs_mansfield"],
    )
    assert st.iloc[0] == "2B(RS-)"


def test_rs_modifier_not_applied_when_atre_promoted_to_2c() -> None:
    p = _series_pack(
        110.0,
        100.0,
        105.0,
        104.0,
        108.0,
        0.5,
        0.5,
        10.0,
        6.5,
        1.0,
        -1.0,
    )
    st = classify_stage_series(
        p["close"],
        p["sma150"],
        p["sma50"],
        p["sma21"],
        p["ema10"],
        p["sma150_slope"],
        p["sma50_slope"],
        p["ext_pct"],
        p["atre_150"],
        p["vol_ratio"],
        p["rs_mansfield"],
    )
    assert st.iloc[0] == "2C"


def test_breakout_override_timeframe_inline_1b_to_2a() -> None:
    assert (
        _tf(
            102.0,
            100.0,
            98.0,
            101.0,
            sma21=99.5,
            sma150_slope=0.2,
            sma50_slope=0.1,
            ext_pct=2.0,
            vol_ratio=1.6,
        )
        == "2A"
    )


def test_breakout_override_series_post_step() -> None:
    p = _series_pack(
        102.0,
        100.0,
        98.0,
        99.5,
        101.0,
        0.2,
        0.1,
        2.0,
        0.0,
        1.6,
        0.0,
    )
    st = classify_stage_series(
        p["close"],
        p["sma150"],
        p["sma50"],
        p["sma21"],
        p["ema10"],
        p["sma150_slope"],
        p["sma50_slope"],
        p["ext_pct"],
        p["atre_150"],
        p["vol_ratio"],
        p["rs_mansfield"],
    )
    assert st.iloc[0] == "2A"


# ---------------------------------------------------------------------------
# Boundary thresholds (SLOPE_T = 0.35, ext -15 / 5 / 15)
# ---------------------------------------------------------------------------


def test_slope_at_boundary_0_35_not_strongly_up() -> None:
    # slope_up requires > 0.35; at exactly 0.35, 2B/2C do not apply.
    assert (
        _tf(
            110.0,
            100.0,
            105.0,
            108.0,
            sma150_slope=0.35,
            sma50_slope=0.2,
            ext_pct=10.0,
        )
        == "3A"
    )


def test_ext_at_boundary_5_is_2a_when_above_and_slope_positive() -> None:
    assert (
        _tf(
            105.0,
            100.0,
            102.0,
            104.0,
            sma150_slope=0.4,
            sma50_slope=0.2,
            ext_pct=5.0,
        )
        == "2A"
    )


def test_ext_at_boundary_15_is_2b_when_strongly_up() -> None:
    assert (
        _tf(
            115.0,
            100.0,
            108.0,
            113.0,
            sma150_slope=0.5,
            sma50_slope=0.4,
            ext_pct=15.0,
        )
        == "2B"
    )


def test_ext_just_above_15_is_2c() -> None:
    assert (
        _tf(
            115.1,
            100.0,
            108.0,
            113.0,
            sma150_slope=0.5,
            sma50_slope=0.4,
            ext_pct=15.1,
        )
        == "2C"
    )


def test_ext_boundary_minus_15_is_4b_not_4c() -> None:
    assert (
        _tf(
            85.0,
            100.0,
            90.0,
            84.0,
            sma150_slope=-0.5,
            sma50_slope=-0.3,
            ext_pct=-15.0,
        )
        == "4B"
    )


def test_abs_ext_boundary_5_excludes_1a_1b() -> None:
    # abs(ext) < 5 required for 1A/1B; exactly 5 skips those buckets (then 2A if above + slope_positive).
    assert (
        _tf(
            105.0,
            100.0,
            102.0,
            104.5,
            sma150_slope=0.4,
            sma50_slope=0.2,
            ext_pct=5.0,
        )
        == "2A"
    )


# ---------------------------------------------------------------------------
# classify_stage_series multi-row sanity
# ---------------------------------------------------------------------------


def test_classify_stage_series_vector_length() -> None:
    n = 5
    idx = pd.RangeIndex(n)
    z = pd.Series([0.0] * n, index=idx)
    ones = pd.Series([1.0] * n, index=idx)
    close = pd.Series([110.0, 90.0, 102.0, 108.0, 95.0], index=idx)
    sma150 = pd.Series([100.0] * n, index=idx)
    sma50 = pd.Series([105.0, 95.0, 100.0, 104.0, 97.0], index=idx)
    sma21 = pd.Series([104.0, 93.0, 99.0, 103.0, 96.0], index=idx)
    ema10 = pd.Series([108.0, 89.0, 101.5, 107.0, 94.0], index=idx)
    sma150_slope = pd.Series([0.5, -0.5, 0.2, 0.2, -0.1], index=idx)
    sma50_slope = pd.Series([0.5, -0.3, 0.1, 0.1, -0.2], index=idx)
    ext_pct = pd.Series([10.0, -10.0, 2.0, 8.0, -5.0], index=idx)
    st = classify_stage_series(
        close,
        sma150,
        sma50,
        sma21,
        ema10,
        sma150_slope,
        sma50_slope,
        ext_pct,
        z,
        ones,
        ones,
    )
    assert list(st) == ["2B", "4B", "1B", "3A", "4A"]


def test_ext_pct_default_when_omitted_matches_formula() -> None:
    price, sma = 103.0, 100.0
    expected_ext = (price - sma) / sma * 100.0
    assert math.isclose(expected_ext, 3.0)
    out = classify_stage_for_timeframe(
        price,
        sma,
        101.0,
        102.5,
        sma21=100.0,
        sma150_slope=0.4,
        sma50_slope=0.2,
        ext_pct=None,
    )
    assert out == "2A"
