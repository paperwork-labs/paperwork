"""Slippage tracking and analytics service.

Aggregates execution quality metrics across orders for analysis and ML training.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models.order import Order, OrderStatus

logger = logging.getLogger(__name__)


@dataclass
class SlippageStats:
    """Aggregated slippage statistics."""
    total_orders: int
    orders_with_slippage: int
    avg_slippage_pct: float
    median_slippage_pct: float
    max_slippage_pct: float
    min_slippage_pct: float
    total_slippage_dollars: float
    avg_fill_latency_ms: float
    avg_slippage_by_side: Dict[str, float]
    avg_slippage_by_broker: Dict[str, float]
    avg_slippage_by_hour: Dict[int, float]


class SlippageTracker:
    """Tracks and analyzes execution slippage across orders."""

    def __init__(self, db: Session):
        self.db = db

    def get_slippage_stats(
        self,
        user_id: Optional[int] = None,
        symbol: Optional[str] = None,
        broker_type: Optional[str] = None,
        days: int = 30,
    ) -> SlippageStats:
        """Get aggregated slippage statistics for filled orders.
        
        Args:
            user_id: Filter by user (optional, for multi-tenant)
            symbol: Filter by symbol (optional)
            broker_type: Filter by broker (optional)
            days: Lookback period in days
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = self.db.query(Order).filter(
            Order.status == OrderStatus.FILLED.value,
            Order.filled_at >= cutoff,
            Order.slippage_pct.isnot(None),
        )
        
        if user_id:
            query = query.filter(Order.user_id == user_id)
        if symbol:
            query = query.filter(Order.symbol == symbol.upper())
        if broker_type:
            query = query.filter(Order.broker_type == broker_type)
        
        orders = query.all()
        
        if not orders:
            return SlippageStats(
                total_orders=0,
                orders_with_slippage=0,
                avg_slippage_pct=0.0,
                median_slippage_pct=0.0,
                max_slippage_pct=0.0,
                min_slippage_pct=0.0,
                total_slippage_dollars=0.0,
                avg_fill_latency_ms=0.0,
                avg_slippage_by_side={},
                avg_slippage_by_broker={},
                avg_slippage_by_hour={},
            )
        
        slippages = [float(o.slippage_pct) for o in orders if o.slippage_pct is not None]
        latencies = [o.fill_latency_ms for o in orders if o.fill_latency_ms is not None]
        dollars = [float(o.slippage_dollars) for o in orders if o.slippage_dollars is not None]
        
        # Calculate by-side averages
        by_side: Dict[str, List[float]] = {"buy": [], "sell": []}
        for o in orders:
            if o.slippage_pct is not None and o.side in by_side:
                by_side[o.side].append(float(o.slippage_pct))
        avg_by_side = {
            side: sum(vals) / len(vals) if vals else 0.0
            for side, vals in by_side.items()
        }
        
        # Calculate by-broker averages
        by_broker: Dict[str, List[float]] = {}
        for o in orders:
            if o.slippage_pct is not None and o.broker_type:
                by_broker.setdefault(o.broker_type, []).append(float(o.slippage_pct))
        avg_by_broker = {
            broker: sum(vals) / len(vals) if vals else 0.0
            for broker, vals in by_broker.items()
        }
        
        # Calculate by-hour averages (hour of day UTC)
        by_hour: Dict[int, List[float]] = {}
        for o in orders:
            if o.slippage_pct is not None and o.submitted_at:
                hour = o.submitted_at.hour
                by_hour.setdefault(hour, []).append(float(o.slippage_pct))
        avg_by_hour = {
            hour: sum(vals) / len(vals) if vals else 0.0
            for hour, vals in by_hour.items()
        }
        
        sorted_slippages = sorted(slippages)
        median_idx = len(sorted_slippages) // 2
        median = (
            sorted_slippages[median_idx]
            if len(sorted_slippages) % 2 == 1
            else (sorted_slippages[median_idx - 1] + sorted_slippages[median_idx]) / 2
        ) if sorted_slippages else 0.0
        
        return SlippageStats(
            total_orders=len(orders),
            orders_with_slippage=len(slippages),
            avg_slippage_pct=sum(slippages) / len(slippages) if slippages else 0.0,
            median_slippage_pct=median,
            max_slippage_pct=max(slippages) if slippages else 0.0,
            min_slippage_pct=min(slippages) if slippages else 0.0,
            total_slippage_dollars=sum(dollars) if dollars else 0.0,
            avg_fill_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
            avg_slippage_by_side=avg_by_side,
            avg_slippage_by_broker=avg_by_broker,
            avg_slippage_by_hour=avg_by_hour,
        )

    def get_worst_slippage_orders(
        self,
        user_id: Optional[int] = None,
        limit: int = 10,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get orders with the worst slippage for analysis."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = self.db.query(Order).filter(
            Order.status == OrderStatus.FILLED.value,
            Order.filled_at >= cutoff,
            Order.slippage_pct.isnot(None),
        )
        
        if user_id:
            query = query.filter(Order.user_id == user_id)
        
        orders = query.order_by(Order.slippage_pct.desc()).limit(limit).all()
        
        return [
            {
                "id": o.id,
                "symbol": o.symbol,
                "side": o.side,
                "quantity": o.quantity,
                "decision_price": o.decision_price,
                "filled_avg_price": o.filled_avg_price,
                "slippage_pct": o.slippage_pct,
                "slippage_dollars": o.slippage_dollars,
                "fill_latency_ms": o.fill_latency_ms,
                "broker_type": o.broker_type,
                "submitted_at": o.submitted_at.isoformat() if o.submitted_at else None,
                "filled_at": o.filled_at.isoformat() if o.filled_at else None,
            }
            for o in orders
        ]

    def get_slippage_by_symbol(
        self,
        user_id: Optional[int] = None,
        days: int = 30,
    ) -> Dict[str, Dict[str, Any]]:
        """Get slippage breakdown by symbol."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = self.db.query(Order).filter(
            Order.status == OrderStatus.FILLED.value,
            Order.filled_at >= cutoff,
            Order.slippage_pct.isnot(None),
        )
        
        if user_id:
            query = query.filter(Order.user_id == user_id)
        
        orders = query.all()
        
        by_symbol: Dict[str, List[Order]] = {}
        for o in orders:
            by_symbol.setdefault(o.symbol, []).append(o)
        
        result = {}
        for symbol, symbol_orders in by_symbol.items():
            slippages = [float(o.slippage_pct) for o in symbol_orders if o.slippage_pct is not None]
            dollars = [float(o.slippage_dollars) for o in symbol_orders if o.slippage_dollars is not None]
            
            result[symbol] = {
                "order_count": len(symbol_orders),
                "avg_slippage_pct": sum(slippages) / len(slippages) if slippages else 0.0,
                "total_slippage_dollars": sum(dollars) if dollars else 0.0,
            }
        
        return result


def get_slippage_stats_dict(stats: SlippageStats) -> Dict[str, Any]:
    """Convert SlippageStats to dict for API response."""
    return {
        "total_orders": stats.total_orders,
        "orders_with_slippage": stats.orders_with_slippage,
        "avg_slippage_pct": round(stats.avg_slippage_pct, 4),
        "median_slippage_pct": round(stats.median_slippage_pct, 4),
        "max_slippage_pct": round(stats.max_slippage_pct, 4),
        "min_slippage_pct": round(stats.min_slippage_pct, 4),
        "total_slippage_dollars": round(stats.total_slippage_dollars, 2),
        "avg_fill_latency_ms": round(stats.avg_fill_latency_ms, 1),
        "by_side": {k: round(v, 4) for k, v in stats.avg_slippage_by_side.items()},
        "by_broker": {k: round(v, 4) for k, v in stats.avg_slippage_by_broker.items()},
        "by_hour": {str(k): round(v, 4) for k, v in stats.avg_slippage_by_hour.items()},
    }
