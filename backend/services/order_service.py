"""Order execution service with enforced risk guardrails.

Delegates risk checking to the canonical RiskGate in
backend.services.execution.risk_gate.  The RiskViolation exception
is re-exported from there so callers only need one import.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.order import Order, OrderStatus
from backend.models.market_data import MarketSnapshot
from backend.services.execution.broker_base import OrderRequest
from backend.services.execution.risk_gate import RiskGate, RiskViolation

logger = logging.getLogger(__name__)

_risk_gate = RiskGate()


class OrderService:
    def __init__(self):
        self._ibkr_client = None
        self._broker_router = None

    @property
    def ibkr(self):
        if self._ibkr_client is None:
            from backend.services.clients.ibkr_client import ibkr_client
            self._ibkr_client = ibkr_client
        return self._ibkr_client

    @property
    def router(self):
        if self._broker_router is None:
            from backend.services.execution.broker_router import broker_router
            self._broker_router = broker_router
        return self._broker_router

    def _get_executor(self, broker_type: str = "ibkr"):
        return self.router.get(broker_type)

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
        side: str,
        order_type: str,
        quantity: float,
        price_estimate: float,
    ) -> List[str]:
        """Run risk checks via the canonical RiskGate.

        Raises RiskViolation if a hard limit is breached.
        Returns a list of soft warnings for advisory-only concerns.
        """
        req = OrderRequest.from_user_input(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
        )
        _risk_gate.check(req, price_estimate)
        return []

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
        warnings = self._check_risk_gates(
            db, symbol, side, order_type, quantity, price_estimate
        )

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
        """Submit a previewed order for execution via broker router."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": "Order not found"}
        if created_by is not None and order.created_by != created_by:
            return {"error": "Forbidden"}
        if order.status != OrderStatus.PREVIEW.value:
            return {"error": f"Order is in '{order.status}' state, cannot submit"}

        req = OrderRequest.from_user_input(
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            limit_price=order.limit_price,
            stop_price=order.stop_price,
        )

        broker = order.broker_type or "ibkr"
        executor = self._get_executor(broker)
        result = await executor.place_order(req)

        if not result.ok:
            order.status = OrderStatus.ERROR.value
            order.error_message = result.error
        else:
            order.status = OrderStatus.SUBMITTED.value
            order.broker_order_id = str(result.broker_order_id or "")
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
        """Cancel a submitted order via broker router."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": "Order not found"}
        if created_by is not None and order.created_by != created_by:
            return {"error": "Forbidden"}
        if order.status not in (OrderStatus.SUBMITTED.value, OrderStatus.PARTIALLY_FILLED.value):
            return {"error": f"Cannot cancel order in '{order.status}' state"}

        if order.broker_order_id:
            broker = order.broker_type or "ibkr"
            executor = self._get_executor(broker)
            result = await executor.cancel_order(order.broker_order_id)
            if not result.ok:
                return {"error": result.error}

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

        broker = order.broker_type or "ibkr"
        executor = self._get_executor(broker)
        result = await executor.get_order_status(order.broker_order_id)

        status_map = {
            "Submitted": OrderStatus.SUBMITTED.value,
            "PreSubmitted": OrderStatus.PENDING_SUBMIT.value,
            "Filled": OrderStatus.FILLED.value,
            "Cancelled": OrderStatus.CANCELLED.value,
            "Inactive": OrderStatus.REJECTED.value,
        }
        new_status = status_map.get(result.status, order.status)
        filled = result.filled_quantity or 0
        remaining = result.raw.get("remaining", 0) if result.raw else 0
        if filled > 0 and remaining > 0:
            new_status = OrderStatus.PARTIALLY_FILLED.value
        order.status = new_status
        if filled:
            order.filled_quantity = filled
        if result.avg_fill_price is not None:
            order.filled_avg_price = result.avg_fill_price
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
