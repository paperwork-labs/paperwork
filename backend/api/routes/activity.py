from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from backend.api.dependencies import get_optional_user
from backend.database import SessionLocal
from backend.models.broker_account import BrokerAccount
from backend.models.user import User
from backend.services.portfolio.activity_aggregator import activity_aggregator

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _resolve_account_id(db, account_id_raw: Optional[str]) -> Optional[int]:
    """Resolve account_id which may be an int PK or account_number string."""
    if account_id_raw is None:
        return None
    try:
        return int(account_id_raw)
    except (ValueError, TypeError):
        row = db.query(BrokerAccount.id).filter(
            BrokerAccount.account_number == account_id_raw
        ).first()
        return row[0] if row else None


@router.get("/activity")
async def get_activity(
    account_id: Optional[str] = Query(None, description="Account PK or account number"),
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
        resolved_id = _resolve_account_id(db, account_id)
        result = activity_aggregator.get_activity(
            db=db,
            account_id=resolved_id,
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
    account_id: Optional[str] = Query(None, description="Account PK or account number"),
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    symbol: Optional[str] = Query(None),
    user: User | None = Depends(get_optional_user),
    db = Depends(get_db),
) -> Dict[str, Any]:
    try:
        resolved_id = _resolve_account_id(db, account_id)
        rows = activity_aggregator.get_daily_summary(
            db=db,
            account_id=resolved_id,
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


