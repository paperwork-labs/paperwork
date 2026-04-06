"""Pre-trade risk gate — validates orders before they reach any broker.

Includes Stage Analysis spec position sizing (ATR-based with Regime Multiplier x Stage Cap).
See Stage_Analysis.docx Section 9.

DANGER ZONE: This file affects capital protection. See .cursor/rules/protected-regions.mdc
Related docs: docs/TRADING_PRINCIPLES.md, Stage_Analysis.docx Section 9
Related rules: portfolio-manager.mdc, risk-manager.mdc
IRON LAW: Single execution path - OrderManager → RiskGate → BrokerRouter. Never bypass.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.config import settings as app_settings
from backend.models.market_data import MarketSnapshot
from backend.services.execution.broker_base import OrderRequest
from backend.services.market.regime_engine import (
    REGIME_R1,
    REGIME_R2,
    REGIME_R3,
    REGIME_R4,
    REGIME_R5,
    REGIME_RULES,
)

logger = logging.getLogger(__name__)

MAX_ORDER_VALUE = 100_000
MAX_SINGLE_POSITION_PCT = app_settings.MAX_SINGLE_POSITION_PCT

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


class RiskViolation(Exception):
    """Hard block: order cannot proceed."""


class RiskGate:
    """Stateless pre-trade risk checker.

    Raises RiskViolation for hard blocks.
    Returns a list of soft warnings for advisory concerns.
    """

    def __init__(
        self,
        max_order_value: float = MAX_ORDER_VALUE,
        max_position_pct: float = MAX_SINGLE_POSITION_PCT,
    ):
        self.max_order_value = max_order_value
        self.max_position_pct = max_position_pct

    def check(
        self,
        req: OrderRequest,
        price_estimate: float,
        db: Optional[Session] = None,
        portfolio_equity: Optional[float] = None,
        risk_budget: Optional[float] = None,
    ) -> List[str]:
        """Run all risk checks. Raises on hard block, returns soft warnings."""
        warnings: List[str] = []
        est_value = req.quantity * price_estimate

        if est_value > self.max_order_value:
            raise RiskViolation(
                f"Order value ${est_value:,.0f} exceeds "
                f"${self.max_order_value:,.0f} maximum"
            )

        if portfolio_equity and portfolio_equity > 0:
            pct = est_value / portfolio_equity
            if pct > self.max_position_pct:
                raise RiskViolation(
                    f"Position would be {pct:.1%} of equity, "
                    f"exceeds {self.max_position_pct:.0%} maximum"
                )

        if db and price_estimate > 0 and risk_budget and risk_budget > 0:
            sizing_warning = self._check_stage_regime_sizing(
                db, req, price_estimate, risk_budget
            )
            if sizing_warning:
                warnings.append(sizing_warning)

        return warnings

    def _check_stage_regime_sizing(
        self,
        db: Session,
        req: OrderRequest,
        price_estimate: float,
        risk_budget: float,
    ) -> Optional[str]:
        """Enforce Stage Analysis spec position sizing as a hard cap.

        Raises RiskViolation if requested quantity exceeds stage cap.
        Returns None if sizing is within limits.
        """
        from backend.services.market.regime_engine import get_current_regime

        snap = (
            db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol == req.symbol.upper(),
                MarketSnapshot.analysis_type == "technical_snapshot",
            )
            .order_by(MarketSnapshot.analysis_timestamp.desc())
            .first()
        )
        if not snap or not snap.stage_label or not snap.atrp_14:
            return None

        regime = get_current_regime(db)
        regime_state = regime.regime_state if regime else "R3"

        result = compute_position_size(
            risk_budget=risk_budget,
            atrp_14=float(snap.atrp_14),
            stop_multiplier=DEFAULT_STOP_MULTIPLIER,
            regime_state=regime_state,
            stage_label=snap.stage_label,
            current_price=price_estimate,
        )

        if result.shares <= 0:
            raise RiskViolation(
                f"Position sizing: {snap.stage_label} in {regime_state} has 0% stage cap "
                f"— no new longs allowed"
            )

        if req.quantity > result.shares:
            logger.warning(
                "Position sizing cap BLOCKED: %s requested %d shares, max is %d "
                "(stage=%s, regime=%s, cap=%.0f%%)",
                req.symbol, req.quantity, result.shares,
                snap.stage_label, regime_state, result.stage_cap * 100,
            )
            raise RiskViolation(
                f"Position sizing: requested {req.quantity} shares exceeds "
                f"max of {result.shares} "
                f"(stage {snap.stage_label}, regime {regime_state}, "
                f"cap {result.stage_cap:.0%})"
            )

        return None

    def estimate_price(
        self,
        db: Session,
        symbol: str,
        limit_price: Optional[float],
        stop_price: Optional[float],
    ) -> float:
        """Estimate order price for risk checks.

        Raises RiskViolation if no valid price can be determined — conservative
        fail-safe to prevent understated risk checks when price is unknown.
        """
        price = limit_price or stop_price or 0.0
        if not price:
            snap = (
                db.query(MarketSnapshot.current_price)
                .filter(MarketSnapshot.symbol == symbol.upper())
                .order_by(MarketSnapshot.analysis_timestamp.desc())
                .first()
            )
            if snap and snap[0] is not None:
                try:
                    price = float(snap[0])
                except (TypeError, ValueError):
                    raise RiskViolation(
                        f"Cannot parse price for {symbol} from snapshot — "
                        f"order rejected (conservative fail-safe)"
                    )
            else:
                raise RiskViolation(
                    f"No price available for {symbol} — "
                    f"order rejected (conservative fail-safe)"
                )
        return price
