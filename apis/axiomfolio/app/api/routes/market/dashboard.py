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
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.rate_limit import limiter
from app.database import get_db
from app.models.user import User
from app.services.silver.market.market_data_service import infra
from app.api.dependencies import get_market_data_viewer
from app.api.schemas.market import MarketDashboardResponse
from app.config import settings

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
    """Reader-friendly market dashboard summary for momentum workflows.

    Reads exclusively from Redis cache. On cache miss, triggers a Celery
    worker task to build the dashboard and returns HTTP 202 so the web
    process never runs the heavy build_dashboard() query.
    """
    if universe not in ("all", "etf", "holdings"):
        universe = "all"
    cache_key = f"dashboard:{universe}"

    try:
        cached = infra.redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    try:
        from app.tasks.market.maintenance import warm_dashboard_cache
        warm_dashboard_cache.delay(universe)
        logger.info("Dashboard cache miss (universe=%s) -- triggered async warm", universe)
    except Exception as e:
        logger.warning("Failed to trigger dashboard warm task: %s", e)

    return JSONResponse(
        status_code=202,
        content={
            "status": "warming",
            "message": "Dashboard is being computed. Refresh in ~30 seconds.",
        },
    )


@router.get("/volatility-dashboard")
async def get_volatility_dashboard(
    _viewer: User = Depends(get_market_data_viewer),
) -> Dict[str, Any]:
    """VIX/VVIX/VIX3M volatility regime dashboard."""
    from app.services.silver.market.volatility_service import VolatilityService

    vol_svc = VolatilityService(
        redis_client=infra.redis_client,
        fmp_api_key=getattr(settings, "FMP_API_KEY", None),
    )
    return await vol_svc.get_dashboard()
