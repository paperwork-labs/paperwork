"""Scan Overlay Engine (v4 Section 7)

Assigns stocks to scan tiers based on 6 filters per tier.
Tiers are regime-gated: R1 sees all tiers, R5 sees only short tiers.

4 long tiers (Breakout Elite/Standard, Early Base, Speculative) + 2 short tiers (Breakdown Elite/Standard).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from backend.services.market.regime_engine import (
    REGIME_R1,
    REGIME_R2,
    REGIME_R3,
    REGIME_R4,
    REGIME_R5,
)

logger = logging.getLogger(__name__)


# ── Tier definitions ──

TIER_BREAKOUT_ELITE = "Breakout Elite"  # Best long candidates
TIER_BREAKOUT_STANDARD = "Breakout Standard"
TIER_EARLY_BASE = "Early Base"
TIER_SPECULATIVE = "Speculative"  # Marginal longs
TIER_BREAKDOWN_ELITE = "Breakdown Elite"  # Best short candidates
TIER_BREAKDOWN_STANDARD = "Breakdown Standard"

ALL_LONG_TIERS = [TIER_BREAKOUT_ELITE, TIER_BREAKOUT_STANDARD, TIER_EARLY_BASE, TIER_SPECULATIVE]
ALL_SHORT_TIERS = [TIER_BREAKDOWN_ELITE, TIER_BREAKDOWN_STANDARD]

# Regime → which long tiers are accessible
REGIME_LONG_ACCESS = {
    REGIME_R1: [TIER_BREAKOUT_ELITE, TIER_BREAKOUT_STANDARD, TIER_EARLY_BASE, TIER_SPECULATIVE],
    REGIME_R2: [TIER_BREAKOUT_ELITE, TIER_BREAKOUT_STANDARD, TIER_EARLY_BASE],
    REGIME_R3: [TIER_BREAKOUT_ELITE, TIER_BREAKOUT_STANDARD],
    REGIME_R4: [TIER_BREAKOUT_ELITE],
    REGIME_R5: [],
}

# Regime → which short tiers are accessible
REGIME_SHORT_ACCESS = {
    REGIME_R1: [],
    REGIME_R2: [],
    REGIME_R3: [TIER_BREAKDOWN_ELITE],
    REGIME_R4: [TIER_BREAKDOWN_ELITE, TIER_BREAKDOWN_STANDARD],
    REGIME_R5: [TIER_BREAKDOWN_ELITE, TIER_BREAKDOWN_STANDARD],
}


@dataclass
class ScanInput:
    """Per-stock scan inputs from MarketSnapshot."""
    symbol: str
    stage_label: str
    rs_mansfield: Optional[float]
    ema10_dist_n: Optional[float]
    atre_150_pctile: Optional[float]  # ATRE_150 percentile (0-100)
    range_pos_52w: Optional[float]  # Range position in 52-week range (0-100)
    ext_pct: Optional[float]
    atrp_14: Optional[float]


def _safe(val: Optional[float], default: float = 0.0) -> float:
    return val if val is not None else default


def classify_long_tier(inp: ScanInput, regime: str) -> Optional[str]:
    """Assign a stock to the best matching long tier, or None if no match.

    Breakout Elite (highest conviction): 2A/2B stage, RS > 0, tight EMA10, top ATRE percentile, high range
    Breakout Standard: 2A/2B/2C, RS > -5, moderate EMA10 distance
    Early Base: 1B/2A/2B, any RS, wider EMA10 tolerance
    Speculative: 1A/1B/2A, weaker metrics but still long-eligible
    """
    stage = inp.stage_label
    dist_n = _safe(inp.ema10_dist_n)
    atre_p = _safe(inp.atre_150_pctile)
    range52 = _safe(inp.range_pos_52w)

    accessible = REGIME_LONG_ACCESS.get(regime, [])

    # Breakout Elite — highest conviction (RS required; None is unassigned)
    if TIER_BREAKOUT_ELITE in accessible and inp.rs_mansfield is not None:
        rs = inp.rs_mansfield
        if stage in ("2A", "2B") and rs > 0 and dist_n <= 2.0 and atre_p >= 70 and range52 >= 60:
            return TIER_BREAKOUT_ELITE

    # Breakout Standard (RS required; None is unassigned)
    if TIER_BREAKOUT_STANDARD in accessible and inp.rs_mansfield is not None:
        rs = inp.rs_mansfield
        if stage in ("2A", "2B", "2C") and rs > -5 and dist_n <= 3.0 and range52 >= 40:
            return TIER_BREAKOUT_STANDARD

    # Early Base
    if TIER_EARLY_BASE in accessible:
        if stage in ("1B", "2A", "2B") and dist_n <= 4.0:
            return TIER_EARLY_BASE

    # Speculative — marginal
    if TIER_SPECULATIVE in accessible:
        if stage in ("1A", "1B", "2A"):
            return TIER_SPECULATIVE

    return None


def classify_short_tier(inp: ScanInput, regime: str) -> Optional[str]:
    """Assign a stock to the best matching short tier, or None if no match.

    Breakdown Elite: 4A/4B stage, RS < 0, tight EMA10 (below), low range
    Breakdown Standard: 3B/4A/4B/4C, RS < 5, wider tolerance
    """
    stage = inp.stage_label
    dist_n = _safe(inp.ema10_dist_n)
    range52 = _safe(inp.range_pos_52w)

    accessible = REGIME_SHORT_ACCESS.get(regime, [])

    # Breakdown Elite — highest conviction shorts (RS required; None is unassigned)
    if TIER_BREAKDOWN_ELITE in accessible and inp.rs_mansfield is not None:
        rs = inp.rs_mansfield
        if stage in ("4A", "4B") and rs < 0 and dist_n >= -2.0 and range52 <= 30:
            return TIER_BREAKDOWN_ELITE

    # Breakdown Standard
    if TIER_BREAKDOWN_STANDARD in accessible:
        rs = _safe(inp.rs_mansfield)
        if stage in ("3B", "4A", "4B", "4C") and rs < 5:
            return TIER_BREAKDOWN_STANDARD

    return None


def classify_scan_tier(inp: ScanInput, regime: str) -> Optional[str]:
    """Assign a stock to the best matching tier (long or short)."""
    long_tier = classify_long_tier(inp, regime)
    if long_tier:
        return long_tier
    return classify_short_tier(inp, regime)


def derive_action_label(stage_label: str, scan_tier: Optional[str], regime: str) -> str:
    """Derive the action label (BUY/HOLD/WATCH/REDUCE/SHORT/AVOID) from stage + scan + regime."""
    if scan_tier in (TIER_BREAKDOWN_ELITE, TIER_BREAKDOWN_STANDARD):
        return "SHORT"

    if scan_tier == TIER_BREAKOUT_ELITE:
        return "BUY"

    if scan_tier == TIER_BREAKOUT_STANDARD:
        if regime in (REGIME_R1, REGIME_R2):
            return "BUY"
        return "WATCH"

    if scan_tier in (TIER_EARLY_BASE, TIER_SPECULATIVE):
        return "WATCH"

    # No scan tier — derive from stage
    if stage_label in ("2A", "2B"):
        return "HOLD" if regime in (REGIME_R3, REGIME_R4) else "WATCH"
    if stage_label == "2C":
        return "HOLD"
    if stage_label in ("3A", "3B"):
        return "REDUCE"
    if stage_label.startswith("4"):
        return "AVOID"
    if stage_label.startswith("1"):
        return "WATCH"

    return "AVOID"
