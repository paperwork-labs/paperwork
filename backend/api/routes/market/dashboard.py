"""
Market Dashboard Routes
=======================

Dashboard endpoints for market overview and volatility.
Endpoints are synchronous to keep SQLAlchemy Session on the calling thread.
"""

import json
import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.services.market.market_data_service import market_data_service
from backend.services.market.market_dashboard_service import MarketDashboardService
from backend.api.dependencies import get_market_data_viewer
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def get_market_dashboard(
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
    universe: str = "all",
) -> Dict[str, Any]:
    """Reader-friendly market dashboard summary for momentum workflows."""
    if universe not in ("all", "etf", "holdings"):
        universe = "all"
    try:
        cache_key = f"dashboard:{universe}"
        try:
            cached = market_data_service.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            cached = None
        dashboard = MarketDashboardService()
        result = dashboard.build_dashboard(db, universe=universe)
        try:
            serialized = json.dumps(result, default=str)
            market_data_service.redis_client.setex(cache_key, 60, serialized)
        except Exception:
            logger.debug("Failed to cache dashboard result")
        return result
    except Exception as e:
        logger.error("market dashboard error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/volatility-dashboard")
async def get_volatility_dashboard(
    _viewer: User = Depends(get_market_data_viewer),
) -> Dict[str, Any]:
    """VIX/VVIX/VIX3M volatility regime dashboard."""
    from backend.services.market.volatility_service import VolatilityService

    vol_svc = VolatilityService(
        redis_client=market_data_service.redis_client,
        fmp_api_key=getattr(settings, "FMP_API_KEY", None),
    )
    return await vol_svc.get_dashboard()
