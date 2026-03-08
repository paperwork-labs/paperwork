"""Order execution service with enforced risk guardrails."""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.order import Order, OrderStatus
from backend.models.market_data import MarketSnapshot

logger = logging.getLogger(__name__)

MAX_ORDER_VALUE = 100_000
MAX_SINGLE_POSITION_PCT = 0.25


class RiskViolation(Exception):
    """Raised when a risk guardrail blocks an order."""


class OrderService:
    def __init__(self):
        self._ibkr_client = None

    @property
    def ibkr(self):
        if self._ibkr_client is None:
            from backend.services.clients.ibkr_client import ibkr_client
            self._ibkr_client = ibkr_client
        return self._ibkr_client

    def _estimate_price(
        self,
        db: Session,
        symbol: str,
        limit_price: Optional[float],
        stop_price: Optional[float],
    ) -> float:
        price = limit_price or stop_price or 0
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

    def _check_risk_gates(
        self,
        db: Session,
        symbol: str,
        quantity: float,
        price_estimate: float,
    ) -> List[str]:
        """Run risk checks. Raises RiskViolation if a hard limit is breached.
        Returns a list of soft warnings for advisory-only concerns."""
        warnings: List[str] = []
        est_value = quantity * price_estimate

        if est_value > MAX_ORDER_VALUE:
            raise RiskViolation(
                f"Order value ${est_value:,.0f} exceeds "
                f"${MAX_ORDER_VALUE:,.0f} maximum"
            )

        # TODO: MAX_SINGLE_POSITION_PCT check requires per-user portfolio equity.
        # The previous implementation incorrectly used sum(MarketSnapshot.current_price)
        # across the entire universe. Will be implemented when user equity is available
        # from the positions/holdings table.

        return warnings

    async def preview_order(
        self,
        db: Session,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a preview order using whatIfOrder. Enforces risk gates."""
        ib_order_type_map = {"market": "MKT", "limit": "LMT", "stop": "STP", "stop_limit": "STP_LMT"}
        ib_action = "BUY" if side.lower() == "buy" else "SELL"
        ib_otype = ib_order_type_map.get(order_type.lower(), "MKT")

        preview = await self.ibkr.what_if_order(
            symbol=symbol,
            action=ib_action,
            quantity=quantity,
            order_type=ib_otype,
            limit_price=limit_price,
            stop_price=stop_price,
        )

        price_estimate = self._estimate_price(db, symbol, limit_price, stop_price)
        warnings = self._check_risk_gates(db, symbol, quantity, price_estimate)

        order = Order(
            symbol=symbol.upper(),
            side=side.lower(),
            order_type=order_type.lower(),
            status=OrderStatus.PREVIEW.value,
            quantity=quantity,
            limit_price=limit_price,
            stop_price=stop_price,
            estimated_commission=preview.get("estimated_commission"),
            estimated_margin_impact=preview.get("estimated_margin_impact"),
            estimated_equity_with_loan=preview.get("estimated_equity_with_loan"),
            preview_data=preview,
            created_by=created_by,
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        return {
            "order_id": order.id,
            "status": order.status,
            "preview": preview,
            "warnings": warnings,
        }

    async def submit_order(
        self, db: Session, order_id: int, created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit a previewed order for execution."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": "Order not found"}
        if created_by is not None and order.created_by != created_by:
            return {"error": "Forbidden"}
        if order.status != OrderStatus.PREVIEW.value:
            return {"error": f"Order is in '{order.status}' state, cannot submit"}

        ib_order_type_map = {"market": "MKT", "limit": "LMT", "stop": "STP", "stop_limit": "STP_LMT"}
        ib_action = "BUY" if order.side == "buy" else "SELL"
        ib_otype = ib_order_type_map.get(order.order_type, "MKT")

        result = await self.ibkr.place_order(
            symbol=order.symbol,
            action=ib_action,
            quantity=order.quantity,
            order_type=ib_otype,
            limit_price=order.limit_price,
            stop_price=order.stop_price,
        )

        if result.get("error"):
            order.status = OrderStatus.ERROR.value
            order.error_message = result["error"]
        else:
            order.status = OrderStatus.SUBMITTED.value
            order.broker_order_id = str(result.get("broker_order_id", ""))
            order.submitted_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(order)
        return {
            "order_id": order.id,
            "status": order.status,
            "broker_order_id": order.broker_order_id,
            "error": order.error_message,
        }

    async def cancel_order(
        self, db: Session, order_id: int, created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cancel a submitted order."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": "Order not found"}
        if created_by is not None and order.created_by != created_by:
            return {"error": "Forbidden"}
        if order.status not in (OrderStatus.SUBMITTED.value, OrderStatus.PARTIALLY_FILLED.value):
            return {"error": f"Cannot cancel order in '{order.status}' state"}

        if order.broker_order_id:
            result = await self.ibkr.cancel_order(order.broker_order_id)
            if result.get("error"):
                return {"error": result["error"]}

        order.status = OrderStatus.CANCELLED.value
        order.cancelled_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(order)
        return {"order_id": order.id, "status": order.status}

    async def poll_order_status(
        self, db: Session, order_id: int, created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Poll broker for latest order status and update DB."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": "Order not found"}
        if created_by is not None and order.created_by != created_by:
            return {"error": "Forbidden"}
        if (
            not order.broker_order_id
            or order.status
            in (OrderStatus.PREVIEW.value, OrderStatus.FILLED.value, OrderStatus.CANCELLED.value)
        ):
            return self._order_to_dict(order)

        broker_status = await self.ibkr.get_order_status(order.broker_order_id)
        if broker_status.get("status"):
            status_map = {
                "Submitted": OrderStatus.SUBMITTED.value,
                "PreSubmitted": OrderStatus.PENDING_SUBMIT.value,
                "Filled": OrderStatus.FILLED.value,
                "Cancelled": OrderStatus.CANCELLED.value,
                "Inactive": OrderStatus.REJECTED.value,
            }
            new_status = status_map.get(broker_status["status"], order.status)
            order.status = new_status
            if broker_status.get("filled") is not None:
                order.filled_quantity = broker_status["filled"]
            if broker_status.get("avg_fill_price") is not None:
                order.filled_avg_price = broker_status["avg_fill_price"]
            if new_status == OrderStatus.FILLED.value and not order.filled_at:
                order.filled_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(order)
        return self._order_to_dict(order)

    def list_orders(
        self,
        db: Session,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        created_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List orders with optional filters."""
        q = db.query(Order).order_by(Order.created_at.desc())
        if created_by is not None:
            q = q.filter(Order.created_by == created_by)
        if status:
            q = q.filter(Order.status == status)
        if symbol:
            q = q.filter(Order.symbol == symbol.upper())
        orders = q.limit(limit).all()
        return [self._order_to_dict(o) for o in orders]

    def get_order(
        self, db: Session, order_id: int, created_by: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get single order by ID."""
        q = db.query(Order).filter(Order.id == order_id)
        if created_by is not None:
            q = q.filter(Order.created_by == created_by)
        order = q.first()
        return self._order_to_dict(order) if order else None

    @staticmethod
    def _order_to_dict(order: Order) -> Dict[str, Any]:
        return {
            "id": order.id,
            "symbol": order.symbol,
            "side": order.side,
            "order_type": order.order_type,
            "status": order.status,
            "quantity": order.quantity,
            "limit_price": order.limit_price,
            "stop_price": order.stop_price,
            "filled_quantity": order.filled_quantity,
            "filled_avg_price": order.filled_avg_price,
            "account_id": order.account_id,
            "broker_order_id": order.broker_order_id,
            "strategy_id": order.strategy_id,
            "signal_id": order.signal_id,
            "position_id": order.position_id,
            "user_id": order.user_id,
            "source": order.source,
            "broker_type": order.broker_type,
            "estimated_commission": order.estimated_commission,
            "estimated_margin_impact": order.estimated_margin_impact,
            "preview_data": order.preview_data,
            "error_message": order.error_message,
            "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
            "filled_at": order.filled_at.isoformat() if order.filled_at else None,
            "cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "created_by": order.created_by,
        }


order_service = OrderService()
