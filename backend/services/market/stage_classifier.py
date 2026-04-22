"""Weinstein Stage Analysis classifier — 10 sub-stages via SMA150 anchor.

Functions:
    classify_stage_for_timeframe  — scalar single-bar classification
    classify_stage_scalar         — scalar with ATRE placeholder
    classify_stage_full           — scalar with full state management
    classify_stage_series         — vectorized full-series classification
    compute_weinstein_stage_from_daily  — daily OHLCV → latest stage dict
    compute_weinstein_stage_series_from_daily — daily OHLCV → stage series DF
    weekly_from_daily             — weekly resample helper

Medallion layer: silver. See docs/ARCHITECTURE.md and D127.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from backend.services.market.atr_series import calculate_atr_series

logger = logging.getLogger(__name__)

SLOPE_T = 0.35  # ±0.35% slope threshold


@dataclass
class StageResult:
    """Full stage classification output with state tracking."""
    stage_label: str
    atre_promoted: bool = False
    pass_count: int = 0
    action_override: Optional[str] = None
    manual_review: bool = False


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
    """Classify stage for any timeframe using Stage Analysis rules (SMA150 anchor).

    Ext% bands: 4C(≤-30) 4B(-30,-15] 4A(-15,-5] 1A/3A(-5,0] 2A[0,8] 2B(8,20] 2C(>20)
    Boundary rule: on-boundary = more conservative assignment.

    ATRE override (promote 2A/2B → 2C when ATRE_150 > 6) and RS modifier are
    applied in post-classification steps, not in this function.

    Priority order (first match wins): 4C→4B→4A→1A→1B→2A→2B→2C→3A→3B→fallback.
    """
    if sma150_slope is None or sma50_slope is None:
        return prev_stage if prev_stage is not None else "UNKNOWN"
    if ext_pct is None:
        if sma150 == 0:
            return prev_stage if prev_stage is not None else "UNKNOWN"
        ext_pct = (price - sma150) / sma150 * 100.0

    above = price > sma150
    below = not above

    slope_strongly_down = sma150_slope < -SLOPE_T
    slope_flat = abs(sma150_slope) <= SLOPE_T
    slope_up = sma150_slope > SLOPE_T
    slope_non_negative = sma150_slope >= 0
    slope_gently_positive = 0 < sma150_slope <= SLOPE_T

    # ── Stage 4: Decline ──

    # 4C: Capitulation — far below SMA150, steep decline
    if below and slope_strongly_down and ext_pct <= -30:
        return "4C"

    # 4B: Accelerating decline — below SMA150, steep, SMA50 confirms
    if below and slope_strongly_down and -30 < ext_pct <= -15 and sma50 < sma150:
        return "4B"

    # 4A: Early decline — below SMA150, slope declining or flat with SMA50 weakening
    if below and (slope_strongly_down or (slope_flat and sma50_slope < -SLOPE_T)):
        if -15 < ext_pct <= -5:
            return "4A"

    # ── Stage 1: Base ──

    # 1A: Deep base — flat SMA150, SMA50 ≤ SMA150 disambiguates from 3A
    if slope_flat and sma50 <= sma150 and -5 < ext_pct <= 0:
        return "1A"

    # 1B: Late base / coiling — flat SMA150, approaching breakout
    if slope_flat and -5 < ext_pct <= 0 and price > sma21 and ema10 > sma21:
        return "1B"

    # ── Stage 2: Advance ──

    # 2A: Early advance — EMA stack required, ext 0-8%
    if above and slope_non_negative and 0 <= ext_pct <= 8 and ema10 > sma21 > sma50:
        return "2A"

    # 2B: Confirmed advance — strong slope, SMA50 confirms
    if above and slope_up and 8 < ext_pct <= 20 and sma50 > sma150 and sma50_slope > SLOPE_T:
        return "2B"

    # 2C: Extended advance — high extension
    if above and slope_up and ext_pct > 20:
        return "2C"

    # ── Stage 3: Distribution ──

    # 3A: Early distribution — SMA50 > SMA150 disambiguates from 1A
    if slope_gently_positive and -5 < ext_pct <= 0 and sma50 > sma150 and sma50_slope < SLOPE_T:
        return "3A"

    # 3B: Late distribution — deteriorating structure
    if slope_flat and price < sma50 and sma50_slope < 0 and ema10 < sma21 < sma50:
        return "3B"

    # Fallback: no rule matched — assigned 3A, caller should set manual_review
    return "3A"


def _is_genuine_3a(
    sma150_slope: float,
    sma50_slope: float,
    ext_pct: float,
    sma50: float,
    sma150: float,
) -> bool:
    """Check if 3A conditions genuinely match (vs fallback)."""
    return (
        0 < sma150_slope <= SLOPE_T
        and -5 < ext_pct <= 0
        and sma50 > sma150
        and sma50_slope < SLOPE_T
    )


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
    """Classify a single bar into one of 10 sub-stages.

    Delegates to :func:`classify_stage_for_timeframe`. The ATRE override
    (promote 2A/2B → 2C when ATRE_150 > 6) is applied in callers via
    :func:`classify_stage_full`.
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


