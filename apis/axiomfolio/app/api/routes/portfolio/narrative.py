"""Daily portfolio narrative API."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import SessionLocal, get_db
from app.models.narrative import PortfolioNarrative
from app.models.user import User
from app.services.market.market_data_service import infra

logger = logging.getLogger(__name__)

router = APIRouter()

NARRATIVE_TIMEOUT_COUNTER_KEY = "narrative_timeout_total"
_FETCH_LATEST_TIMEOUT_S = 1.0


def _incr_narrative_timeout_counter() -> None:
    try:
        infra.redis_client.incr(NARRATIVE_TIMEOUT_COUNTER_KEY)
    except Exception as e:
        logger.warning("narrative: timeout counter redis incr failed: %s", e)


def _serialize(row: PortfolioNarrative) -> dict[str, Any]:
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


def _fetch_latest_row_in_thread(user_id: int) -> PortfolioNarrative | None:
    """Load latest narrative in a dedicated session (for asyncio.to_thread; sessions are not thread-safe)."""
    db = SessionLocal()
    try:
        return (
            db.query(PortfolioNarrative)
            .filter(PortfolioNarrative.user_id == user_id)
            .order_by(PortfolioNarrative.created_at.desc())
            .first()
        )
    finally:
        db.close()


def _pending_payload() -> dict[str, Any]:
    return {
        "narrative": None,
        "status": "pending",
        "generated_at": None,
    }


@router.get("/narrative/latest")
async def get_latest_narrative(
    user: User = Depends(get_current_user),
):
    try:
        row = await asyncio.wait_for(
            asyncio.to_thread(_fetch_latest_row_in_thread, user.id),
            timeout=_FETCH_LATEST_TIMEOUT_S,
        )
    except TimeoutError:
        _incr_narrative_timeout_counter()
        logger.warning(
            "narrative latest fetch timed out user_id=%s timeout_s=%s",
            user.id,
            _FETCH_LATEST_TIMEOUT_S,
        )
        return _pending_payload()
    except Exception as e:
        logger.warning("narrative latest fetch failed user_id=%s: %s", user.id, e)
        return _pending_payload()

    if row is None:
        return _pending_payload()
    return _serialize(row)


@router.get("/narrative")
async def get_narrative_by_date(
    narrative_date: date = Query(..., alias="date", description="Calendar date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
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
