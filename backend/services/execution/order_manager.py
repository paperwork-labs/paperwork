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
from backend.services.risk.circuit_breaker import circuit_breaker
from backend.services.risk.pre_trade_validator import PreTradeValidator

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
        user_id: int,
        broker_type: str = "ibkr",
        risk_budget: Optional[float] = None,
        portfolio_equity: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Preview order: risk check → whatIfOrder → persist.
        
        Enforces correct order: RiskGate FIRST (rejects bad orders before
        consuming broker API quota), then broker preview.
        
        Args:
            risk_budget: Dollar amount willing to risk on this trade (for position sizing)
            portfolio_equity: Total portfolio value (for max position % check)
        """
        price = self.risk_gate.estimate_price(
            db, req.symbol, req.limit_price, req.stop_price
        )
        
        # Lookup portfolio equity if not provided
        if portfolio_equity is None:
            portfolio_equity = self._get_portfolio_equity(db, user_id)
        
        # Default risk budget to 1% of portfolio if not specified
        if risk_budget is None and portfolio_equity and portfolio_equity > 0:
            risk_budget = portfolio_equity * 0.01
        
        warnings = self.risk_gate.check(
            req, price, db,
            portfolio_equity=portfolio_equity,
            risk_budget=risk_budget,
        )

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
            user_id=user_id,
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
    
    def _get_portfolio_equity(self, db: Session, user_id: int) -> Optional[float]:
        """Lookup total portfolio equity for a user."""
        try:
            from backend.models.account_balance import AccountBalance
            balance = (
                db.query(AccountBalance)
                .filter(AccountBalance.user_id == user_id)
                .order_by(AccountBalance.as_of_date.desc())
                .first()
            )
            if balance and balance.total_value:
                return float(balance.total_value)
        except Exception as e:
            logger.warning("Failed to lookup portfolio equity for user %s: %s", user_id, e)
        return None

    async def submit(
        self,
        db: Session,
        order_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """Submit a previewed order for execution.
        
        Flow: PreTradeValidator → CircuitBreaker size adjustment → Broker submit
        """
        order = (
            db.query(Order)
            .filter(Order.id == order_id, Order.user_id == user_id)
            .first()
        )
        if not order:
            return {"error": "Order not found"}
        if order.status != OrderStatus.PREVIEW.value:
            return {"error": f"Order is in '{order.status}' state, cannot submit"}

        # ========================================
        # PRE-TRADE VALIDATION (Circuit Breaker + Risk Checks)
        # ========================================
        is_exit = order.side.lower() == "sell" and order.position_id is not None
        portfolio_equity = self._get_portfolio_equity(db, user_id) or 100_000

        validator = PreTradeValidator(db, user_id=user_id)
        validation = validator.validate(order, portfolio_equity, is_exit=is_exit)

        if not validation.allowed:
            order.status = OrderStatus.REJECTED.value
            order.error_message = f"Pre-trade validation failed: {validation.summary}"
            db.commit()
            db.refresh(order)
            logger.warning(
                "Order %s rejected by pre-trade validator: %s",
                order_id,
                validation.reasons,
            )
            return {
                **_order_to_dict(order),
                "validation": {
                    "allowed": False,
                    "reasons": validation.reasons,
                    "checks": [
                        {"name": c.name, "passed": c.passed, "reason": c.reason}
                        for c in validation.checks
                    ],
                },
            }

        # Apply size multiplier from circuit breaker (tier 1 = 50% size)
        adjusted_quantity = int(order.quantity * validation.size_multiplier)
        if adjusted_quantity <= 0:
            order.status = OrderStatus.REJECTED.value
            order.error_message = "Order quantity reduced to zero by circuit breaker"
            db.commit()
            db.refresh(order)
            return {
                **_order_to_dict(order),
                "validation": {"allowed": False, "reasons": ["Size reduced to zero"]},
            }

        # Log if quantity was adjusted
        if adjusted_quantity != order.quantity:
            logger.info(
                "Order %s quantity adjusted from %d to %d (size_multiplier=%.2f)",
                order_id,
                order.quantity,
                adjusted_quantity,
                validation.size_multiplier,
            )

        req = OrderRequest.from_user_input(
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=adjusted_quantity,
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
            # Update quantity if it was adjusted
            if adjusted_quantity != order.quantity:
                order.quantity = adjusted_quantity

        db.commit()
        db.refresh(order)
        return _order_to_dict(order)

    async def cancel(
        self,
        db: Session,
        order_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """Cancel a submitted order."""
        order = (
            db.query(Order)
            .filter(Order.id == order_id, Order.user_id == user_id)
            .first()
        )
        if not order:
            return {"error": "Order not found"}
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
        user_id: int,
    ) -> Dict[str, Any]:
        """Poll broker for latest order status."""
        order = (
            db.query(Order)
            .filter(Order.id == order_id, Order.user_id == user_id)
            .first()
        )
        if not order:
            return {"error": "Order not found"}
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
        user_id: int,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        q = db.query(Order).filter(Order.user_id == user_id).order_by(Order.created_at.desc())
        if status:
            q = q.filter(Order.status == status)
        if symbol:
            q = q.filter(Order.symbol == symbol.upper())
        return [_order_to_dict(o) for o in q.limit(limit).all()]

    def get_order(
        self,
        db: Session,
        order_id: int,
        user_id: int,
    ) -> Optional[Dict[str, Any]]:
        q = db.query(Order).filter(Order.id == order_id, Order.user_id == user_id)
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
