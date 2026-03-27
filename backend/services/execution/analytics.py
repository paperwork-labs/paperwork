"""Execution analytics service."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.execution import ExecutionMetrics


class ExecutionAnalyticsService:
    """Service for analyzing execution quality."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record_fill(
        self,
        order_id: int,
        user_id: int,
        symbol: str,
        broker: str,
        side: str,
        expected_price: Optional[Decimal],
        fill_price: Decimal,
        quantity_ordered: int,
        quantity_filled: int,
        submitted_at: Optional[datetime],
        filled_at: datetime,
    ) -> ExecutionMetrics:
        """Record execution metrics for a filled order."""
        side_norm = (side or "").lower()

        # Calculate slippage
        slippage_pct: Optional[float] = None
        slippage_dollars: Optional[Decimal] = None
        if expected_price is not None and expected_price > 0:
            slippage_pct = float((fill_price - expected_price) / expected_price * 100)
            slippage_dollars = (fill_price - expected_price) * quantity_filled
            # Negative slippage is good for buys, bad for sells
            if side_norm == "sell":
                slippage_pct = -slippage_pct
                slippage_dollars = -slippage_dollars

        # Calculate time to fill
        time_to_fill_ms: Optional[int] = None
        if submitted_at is not None and filled_at is not None:
            time_to_fill_ms = int((filled_at - submitted_at).total_seconds() * 1000)

        # Calculate fill rate
        fill_rate = quantity_filled / quantity_ordered if quantity_ordered > 0 else 0.0

        partial_fills: Optional[int] = None
        if quantity_ordered > 0 and 0 < quantity_filled < quantity_ordered:
            partial_fills = 1

        metrics = ExecutionMetrics(
            order_id=order_id,
            user_id=user_id,
            symbol=symbol,
            broker=broker,
            side=side_norm or side,
            expected_price=expected_price,
            fill_price=fill_price,
            slippage_pct=slippage_pct,
            slippage_dollars=slippage_dollars,
            submitted_at=submitted_at,
            filled_at=filled_at,
            time_to_fill_ms=time_to_fill_ms,
            fill_rate=fill_rate,
            partial_fills=partial_fills,
        )
        self.db.add(metrics)
        return metrics

    def get_broker_stats(
        self,
        user_id: int,
        days: int = 30,
    ) -> Dict[str, Dict[str, Any]]:
        """Get execution stats grouped by broker."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        results = (
            self.db.query(
                ExecutionMetrics.broker,
                func.count(ExecutionMetrics.id).label("total_orders"),
                func.avg(ExecutionMetrics.slippage_pct).label("avg_slippage_pct"),
                func.avg(ExecutionMetrics.time_to_fill_ms).label("avg_time_to_fill_ms"),
                func.avg(ExecutionMetrics.fill_rate).label("avg_fill_rate"),
            )
            .filter(
                ExecutionMetrics.user_id == user_id,
                ExecutionMetrics.created_at >= cutoff,
            )
            .group_by(ExecutionMetrics.broker)
            .all()
        )

        return {
            r.broker: {
                "total_orders": r.total_orders,
                "avg_slippage_pct": round(r.avg_slippage_pct or 0, 4),
                "avg_time_to_fill_ms": int(r.avg_time_to_fill_ms or 0),
                "avg_fill_rate": round(r.avg_fill_rate or 0, 4),
            }
            for r in results
        }

    def get_symbol_stats(
        self,
        user_id: int,
        days: int = 30,
    ) -> Dict[str, Dict[str, Any]]:
        """Get execution stats grouped by symbol."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        results = (
            self.db.query(
                ExecutionMetrics.symbol,
                func.count(ExecutionMetrics.id).label("total_orders"),
                func.avg(ExecutionMetrics.slippage_pct).label("avg_slippage_pct"),
            )
            .filter(
                ExecutionMetrics.user_id == user_id,
                ExecutionMetrics.created_at >= cutoff,
            )
            .group_by(ExecutionMetrics.symbol)
            .order_by(func.count(ExecutionMetrics.id).desc())
            .limit(20)
            .all()
        )

        return {
            r.symbol: {
                "total_orders": r.total_orders,
                "avg_slippage_pct": round(r.avg_slippage_pct or 0, 4),
            }
            for r in results
        }


