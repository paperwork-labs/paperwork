"""
Market Regime Routes
====================

Endpoints for market regime state and history.
"""

from datetime import date, datetime, timedelta
from typing import Dict, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.api.dependencies import get_market_data_viewer
from app.models.market_data import MarketRegime
from app.models.user import User

router = APIRouter(prefix="/regime", tags=["regime"])


@router.get("/current")
async def get_current_regime(
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
) -> Dict[str, Any]:
    """Get the most recent market regime state."""
    from app.services.market.regime_engine import get_current_regime as _get_regime

    regime = _get_regime(db)
    if regime is None:
        return {"regime": None, "message": "No regime data computed yet"}
    return {
        "regime": {
            "as_of_date": regime.as_of_date.isoformat() if regime.as_of_date else None,
            "regime_state": regime.regime_state,
            "composite_score": regime.composite_score,
            "vix_spot": regime.vix_spot,
            "vix3m_vix_ratio": regime.vix3m_vix_ratio,
            "vvix_vix_ratio": regime.vvix_vix_ratio,
            "nh_nl": regime.nh_nl,
            "pct_above_200d": regime.pct_above_200d,
            "pct_above_50d": regime.pct_above_50d,
            "score_vix": regime.score_vix,
            "score_vix3m_vix": regime.score_vix3m_vix,
            "score_vvix_vix": regime.score_vvix_vix,
            "score_nh_nl": regime.score_nh_nl,
            "score_above_200d": regime.score_above_200d,
            "score_above_50d": regime.score_above_50d,
            "weights_used": regime.weights_used,
            "cash_floor_pct": regime.cash_floor_pct,
            "max_equity_exposure_pct": regime.max_equity_exposure_pct,
            "regime_multiplier": regime.regime_multiplier,
        }
    }


@router.get("/history")
async def get_regime_history(
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
) -> Dict[str, Any]:
    """Get regime history for the last N days."""
    # MarketRegime.as_of_date is DateTime (see models/market_data.py); rows are
    # written at midnight via persist_regime(). Use a date-based window and the
    # same midnight representation so we compare like-for-like and keep exactly
    # N calendar days (utcnow()-timedelta can omit the oldest calendar day).
    cutoff_date = date.today() - timedelta(days=days)
    cutoff = datetime.combine(cutoff_date, datetime.min.time())
    stmt = (
        select(MarketRegime)
        .where(MarketRegime.as_of_date >= cutoff)
        .order_by(MarketRegime.as_of_date.asc())
    )
    rows = db.execute(stmt).scalars().all()
    return {
        "history": [
            {
                "as_of_date": r.as_of_date.isoformat() if r.as_of_date else None,
                "regime_state": r.regime_state,
                "composite_score": r.composite_score,
            }
            for r in rows
        ]
    }
