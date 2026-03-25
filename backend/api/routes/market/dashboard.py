"""
Market Dashboard Routes
=======================

Dashboard endpoints for market overview and volatility.
"""

import json
import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.services.market.market_data_service import MarketDataService
from backend.services.market.market_dashboard_service import MarketDashboardService
from backend.api.dependencies import get_market_data_viewer
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def get_market_dashboard(
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
) -> Dict[str, Any]:
    """Reader-friendly market dashboard summary for momentum workflows."""
    try:
        dashboard = MarketDashboardService()
        return dashboard.build_dashboard(db)
    except Exception as e:
        logger.error(f"market dashboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/volatility-dashboard")
async def get_volatility_dashboard(
    _viewer: User = Depends(get_market_data_viewer),
) -> Dict[str, Any]:
    """VIX/VVIX/VIX3M volatility regime dashboard."""
    import aiohttp

    cache_key = "volatility_dashboard"
    svc = MarketDataService()
    cached = svc.redis_client.get(cache_key) if svc.redis_client else None
    if cached:
        return json.loads(cached)

    result: Dict[str, Any] = {
        "vix": None, "vvix": None, "vix3m": None,
        "term_structure_ratio": None, "vol_of_vol_ratio": None,
        "regime": "unknown", "signal": "",
    }

    fmp_key = getattr(settings, "FMP_API_KEY", None)
    if not fmp_key:
        return result

    symbols = {"vix": "^VIX", "vvix": "^VVIX", "vix3m": "^VIX3M"}
    quotes: Dict[str, float] = {}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        for key, sym in symbols.items():
            try:
                url = f"https://financialmodelingprep.com/api/v3/quote/{sym}?apikey={fmp_key}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data and isinstance(data, list) and len(data) > 0:
                            quotes[key] = float(data[0].get("price", 0))
            except Exception as exc:
                logger.warning("Failed to fetch volatility quote for key=%s symbol=%s: %s", key, sym, exc)

    vix = quotes.get("vix")
    vvix = quotes.get("vvix")
    vix3m = quotes.get("vix3m")

    result["vix"] = vix
    result["vvix"] = vvix
    result["vix3m"] = vix3m

    if vix and vix > 0:
        if vix3m:
            result["term_structure_ratio"] = round(vix3m / vix, 3)
        if vvix:
            result["vol_of_vol_ratio"] = round(vvix / vix, 2)

    if vix is not None:
        if vix < 15:
            result["regime"] = "calm"
        elif vix < 20:
            result["regime"] = "elevated"
        elif vix < 30:
            result["regime"] = "fear"
        else:
            result["regime"] = "extreme"

    ts = result.get("term_structure_ratio")
    vov = result.get("vol_of_vol_ratio")
    if vov is not None and ts is not None:
        if vov < 3.5 and ts is not None and ts >= 1.0:
            result["signal"] = "Protection is cheap - good time to hedge"
        elif vov > 6.0:
            result["signal"] = "Market stressed - hedges expensive, consider reducing"
        elif vix is not None and vix < 15 and ts is not None and ts >= 1.0:
            result["signal"] = "Calm markets - no urgency"
        else:
            result["signal"] = ""

    if svc.redis_client:
        svc.redis_client.setex(cache_key, 300, json.dumps(result))

    return result
