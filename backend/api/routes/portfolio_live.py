"""Live portfolio endpoint to satisfy frontend `/api/v1/portfolio/live` requests.
Returns the same data as `/summary` but without auth for now (temporarily).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Any
import logging

from backend.database import get_db
from backend.models.user import User
from backend.models.position import Position
from backend.models import BrokerAccount

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/live", response_model=Dict[str, Any])
async def get_live_portfolio(
    user_id: int | None = Query(None, description="User ID (optional)"),
    account_id: str | None = Query(
        None, description="Filter by account number (e.g., IBKR_ACCOUNT)"
    ),
    db: Session = Depends(get_db),
):
    """Aggregated live portfolio snapshot for React dashboard."""
    try:
        # Determine which user to serve
        if user_id is None:
            user = db.query(User).first()
        else:
            user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        query = (
            db.query(Position)
            .join(BrokerAccount, Position.account_id == BrokerAccount.id)
            .filter(Position.user_id == user.id)
        )
        if account_id:
            query = query.filter(BrokerAccount.account_number == account_id)
        positions_models = query.all()

        acct_ids = {p.account_id for p in positions_models}
        accounts_map = {
            a.id: a
            for a in db.query(BrokerAccount).filter(
                BrokerAccount.id.in_(acct_ids)
            ).all()
        }

        # Build accounts mapping like Snowball Analytics style expected by frontend
        accounts: Dict[str, Any] = {}
        for p in positions_models:
            acc = accounts_map.get(p.account_id)
            if not acc:
                continue
            acc_key = acc.account_number
            if acc_key not in accounts:
                accounts[acc_key] = {
                    "account_summary": {
                        "account_name": getattr(
                            acc, "account_name", acc.account_number
                        ),
                        "account_type": (
                            acc.account_type.value
                            if getattr(acc, "account_type", None)
                            else "taxable"
                        ),
                        "broker": (
                            acc.broker.value if getattr(acc, "broker", None) else "IBKR"
                        ),
                        "net_liquidation": 0.0,
                        "unrealized_pnl": 0.0,
                        "unrealized_pnl_pct": 0.0,
                        "day_change": 0.0,
                        "day_change_pct": 0.0,
                        "total_cash": 0.0,
                        "available_funds": None,
                        "buying_power": None,
                    },
                    "all_positions": [],
                }

            mv = float(p.market_value or 0)
            upnl = float(p.unrealized_pnl or 0)
            accounts[acc_key]["account_summary"]["net_liquidation"] += mv
            accounts[acc_key]["account_summary"]["unrealized_pnl"] += upnl
            accounts[acc_key]["account_summary"]["day_change"] += float(p.day_pnl or 0)

            # Append a position object shaped for the frontend holdings/portfolio pages
            accounts[acc_key]["all_positions"].append(
                {
                    "symbol": p.symbol,
                    "contract_type": (
                        "OPT"
                        if p.instrument_type
                        and p.instrument_type.upper().startswith("OPTION")
                        else "STK"
                    ),
                    "position": float(p.quantity or 0),
                    "position_value": mv,
                    "unrealized_pnl": upnl,
                    "unrealized_pnl_pct": float(p.unrealized_pnl_pct or 0),
                    "market_price": float(p.current_price or 0),
                    "day_change": float(p.day_pnl or 0),
                    "day_change_pct": float(p.day_pnl_pct or 0),
                    "sector": p.sector or "Unknown",
                }
            )

        # compute top-level summary
        total_value = sum(
            acc["account_summary"]["net_liquidation"] for acc in accounts.values()
        )
        total_unreal = sum(
            acc["account_summary"]["unrealized_pnl"] for acc in accounts.values()
        )
        summary = {
            "total_market_value": total_value,
            "total_cost_basis": None,
            "unrealized_pnl": total_unreal,
            "unrealized_pnl_pct": (
                (total_unreal / total_value * 100) if total_value else 0.0
            ),
        }

        return {
            "accounts": accounts,
            "portfolio_summary": summary,
            "last_updated": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"❌ Live portfolio error for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
