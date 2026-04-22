"""High-level order manager -- orchestrates risk checks, broker routing, and DB persistence.

DANGER ZONE: This file is the single execution path. See .cursor/rules/protected-regions.mdc
Related docs: docs/TRADING_PRINCIPLES.md
Related rules: portfolio-manager.mdc
IRON LAW: Single execution path - OrderManager → RiskGate → BrokerRouter. Never bypass.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.broker_account import BrokerAccount
from backend.models.order import Order, OrderStatus
from backend.models.trade import Trade
from backend.services.execution.broker_base import OrderRequest, OrderResult, PreviewResult
from backend.services.execution.broker_router import broker_router
from backend.services.execution.risk_gate import RiskGate, RiskViolation
from backend.services.risk.circuit_breaker import circuit_breaker
from backend.services.risk.pre_trade_validator import PreTradeValidator

logger = logging.getLogger(__name__)

# Submit lock TTL - prevents double-submit race condition
SUBMIT_LOCK_TTL_SECONDS = 30


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
            decision_price=price,  # Capture decision price for slippage tracking
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

    def _compute_slippage_metrics(self, order: Order) -> None:
        """Compute slippage metrics when order is filled.
        
        Updates order.slippage_pct, slippage_dollars, and fill_latency_ms.
        Slippage is positive when execution is worse than decision price:
        - For buys: positive slippage = filled higher than decision
        - For sells: positive slippage = filled lower than decision
        """
        if order.decision_price is None or order.filled_avg_price is None:
            return
        
        decision = float(order.decision_price)
        fill = float(order.filled_avg_price)
        qty = float(order.filled_quantity or order.quantity or 0)
        
        if decision <= 0:
            return
        
        # Calculate slippage (positive = worse execution)
        if order.side.lower() == "buy":
            # For buys: higher fill = worse = positive slippage
            slippage_pct = ((fill - decision) / decision) * 100
            slippage_dollars = (fill - decision) * qty
        else:
            # For sells: lower fill = worse = positive slippage
            slippage_pct = ((decision - fill) / decision) * 100
            slippage_dollars = (decision - fill) * qty
        
        order.slippage_pct = round(slippage_pct, 4)
        order.slippage_dollars = round(slippage_dollars, 2)
        
        # Calculate fill latency
        if order.submitted_at and order.filled_at:
            latency = (order.filled_at - order.submitted_at).total_seconds() * 1000
            order.fill_latency_ms = int(latency)
        
        logger.info(
            "Order %s slippage: %.4f%% ($%.2f), latency: %s ms",
            order.id,
            order.slippage_pct,
            order.slippage_dollars,
            order.fill_latency_ms,
        )

    async def submit(
        self,
        db: Session,
        order_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """Submit a previewed order for execution.
        
        Flow: Acquire submit lock → PreTradeValidator → CircuitBreaker size adjustment → Broker submit
        
        Uses Redis lock to prevent double-submit race condition when parallel
        HTTP requests or Celery retries attempt to submit the same order.
        """
        # Acquire submit lock to prevent race condition
        lock_key = f"order:submit:{order_id}"
        try:
            from backend.services.cache import redis_client
            lock_acquired = redis_client.set(
                lock_key, "1", nx=True, ex=SUBMIT_LOCK_TTL_SECONDS
            )
            if not lock_acquired:
                logger.warning("Order %s submit blocked by concurrent request", order_id)
                return {"error": "Order submission already in progress"}
        except Exception as e:
            logger.warning("Redis lock failed for order %s, proceeding with DB check: %s", order_id, e)

        order = (
            db.query(Order)
            .filter(Order.id == order_id, Order.user_id == user_id)
            .first()
        )
        if not order:
            return {"error": "Order not found"}
        if order.status != OrderStatus.PREVIEW.value:
            return {"error": f"Order is in '{order.status}' state, cannot submit"}

        from backend.config import settings as _shadow_settings
        if _shadow_settings.SHADOW_TRADING_MODE:
            from backend.services.execution.shadow_order_recorder import ShadowOrderRecorder
            return ShadowOrderRecorder(session=db).record(order_id=order_id, user_id=user_id)

        # ========================================
        # PRE-TRADE VALIDATION (Circuit Breaker + Risk Checks)
        # ========================================
        is_exit = order.side.lower() == "sell" and order.position_id is not None
        raw_equity = self._get_portfolio_equity(db, user_id)
        portfolio_equity = raw_equity
        if portfolio_equity is None:
            logger.warning(
                "Portfolio equity unavailable for user %s; using $100,000 fallback for order %s pre-trade checks",
                user_id,
                order_id,
            )
            portfolio_equity = 100_000.0

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

        price = self.risk_gate.estimate_price(
            db, req.symbol, req.limit_price, req.stop_price
        )
        risk_budget = (
            portfolio_equity * 0.01 if portfolio_equity and portfolio_equity > 0 else None
        )
        try:
            self.risk_gate.check(
                req,
                price,
                db,
                portfolio_equity=portfolio_equity,
                risk_budget=risk_budget,
            )
        except RiskViolation as e:
            order.status = OrderStatus.REJECTED.value
            order.error_message = f"Risk gate rejected: {e}"
            db.commit()
            db.refresh(order)
            logger.warning("Order %s rejected by risk gate: %s", order_id, e)
            return {
                **_order_to_dict(order),
                "risk_gate": {"allowed": False, "reason": str(e)},
            }

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
            
            # Compute slippage metrics on fill
            self._compute_slippage_metrics(order)
            
            # Record fill with circuit breaker for daily loss tracking
            try:
                from backend.models.position import Position, PositionType
                
                fill_price = float(order.filled_avg_price or 0)
                fill_qty = float(order.filled_quantity or order.quantity or 0)
                is_exit = order.side.lower() == "sell" and order.position_id is not None
                
                # Calculate P&L for exits using position's average_cost
                pnl = 0.0
                if is_exit and order.position_id:
                    position = db.query(Position).filter(Position.id == order.position_id).first()
                    if position and position.average_cost:
                        avg_cost = float(position.average_cost)
                        # Check if short position (profit when price drops)
                        is_short = position.position_type in (
                            PositionType.SHORT, PositionType.OPTION_SHORT, PositionType.FUTURE_SHORT
                        )
                        if is_short:
                            pnl = (avg_cost - fill_price) * fill_qty
                        else:
                            pnl = (fill_price - avg_cost) * fill_qty
                
                circuit_breaker.record_fill(
                    symbol=order.symbol,
                    pnl=pnl,
                    is_exit=is_exit,
                )
                logger.info(
                    "Order %s fill recorded with circuit breaker: pnl=%.2f, is_exit=%s",
                    order.id, pnl, is_exit
                )
            except Exception as e:
                logger.warning("Failed to record fill with circuit breaker for order %s: %s", order.id, e)

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
        cap = max(0, int(limit or 0))
        if cap == 0:
            return []

        fetch_n = cap * 2
        order_sort = func.coalesce(
            Order.filled_at, Order.submitted_at, Order.created_at
        )
        q = db.query(Order).filter(Order.user_id == user_id)
        if status:
            q = q.filter(Order.status == status)
        if symbol:
            q = q.filter(Order.symbol == symbol.upper())
        q = q.order_by(order_sort.desc().nullslast()).limit(fetch_n)
        order_rows: List[Dict[str, Any]] = []
        for o in q:
            d = _order_to_dict(o)
            d["_sort_ts"] = _order_list_sort_ts(o)
            order_rows.append(d)

        trade_sort = func.coalesce(
            Trade.execution_time, Trade.order_time, Trade.created_at
        )
        tq = (
            db.query(Trade, BrokerAccount)
            .join(BrokerAccount, Trade.account_id == BrokerAccount.id)
            .filter(BrokerAccount.user_id == user_id)
        )
        if status:
            st = status.strip()
            tq = tq.filter(Trade.status.ilike(st))
        if symbol:
            tq = tq.filter(Trade.symbol == symbol.upper())
        tq = tq.order_by(trade_sort.desc().nullslast()).limit(fetch_n)
        trade_rows: List[Dict[str, Any]] = []
        for t, acct in tq:
            d = _trade_to_ledger_dict(t, acct, user_id)
            d["_sort_ts"] = _trade_list_sort_ts(t)
            trade_rows.append(d)

        combined = sorted(
            order_rows + trade_rows,
            key=lambda row: row["_sort_ts"],
            reverse=True,
        )[:cap]
        for d in combined:
            d.pop("_sort_ts", None)
        return combined

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
        # Execution quality analytics
        "decision_price": order.decision_price,
        "slippage_pct": order.slippage_pct,
        "slippage_dollars": order.slippage_dollars,
        "fill_latency_ms": order.fill_latency_ms,
        "vwap_at_fill": order.vwap_at_fill,
        "spread_at_order": order.spread_at_order,
        # Timestamps
        "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
        "filled_at": order.filled_at.isoformat() if order.filled_at else None,
        "cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "created_by": order.created_by,
        "ledger": "order",
    }


def _order_list_sort_ts(order: Order) -> datetime:
    for attr in (order.filled_at, order.submitted_at, order.created_at):
        if attr is not None:
            if attr.tzinfo is None:
                return attr.replace(tzinfo=timezone.utc)
            return attr.astimezone(timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)


def _trade_list_sort_ts(t: Trade) -> datetime:
    for attr in (t.execution_time, t.order_time, t.created_at):
        if attr is not None:
            if attr.tzinfo is None:
                return attr.replace(tzinfo=timezone.utc)
            return attr.astimezone(timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)


def _trade_to_ledger_dict(
    t: Trade, acct: Optional[BrokerAccount], user_id: int
) -> Dict[str, Any]:
    """Shape broker-ledger Trade rows to match the orders API schema for list views.

    When ``list_orders`` has already joined ``BrokerAccount``, pass that row; otherwise
    ``acct`` may be None (falls back to raw ``account_id`` in the API-shaped dict).
    """
    acct_id_str: Optional[str] = (
        str(acct.account_number)
        if acct is not None and acct.account_number is not None
        else str(t.account_id)
    )
    st = (t.status or "FILLED").strip() or "FILLED"
    st_lower = st.lower()
    q = float(t.quantity or 0)
    px = float(t.price) if t.price is not None else 0.0
    return {
        "id": -int(t.id),  # synthetic: negative ids are broker-ledger; no collision with live orders
        "symbol": t.symbol,
        "side": (t.side or "buy").lower(),
        "order_type": (t.order_type or "market").lower(),
        "status": st_lower,
        "quantity": q,
        "limit_price": None,
        "stop_price": None,
        "filled_quantity": q,
        "filled_avg_price": px,
        "account_id": acct_id_str,
        "broker_order_id": t.order_id,
        "strategy_id": None,
        "signal_id": t.signal_id,
        "position_id": None,
        "user_id": user_id,
        "source": "manual",
        "broker_type": (acct.broker.value if acct and acct.broker is not None else "schwab"),
        "estimated_commission": float(t.commission) if t.commission is not None else None,
        "estimated_margin_impact": None,
        "preview_data": None,
        "error_message": None,
        "decision_price": None,
        "slippage_pct": None,
        "slippage_dollars": None,
        "fill_latency_ms": None,
        "vwap_at_fill": None,
        "spread_at_order": None,
        "submitted_at": t.order_time.isoformat() if t.order_time else None,
        "filled_at": t.execution_time.isoformat() if t.execution_time else None,
        "cancelled_at": None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "created_by": None,
        "ledger": "trade",
    }
