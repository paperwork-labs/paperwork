from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from backend.api.dependencies import get_optional_user
from backend.database import SessionLocal
from backend.models.user import User
from backend.services.portfolio.activity_aggregator import activity_aggregator

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/activity")
async def get_activity(
    account_id: Optional[int] = Query(None),
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    symbol: Optional[str] = Query(None),
    category: Optional[str] = Query(None, description="TRADE, DIVIDEND, COMMISSION, etc."),
    side: Optional[str] = Query(None, description="BUY or SELL"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: User | None = Depends(get_optional_user),
    db = Depends(get_db),
) -> Dict[str, Any]:
    try:
        result = activity_aggregator.get_activity(
            db=db,
            account_id=account_id,
            start=start,
            end=end,
            symbol=symbol,
            category=category,
            side=side,
            limit=limit,
            offset=offset,
            use_mv=True,
        )
        return {"status": "success", "data": {"activity": result["activity"], "total": result["total"]}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activity/daily_summary")
async def get_activity_daily_summary(
    account_id: Optional[int] = Query(None),
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    symbol: Optional[str] = Query(None),
    user: User | None = Depends(get_optional_user),
    db = Depends(get_db),
) -> Dict[str, Any]:
    try:
        rows = activity_aggregator.get_daily_summary(
            db=db,
            account_id=account_id,
            start=start,
            end=end,
            symbol=symbol,
            use_mv=True,
        )
        return {"status": "success", "data": {"daily": rows}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/activity/refresh")
async def refresh_activity_materialized_views(
    user: User | None = Depends(get_optional_user),
    db = Depends(get_db),
) -> Dict[str, Any]:
    try:
        res = activity_aggregator.refresh_materialized_views(db)
        return {"status": "success", "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


