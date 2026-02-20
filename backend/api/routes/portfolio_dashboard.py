"""Dashboard endpoint that merges summary, positions, dividends for front-end /portfolio/dashboard."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

from backend.database import get_db
from backend.models.user import User
from backend.models.position import Position
from backend.models.transaction import Dividend
from backend.models.portfolio import PortfolioSnapshot
from backend.models.broker_account import BrokerAccount

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dashboard", response_model=Dict[str, Any])
async def get_dashboard(
    user_id: int | None = Query(None),
    days: int = Query(365, ge=1, le=3650),
    db: Session = Depends(get_db),
):
    """Simple dashboard summary until full analytics ready."""
    try:
        user = (
            db.query(User).first()
            if user_id is None
            else db.query(User).filter(User.id == user_id).first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # positions
        pos_models = db.query(Position).filter(Position.user_id == user.id).all()
        positions = [
            {
                "symbol": p.symbol,
                "quantity": float(p.quantity),
                "market_value": float(p.market_value or 0),
                "unrealized_pnl": float(p.unrealized_pnl or 0),
                "sector": (p.sector or "").strip() or "Other",
            }
            for p in pos_models
        ]
        total_value = sum(p["market_value"] for p in positions)
        total_cost = sum(float(p.total_cost_basis or 0) for p in pos_models)

        # dividends last X days
        cutoff = datetime.utcnow() - timedelta(days=days)
        divs = (
            db.query(Dividend)
            .filter(
                Dividend.account_id.in_(
                    db.query(Position.account_id).filter(Position.user_id == user.id)
                ),
                Dividend.ex_date >= cutoff,
            )
            .count()
        )

        summary = {
            "total_market_value": total_value,
            "total_cost_basis": total_cost,
            "unrealized_pnl": total_value - total_cost if total_cost else 0,
            "positions_count": len(positions),
            "dividends_count_last_period": divs,
        }

        # sector_allocation: aggregate by sector
        sector_value: Dict[str, float] = {}
        for p in pos_models:
            sec = (p.sector or "").strip() or "Other"
            sector_value[sec] = sector_value.get(sec, 0) + float(p.market_value or 0)
        sector_allocation = [
            {"sector": name, "value": val, "pct": round((val / total_value * 100), 2) if total_value else 0}
            for name, val in sorted(sector_value.items(), key=lambda x: -x[1])
        ]

        # top_performers / top_losers by unrealized_pnl
        sorted_by_pnl = sorted(
            pos_models,
            key=lambda p: float(p.unrealized_pnl or 0),
            reverse=True,
        )
        top_performers = [
            {"symbol": p.symbol, "market_value": float(p.market_value or 0), "unrealized_pnl": float(p.unrealized_pnl or 0)}
            for p in sorted_by_pnl if float(p.unrealized_pnl or 0) > 0
        ][:5]
        top_losers = [
            {"symbol": p.symbol, "market_value": float(p.market_value or 0), "unrealized_pnl": float(p.unrealized_pnl or 0)}
            for p in sorted_by_pnl if float(p.unrealized_pnl or 0) < 0
        ][-5:]
        top_losers.reverse()

        # accounts_summary: per-account value and count
        broker_accounts = db.query(BrokerAccount).filter(BrokerAccount.user_id == user.id).all()
        accounts_summary = []
        for acc in broker_accounts:
            acc_positions = [p for p in pos_models if p.account_id == acc.id]
            acc_value = sum(float(p.market_value or 0) for p in acc_positions)
            accounts_summary.append({
                "account_id": acc.account_number,
                "broker": acc.broker.value,
                "account_type": acc.account_type.value,
                "total_value": acc_value,
                "positions_count": len(acc_positions),
                "last_successful_sync": acc.last_successful_sync.isoformat() if acc.last_successful_sync else None,
            })

        return {
            "status": "success",
            "data": {
                "user_id": user.id,
                "summary": summary,
                "positions": positions,
                "generated_at": datetime.utcnow().isoformat(),
                "total_value": total_value,
                "total_unrealized_pnl": summary["unrealized_pnl"],
                "total_unrealized_pnl_pct": (
                    (summary["unrealized_pnl"] / summary["total_cost_basis"] * 100)
                    if summary["total_cost_basis"]
                    else 0
                ),
                "day_change": 0,
                "day_change_pct": 0,
                "accounts_summary": accounts_summary,
                "accounts_count": len(accounts_summary),
                "sector_allocation": sector_allocation,
                "top_performers": top_performers,
                "top_losers": top_losers,
                "holdings_count": len(positions),
                "last_updated": datetime.utcnow().isoformat(),
                "brokerages": ["IBKR", "TASTYTRADE"],
            },
        }
    except Exception as e:
        logger.error(f"dashboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _parse_period(period: str) -> Optional[timedelta]:
    """Return timedelta for period or None for 'all'."""
    p = (period or "").strip().lower()
    if p in ("all", ""):
        return None
    if p == "30d" or p == "1m":
        return timedelta(days=30)
    if p == "90d" or p == "3m":
        return timedelta(days=90)
    if p == "1y":
        return timedelta(days=365)
    if p == "ytd":
        return None  # special: filter by year
    return timedelta(days=365)


@router.get("/performance/history", response_model=Dict[str, Any])
async def get_performance_history(
    user_id: int | None = Query(None),
    account_id: Optional[str] = Query(None, description="Filter by account number"),
    period: str = Query("1y", description="30d, 90d, 1y, all"),
    db: Session = Depends(get_db),
):
    """Return portfolio_snapshots time series for the performance chart (aggregate total_value per day)."""
    try:
        user = (
            db.query(User).first()
            if user_id is None
            else db.query(User).filter(User.id == user_id).first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        account_ids_q = (
            db.query(BrokerAccount.id).filter(BrokerAccount.user_id == user.id)
        )
        if account_id:
            account_ids_q = account_ids_q.filter(BrokerAccount.account_number == account_id)
        account_ids = [r[0] for r in account_ids_q.all()]

        if not account_ids:
            return {
                "status": "success",
                "data": {
                    "series": [],
                    "period": period,
                    "generated_at": datetime.utcnow().isoformat(),
                },
            }

        query = (
            db.query(
                func.date(PortfolioSnapshot.snapshot_date).label("date"),
                func.sum(PortfolioSnapshot.total_value).label("total_value"),
            )
            .filter(PortfolioSnapshot.account_id.in_(account_ids))
            .group_by(func.date(PortfolioSnapshot.snapshot_date))
            .order_by(func.date(PortfolioSnapshot.snapshot_date))
        )

        delta = _parse_period(period)
        now = datetime.utcnow()
        if period and period.strip().lower() == "ytd":
            query = query.filter(func.extract("year", PortfolioSnapshot.snapshot_date) == now.year)
        elif delta:
            since = now - delta
            query = query.filter(PortfolioSnapshot.snapshot_date >= since)

        rows = query.all()
        series = [
            {"date": row.date.isoformat() if hasattr(row.date, "isoformat") else str(row.date), "total_value": float(row.total_value)}
            for row in rows
        ]

        return {
            "status": "success",
            "data": {
                "series": series,
                "period": period,
                "generated_at": datetime.utcnow().isoformat(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"performance/history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
