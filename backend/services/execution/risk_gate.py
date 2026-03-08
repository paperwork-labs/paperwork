"""Pre-trade risk gate -- validates orders before they reach any broker."""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.market_data import MarketSnapshot
from backend.services.execution.broker_base import OrderRequest

logger = logging.getLogger(__name__)

MAX_ORDER_VALUE = 100_000
MAX_SINGLE_POSITION_PCT = 0.25


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
    ) -> List[str]:
        """Run all risk checks. Raises on hard block, returns soft warnings."""
        warnings: List[str] = []
        est_value = req.quantity * price_estimate

        if est_value > self.max_order_value:
            raise RiskViolation(
                f"Order value ${est_value:,.0f} exceeds "
                f"${self.max_order_value:,.0f} maximum"
            )

        if db and price_estimate > 0:
            total_equity = (
                db.query(func.sum(MarketSnapshot.current_price))
                .filter(MarketSnapshot.current_price.isnot(None))
                .scalar()
            )
            if total_equity and total_equity > 0:
                pct = est_value / float(total_equity)
                if pct > self.max_position_pct:
                    raise RiskViolation(
                        f"Order would be {pct:.0%} of portfolio, "
                        f"exceeding {self.max_position_pct:.0%} limit"
                    )

        return warnings

    def estimate_price(
        self,
        db: Session,
        symbol: str,
        limit_price: Optional[float],
        stop_price: Optional[float],
    ) -> float:
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
                    pass
        return price
