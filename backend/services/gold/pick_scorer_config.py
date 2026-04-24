"""Configuration for pick quality scoring (weights, thresholds, multipliers).

Single source of truth for tunables so weights can be revised without
scattered literals (reversible via config per decision log).

medallion: gold
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import FrozenSet


@dataclass(frozen=True)
class PickScorerConfig:
    """Default weights sum to 1.0."""

    weight_stage: Decimal = Decimal("0.25")
    weight_rs: Decimal = Decimal("0.20")
    weight_regime: Decimal = Decimal("0.15")
    weight_td: Decimal = Decimal("0.10")
    weight_pullback: Decimal = Decimal("0.15")
    weight_liquidity: Decimal = Decimal("0.10")
    weight_earnings: Decimal = Decimal("0.05")

    # Approximate 20d dollar volume (close * avg volume). No
    # ``dollar_volume_20d`` column on ``MarketSnapshot``; see scorer.
    min_dollar_volume_20d: Decimal = Decimal("50000000")

    # Penalize when earnings fall within this many calendar days of the
    # snapshot reference date.
    earnings_lookahead_days: int = 14

    # Below this many days to earnings, earnings component is minimal.
    earnings_high_risk_days: int = 3


def default_config() -> PickScorerConfig:
    return PickScorerConfig()


def regime_multiplier(regime_code: str) -> Decimal:
    """Applied to the weighted component sum (after weighting, before clip)."""
    m = {
        "R1": Decimal("1.0"),
        "R2": Decimal("0.9"),
        "R3": Decimal("0.6"),
        "R4": Decimal("0.3"),
        "R5": Decimal("0.0"),
    }
    return m.get((regime_code or "").strip().upper(), Decimal("1.0"))


def regime_alignment_raw_score(regime_code: str) -> tuple[Decimal, str]:
    """Long-side alignment score (0-100) for the weighted regime *component*."""
    key = (regime_code or "").strip().upper()
    if key == "R1":
        return Decimal("100"), "Risk-on regime supports long exposure"
    if key == "R2":
        return Decimal("90"), "Constructive regime for longs"
    if key == "R3":
        return Decimal("55"), "Neutral/choppy regime; selective longs"
    if key == "R4":
        return Decimal("30"), "Risk-off; longs face headwinds"
    if key == "R5":
        return Decimal("0"), "Crisis regime; avoid new longs"
    return (
        Decimal("50"),
        "Regime state unavailable; alignment treated as neutral",
    )


# Stage labels from ``MarketSnapshot.stage_label`` (SMA150 anchor taxonomy).
HIGH_STAGE_LABELS: FrozenSet[str] = frozenset({"2A", "2B"})
MID_STAGE_LABELS: FrozenSet[str] = frozenset({"2C"})
LATE_STAGE_LABELS: FrozenSet[str] = frozenset({"3A", "3B"})
DIST_STAGE_LABELS: FrozenSet[str] = frozenset({"4A", "4B", "4C"})
BASE_STAGE_LABELS: FrozenSet[str] = frozenset({"1A", "1B"})


def sum_weights(cfg: PickScorerConfig) -> Decimal:
    return (
        cfg.weight_stage
        + cfg.weight_rs
        + cfg.weight_regime
        + cfg.weight_td
        + cfg.weight_pullback
        + cfg.weight_liquidity
        + cfg.weight_earnings
    )
