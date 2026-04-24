"""Earnings Calendar Routes.

Query upcoming and recent earnings events from the earnings_calendar table.
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_market_data_viewer
from app.database import get_db
from app.models.user import User
from app.services.silver.market.earnings_calendar_service import earnings_calendar_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["earnings"])


@router.get("/earnings")
def get_earnings_calendar(
    db: Session = Depends(get_db),
    viewer: User = Depends(get_market_data_viewer),
    from_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    symbols: Optional[str] = Query(None, description="Comma-separated symbols"),
) -> Dict[str, Any]:
    """Return earnings calendar events, optionally filtered by date range and symbols."""
    try:
        fd = date.fromisoformat(from_date) if from_date else date.today() - timedelta(days=7)
        td = date.fromisoformat(to_date) if to_date else date.today() + timedelta(days=30)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {exc}")

    sym_list: Optional[List[str]] = None
    if symbols:
        sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    try:
        events = earnings_calendar_service.get_earnings_calendar(
            db=db,
            from_date=fd,
            to_date=td,
            symbols=sym_list,
        )
        return {
            "from_date": fd.isoformat(),
            "to_date": td.isoformat(),
            "count": len(events),
            "events": events,
        }
    except Exception as exc:
        logger.exception("get_earnings_calendar failed: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")
