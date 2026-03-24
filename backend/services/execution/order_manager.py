"""High-level order manager -- orchestrates risk checks, broker routing, and DB persistence."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models.order import Order, OrderStatus
from backend.services.execution.broker_base import OrderRequest, OrderResult, PreviewResult
from backend.services.execution.broker_router import broker_router
from backend.services.execution.risk_gate import RiskGate, RiskViolation

logger = logging.getLogger(__name__)


class OrderManager:
    """Unified order lifecycle manager.

    Sequence: risk_gate.check → broker.preview → persist → broker.place → update
    """

    def __init__(
        self,
        risk_gate: Optional[RiskGate] = None,
    ):
        self.risk_gate = risk_gate or RiskGate()

    async def preview(
        self,
        db: Session,
        req: OrderRequest,
        broker_type: str = "ibkr",
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Preview order: risk check → whatIfOrder → persist."""
        price = self.risk_gate.estimate_price(
            db, req.symbol, req.limit_price, req.stop_price
        )
        warnings = self.risk_gate.check(req, price, db)

        executor = broker_router.get(broker_type)
        preview: PreviewResult = await executor.preview_order(req)

        if not preview.ok:
            return {"error": preview.error}

        order = Order(
            symbol=req.symbol,
            side=req.side.value.lower(),
            order_type=req.order_type.value.lower(),
            status=OrderStatus.PREVIEW.value,
            quantity=req.quantity,
            limit_price=req.limit_price,
            stop_price=req.stop_price,
            source="manual",
            broker_type=broker_type,
            estimated_commission=preview.estimated_commission,
            estimated_margin_impact=preview.estimated_margin_impact,
            estimated_equity_with_loan=preview.estimated_equity_with_loan,
            preview_data=preview.raw,
            created_by=created_by,
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        return {
            "order_id": order.id,
            "status": order.status,
            "preview": preview.raw,
            "warnings": warnings,
        }

    async def submit(
        self,
        db: Session,
        order_id: int,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a previewed order for execution."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": "Order not found"}
        if created_by is not None and order.created_by != created_by:
            return {"error": "Forbidden"}
        if order.status != OrderStatus.PREVIEW.value:
            return {"error": f"Order is in '{order.status}' state, cannot submit"}

        req = OrderRequest(
            symbol=order.symbol,
            side=order.side.upper(),
            order_type=order.order_type.upper(),
            quantity=order.quantity,
            limit_price=order.limit_price,
            stop_price=order.stop_price,
        )

        executor = broker_router.get(order.broker_type or "ibkr")
        result: OrderResult = await executor.place_order(req)

        if not result.ok:
            order.status = OrderStatus.ERROR.value
            order.error_message = result.error
        else:
            order.status = OrderStatus.SUBMITTED.value
            order.broker_order_id = result.broker_order_id
            order.submitted_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(order)
        return _order_to_dict(order)

    async def cancel(
        self,
        db: Session,
        order_id: int,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancel a submitted order."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": "Order not found"}
        if created_by is not None and order.created_by != created_by:
            return {"error": "Forbidden"}
        if order.status not in (
            OrderStatus.SUBMITTED.value,
            OrderStatus.PARTIALLY_FILLED.value,
        ):
            return {"error": f"Cannot cancel order in '{order.status}' state"}

        if order.broker_order_id:
            executor = broker_router.get(order.broker_type or "ibkr")
            result = await executor.cancel_order(order.broker_order_id)
            if not result.ok:
                return {"error": result.error}

        order.status = OrderStatus.CANCELLED.value
        order.cancelled_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(order)
        return _order_to_dict(order)

    async def poll_status(
        self,
        db: Session,
        order_id: int,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Poll broker for latest order status."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": "Order not found"}
        if created_by is not None and order.created_by != created_by:
            return {"error": "Forbidden"}
        if (
            not order.broker_order_id
            or order.status in (
                OrderStatus.PREVIEW.value,
                OrderStatus.FILLED.value,
                OrderStatus.CANCELLED.value,
            )
        ):
            return _order_to_dict(order)

        executor = broker_router.get(order.broker_type or "ibkr")
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
        return _order_to_dict(order)

    def list_orders(
        self,
        db: Session,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        created_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        q = db.query(Order).order_by(Order.created_at.desc())
        if created_by is not None:
            q = q.filter(Order.created_by == created_by)
        if status:
            q = q.filter(Order.status == status)
        if symbol:
            q = q.filter(Order.symbol == symbol.upper())
        return [_order_to_dict(o) for o in q.limit(limit).all()]

    def get_order(
        self,
        db: Session,
        order_id: int,
        created_by: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        q = db.query(Order).filter(Order.id == order_id)
        if created_by is not None:
            q = q.filter(Order.created_by == created_by)
        order = q.first()
        return _order_to_dict(order) if order else None


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
