"""Scan Overlay Engine (v4 Section 7)

Assigns stocks to scan tiers based on 6 filters per tier.
Tiers are regime-gated: R1 sees all tiers, R5 sees only short tiers.

4 long tiers (Set 1–4) + 2 short tiers (Short Set 1–2).
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

TIER_SET_1 = "Set 1"  # Best long candidates
TIER_SET_2 = "Set 2"
TIER_SET_3 = "Set 3"
TIER_SET_4 = "Set 4"  # Marginal longs
TIER_SHORT_1 = "Short Set 1"  # Best short candidates
TIER_SHORT_2 = "Short Set 2"

ALL_LONG_TIERS = [TIER_SET_1, TIER_SET_2, TIER_SET_3, TIER_SET_4]
ALL_SHORT_TIERS = [TIER_SHORT_1, TIER_SHORT_2]

# Regime → which long tiers are accessible
REGIME_LONG_ACCESS = {
    REGIME_R1: [TIER_SET_1, TIER_SET_2, TIER_SET_3, TIER_SET_4],
    REGIME_R2: [TIER_SET_1, TIER_SET_2, TIER_SET_3],
    REGIME_R3: [TIER_SET_1, TIER_SET_2],
    REGIME_R4: [TIER_SET_1],
    REGIME_R5: [],
}

# Regime → which short tiers are accessible
REGIME_SHORT_ACCESS = {
    REGIME_R1: [],
    REGIME_R2: [],
    REGIME_R3: [TIER_SHORT_1],
    REGIME_R4: [TIER_SHORT_1, TIER_SHORT_2],
    REGIME_R5: [TIER_SHORT_1, TIER_SHORT_2],
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

    Set 1 (highest conviction): 2A/2B stage, RS > 0, tight EMA10, top ATRE percentile, high range
    Set 2: 2A/2B/2C, RS > -5, moderate EMA10 distance
    Set 3: 1B/2A/2B, any RS, wider EMA10 tolerance
    Set 4: 1A/1B/2A, weaker metrics but still long-eligible
    """
    stage = inp.stage_label
    rs = _safe(inp.rs_mansfield)
    dist_n = _safe(inp.ema10_dist_n)
    atre_p = _safe(inp.atre_150_pctile)
    range52 = _safe(inp.range_pos_52w)

    accessible = REGIME_LONG_ACCESS.get(regime, [])

    # Set 1 — highest conviction
    if TIER_SET_1 in accessible:
        if stage in ("2A", "2B") and rs > 0 and dist_n <= 2.0 and atre_p >= 70 and range52 >= 60:
            return TIER_SET_1

    # Set 2
    if TIER_SET_2 in accessible:
        if stage in ("2A", "2B", "2C") and rs > -5 and dist_n <= 3.0 and range52 >= 40:
            return TIER_SET_2

    # Set 3
    if TIER_SET_3 in accessible:
        if stage in ("1B", "2A", "2B") and dist_n <= 4.0:
            return TIER_SET_3

    # Set 4 — marginal
    if TIER_SET_4 in accessible:
        if stage in ("1A", "1B", "2A"):
            return TIER_SET_4

    return None


def classify_short_tier(inp: ScanInput, regime: str) -> Optional[str]:
    """Assign a stock to the best matching short tier, or None if no match.

    Short Set 1: 4A/4B stage, RS < 0, tight EMA10 (below), low range
    Short Set 2: 3B/4A/4B/4C, RS < 5, wider tolerance
    """
    stage = inp.stage_label
    rs = _safe(inp.rs_mansfield)
    dist_n = _safe(inp.ema10_dist_n)
    range52 = _safe(inp.range_pos_52w)

    accessible = REGIME_SHORT_ACCESS.get(regime, [])

    # Short Set 1 — highest conviction shorts
    if TIER_SHORT_1 in accessible:
        if stage in ("4A", "4B") and rs < 0 and dist_n >= -2.0 and range52 <= 30:
            return TIER_SHORT_1

    # Short Set 2
    if TIER_SHORT_2 in accessible:
        if stage in ("3B", "4A", "4B", "4C") and rs < 5:
            return TIER_SHORT_2

    return None


def classify_scan_tier(inp: ScanInput, regime: str) -> Optional[str]:
    """Assign a stock to the best matching tier (long or short)."""
    long_tier = classify_long_tier(inp, regime)
    if long_tier:
        return long_tier
    return classify_short_tier(inp, regime)


def derive_action_label(stage_label: str, scan_tier: Optional[str], regime: str) -> str:
    """Derive the action label (BUY/HOLD/WATCH/REDUCE/SHORT/AVOID) from stage + scan + regime."""
    if scan_tier in (TIER_SHORT_1, TIER_SHORT_2):
        return "SHORT"

    if scan_tier == TIER_SET_1:
        return "BUY"

    if scan_tier == TIER_SET_2:
        if regime in (REGIME_R1, REGIME_R2):
            return "BUY"
        return "WATCH"

    if scan_tier in (TIER_SET_3, TIER_SET_4):
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