def classify_stage_full(
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
    rs_mansfield: Optional[float] = None,
    *,
    regime_state: str = "R1",
    prior_stage: str = "UNKNOWN",
    prior_atre_promoted: bool = False,
    prior_pass_count: int = 0,
) -> StageResult:
    """Full classification with state management.

    Applies: ATRE sticky (hysteresis 6.0 promote / 4.0 clear), pass_count,
    action_override (2C+R4 → action "3A"), RS modifier, manual_review fallback.
    """
    # Step 1: Determine ATRE promoted state (hysteresis)
    atre_promoted = prior_atre_promoted
    if not atre_promoted and atre_150 is not None and atre_150 > 6.0:
        atre_promoted = True
    elif atre_promoted and atre_150 is not None and atre_150 < 4.0:
        atre_promoted = False

    # Step 2: Classify raw stage (without ATRE override)
    stage = classify_stage_scalar(
        close, sma150, sma50, sma21, ema10,
        sma150_slope, sma50_slope, ext_pct, atre_150, vol_ratio,
    )

    # Step 3: ATRE override post-check (2A/2B → 2C when promoted)
    if stage in ("2A", "2B") and atre_promoted:
        stage = "2C"

    # Step 4: RS modifier
    if stage == "2B" and rs_mansfield is not None and rs_mansfield < 0:
        stage = "2B(RS-)"

    # Step 5: pass_count tracking
    pass_count = prior_pass_count
    is_stage_4 = prior_stage.startswith("4") if prior_stage else False
    if is_stage_4:
        pass_count = 0
    if stage == "2B" and prior_stage != "2B" and not prior_stage.startswith("2B"):
        pass_count += 1

    # Step 6: action_override (2C in R4 → act as 3A)
    action_override: Optional[str] = None
    if stage == "2C" and regime_state == "R4":
        action_override = "3A"

    # Step 7: manual_review if fallback
    manual_review = False
    if stage == "3A" and not _is_genuine_3a(sma150_slope, sma50_slope, ext_pct, sma50, sma150):
        manual_review = True

    return StageResult(
        stage_label=stage,
        atre_promoted=atre_promoted,
        pass_count=pass_count,
        action_override=action_override,
        manual_review=manual_review,
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
    """Vectorized stage classification for full time series.

    Priority order (first match wins): 4C→4B→4A→1A→1B→2A→2B→2C→3A→3B→fallback.
    Post-classification: ATRE override, RS modifier.
    """
    stage = pd.Series("UNKNOWN", index=close.index, dtype="object")

    above = close > sma150
    below = ~above
    has_data = sma150.notna() & sma150_slope.notna() & ext_pct.notna() & sma50_slope.notna()

    slope_strongly_down = sma150_slope < -SLOPE_T
    slope_flat = sma150_slope.abs() <= SLOPE_T
    slope_up = sma150_slope > SLOPE_T
    slope_non_negative = sma150_slope >= 0
    slope_gently_positive = (sma150_slope > 0) & (sma150_slope <= SLOPE_T)

    assigned = pd.Series(False, index=close.index)

    def assign(mask: pd.Series, label: str) -> None:
        nonlocal assigned
        hit = has_data & mask & ~assigned
        stage[hit] = label
        assigned = assigned | hit

    # 4C: Capitulation
    assign(below & slope_strongly_down & (ext_pct <= -30), "4C")

    # 4B: Accelerating decline (SMA50 < SMA150)
    assign(below & slope_strongly_down & (ext_pct > -30) & (ext_pct <= -15) & (sma50 < sma150), "4B")

    # 4A: Early decline
    assign(
        below
        & (slope_strongly_down | (slope_flat & (sma50_slope < -SLOPE_T)))
        & (ext_pct > -15) & (ext_pct <= -5),
        "4A",
    )

    # 1A: Deep base (SMA50 ≤ SMA150)
    assign(slope_flat & (sma50 <= sma150) & (ext_pct > -5) & (ext_pct <= 0), "1A")

    # 1B: Late base (flat slope, near SMA150)
    assign(
        slope_flat & (ext_pct > -5) & (ext_pct <= 0) & (close > sma21) & (ema10 > sma21),
        "1B",
    )

    # 2A: Early advance (EMA stack required)
    assign(above & slope_non_negative & (ext_pct >= 0) & (ext_pct <= 8) & (ema10 > sma21) & (sma21 > sma50), "2A")

    # 2B: Confirmed advance (strong slope, SMA50 confirms)
    assign(
        above & slope_up & (ext_pct > 8) & (ext_pct <= 20) & (sma50 > sma150) & (sma50_slope > SLOPE_T),
        "2B",
    )

    # 2C: Extended advance
    assign(above & slope_up & (ext_pct > 20), "2C")

    # 3A: Early distribution (SMA50 > SMA150 disambiguates)
    assign(
        slope_gently_positive & (ext_pct > -5) & (ext_pct <= 0) & (sma50 > sma150) & (sma50_slope < SLOPE_T),
        "3A",
    )

    # 3B: Late distribution
    assign(
        slope_flat & (close < sma50) & (sma50_slope < 0) & (ema10 < sma21) & (sma21 < sma50),
        "3B",
    )

    # Fallback: unassigned bars with data → 3A
    fallback = has_data & ~assigned
    stage[fallback] = "3A"

    # Post-classification: Breakout override — 1B with volume + stacked MAs → 2A
    breakout = (
        (stage == "1B") & above
        & (vol_ratio > 1.5) & (ema10 > sma21) & (sma21 > sma50)
    )
    stage[breakout] = "2A"

    # Post-classification: ATRE override — 2A/2B with ATRE_150 > 6 → 2C
    atre_override = (stage.isin(["2A", "2B"])) & (atre_150 > 6.0)
    stage[atre_override] = "2C"

    # Post-classification: RS modifier
    rs_flag = (stage == "2B") & (rs_mansfield < 0)
    stage[rs_flag] = "2B(RS-)"

    return stage


def compute_weinstein_stage_from_daily(
    daily_sym_newest_first: pd.DataFrame,
    daily_bm_newest_first: pd.DataFrame,
    *,
    regime_state: str = "R1",
    prior_stage: str = "UNKNOWN",
    prior_atre_promoted: bool = False,
    prior_pass_count: int = 0,
) -> Dict[str, Any]:
    """Compute Stage Analysis from daily OHLCV (both newest->first).

    Uses SMA150 as primary anchor. Returns latest bar's stage + supporting
    metrics + state fields (atre_promoted, pass_count, action_override,
    manual_review).
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
        "atre_promoted": prior_atre_promoted,
        "pass_count": prior_pass_count,
        "action_override": None,
        "manual_review": False,
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

    result = classify_stage_full(
        c, s150, s50 or 0, s21 or 0, e10 or 0,
        sl150, sl50, ep, at150 or 0, vr or 0,
        rm,
        regime_state=regime_state,
        prior_stage=prior_stage,
        prior_atre_promoted=prior_atre_promoted,
        prior_pass_count=prior_pass_count,
    )

    return {
        "stage": f"STAGE_{result.stage_label}",
        "stage_label": result.stage_label,
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
        "atre_promoted": result.atre_promoted,
        "pass_count": result.pass_count,
        "action_override": result.action_override,
        "manual_review": result.manual_review,
    }


def compute_weinstein_stage_series_from_daily(
    daily_sym_newest_first: pd.DataFrame,
    daily_bm_newest_first: pd.DataFrame,
) -> pd.DataFrame:
    """Compute daily stage/RS series using SMA150 as primary anchor.

    Output columns (daily resolution):
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
