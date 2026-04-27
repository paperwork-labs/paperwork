"""Stage Analysis position sizing (Section 9) — pure gold-layer math.

Shared by trade card composition and the execution RiskGate. Lives in ``gold/``
so strategy layers do not import ``execution/`` for sizing.

medallion: gold
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.silver.regime.regime_engine import (
    REGIME_R1,
    REGIME_R2,
    REGIME_R3,
    REGIME_R4,
    REGIME_R5,
    REGIME_RULES,
)

# Stage Analysis spec Stage Caps: maximum % of full position allowed per stage per regime
# Format: stage_label → {regime → cap_fraction}
STAGE_CAPS = {
    "1A": {REGIME_R1: 0.0, REGIME_R2: 0.0, REGIME_R3: 0.0, REGIME_R4: 0.0, REGIME_R5: 0.0},
    "1B": {REGIME_R1: 0.0, REGIME_R2: 0.0, REGIME_R3: 0.0, REGIME_R4: 0.0, REGIME_R5: 0.0},
    "2A": {REGIME_R1: 0.75, REGIME_R2: 0.50, REGIME_R3: 0.50, REGIME_R4: 0.33, REGIME_R5: 0.0},
    "2B": {REGIME_R1: 1.0, REGIME_R2: 1.0, REGIME_R3: 0.75, REGIME_R4: 0.0, REGIME_R5: 0.0},
    "2C": {REGIME_R1: 1.0, REGIME_R2: 0.75, REGIME_R3: 0.50, REGIME_R4: 0.0, REGIME_R5: 0.0},
    "3A": {REGIME_R1: 0.50, REGIME_R2: 0.25, REGIME_R3: 0.0, REGIME_R4: 0.0, REGIME_R5: 0.0},
    "3B": {REGIME_R1: 0.0, REGIME_R2: 0.0, REGIME_R3: 0.0, REGIME_R4: 0.0, REGIME_R5: 0.0},
    "4A": {REGIME_R1: 0.0, REGIME_R2: 0.0, REGIME_R3: 0.0, REGIME_R4: 0.0, REGIME_R5: 0.0},
    "4B": {REGIME_R1: 0.0, REGIME_R2: 0.0, REGIME_R3: 0.0, REGIME_R4: 0.0, REGIME_R5: 0.0},
    "4C": {REGIME_R1: 0.0, REGIME_R2: 0.0, REGIME_R3: 0.0, REGIME_R4: 0.0, REGIME_R5: 0.0},
}

DEFAULT_STOP_MULTIPLIER = 2.0


@dataclass
class PositionSizeResult:
    """Stage Analysis spec position sizing output."""

    full_position_dollars: float
    stage_cap: float  # 0.0–1.0 fraction
    capped_position_dollars: float
    shares: int
    risk_budget: float
    atrp_14: float
    stop_multiplier: float
    regime_multiplier: float
    regime_state: str
    stage_label: str


def compute_position_size(
    risk_budget: float,
    atrp_14: float,
    stop_multiplier: float,
    regime_state: str,
    stage_label: str,
    current_price: float,
) -> PositionSizeResult:
    """Stage Analysis spec Position Sizing Formula (Section 9):

    Full Position ($) = [Risk Budget / (ATR%14 × Stop Multiplier)] × Regime Multiplier
    Then apply Stage Cap.
    """
    regime_rules = REGIME_RULES.get(regime_state, REGIME_RULES[REGIME_R3])
    regime_mult = regime_rules["multiplier"]

    if atrp_14 <= 0 or stop_multiplier <= 0 or current_price <= 0:
        return PositionSizeResult(
            full_position_dollars=0,
            stage_cap=0,
            capped_position_dollars=0,
            shares=0,
            risk_budget=risk_budget,
            atrp_14=atrp_14,
            stop_multiplier=stop_multiplier,
            regime_multiplier=regime_mult,
            regime_state=regime_state,
            stage_label=stage_label,
        )

    full_position = (risk_budget / (atrp_14 / 100 * stop_multiplier)) * regime_mult

    clean_stage = stage_label.replace("(RS-)", "")
    caps = STAGE_CAPS.get(clean_stage, {})
    stage_cap = caps.get(regime_state, 0.0)

    capped = full_position * stage_cap
    shares = int(capped / current_price) if current_price > 0 else 0

    return PositionSizeResult(
        full_position_dollars=round(full_position, 2),
        stage_cap=stage_cap,
        capped_position_dollars=round(capped, 2),
        shares=shares,
        risk_budget=risk_budget,
        atrp_14=atrp_14,
        stop_multiplier=stop_multiplier,
        regime_multiplier=regime_mult,
        regime_state=regime_state,
        stage_label=stage_label,
    )
