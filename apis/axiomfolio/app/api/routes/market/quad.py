"""
Market Quad Routes
==================

Endpoints for Hedgeye GIP Quad Model state and history.
"""

from datetime import date, datetime, timedelta
from typing import Dict, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.dependencies import get_market_data_viewer
from app.models.market_data import MarketQuad
from app.models.user import User

router = APIRouter(prefix="/quad", tags=["quad"])


@router.get("/current")
async def get_current_quad(
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
) -> Dict[str, Any]:
    """Get the most recent Quad state."""
    stmt = select(MarketQuad).order_by(MarketQuad.as_of_date.desc()).limit(1)
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        return {"quad": None, "message": "No quad data computed yet"}
    return {
        "quad": {
            "as_of_date": row.as_of_date.isoformat() if row.as_of_date else None,
            "quarterly_quad": row.quarterly_quad,
            "monthly_quad": row.monthly_quad,
            "operative_quad": row.operative_quad,
            "quarterly_depth": row.quarterly_depth,
            "monthly_depth": row.monthly_depth,
            "divergence_flag": row.divergence_flag,
            "divergence_months": row.divergence_months,
            "source": row.source,
        }
    }


@router.get("/history")
async def get_quad_history(
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
) -> Dict[str, Any]:
    """Get quad history for the last N days."""
    cutoff_date = date.today() - timedelta(days=days)
    cutoff = datetime.combine(cutoff_date, datetime.min.time())
    stmt = (
        select(MarketQuad)
        .where(MarketQuad.as_of_date >= cutoff)
        .order_by(MarketQuad.as_of_date.asc())
    )
    rows = db.execute(stmt).scalars().all()
    return {
        "history": [
            {
                "as_of_date": r.as_of_date.isoformat() if r.as_of_date else None,
                "quarterly_quad": r.quarterly_quad,
                "monthly_quad": r.monthly_quad,
                "operative_quad": r.operative_quad,
                "quarterly_depth": r.quarterly_depth,
                "monthly_depth": r.monthly_depth,
                "divergence_flag": r.divergence_flag,
                "divergence_months": r.divergence_months,
            }
            for r in rows
        ]
    }
