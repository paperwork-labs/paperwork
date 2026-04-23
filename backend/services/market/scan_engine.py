"""Scan Overlay Engine

Assigns stocks to scan tiers based on 6 filters per tier.
Tiers are regime-gated: R1 sees all tiers, R5 sees only short tiers.
Quad sector filter restricts scans to SCAN sectors per the Quad × Regime matrix.

4 long tiers (Breakout Elite/Standard, Early Base, Speculative) + 2 short tiers (Breakdown Elite/Standard).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Sequence

from backend.services.market.regime_engine import (
    REGIME_R1,
    REGIME_R2,
    REGIME_R3,
    REGIME_R4,
    REGIME_R5,
)
from backend.services.market.quad_engine import get_sector_action

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
    sector: Optional[str] = None
    sub_industry: Optional[str] = None
    pass_count: int = 0
    current_price: Optional[float] = None
    atr_30: Optional[float] = None
    # Daily snapshot of ``HistoricalIV.iv_rank_252`` for the symbol. ``None``
    # during the 252-day warm-up (see G5 / ``docs/plans/G5_IV_RANK_SURFACE.md``).
    # ``None`` is meaningful: filters using :func:`apply_iv_rank_filter`
    # EXCLUDE null-rank rows rather than coercing to 0 (same R29 pattern
    # as ``rs_mansfield``).
    iv_rank_252: Optional[float] = None


def _safe(val: Optional[float], default: float = 0.0) -> float:
    return val if val is not None else default


def _is_sector_scannable(sector: Optional[str], quad: str, regime: str) -> bool:
    """Check if a sector is scannable in the current Quad × Regime."""
    if sector is None:
        return True  # unknown sector: allow through, let other filters decide
    action = get_sector_action(sector, quad, regime)
    return action == "SCAN"


def classify_long_tier(
    inp: ScanInput,
    regime: str,
    *,
    quad: str = "Q1",
) -> Optional[str]:
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

    # Quad sector filter: AVOID sectors are excluded from all long scans
    if not _is_sector_scannable(inp.sector, quad, regime):
        return None

    # Second-pass 2B prohibition in R3-R5
    if stage == "2B" and inp.pass_count >= 2 and regime in (REGIME_R3, REGIME_R4, REGIME_R5):
        return None

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


def classify_scan_tier(
    inp: ScanInput,
    regime: str,
    *,
    quad: str = "Q1",
) -> Optional[str]:
    """Assign a stock to the best matching tier (long or short)."""
    long_tier = classify_long_tier(inp, regime, quad=quad)
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


# ── Forward R/R (Spec Section 9.2) ──

def compute_forward_rr(
    close: float,
    atr_30: float,
    stop: Optional[float] = None,
    regime: str = "R1",
) -> Optional[float]:
    """Compute forward risk/reward ratio.

    Target = Close + (multiplier × ATR30).
    R1-R2: multiplier = 3.0; R3-R5: multiplier = 2.5.
    Stop defaults to Close - (1.5 × ATR30) if not provided.
    """
    if close <= 0 or atr_30 <= 0:
        return None

    mult = 3.0 if regime in (REGIME_R1, REGIME_R2) else 2.5
    target = close + mult * atr_30

    if stop is None:
        stop = close - 1.5 * atr_30

    risk = close - stop
    if risk <= 0:
        return None

    return (target - close) / risk


# ── Correlation Constraint (Spec Section 11.5) ──

def check_correlation_constraint(
    positions: Sequence[dict],
    candidate_sub_industry: Optional[str],
    max_same_sub_industry: int = 3,
) -> bool:
    """Check if adding a position violates the correlation constraint.

    Max 3 positions in the same GICS sub-industry.
    Returns True if the candidate passes (can be added), False if blocked.
    """
    if candidate_sub_industry is None:
        return True

    count = sum(
        1 for p in positions
        if p.get("sub_industry") == candidate_sub_industry
    )
    return count < max_same_sub_industry


# ── Sector Confirmation (Spec Section 9.4) ──

def compute_sector_confirmation(
    sector_etf_stage: str,
) -> str:
    """Determine sector confirmation based on sector ETF stage.

    - Stage 2 (any sub-stage): CONFIRMING
    - Stage 1: NEUTRAL
    - Stage 3 or 4: DENYING
    """
    if sector_etf_stage.startswith("2"):
        return "CONFIRMING"
    if sector_etf_stage.startswith("1"):
        return "NEUTRAL"
    if sector_etf_stage.startswith("3") or sector_etf_stage.startswith("4"):
        return "DENYING"
    return "NEUTRAL"


def compute_sector_divergence_pct(
    sector_confirmations: dict[str, str],
) -> float:
    """Compute what % of SCAN sectors are DENYING the Quad.

    When >= 50%, this is an early warning of a Quad transition.
    Returns 0.0–100.0.
    """
    if not sector_confirmations:
        return 0.0
    total = len(sector_confirmations)
    denying = sum(1 for v in sector_confirmations.values() if v == "DENYING")
    return (denying / total) * 100.0


# ── IV-rank filter (G5) ──

# Supported comparison operators for the ``iv_rank_252`` filter.
IV_RANK_OPS = ("lt", "lte", "gt", "gte", "between")


def apply_iv_rank_filter(
    rows: Sequence[ScanInput],
    op: str,
    value: float,
    *,
    value2: Optional[float] = None,
) -> list[ScanInput]:
    """Filter scan inputs by ``iv_rank_252``.

    Operators: ``lt``, ``lte``, ``gt``, ``gte``, ``between``.

    Null-rank rows are **always excluded** -- a symbol with no IV history
    is NOT "iv_rank = 0", and conflating the two would silently pass
    ramping/un-covered symbols through a "cheap options" filter that
    depends on rank < 20 semantics. This mirrors the R29 convention for
    ``rs_mansfield``.

    Raises ``ValueError`` for unknown ops or a missing ``value2`` on
    ``between``.
    """
    op_l = (op or "").lower()
    if op_l not in IV_RANK_OPS:
        raise ValueError(f"unknown iv_rank operator: {op!r} (allowed: {IV_RANK_OPS})")
    if op_l == "between" and value2 is None:
        raise ValueError("'between' operator requires value2")

    lo = min(value, value2) if op_l == "between" and value2 is not None else None
    hi = max(value, value2) if op_l == "between" and value2 is not None else None

    out: list[ScanInput] = []
    for r in rows:
        v = r.iv_rank_252
        if v is None:  # R29 -- never treat absent as 0
            continue
        ok = False
        if op_l == "lt":
            ok = v < value
        elif op_l == "lte":
            ok = v <= value
        elif op_l == "gt":
            ok = v > value
        elif op_l == "gte":
            ok = v >= value
        elif op_l == "between":
            # both bounds inclusive -- standard "between x and y" semantics
            ok = lo is not None and hi is not None and lo <= v <= hi
        if ok:
            out.append(r)
    return out
