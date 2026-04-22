"""Discipline-bounded trajectory math for portfolio overview (C7).

Anchor tiers follow **D119** / **MASTER_PLAN_2026.md**: for non-founder accounts,
ceilings are proportional to the account's **YTD starting equity** using cumulative
return rungs of **+50%, +100%, +200%** (i.e. multipliers **1.5×, 2.0×, 3.0×**
on starting equity). This mirrors the three discipline bands described for the
founder book (unleveraged / leveraged / speculative) without hard-coding
absolute dollar targets per user.

**Year-end projection** (explicit linear extrapolation):

Let ``S`` = starting equity at the YTD anchor (first balance on/after 1 Jan,
or last balance before 1 Jan if none in-year). Let ``C`` = latest equity,
``d`` = calendar days elapsed since 1 Jan UTC (minimum 1 to avoid division by
zero). Let ``R = (C - S) / S`` (YTD return).

Extrapolate the same *average daily growth factor* through 365 days::

    projected_year_end = S * (1 + R * (365 / d))

Which is algebraically ``S + (C - S) * (365/d)`` — straight-line extension of
YTD P&L. When ``S <= 0`` or missing, projection is undefined (caller surfaces
empty state).

All money math uses ``Decimal``; callers serialize to JSON floats where needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional, Tuple

# D119 proportional defaults (MASTER_PLAN: 50% / 100% / 200% cumulative rungs).
_UNLEVERAGED_MULT = Decimal("1.5")
_LEVERAGED_MULT = Decimal("2.0")
_SPECULATIVE_MULT = Decimal("3.0")

Trend = Literal["up", "flat", "down"]


@dataclass(frozen=True)
class TrajectoryAnchors:
    unleveraged_ceiling: Decimal
    leveraged_ceiling: Decimal
    speculative_ceiling: Decimal


def compute_anchors(starting_equity: Decimal) -> TrajectoryAnchors:
    """Return tier ceilings from YTD starting equity (all ``Decimal``)."""
    s = starting_equity
    return TrajectoryAnchors(
        unleveraged_ceiling=(s * _UNLEVERAGED_MULT).quantize(Decimal("0.01")),
        leveraged_ceiling=(s * _LEVERAGED_MULT).quantize(Decimal("0.01")),
        speculative_ceiling=(s * _SPECULATIVE_MULT).quantize(Decimal("0.01")),
    )


def compute_ytd_fraction_as_of(as_of: datetime) -> Decimal:
    """Days since 1 Jan UTC (inclusive of partial day as full days + 1 minimum)."""
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    else:
        as_of = as_of.astimezone(timezone.utc)
    year_start = datetime(as_of.year, 1, 1, tzinfo=timezone.utc)
    delta = as_of - year_start
    days = int(delta.total_seconds() // 86400) + 1
    return Decimal(max(1, days))


def compute_projected_year_end(
    *,
    starting_equity: Decimal,
    current_equity: Decimal,
    as_of: datetime,
) -> Optional[Decimal]:
    """Linear YTD extrapolation to calendar year-end; ``None`` if invalid."""
    if starting_equity <= 0:
        return None
    r = (current_equity - starting_equity) / starting_equity
    d = compute_ytd_fraction_as_of(as_of)
    factor = Decimal("365") / d
    projected = starting_equity * (Decimal("1") + r * factor)
    return projected.quantize(Decimal("0.01"))


def compute_trend(
    *,
    starting_equity: Decimal,
    current_equity: Decimal,
) -> Trend:
    """Classify YTD direction; ``flat`` within one cent."""
    if starting_equity <= 0:
        return "flat"
    diff = current_equity - starting_equity
    if abs(diff) < Decimal("0.01"):
        return "flat"
    return "up" if diff > 0 else "down"


def decimal_from_balance_fields(net_liquidation: Optional[float], equity: Optional[float]) -> Decimal:
    """Prefer net liquidation, then equity; broker-agnostic NLV semantics."""
    for v in (net_liquidation, equity):
        if v is not None and float(v) > 0:
            return Decimal(str(v)).quantize(Decimal("0.01"))
    return Decimal("0")
