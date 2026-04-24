"""
Sentiment composite (VIX, AAII, Fear & Greed, Regime) for the Sentiment banner.

AAII and Fear & Greed are stubbed until a free feed is wired; see ``_fetch_aaii`` / ``_fetch_fear_greed``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_market_data_viewer
from app.api.middleware.response_cache import redis_response_cache
from app.database import get_db
from app.models.market_data import MarketRegime, MarketSnapshot
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


def _fetch_aaii() -> dict[str, float] | None:
    # TODO(c6-data): wire real AAII/F&G feed
    return None


def _fetch_fear_greed() -> dict[str, Any] | None:
    # TODO(c6-data): wire real AAII/F&G feed
    return None


def _vix_from_snapshot(db: Session) -> float | None:
    """Latest ^VIX spot from market_snapshot (technical_snapshot)."""
    stmt = (
        select(MarketSnapshot.current_price, MarketSnapshot.as_of_timestamp)
        .where(
            MarketSnapshot.symbol == "^VIX",
            MarketSnapshot.analysis_type == "technical_snapshot",
        )
        .order_by(
            MarketSnapshot.as_of_timestamp.desc().nulls_last(),
            MarketSnapshot.id.desc(),
        )
        .limit(1)
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    price = row[0]
    if price is None:
        return None
    return float(price)


def _latest_regime_row(db: Session) -> MarketRegime | None:
    stmt = select(MarketRegime).order_by(MarketRegime.as_of_date.desc()).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def _iso_asof(
    regime: MarketRegime | None,
) -> str:
    now = datetime.now(UTC)
    candidates: list[datetime] = [now]
    if regime and regime.as_of_date is not None:
        ad = regime.as_of_date
        if ad.tzinfo is None:
            ad = ad.replace(tzinfo=UTC)
        else:
            ad = ad.astimezone(UTC)
        candidates.append(ad)
    latest = max(candidates)
    return latest.isoformat()


def build_sentiment_composite_payload(db: Session) -> dict[str, Any]:
    """Assemble the composite JSON body (used by the route and tests)."""
    regime = _latest_regime_row(db)
    vix: float | None = None
    if regime and regime.vix_spot is not None:
        vix = float(regime.vix_spot)
    if vix is None:
        vix = _vix_from_snapshot(db)

    regime_out: dict[str, Any] | None = None
    if regime is not None and regime.regime_state:
        comp = regime.composite_score
        regime_out = {
            "state": str(regime.regime_state),
            "score": float(comp) if comp is not None else None,
        }

    aaii = _fetch_aaii()
    fear_greed = _fetch_fear_greed()

    return {
        "vix": vix,
        "aaii": aaii,
        "fear_greed": fear_greed,
        "regime": regime_out,
        "asof": _iso_asof(regime),
    }


@router.get("/composite")
@redis_response_cache(ttl_seconds=300)
async def get_sentiment_composite(
    request: Request,
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
) -> dict[str, Any]:
    try:
        return build_sentiment_composite_payload(db)
    except Exception as e:
        logger.warning("sentiment composite failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build sentiment composite",
        ) from e
