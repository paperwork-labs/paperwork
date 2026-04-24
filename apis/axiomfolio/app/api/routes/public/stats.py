"""
Public aggregate stats for marketing / transparency (no auth).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.rate_limit import limiter
from app.constants.public_stats import BROKERS_SUPPORTED
from app.database import get_db
from app.models.position import Position, PositionStatus
from app.services.silver.market.market_data_service import infra

logger = logging.getLogger(__name__)

router = APIRouter(tags=["public"])

_CACHE_KEY = "public:stats:response:v1"
_CACHE_TTL_S = 300
# Optional Redis counter for chart renders (wired from chart mount events in a follow-up).
_CHARTS_COUNTER_KEY = "public:stats:charts_rendered_24h"


class PublicStatsResponse(BaseModel):
    portfolios_tracked: int = Field(..., ge=0)
    charts_rendered_24h: int = Field(..., ge=0)
    brokers_supported: int = Field(..., ge=0)


def _read_charts_counter() -> int:
    try:
        raw = infra.redis_client.get(_CHARTS_COUNTER_KEY)
        if raw is None:
            return 0
        if isinstance(raw, (bytes, bytearray)):
            return int(raw.decode("utf-8"))
        return int(str(raw))
    except Exception as e:
        logger.warning("public stats: charts counter read failed: %s", e)
        return 0


def _try_cache_get() -> Dict[str, Any] | None:
    try:
        cached = infra.redis_client.get(_CACHE_KEY)
        if not cached:
            return None
        if isinstance(cached, (bytes, bytearray)):
            cached = cached.decode("utf-8")
        data = json.loads(cached)
        if not isinstance(data, dict):
            return None
        return data
    except Exception as e:
        logger.warning("public stats: cache read failed: %s", e)
        return None


def _try_cache_set(payload: Dict[str, Any]) -> None:
    try:
        infra.redis_client.setex(_CACHE_KEY, _CACHE_TTL_S, json.dumps(payload))
    except Exception as e:
        logger.warning("public stats: cache write failed: %s", e)


def _compute_payload(db: Session) -> Dict[str, Any]:
    row = db.scalar(
        select(func.count(func.distinct(Position.user_id))).where(Position.status == PositionStatus.OPEN)
    )
    portfolios_tracked = int(row or 0)
    charts_rendered_24h = _read_charts_counter()
    return {
        "portfolios_tracked": portfolios_tracked,
        "charts_rendered_24h": charts_rendered_24h,
        "brokers_supported": int(BROKERS_SUPPORTED),
    }


@router.get("/stats", response_model=PublicStatsResponse)
@limiter.limit("60/minute")
def get_public_stats(request: Request, db: Session = Depends(get_db)) -> PublicStatsResponse:
    """Aggregates safe to publish without authentication. Cached five minutes in Redis."""
    cached = _try_cache_get()
    if cached is not None:
        try:
            return PublicStatsResponse.model_validate(cached)
        except Exception as e:
            logger.warning("public stats: cache validate failed, recomputing: %s", e)

    payload = _compute_payload(db)
    _try_cache_set(payload)
    return PublicStatsResponse.model_validate(payload)
