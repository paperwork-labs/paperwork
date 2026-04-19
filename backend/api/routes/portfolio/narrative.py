"""Daily portfolio narrative API."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import get_portfolio_user
from backend.database import get_db
from backend.models.narrative import PortfolioNarrative
from backend.models.user import User

router = APIRouter()


def _serialize(row: PortfolioNarrative) -> Dict[str, Any]:
    created = row.created_at
    if created.tzinfo is None:
        created_iso = created.isoformat() + "Z"
    else:
        created_iso = created.isoformat()
    return {
        "date": row.narrative_date.isoformat(),
        "text": row.text,
        "provider": row.provider,
        "model": row.model,
        "is_fallback": row.is_fallback,
        "generated_at": created_iso,
    }


@router.get("/narrative/latest")
async def get_latest_narrative(
    db: Session = Depends(get_db),
    user: User = Depends(get_portfolio_user),
):
    row = (
        db.query(PortfolioNarrative)
        .filter(PortfolioNarrative.user_id == user.id)
        .order_by(PortfolioNarrative.created_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No narrative yet")
    return _serialize(row)


@router.get("/narrative")
async def get_narrative_by_date(
    narrative_date: date = Query(..., alias="date", description="Calendar date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_portfolio_user),
):
    row = (
        db.query(PortfolioNarrative)
        .filter(
            PortfolioNarrative.user_id == user.id,
            PortfolioNarrative.narrative_date == narrative_date,
        )
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Narrative not found for date")
    return _serialize(row)
