"""Hedgeye GIP Quad Engine — macro environment classification.

Classifies the macro environment into Quads 1–4 based on the rate-of-change
of real GDP growth and CPI inflation.  The Quad sets the medium-term expectation:
asset class bias, sector tilt, and concentration limits.

Functions:
    classify_quad       — determine Q1-Q4 from GDP/CPI first differences
    compute_depth       — Deep vs Shallow from magnitude of first differences
    compute_quad_state  — full classification with divergence tracking
    get_concentration_limits — Quad-adjusted concentration limits
    get_sector_action   — SCAN/WATCH/AVOID for a sector × Quad pair
    check_t10_trigger   — whether a Quad transition fires T10 exit cascade

medallion: silver
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class QuadState:
    """Full Quad classification output with divergence tracking."""

    quarterly_quad: str  # Q1, Q2, Q3, Q4
    monthly_quad: str  # Q1, Q2, Q3, Q4
    quarterly_depth: str  # Deep, Shallow
    monthly_depth: str  # Deep, Shallow
    operative_quad: str  # Monthly if diverged 2+ months, else Quarterly
    divergence_flag: bool = False
    divergence_months: int = 0
    t10_triggered: bool = False


DEPTH_THRESHOLD_BPS = 30  # |first difference| > 30bps = Deep


def classify_quad(gdp_first_diff: float, cpi_first_diff: float) -> str:
    """Classify into Q1-Q4 from GDP and CPI first differences.

    Axes (rate-of-change of rate-of-change):
        GDP first diff > 0 → Growth accelerating
        CPI first diff > 0 → Inflation accelerating
    """
    growth_up = gdp_first_diff > 0
    inflation_up = cpi_first_diff > 0

    if growth_up and not inflation_up:
        return "Q1"  # Goldilocks: Growth ↑ Inflation ↓
    if growth_up and inflation_up:
        return "Q2"  # Reflation: Growth ↑ Inflation ↑
    if not growth_up and inflation_up:
        return "Q3"  # Stagflation: Growth ↓ Inflation ↑
    return "Q4"  # Deflation: Growth ↓ Inflation ↓


def compute_depth(gdp_first_diff: float, cpi_first_diff: float) -> str:
    """Deep vs Shallow from magnitude of first differences.

    Deep = |first difference| > 30bps on either axis.
    """
    if (
        abs(gdp_first_diff) > DEPTH_THRESHOLD_BPS / 100
        or abs(cpi_first_diff) > DEPTH_THRESHOLD_BPS / 100
    ):
        return "Deep"
    return "Shallow"


def compute_quad_state(
    *,
    gdp_first_diff_quarterly: float,
    cpi_first_diff_quarterly: float,
    gdp_first_diff_monthly: float,
    cpi_first_diff_monthly: float,
    prior_divergence_months: int = 0,
) -> QuadState:
    """Full Quad classification with divergence tracking.

    When Monthly Quad diverges from Quarterly for 2+ consecutive months,
    the Monthly Quad becomes the operative Quad for sector filtering and
    concentration limits.
    """
    q_quad = classify_quad(gdp_first_diff_quarterly, cpi_first_diff_quarterly)
    m_quad = classify_quad(gdp_first_diff_monthly, cpi_first_diff_monthly)
    q_depth = compute_depth(gdp_first_diff_quarterly, cpi_first_diff_quarterly)
    m_depth = compute_depth(gdp_first_diff_monthly, cpi_first_diff_monthly)

    divergence_flag = q_quad != m_quad
    divergence_months = (prior_divergence_months + 1) if divergence_flag else 0

    operative_quad = m_quad if divergence_months >= 2 else q_quad

    return QuadState(
        quarterly_quad=q_quad,
        monthly_quad=m_quad,
        quarterly_depth=q_depth,
        monthly_depth=m_depth,
        operative_quad=operative_quad,
        divergence_flag=divergence_flag,
        divergence_months=divergence_months,
    )


# ── Concentration Limits (Spec Section 7.2) ──


@dataclass
class QuadConcentrationLimits:
    """Quad-adjusted concentration limits for portfolio sizing."""

    max_equity_pct: float
    max_single_sector_pct: float
    max_single_position_pct: float
    min_cash_floor_pct: float
    commodity_gold_alloc_pct: float
    fixed_income_alloc_pct: float


_QUAD_LIMITS: dict[str, QuadConcentrationLimits] = {
    "Q1": QuadConcentrationLimits(
        max_equity_pct=100,
        max_single_sector_pct=30,
        max_single_position_pct=8,
        min_cash_floor_pct=0,
        commodity_gold_alloc_pct=10,
        fixed_income_alloc_pct=0,
    ),
    "Q2": QuadConcentrationLimits(
        max_equity_pct=90,
        max_single_sector_pct=25,
        max_single_position_pct=6,
        min_cash_floor_pct=10,
        commodity_gold_alloc_pct=25,
        fixed_income_alloc_pct=10,
    ),
    "Q3": QuadConcentrationLimits(
        max_equity_pct=40,
        max_single_sector_pct=15,
        max_single_position_pct=4,
        min_cash_floor_pct=50,
        commodity_gold_alloc_pct=30,
        fixed_income_alloc_pct=25,
    ),
    "Q4": QuadConcentrationLimits(
        max_equity_pct=20,
        max_single_sector_pct=10,
        max_single_position_pct=2,
        min_cash_floor_pct=80,
        commodity_gold_alloc_pct=15,
        fixed_income_alloc_pct=40,
    ),
}


def get_concentration_limits(
    quad: str,
    depth: str = "Deep",
) -> QuadConcentrationLimits:
    """Return concentration limits for a Quad + depth.

    In shallow Quads, reduce max equity by 25% from the top of the range.
    """
    limits = _QUAD_LIMITS.get(quad)
    if limits is None:
        logger.warning("Unknown quad %r, defaulting to Q4 limits", quad)
        limits = _QUAD_LIMITS["Q4"]

    if depth == "Shallow":
        return QuadConcentrationLimits(
            max_equity_pct=limits.max_equity_pct * 0.75,
            max_single_sector_pct=limits.max_single_sector_pct,
            max_single_position_pct=limits.max_single_position_pct,
            min_cash_floor_pct=limits.min_cash_floor_pct,
            commodity_gold_alloc_pct=limits.commodity_gold_alloc_pct,
            fixed_income_alloc_pct=limits.fixed_income_alloc_pct,
        )
    return limits


# ── Sector Rotation Matrix (Spec Section 9.3) ──
# Action per sector × Quad when Regime = R1/R2 (bullish internals).

_SECTOR_MATRIX: dict[str, dict[str, str]] = {
    "Technology": {"Q1": "SCAN", "Q2": "SCAN", "Q3": "WATCH", "Q4": "AVOID"},
    "Consumer Disc.": {"Q1": "SCAN", "Q2": "SCAN", "Q3": "AVOID", "Q4": "AVOID"},
    "Industrials": {"Q1": "SCAN", "Q2": "SCAN", "Q3": "AVOID", "Q4": "AVOID"},
    "Financials": {"Q1": "WATCH", "Q2": "SCAN", "Q3": "AVOID", "Q4": "AVOID"},
    "Energy": {"Q1": "WATCH", "Q2": "SCAN", "Q3": "SCAN", "Q4": "AVOID"},
    "Health Care": {"Q1": "AVOID", "Q2": "AVOID", "Q3": "SCAN", "Q4": "SCAN"},
    "Consumer Staples": {"Q1": "AVOID", "Q2": "AVOID", "Q3": "WATCH", "Q4": "SCAN"},
    "Utilities": {"Q1": "AVOID", "Q2": "AVOID", "Q3": "SCAN", "Q4": "SCAN"},
    "Materials": {"Q1": "SCAN", "Q2": "SCAN", "Q3": "WATCH", "Q4": "AVOID"},
    "REITs": {"Q1": "SCAN", "Q2": "AVOID", "Q3": "SCAN", "Q4": "WATCH"},
    "Comm. Services": {"Q1": "SCAN", "Q2": "AVOID", "Q3": "AVOID", "Q4": "AVOID"},
    "Defense/Aero": {"Q1": "SCAN", "Q2": "SCAN", "Q3": "SCAN", "Q4": "SCAN"},
    "Gold": {"Q1": "WATCH", "Q2": "WATCH", "Q3": "SCAN", "Q4": "SCAN"},
}

DEFENSIVE_SECTORS = frozenset(
    {"Health Care", "Utilities", "Consumer Staples", "Gold", "Defense/Aero"}
)


def get_sector_action(
    sector: str,
    quad: str,
    regime: str = "R1",
) -> str:
    """Return SCAN/WATCH/AVOID for a sector given the current Quad and Regime.

    Regime governs which sectors are accessible:
    - R1/R2: Full sector matrix applies.
    - R3: Only SCAN or WATCH sectors from current Quad column are accessible.
           AVOID sectors are excluded even for Set 1.
    - R4/R5: Only explicitly defensive sectors (XLV, XLU, XLP, GLD/GDX, ITA).
    """
    sector_row = _SECTOR_MATRIX.get(sector)
    if sector_row is None:
        return "AVOID"

    base_action = sector_row.get(quad, "AVOID")

    if regime in ("R1", "R2"):
        return base_action

    if regime == "R3":
        return base_action if base_action in ("SCAN", "WATCH") else "AVOID"

    # R4/R5: only defensive sectors
    if sector in DEFENSIVE_SECTORS:
        return "WATCH"
    return "AVOID"


def get_scan_sectors(quad: str, regime: str = "R1") -> list[str]:
    """Return list of sectors eligible for scanning (SCAN action only)."""
    return [
        sector for sector in _SECTOR_MATRIX if get_sector_action(sector, quad, regime) == "SCAN"
    ]


# ── T10 Quad Transition Exit (Spec Section 7.1, 10.3) ──

_BEARISH_QUADS = frozenset({"Q3", "Q4"})


def check_t10_trigger(
    prior_quarterly_quad: str,
    new_quarterly_quad: str,
) -> bool:
    """Check whether a Quarterly Quad transition fires T10 exit cascade.

    T10 fires when the Quarterly Quad shifts to Q3 or Q4.
    Action: sell 30% of current equity holdings, ensure cash >= 50%.
    """
    if prior_quarterly_quad == new_quarterly_quad:
        return False
    return new_quarterly_quad in _BEARISH_QUADS


def compute_binding_ceiling(
    regime_max_equity_pct: float,
    quad_max_equity_pct: float,
) -> float:
    """The binding constraint is always the tighter of Regime or Quad limits."""
    return min(regime_max_equity_pct, quad_max_equity_pct)
