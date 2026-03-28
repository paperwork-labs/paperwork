"""Execution quality and slippage analytics routes."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import get_db, get_portfolio_user
from backend.models.user import User
from backend.services.execution.slippage_tracker import (
    SlippageTracker,
    get_slippage_stats_dict,
)

router = APIRouter(prefix="/execution", tags=["execution"])


@router.get("/slippage-stats")
async def get_slippage_stats(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    broker: Optional[str] = Query(None, description="Filter by broker type"),
    days: int = Query(30, ge=1, le=365, description="Lookback period in days"),
    user: User = Depends(get_portfolio_user),
    db: Session = Depends(get_db),
):
    """Get aggregated slippage statistics for filled orders.
    
    Returns average, median, min, max slippage percentages and dollars,
    broken down by side, broker, and hour of day.
    """
    tracker = SlippageTracker(db)
    stats = tracker.get_slippage_stats(
        user_id=user.id,
        symbol=symbol,
        broker_type=broker,
        days=days,
    )
    return get_slippage_stats_dict(stats)


@router.get("/worst-slippage")
async def get_worst_slippage_orders(
    limit: int = Query(10, ge=1, le=50, description="Number of orders to return"),
    days: int = Query(30, ge=1, le=365, description="Lookback period in days"),
    user: User = Depends(get_portfolio_user),
    db: Session = Depends(get_db),
):
    """Get orders with the worst slippage for analysis."""
    tracker = SlippageTracker(db)
    return tracker.get_worst_slippage_orders(
        user_id=user.id,
        limit=limit,
        days=days,
    )


@router.get("/slippage-by-symbol")
async def get_slippage_by_symbol(
    days: int = Query(30, ge=1, le=365, description="Lookback period in days"),
    user: User = Depends(get_portfolio_user),
    db: Session = Depends(get_db),
):
    """Get slippage breakdown by symbol."""
    tracker = SlippageTracker(db)
    return tracker.get_slippage_by_symbol(
        user_id=user.id,
        days=days,
    )
