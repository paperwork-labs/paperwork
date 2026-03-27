"""Paper trading executor - simulated order execution for testing and practice.

Implements BrokerExecutor protocol with in-memory position tracking.
Orders are "filled" instantly at current market price (from MarketSnapshot).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional

from backend.services.execution.broker_base import (
    OrderRequest,
    OrderResult,
    PreviewResult,
)

logger = logging.getLogger(__name__)


@dataclass
class PaperPosition:
    """Virtual position in paper trading account."""
    symbol: str
    quantity: Decimal
    avg_cost: Decimal
    market_value: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")


@dataclass
class PaperOrder:
    """Record of a paper order."""
    order_id: str
    symbol: str
    side: str
    quantity: Decimal
    order_type: str
    status: str  # pending, filled, cancelled
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    fill_price: Optional[Decimal] = None
    filled_quantity: Decimal = Decimal("0")
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    filled_at: Optional[datetime] = None


class PaperExecutor:
    """Paper trading executor with simulated fills.
    
    Features:
    - Instant market order fills at current snapshot price
    - Limit orders fill if price meets condition
    - Position tracking with P&L calculation
    - Configurable starting cash balance
    """

    def __init__(self, starting_cash: float = 100_000.0):
        self._cash = Decimal(str(starting_cash))
        self._starting_cash = Decimal(str(starting_cash))
        self._positions: Dict[str, PaperPosition] = {}
        self._orders: Dict[str, PaperOrder] = {}
        self._order_counter = 0

    @property
    def broker_name(self) -> str:
        return "paper"

    async def connect(self) -> bool:
        """Paper trading is always connected."""
        logger.info("Paper trading executor ready (starting cash: $%.2f)", self._cash)
        return True

    async def disconnect(self) -> None:
        """No-op for paper trading."""
        pass

    def _generate_order_id(self) -> str:
        """Generate a unique paper order ID."""
        self._order_counter += 1
        return f"PAPER-{self._order_counter:06d}-{uuid.uuid4().hex[:8]}"

    def _get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Get current price from MarketSnapshot."""
        try:
            from backend.database import SessionLocal
            from backend.models.market_data import MarketSnapshot
            
            db = SessionLocal()
            try:
                snap = (
                    db.query(MarketSnapshot.current_price)
                    .filter(
                        MarketSnapshot.symbol == symbol,
                        MarketSnapshot.analysis_type == "technical_snapshot",
                    )
                    .order_by(MarketSnapshot.analysis_timestamp.desc())
                    .first()
                )
                if snap and snap[0]:
                    return Decimal(str(snap[0]))
                return None
            finally:
                db.close()
        except Exception as e:
            logger.warning("Failed to get price for %s: %s", symbol, e)
            return None

    async def preview_order(self, req: OrderRequest) -> PreviewResult:
        """Preview paper order with estimated fill."""
        price = self._get_current_price(req.symbol)
        if price is None:
            price = Decimal(str(req.limit_price or 100.0))  # Fallback
        
        order_value = price * Decimal(str(req.quantity))
        commission = Decimal("0")  # Paper trading has no commissions
        
        return PreviewResult(
            estimated_commission=float(commission),
            estimated_margin_impact=float(order_value),
            raw={
                "paper_mode": True,
                "estimated_price": float(price),
                "order_value": float(order_value),
            },
        )

    async def place_order(self, req: OrderRequest) -> OrderResult:
        """Place and immediately attempt to fill paper order."""
        order_id = self._generate_order_id()
        
        paper_order = PaperOrder(
            order_id=order_id,
            symbol=req.symbol,
            side=req.side.value.lower(),
            quantity=Decimal(str(req.quantity)),
            order_type=req.order_type.value,
            status="pending",
            limit_price=Decimal(str(req.limit_price)) if req.limit_price else None,
            stop_price=Decimal(str(req.stop_price)) if req.stop_price else None,
        )
        
        self._orders[order_id] = paper_order
        
        # Attempt immediate fill for market orders
        if req.order_type.value in ("MKT", "market"):
            return await self._fill_order(paper_order)
        
        # For limit/stop orders, check if fillable
        return await self._check_and_fill(paper_order)

    async def _fill_order(self, order: PaperOrder) -> OrderResult:
        """Fill a paper order at current market price."""
        price = self._get_current_price(order.symbol)
        if price is None:
            return OrderResult(
                error=f"No price data available for {order.symbol}",
            )
        
        order_value = price * order.quantity
        
        # Check if we have enough cash for buys
        if order.side == "buy":
            if order_value > self._cash:
                return OrderResult(
                    error=f"Insufficient cash: need ${order_value:.2f}, have ${self._cash:.2f}",
                )
            self._cash -= order_value
        else:
            # For sells, check if we have the position
            pos = self._positions.get(order.symbol)
            if not pos or pos.quantity < order.quantity:
                return OrderResult(
                    error=f"Insufficient shares of {order.symbol}",
                )
        
        # Execute the fill
        order.fill_price = price
        order.filled_quantity = order.quantity
        order.status = "filled"
        order.filled_at = datetime.now(timezone.utc)
        
        # Update position
        self._update_position(order)
        
        logger.info(
            "Paper order filled: %s %s %s @ $%.2f (value: $%.2f)",
            order.side.upper(), order.quantity, order.symbol, price, order_value,
        )
        
        return OrderResult(
            broker_order_id=order.order_id,
            status="filled",
            filled_quantity=float(order.filled_quantity),
            avg_fill_price=float(order.fill_price),
            raw={"paper_mode": True},
        )

    async def _check_and_fill(self, order: PaperOrder) -> OrderResult:
        """Check if limit/stop order can be filled."""
        price = self._get_current_price(order.symbol)
        if price is None:
            order.status = "pending"
            return OrderResult(
                broker_order_id=order.order_id,
                status="pending",
                raw={"paper_mode": True, "reason": "awaiting price data"},
            )
        
        can_fill = False
        
        # Limit order: buy at or below limit, sell at or above limit
        if order.limit_price:
            if order.side == "buy" and price <= order.limit_price:
                can_fill = True
            elif order.side == "sell" and price >= order.limit_price:
                can_fill = True
        
        # Stop order: triggered when price hits stop
        if order.stop_price:
            if order.side == "buy" and price >= order.stop_price:
                can_fill = True
            elif order.side == "sell" and price <= order.stop_price:
                can_fill = True
        
        if can_fill:
            return await self._fill_order(order)
        
        return OrderResult(
            broker_order_id=order.order_id,
            status="pending",
            raw={"paper_mode": True, "awaiting_fill": True},
        )

    def _update_position(self, order: PaperOrder) -> None:
        """Update positions after a fill."""
        pos = self._positions.get(order.symbol)
        
        if order.side == "buy":
            if pos:
                # Average in
                total_cost = (pos.avg_cost * pos.quantity) + (order.fill_price * order.filled_quantity)
                pos.quantity += order.filled_quantity
                pos.avg_cost = total_cost / pos.quantity if pos.quantity > 0 else Decimal("0")
            else:
                # New position
                self._positions[order.symbol] = PaperPosition(
                    symbol=order.symbol,
                    quantity=order.filled_quantity,
                    avg_cost=order.fill_price,
                )
        else:  # sell
            if pos:
                proceeds = order.fill_price * order.filled_quantity
                self._cash += proceeds
                pos.quantity -= order.filled_quantity
                if pos.quantity <= 0:
                    del self._positions[order.symbol]

    async def cancel_order(self, broker_order_id: str) -> OrderResult:
        """Cancel a pending paper order."""
        order = self._orders.get(broker_order_id)
        if not order:
            return OrderResult(error="Order not found")
        
        if order.status == "filled":
            return OrderResult(error="Cannot cancel filled order")
        
        order.status = "cancelled"
        return OrderResult(
            broker_order_id=broker_order_id,
            status="cancelled",
        )

    async def get_order_status(self, broker_order_id: str) -> OrderResult:
        """Get status of a paper order."""
        order = self._orders.get(broker_order_id)
        if not order:
            return OrderResult(error="Order not found")
        
        # For pending limit/stop orders, check if now fillable
        if order.status == "pending":
            result = await self._check_and_fill(order)
            return result
        
        return OrderResult(
            broker_order_id=broker_order_id,
            status=order.status,
            filled_quantity=float(order.filled_quantity),
            avg_fill_price=float(order.fill_price) if order.fill_price else None,
        )

    def get_positions(self) -> list[dict]:
        """Get all paper positions."""
        result = []
        for symbol, pos in self._positions.items():
            price = self._get_current_price(symbol) or pos.avg_cost
            market_value = price * pos.quantity
            unrealized_pnl = market_value - (pos.avg_cost * pos.quantity)
            
            result.append({
                "symbol": symbol,
                "quantity": float(pos.quantity),
                "avg_cost": float(pos.avg_cost),
                "market_value": float(market_value),
                "unrealized_pnl": float(unrealized_pnl),
            })
        return result

    def get_account_summary(self) -> dict:
        """Get paper account summary."""
        positions_value = sum(
            (self._get_current_price(p.symbol) or p.avg_cost) * p.quantity
            for p in self._positions.values()
        )
        total_equity = self._cash + positions_value
        
        return {
            "cash": float(self._cash),
            "positions_value": float(positions_value),
            "total_equity": float(total_equity),
            "starting_cash": float(self._starting_cash),
            "total_return_pct": float(
                ((total_equity - self._starting_cash) / self._starting_cash) * 100
            ) if self._starting_cash > 0 else 0.0,
            "position_count": len(self._positions),
        }

    def is_paper_trading(self) -> bool:
        """Always returns True for paper executor."""
        return True

    def reset(self) -> None:
        """Reset paper account to initial state."""
        self._cash = self._starting_cash
        self._positions.clear()
        self._orders.clear()
        self._order_counter = 0
        logger.info("Paper trading account reset")
