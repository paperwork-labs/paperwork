"""Weinstein Stage Analysis classifier — 10 sub-stages via SMA150 anchor.

Extracted from indicator_engine.py to keep stage classification logic
separate from indicator computation. See Stage_Analysis.docx for the
full specification.

Functions:
    classify_stage_for_timeframe  — scalar single-bar classification
    classify_stage_scalar         — scalar with ATRE placeholder
    classify_stage_series         — vectorized full-series classification
    compute_weinstein_stage_from_daily  — daily OHLCV → latest stage dict
    compute_weinstein_stage_series_from_daily — daily OHLCV → stage series DF
    weekly_from_daily             — weekly resample helper
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from backend.services.market.atr_series import calculate_atr_series

logger = logging.getLogger(__name__)


def weekly_from_daily(df_daily_newest_first: pd.DataFrame) -> pd.DataFrame:
    """Convert daily OHLCV (newest->first index) to weekly (oldest->newest)."""
    if df_daily_newest_first is None or df_daily_newest_first.empty:
        return pd.DataFrame()
    daily = df_daily_newest_first.iloc[::-1].copy()  # oldest->newest
    weekly = pd.DataFrame()
    weekly["Open"] = daily["Open"].resample("W-FRI").first()
    weekly["High"] = daily["High"].resample("W-FRI").max()
    weekly["Low"] = daily["Low"].resample("W-FRI").min()
    weekly["Close"] = daily["Close"].resample("W-FRI").last()
    weekly["Volume"] = daily["Volume"].resample("W-FRI").sum()
    weekly = weekly.dropna()
    return weekly


def classify_stage_for_timeframe(
    price: float,
    sma150: float,
    sma50: float,
    ema10: float,
    prev_stage: Optional[str] = None,
    *,
    sma21: float = 0.0,
    sma150_slope: Optional[float] = None,
    sma50_slope: Optional[float] = None,
    ext_pct: Optional[float] = None,
    vol_ratio: float = 0.0,
) -> str:
    """Classify stage for any timeframe using core Stage Analysis spec rules (SMA150 anchor).

    Requires *sma150_slope* and *sma50_slope* for classification. *ext_pct* defaults
    to ``(price - sma150) / sma150 * 100`` when omitted. If slopes are missing,
    returns *prev_stage* when set, else ``"UNKNOWN"``.

    ATRE override (2A/2B→2C when ATRE_150 > 6) and Mansfield RS (2B→2B(RS-))
    post-steps are applied in :func:`classify_stage_series` and
    :func:`compute_weinstein_stage_from_daily`, not in this function.

    Priority order (first match wins): 4C→4B→4A→1A→1B→2A→2B→2C→3A→3B.
    See Stage_Analysis.docx Section 4 for full rules.
    """
    if sma150_slope is None or sma50_slope is None:
        return prev_stage if prev_stage is not None else "UNKNOWN"
    if ext_pct is None:
        if sma150 == 0:
            return prev_stage if prev_stage is not None else "UNKNOWN"
        ext_pct = (price - sma150) / sma150 * 100.0

    SLOPE_T = 0.35  # ±0.35% slope threshold
    above = price > sma150
    below = not above

    slope_strongly_down = sma150_slope < -SLOPE_T
    slope_down_or_flat = sma150_slope <= 0
    slope_flat = abs(sma150_slope) <= SLOPE_T
    slope_up = sma150_slope > SLOPE_T
    slope_positive = sma150_slope > 0

    # 4C: Deep decline — far below SMA150, slope strongly negative
    if below and slope_strongly_down and ext_pct < -15:
        return "4C"
    # 4B: Active decline — below SMA150, slope strongly negative
    if below and slope_strongly_down:
        return "4B"
    # 4A: Early decline — below SMA150, slope non-positive, SMA50 declining
    if below and slope_down_or_flat and sma50_slope < 0:
        return "4A"
    # 1A: Early base — near SMA150, slope flat/stabilizing, still non-positive
    if abs(ext_pct) < 5 and slope_flat and sma150_slope <= 0:
        return "1A"
    # 1B: Late base / breakout watch — near SMA150, slope flat or gently positive
    if abs(ext_pct) < 5 and (slope_flat or (slope_positive and not slope_up)):
        # Breakout override: 1B→2A when volume confirms and MAs are stacked
        if above and vol_ratio > 1.5 and ema10 > sma21 > sma50:
            return "2A"
        return "1B"
    # 2A: Early advance — above SMA150, slope positive, low extension
    if above and slope_positive and ext_pct <= 5:
        return "2A"
    # 2B: Confirmed advance — above SMA150, slope strongly up, moderate extension
    if above and slope_up and ext_pct <= 15:
        return "2B"
    # 2C: Extended advance — above SMA150, slope strongly up, high extension
    if above and slope_up and ext_pct > 15:
        return "2C"
    # 3A: Early distribution — above SMA150 but slope weakening
    if above and not slope_up:
        return "3A"
    # 3B is effectively unreachable: all above-SMA150 + slope_up bars are captured by 2B/2C.
    # Retained as a safety net for defensive completeness.
    if above:
        return "3B"
    # 4A fallback: remaining below SMA150 bars get base/accumulation classification
    return "4A"


def classify_stage_scalar(
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
) -> str:
    """Classify a single bar into one of 10 Stage Analysis spec sub-stages.

    Delegates to :func:`classify_stage_for_timeframe`. *atre_150* is accepted for
    API compatibility; the ATRE override (2A/2B→2C when ATRE_150 > 6) is applied
    in callers after this returns.
    """
    _ = atre_150
    return classify_stage_for_timeframe(
        close,
        sma150,
        sma50,
        ema10,
        sma21=sma21,
        sma150_slope=sma150_slope,
        sma50_slope=sma50_slope,
        ext_pct=ext_pct,
        vol_ratio=vol_ratio,
    )


def classify_stage_series(
    close: pd.Series,
    sma150: pd.Series,
    sma50: pd.Series,
    sma21: pd.Series,
    ema10: pd.Series,
    sma150_slope: pd.Series,
    sma50_slope: pd.Series,
    ext_pct: pd.Series,
    atre_150: pd.Series,
    vol_ratio: pd.Series,
    rs_mansfield: pd.Series,
) -> pd.Series:
    """Vectorized Stage Analysis spec stage classification for full time series.

    Priority order (first match wins): 4C→4B→4A→1A→1B→2A→2B→2C→3A→3B.
    Post-classification: ATRE override (2A/2B + ATRE_150 > 6 → 2C; not regime-based),
    RS modifier (2B + RS < 0 → "2B(RS-)").
    """
    SLOPE_T = 0.35
    stage = pd.Series("UNKNOWN", index=close.index, dtype="object")

    above = close > sma150
    below = ~above
    has_data = sma150.notna() & sma150_slope.notna() & ext_pct.notna() & sma50_slope.notna()

    slope_strongly_down = sma150_slope < -SLOPE_T
    slope_flat = sma150_slope.abs() <= SLOPE_T
    slope_up = sma150_slope > SLOPE_T
    slope_positive = sma150_slope > 0
    slope_down_or_flat = sma150_slope <= 0

    assigned = pd.Series(False, index=close.index)

    def assign(mask: pd.Series, label: str) -> None:
        nonlocal assigned
        hit = has_data & mask & ~assigned
        stage[hit] = label
        assigned = assigned | hit

    # Priority order: 4C→4B→4A→1A→1B→2A→2B→2C→3A→3B→remaining below
    assign(below & slope_strongly_down & (ext_pct < -15), "4C")
    assign(below & slope_strongly_down, "4B")
    assign(below & slope_down_or_flat & (sma50_slope < 0), "4A")
    assign((ext_pct.abs() < 5) & slope_flat & (sma150_slope <= 0), "1A")
    assign((ext_pct.abs() < 5) & (slope_flat | (slope_positive & ~slope_up)), "1B")
    assign(above & slope_positive & (ext_pct <= 5), "2A")
    assign(above & slope_up & (ext_pct <= 15), "2B")
    assign(above & slope_up & (ext_pct > 15), "2C")
    assign(above & ~slope_up, "3A")
    # 3B is effectively unreachable: all above-SMA150 + slope_up bars are captured by 2B/2C.
    # Retained as a safety net for defensive completeness.
    assign(above, "3B")
    # 4A fallback: remaining below SMA150 bars get base/accumulation classification
    assign(below, "4A")

    # Post-classification: Breakout override — 1B with volume + stacked MAs → promote to 2A
    breakout = (
        (stage == "1B") & above
        & (vol_ratio > 1.5) & (ema10 > sma21) & (sma21 > sma50)
    )
    stage[breakout] = "2A"

    # Post-classification: ATRE override — 2A/2B with ATRE_150 > 6 → 2C (not regime-based)
    atre_override = (stage.isin(["2A", "2B"])) & (atre_150 > 6.0)
    stage[atre_override] = "2C"

    # Post-classification: RS modifier — 2B with RS < 0 → flag
    rs_flag = (stage == "2B") & (rs_mansfield < 0)
    stage[rs_flag] = "2B(RS-)"

    return stage


def compute_weinstein_stage_from_daily(
    daily_sym_newest_first: pd.DataFrame,
    daily_bm_newest_first: pd.DataFrame,
) -> Dict[str, Any]:
    """Compute Stage Analysis (spec) from daily OHLCV (both newest->first).

    Uses SMA150 as primary anchor per Stage_Analysis.docx.
    Returns latest bar's stage + supporting metrics.
    """
    unknown: Dict[str, Any] = {
        "stage": "UNKNOWN",
        "stage_label": "UNKNOWN",
        "stage_slope_pct": None,
        "stage_dist_pct": None,
        "ext_pct": None,
        "sma150_slope": None,
        "sma50_slope": None,
        "ema10_dist_pct": None,
        "ema10_dist_n": None,
        "vol_ratio": None,
        "rs_mansfield_pct": None,
    }
    if (
        daily_sym_newest_first is None
        or daily_sym_newest_first.empty
        or daily_bm_newest_first is None
        or daily_bm_newest_first.empty
    ):
        return dict(unknown)

    sym = daily_sym_newest_first.iloc[::-1]  # oldest→newest
    bm = daily_bm_newest_first.iloc[::-1]

    if len(sym) < 175:
        return dict(unknown)

    close = sym["Close"]
    volume = sym["Volume"] if "Volume" in sym.columns else pd.Series(np.nan, index=sym.index)
    sma150 = close.rolling(150).mean()
    sma50 = close.rolling(50).mean()
    sma21 = close.rolling(21).mean()
    ema10 = close.ewm(span=10, adjust=False).mean()
    vol_avg = volume.rolling(20).mean()

    ext_pct = ((close - sma150) / sma150 * 100).replace([np.inf, -np.inf], np.nan)
    sma150_slope_s = ((sma150 - sma150.shift(20)) / sma150.shift(20) * 100).replace([np.inf, -np.inf], np.nan)
    sma50_slope_s = ((sma50 - sma50.shift(10)) / sma50.shift(10) * 100).replace([np.inf, -np.inf], np.nan)
    vol_ratio_s = (volume / vol_avg).replace([np.inf, -np.inf], np.nan)

    atr14 = calculate_atr_series(sym, 14) if {"High", "Low", "Close"}.issubset(sym.columns) else pd.Series(np.nan, index=sym.index)
    atre_150 = ((close - sma150) / atr14).replace([np.inf, -np.inf], np.nan) if atr14 is not None else pd.Series(np.nan, index=sym.index)
    ema10_dist_pct_s = ((close - ema10) / ema10 * 100).replace([np.inf, -np.inf], np.nan)
    atrp14 = (atr14 / close * 100).replace([np.inf, -np.inf], np.nan) if atr14 is not None else pd.Series(np.nan, index=sym.index)
    ema10_dist_n_s = (ema10_dist_pct_s / atrp14).replace([np.inf, -np.inf], np.nan)

    # RS Mansfield (daily RS vs 252-day SMA of RS)
    bm_close = bm["Close"].reindex(sym.index, method="ffill")
    rs = (close / bm_close.replace(0, np.nan)).astype("float64")
    rs_ma = rs.rolling(252).mean()
    rs_mansfield = ((rs / rs_ma - 1.0) * 100.0).replace([np.inf, -np.inf], np.nan)

    def last_val(s: pd.Series) -> Optional[float]:
        v = s.iloc[-1] if not s.empty else None
        return float(v) if v is not None and not pd.isna(v) else None

    c = last_val(close)
    s150 = last_val(sma150)
    s50 = last_val(sma50)
    s21 = last_val(sma21)
    e10 = last_val(ema10)
    sl150 = last_val(sma150_slope_s)
    sl50 = last_val(sma50_slope_s)
    ep = last_val(ext_pct)
    at150 = last_val(atre_150)
    vr = last_val(vol_ratio_s)
    rm = last_val(rs_mansfield)

    if c is None or s150 is None or sl150 is None or ep is None or sl50 is None:
        return dict(unknown)

    stage_label = classify_stage_scalar(
        c, s150, s50 or 0, s21 or 0, e10 or 0,
        sl150, sl50, ep, at150 or 0, vr or 0,
    )

    # ATRE override: 2A/2B → 2C when price > 6× ATR14 above SMA150 (not regime-based)
    if stage_label in ("2A", "2B") and at150 is not None and at150 > 6.0:
        stage_label = "2C"
    # RS modifier
    if stage_label == "2B" and rm is not None and rm < 0:
        stage_label = "2B(RS-)"

    return {
        "stage": f"STAGE_{stage_label}",
        "stage_label": stage_label,
        "price": c,
        "sma150": s150,
        "stage_slope_pct": sl150,
        "stage_dist_pct": ep,
        "ext_pct": ep,
        "sma150_slope": sl150,
        "sma50_slope": sl50,
        "ema10_dist_pct": last_val(ema10_dist_pct_s),
        "ema10_dist_n": last_val(ema10_dist_n_s),
        "vol_ratio": vr,
        "rs_mansfield_pct": rm,
    }


def compute_weinstein_stage_series_from_daily(
    daily_sym_newest_first: pd.DataFrame,
    daily_bm_newest_first: pd.DataFrame,
) -> pd.DataFrame:
    """Compute daily stage/RS series (Stage Analysis spec) using SMA150 as primary anchor.

    Output columns (daily resolution — no weekly forward-fill):
    - stage_label: 1A|1B|2A|2B|2B(RS-)|2C|3A|3B|4A|4B|4C|UNKNOWN
    - ext_pct, sma150_slope, sma50_slope, ema10_dist_pct, ema10_dist_n
    - vol_ratio, rs_mansfield_pct, stage_slope_pct, stage_dist_pct
    """
    if (
        daily_sym_newest_first is None
        or daily_sym_newest_first.empty
        or daily_bm_newest_first is None
        or daily_bm_newest_first.empty
    ):
        return pd.DataFrame(index=pd.Index([]))

    sym = daily_sym_newest_first.iloc[::-1]  # oldest→newest
    bm = daily_bm_newest_first.iloc[::-1]

    close = sym["Close"]
    volume = sym["Volume"] if "Volume" in sym.columns else pd.Series(np.nan, index=sym.index)

    sma150 = close.rolling(150).mean()
    sma50 = close.rolling(50).mean()
    sma21 = close.rolling(21).mean()
    ema10 = close.ewm(span=10, adjust=False).mean()
    vol_avg = volume.rolling(20).mean()

    ext_pct = ((close - sma150) / sma150 * 100).replace([np.inf, -np.inf], np.nan)
    sma150_slope = ((sma150 - sma150.shift(20)) / sma150.shift(20) * 100).replace([np.inf, -np.inf], np.nan)
    sma50_slope = ((sma50 - sma50.shift(10)) / sma50.shift(10) * 100).replace([np.inf, -np.inf], np.nan)
    vol_ratio = (volume / vol_avg).replace([np.inf, -np.inf], np.nan)

    atr14 = calculate_atr_series(sym, 14) if {"High", "Low", "Close"}.issubset(sym.columns) else pd.Series(np.nan, index=sym.index)
    if atr14 is None:
        atr14 = pd.Series(np.nan, index=sym.index)
    atre_150 = ((close - sma150) / atr14).replace([np.inf, -np.inf], np.nan)
    ema10_dist_pct = ((close - ema10) / ema10 * 100).replace([np.inf, -np.inf], np.nan)
    atrp14 = (atr14 / close * 100).replace([np.inf, -np.inf], np.nan)
    ema10_dist_n = (ema10_dist_pct / atrp14).replace([np.inf, -np.inf], np.nan)

    # RS Mansfield (daily)
    bm_close = bm["Close"].reindex(sym.index, method="ffill")
    rs = (close / bm_close.replace(0, np.nan)).astype("float64")
    rs_ma = rs.rolling(252).mean()
    rs_mansfield = ((rs / rs_ma - 1.0) * 100.0).replace([np.inf, -np.inf], np.nan)

    stage_label = classify_stage_series(
        close, sma150, sma50, sma21, ema10,
        sma150_slope, sma50_slope, ext_pct, atre_150,
        vol_ratio, rs_mansfield,
    )

    daily_out = pd.DataFrame(
        {
            "stage_label": stage_label,
            "stage_slope_pct": sma150_slope,
            "stage_dist_pct": ext_pct,
            "ext_pct": ext_pct,
            "sma150_slope": sma150_slope,
            "sma50_slope": sma50_slope,
            "ema10_dist_pct": ema10_dist_pct,
            "ema10_dist_n": ema10_dist_n,
            "vol_ratio": vol_ratio,
            "rs_mansfield_pct": rs_mansfield,
        },
        index=sym.index,
    )
    return daily_out