def calculate_order_slippage(
    decision_price: float,
    fill_price: float,
    quantity: float,
    side: str,
) -> Dict[str, float]:
    """Calculate slippage metrics for a filled order.

    Args:
        decision_price: Price when order was signaled/created
        fill_price: Average fill price
        quantity: Number of shares
        side: 'buy' or 'sell'

    Returns:
        Dict with slippage_pct, slippage_dollars, favorable (bool)
    """
    if decision_price <= 0:
        return {"slippage_pct": 0.0, "slippage_dollars": 0.0, "favorable": True}

    # For buys: slippage is positive if we paid more than decision price
    # For sells: slippage is positive if we received less than decision price
    if side.lower() == "buy":
        slippage_pct = (fill_price - decision_price) / decision_price * 100
    else:
        slippage_pct = (decision_price - fill_price) / decision_price * 100

    slippage_dollars = abs(fill_price - decision_price) * abs(quantity)
    favorable = slippage_pct < 0

    return {
        "slippage_pct": round(slippage_pct, 4),
        "slippage_dollars": round(slippage_dollars, 2),
        "favorable": favorable,
    }


def update_order_analytics(
    db: Session,
    order_id: int,
    fill_price: float,
    filled_at: datetime,
) -> Dict:
    """Update execution analytics for a filled order.

    Call this when an order is filled to calculate and persist
    execution quality metrics.

    Args:
        db: SQLAlchemy session
        order_id: The order ID to update
        fill_price: Average fill price
        filled_at: Timestamp of fill

    Returns:
        Dict with calculated analytics
    """
    from backend.models.order import Order

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"error": "order_not_found"}

    analytics: Dict = {}

    # Calculate slippage if we have decision price
    if order.decision_price and order.decision_price > 0:
        slip = calculate_order_slippage(
            decision_price=order.decision_price,
            fill_price=fill_price,
            quantity=order.quantity,
            side=order.side,
        )
        order.slippage_pct = slip["slippage_pct"]
        order.slippage_dollars = slip["slippage_dollars"]
        analytics.update(slip)

    # Calculate fill latency
    if order.submitted_at and filled_at:
        latency = (filled_at - order.submitted_at).total_seconds() * 1000
        order.fill_latency_ms = int(latency)
        analytics["fill_latency_ms"] = int(latency)

    return analytics


def get_execution_summary(
    db: Session,
    lookback_days: int = 30,
    strategy_id: Optional[int] = None,
) -> Dict:
    """Get summary statistics of execution quality.

    Args:
        db: SQLAlchemy session
        lookback_days: Days of history to analyze
        strategy_id: Optional filter by strategy

    Returns:
        Dict with execution quality metrics
    """
    from backend.models.order import Order

    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    query = db.query(Order).filter(
        Order.status == "filled",
        Order.filled_at >= cutoff,
        Order.slippage_pct.isnot(None),
    )

    if strategy_id:
        query = query.filter(Order.strategy_id == strategy_id)

    orders = query.all()

    if not orders:
        return {
            "total_orders": 0,
            "avg_slippage_pct": 0.0,
            "total_slippage_dollars": 0.0,
            "avg_fill_latency_ms": 0,
            "favorable_fills_pct": 0.0,
        }

    slippages = [o.slippage_pct for o in orders if o.slippage_pct is not None]
    slippage_dollars = [o.slippage_dollars for o in orders if o.slippage_dollars is not None]
    latencies = [o.fill_latency_ms for o in orders if o.fill_latency_ms is not None]
    favorable = sum(1 for o in orders if o.slippage_pct is not None and o.slippage_pct < 0)

    return {
        "total_orders": len(orders),
        "avg_slippage_pct": round(sum(slippages) / len(slippages), 4) if slippages else 0.0,
        "total_slippage_dollars": round(sum(slippage_dollars), 2) if slippage_dollars else 0.0,
        "avg_fill_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
        "favorable_fills_pct": round(favorable / len(orders) * 100, 1) if orders else 0.0,
        "lookback_days": lookback_days,
    }


def get_slippage_by_symbol(
    db: Session,
    lookback_days: int = 30,
) -> List[Dict]:
    """Get slippage breakdown by symbol.

    Useful for identifying symbols with consistently poor execution.
    """
    from backend.models.order import Order

    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    results = (
        db.query(
            Order.symbol,
            func.count(Order.id).label("order_count"),
            func.avg(Order.slippage_pct).label("avg_slippage_pct"),
            func.sum(Order.slippage_dollars).label("total_slippage_dollars"),
        )
        .filter(
            Order.status == "filled",
            Order.filled_at >= cutoff,
            Order.slippage_pct.isnot(None),
        )
        .group_by(Order.symbol)
        .order_by(func.sum(Order.slippage_dollars).desc())
        .limit(20)
        .all()
    )

    return [
        {
            "symbol": r.symbol,
            "order_count": r.order_count,
            "avg_slippage_pct": round(float(r.avg_slippage_pct or 0), 4),
            "total_slippage_dollars": round(float(r.total_slippage_dollars or 0), 2),
        }
        for r in results
    ]
