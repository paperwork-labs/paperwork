"""Activity feed endpoints.

All endpoints require authentication via JWT.
Activity is scoped to accounts owned by the authenticated user.
"""

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.dependencies import get_current_user, require_role
from app.database import SessionLocal
from app.models.broker_account import BrokerAccount
from app.models.user import User, UserRole
from app.services.portfolio.activity_aggregator import activity_aggregator

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _resolve_account_id(db, account_id_raw: Optional[str], user_id: int) -> Optional[int]:
    """Resolve account_id (int PK or account_number string) scoped to user.

    Returns None if account_id_raw is None (meaning "all user accounts").
    Raises HTTPException 404 if account exists but user doesn't own it.
    """
    if account_id_raw is None:
        return None
    try:
        account_id = int(account_id_raw)
        account = db.query(BrokerAccount).filter(
            BrokerAccount.id == account_id,
            BrokerAccount.user_id == user_id,
        ).first()
    except (ValueError, TypeError):
        account = db.query(BrokerAccount).filter(
            BrokerAccount.account_number == account_id_raw,
            BrokerAccount.user_id == user_id,
        ).first()
    if account_id_raw and not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account.id if account else None


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
    user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    try:
        resolved_id = _resolve_account_id(db, account_id, user.id)
        result = activity_aggregator.get_activity(
            db=db,
            account_id=resolved_id,
            user_id=user.id,
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activity/daily_summary")
async def get_activity_daily_summary(
    account_id: Optional[str] = Query(None, description="Account PK or account number"),
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    symbol: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    try:
        resolved_id = _resolve_account_id(db, account_id, user.id)
        rows = activity_aggregator.get_daily_summary(
            db=db,
            account_id=resolved_id,
            user_id=user.id,
            start=start,
            end=end,
            symbol=symbol,
            use_mv=True,
        )
        return {"status": "success", "data": {"daily": rows}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/activity/refresh")
async def refresh_activity_materialized_views(
    user: User = Depends(require_role(UserRole.OWNER)),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Refresh activity materialized views. Requires OWNER role (expensive operation)."""
    try:
        res = activity_aggregator.refresh_materialized_views(db)
        return {"status": "success", "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


