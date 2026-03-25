"""Dividends endpoint `/api/v1/portfolio/dividends` consumed by React DividendsCalendar.
Returns dividends for the specified user (or default first user) over the given number of days.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.transaction import Dividend
from backend.models.user import User
from backend.models import BrokerAccount

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dividends", response_model=Dict[str, Any])
async def get_dividends(
    days: int = Query(365, ge=1, le=3650),
    user_id: int | None = Query(None, description="User ID (optional)"),
    account_id: str | None = Query(
        None, description="Filter by account number (e.g., U19491234)"
    ),
    db: Session = Depends(get_db),
):
    """Return dividend rows within the last `days` days for the given user.
    The frontend calls `/portfolio/dividends?days=365` so we support that query param.
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Determine user (temporary unauthenticated fallback)
        if user_id is None:
            user = db.query(User).first()
        else:
            user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        base = (
            db.query(Dividend)
            .join(BrokerAccount, Dividend.account_id == BrokerAccount.id)
            .filter(BrokerAccount.user_id == user.id)
            .filter(Dividend.ex_date >= cutoff_date)
        )
        if account_id:
            base = base.filter(BrokerAccount.account_number == account_id)
        divs = base.all()

        results: List[Dict[str, Any]] = []
        for d in divs:
            results.append(
                {
                    "symbol": d.symbol,
                    "ex_date": d.ex_date.isoformat() if d.ex_date else None,
                    "pay_date": d.pay_date.isoformat() if d.pay_date else None,
                    "dividend_per_share": d.dividend_per_share,
                    "shares_held": d.shares_held,
                    "total_dividend": d.total_dividend,
                    "currency": d.currency,
                    "account_id": d.account_id,
                }
            )
        return {"status": "success", "data": {"dividends": results}}
    except Exception as e:
        logger.error(f"❌ Dividends endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
