"""
Coverage Routes
===============

Endpoints for data coverage health monitoring.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.market_data import PriceData
from backend.services.market.market_data_service import MarketDataService
from backend.api.dependencies import get_market_data_viewer
from ._shared import visibility_scope, coverage_education, coverage_actions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coverage", tags=["coverage"])


@router.get("")
async def get_coverage(
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
    fill_trading_days_window: int | None = Query(None, ge=10, le=300),
    fill_lookback_days: int | None = Query(None, ge=30, le=4000),
) -> Dict[str, Any]:
    """Return coverage summary across intervals with last bar timestamps and freshness buckets."""
    try:
        svc = MarketDataService()
        snapshot = svc.coverage.build_coverage_response(
            db,
            fill_trading_days_window=fill_trading_days_window,
            fill_lookback_days=fill_lookback_days,
        )
        meta = snapshot.setdefault("meta", {})
        meta["visibility"] = visibility_scope()
        from backend.api.dependencies import market_exposed_to_all
        meta["exposed_to_all"] = market_exposed_to_all()
        meta["education"] = coverage_education()
        meta["actions"] = coverage_actions(meta.get("backfill_5m_enabled"))
        return snapshot
    except Exception as e:
        logger.error(f"coverage error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}")
async def get_symbol_coverage(
    symbol: str,
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
) -> Dict[str, Any]:
    """Return last bar timestamps for daily and 5m for a symbol."""
    try:
        sym = symbol.upper()
        last_daily = (
            db.query(PriceData.date)
            .filter(PriceData.symbol == sym, PriceData.interval == "1d")
            .order_by(PriceData.date.desc())
            .limit(1)
            .scalar()
        )
        last_m5 = (
            db.query(PriceData.date)
            .filter(PriceData.symbol == sym, PriceData.interval == "5m")
            .order_by(PriceData.date.desc())
            .limit(1)
            .scalar()
        )
        return {
            "symbol": sym,
            "last_daily": last_daily.isoformat() if last_daily else None,
            "last_5m": last_m5.isoformat() if last_m5 else None,
        }
    except Exception as e:
        logger.error(f"symbol coverage error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
