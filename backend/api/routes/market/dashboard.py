"""
Market Dashboard Routes
=======================

Dashboard endpoints for market overview and volatility.
Endpoints are synchronous to keep SQLAlchemy Session on the calling thread.
"""

import json
import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.api.rate_limit import limiter
from backend.database import get_db
from backend.models.user import User
from backend.services.market.market_data_service import infra
from backend.services.market.market_dashboard_service import MarketDashboardService
from backend.api.dependencies import get_market_data_viewer
from backend.api.schemas.market import MarketDashboardResponse
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


@router.get(
    "/dashboard",
    response_model=MarketDashboardResponse,
    response_model_exclude_unset=True,
)
@limiter.limit("30/minute")
def get_market_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    viewer: User = Depends(get_market_data_viewer),
    universe: str = "all",
) -> Dict[str, Any]:
    """Reader-friendly market dashboard summary for momentum workflows."""
    if universe not in ("all", "etf", "holdings"):
        universe = "all"
    if universe in ("holdings",) and viewer:
        cache_key = f"dashboard:{universe}:{viewer.id}"
    else:
        cache_key = f"dashboard:{universe}"
    try:
        try:
            cached = infra.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            cached = None
        dashboard = MarketDashboardService()
        result = dashboard.build_dashboard(db, universe=universe)
        try:
            serialized = json.dumps(result, default=str)
            ttl = 300 if universe == "holdings" else 3600
            infra.redis_client.setex(cache_key, ttl, serialized)
        except Exception as e:
            logger.warning("Failed to cache dashboard result: %s", e)
        return result
    except Exception as e:
        logger.exception("get_market_dashboard failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/volatility-dashboard")
async def get_volatility_dashboard(
    _viewer: User = Depends(get_market_data_viewer),
) -> Dict[str, Any]:
    """VIX/VVIX/VIX3M volatility regime dashboard."""
    from backend.services.market.volatility_service import VolatilityService

    vol_svc = VolatilityService(
        redis_client=infra.redis_client,
        fmp_api_key=getattr(settings, "FMP_API_KEY", None),
    )
    return await vol_svc.get_dashboard()
