"""Order reconciliation -- matches filled orders to broker trades."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from backend.models.order import Order, OrderStatus

logger = logging.getLogger(__name__)


class ReconciliationService:
    """Match filled Orders to Trades and surface discrepancies."""

    def reconcile_fills(
        self, db: Session, lookback_hours: int = 24
    ) -> Dict[str, Any]:
        """Find filled orders and attempt to match them with trades."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        filled_orders = (
            db.query(Order)
            .filter(
                Order.status == OrderStatus.FILLED.value,
                Order.filled_at >= cutoff,
            )
            .all()
        )

        matched: list[Dict[str, Any]] = []
        unmatched: list[Dict[str, Any]] = []

        for order in filled_orders:
            from backend.models.trade import Trade

            try:
                trades = (
                    db.query(Trade)
                    .filter(
                        Trade.symbol == order.symbol,
                        Trade.execution_time
                        >= (order.filled_at - timedelta(minutes=5)),
                        Trade.execution_time
                        <= (order.filled_at + timedelta(minutes=5)),
                    )
                    .all()
                )

                match_found = False
                for trade in trades:
                    if (
                        abs(
                            float(trade.quantity or 0)
                            - float(order.filled_quantity or 0)
                        )
                        < 0.01
                    ):
                        matched.append(
                            {
                                "order_id": order.id,
                                "trade_id": trade.id,
                                "symbol": order.symbol,
                                "quantity": order.filled_quantity,
                            }
                        )
                        match_found = True
                        break

                if not match_found:
                    unmatched.append(
                        {
                            "order_id": order.id,
                            "symbol": order.symbol,
                            "filled_quantity": order.filled_quantity,
                            "filled_at": (
                                order.filled_at.isoformat()
                                if order.filled_at
                                else None
                            ),
                        }
                    )
            except Exception as e:
                logger.warning(
                    "Reconciliation error for order %s: %s", order.id, e
                )
                unmatched.append(
                    {"order_id": order.id, "symbol": order.symbol, "error": str(e)}
                )

        result = {
            "total_orders": len(filled_orders),
            "matched": len(matched),
            "unmatched": len(unmatched),
            "matched_details": matched,
            "unmatched_details": unmatched,
        }

        if unmatched:
            logger.warning(
                "Reconciliation found %d unmatched fills", len(unmatched)
            )

        return result

    def get_pnl_attribution(
        self, db: Session, strategy_id: int
    ) -> Dict[str, Any]:
        """Calculate P&L attributed to a specific strategy."""
        orders = (
            db.query(Order)
            .filter(
                Order.strategy_id == strategy_id,
                Order.status == OrderStatus.FILLED.value,
            )
            .all()
        )

        total_pnl = 0.0
        trades_count = 0

        for order in orders:
            if order.filled_avg_price and order.filled_quantity:
                if order.side == "sell":
                    total_pnl += order.filled_quantity * order.filled_avg_price
                else:
                    total_pnl -= order.filled_quantity * order.filled_avg_price
                trades_count += 1

        return {
            "strategy_id": strategy_id,
            "total_pnl": total_pnl,
            "trades_count": trades_count,
        }


reconciliation_service = ReconciliationService()
