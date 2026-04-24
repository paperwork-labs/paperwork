"""Dividends endpoint `/api/v1/portfolio/dividends` consumed by React DividendsCalendar.
Returns dividends for the authenticated user over the given number of days.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user
from backend.database import get_db
from backend.models.transaction import Dividend
from backend.models.user import User
from backend.models import BrokerAccount

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dividends", response_model=Dict[str, Any])
async def get_dividends(
    days: int = Query(365, ge=1, le=3650),
    account_id: str | None = Query(
        None, description="Filter by account number (e.g., U19491234)"
    ),
    symbol: str | None = Query(
        None,
        max_length=20,
        description=(
            "Filter rows to a single ticker (case-insensitive). When set, the "
            "endpoint returns only dividends paid on that symbol; this is the "
            "shape consumed by the per-holding chart's dividend dot overlay "
            "so the chart hook does not need to download the entire account "
            "payload just to filter client-side."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return dividend rows within the last `days` days for the authenticated user.

    Filters are composable and applied at the SQL layer (no Python-side
    post-filter): caller can scope to a specific brokerage account
    (`account_id`) and/or a single ticker (`symbol`). Both are optional;
    when omitted the response covers every dividend across every account
    the authenticated user owns.
    """
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        base = (
            db.query(Dividend)
            .join(BrokerAccount, Dividend.account_id == BrokerAccount.id)
            .filter(BrokerAccount.user_id == current_user.id)
            .filter(Dividend.ex_date >= cutoff_date)
        )
        if account_id:
            base = base.filter(BrokerAccount.account_number == account_id)
        if symbol:
            # Symbols are stored upper-cased at ingest (see flexquery + tasty
            # normalizers) — match upper-cased and trim whitespace so the
            # caller can be sloppy with casing without missing rows.
            base = base.filter(Dividend.symbol == symbol.strip().upper())
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
