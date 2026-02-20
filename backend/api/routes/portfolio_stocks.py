"""Portfolio stocks endpoints for frontend (renamed from holdings)."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import logging

from backend.database import get_db
from backend.models.position import Position
from backend.models import BrokerAccount
from backend.models.tax_lot import TaxLot
from backend.models.user import User
from backend.models.market_data import MarketSnapshot

logger = logging.getLogger(__name__)

router = APIRouter()


def _latest_snapshots_by_symbol(db: Session, symbols: List[str]) -> Dict[str, Any]:
    """Return a dict symbol -> snapshot fields (stage_label, rs_mansfield_pct, etc.) for latest snapshot per symbol."""
    if not symbols:
        return {}
    # Subquery: max(COALESCE(as_of_timestamp, analysis_timestamp)) per symbol
    ts_col = func.coalesce(
        MarketSnapshot.as_of_timestamp, MarketSnapshot.analysis_timestamp
    )
    subq = (
        db.query(MarketSnapshot.symbol, func.max(ts_col).label("max_ts"))
        .filter(MarketSnapshot.symbol.in_(symbols))
        .group_by(MarketSnapshot.symbol)
        .subquery()
    )
    snapshots = (
        db.query(MarketSnapshot)
        .join(
            subq,
            (MarketSnapshot.symbol == subq.c.symbol)
            & (ts_col == subq.c.max_ts),
        )
        .all()
    )
    out: Dict[str, Any] = {}
    for s in snapshots:
        out[s.symbol] = {
            "stage_label": s.stage_label,
            "rs_mansfield_pct": float(s.rs_mansfield_pct) if s.rs_mansfield_pct is not None else None,
            "perf_1d": float(s.perf_1d) if s.perf_1d is not None else None,
            "perf_5d": float(s.perf_5d) if s.perf_5d is not None else None,
            "perf_20d": float(s.perf_20d) if s.perf_20d is not None else None,
            "rsi": float(s.rsi) if s.rsi is not None else None,
            "atr_14": float(s.atr_14) if s.atr_14 is not None else None,
            "sma_50": float(s.sma_50) if s.sma_50 is not None else None,
            "sma_200": float(s.sma_200) if s.sma_200 is not None else None,
        }
    return out


@router.get("/stocks", response_model=Dict[str, Any])
async def get_stocks(
    user_id: int | None = Query(None, description="User ID (optional)"),
    account_id: str | None = Query(
        None, description="Filter by account number (e.g., IBKR_ACCOUNT)"
    ),
    include_market_data: bool = Query(
        True, description="Enrich with market snapshot (stage, RS, perf, rsi, atr)"
    ),
    db: Session = Depends(get_db),
):
    """Return equity positions for Stocks page. Optionally enriched with market snapshot (stage, RS, etc.)."""
    try:
        user = (
            db.query(User).first()
            if user_id is None
            else db.query(User).filter(User.id == user_id).first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        query = (
            db.query(Position)
            .join(BrokerAccount, Position.account_id == BrokerAccount.id)
            .filter(
                Position.user_id == user.id,
                Position.instrument_type == "STOCK",
                Position.quantity != 0,
            )
        )
        if account_id:
            query = query.filter(BrokerAccount.account_number == account_id)
        positions = query.all()

        symbols = list({p.symbol for p in positions})
        snapshot_by_symbol: Dict[str, Any] = {}
        if include_market_data and symbols:
            snapshot_by_symbol = _latest_snapshots_by_symbol(db, symbols)

        result: List[Dict[str, Any]] = []
        for p in positions:
            row: Dict[str, Any] = {
                "id": p.id,
                "symbol": p.symbol,
                "account_number": p.account.account_number if p.account else None,
                "broker": "IBKR",
                "shares": float(p.quantity),
                "current_price": float(p.current_price or 0),
                "market_value": float(p.market_value or 0),
                "cost_basis": float(p.total_cost_basis or 0),
                "average_cost": float(p.average_cost or 0),
                "unrealized_pnl": float(p.unrealized_pnl or 0),
                "unrealized_pnl_pct": float(p.unrealized_pnl_pct or 0),
                "day_pnl": float(p.day_pnl or 0),
                "day_pnl_pct": float(p.day_pnl_pct or 0),
                "sector": p.sector or "",
                "industry": p.industry or "",
                "last_updated": (
                    p.position_updated_at.isoformat()
                    if p.position_updated_at
                    else None
                ),
            }
            if include_market_data and p.symbol in snapshot_by_symbol:
                row.update(snapshot_by_symbol[p.symbol])
            result.append(row)

        return {"status": "success", "data": {"total": len(result), "stocks": result}}
    except Exception as e:
        logger.error(f"Stocks endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{position_id}/tax-lots", response_model=Dict[str, Any])
async def get_tax_lots_for_stock(
    position_id: int = Path(..., description="Position ID"),
    db: Session = Depends(get_db),
):
    """Return tax lots associated with a Position (by FK)."""
    try:
        position = db.query(Position).filter(Position.id == position_id).first()
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")

        lots = (
            db.query(TaxLot)
            .filter(
                TaxLot.symbol == position.symbol,
                TaxLot.account_id == position.account_id,
            )
            .all()
        )
        result = []
        for lot in lots:
            result.append(
                {
                    "id": lot.id,
                    "shares": float(lot.quantity),
                    "shares_remaining": float(lot.quantity),
                    "purchase_date": (
                        lot.acquisition_date.isoformat()
                        if lot.acquisition_date
                        else None
                    ),
                    "cost_per_share": float(lot.cost_per_share or 0),
                    "market_value": float(lot.market_value or 0),
                    "unrealized_pnl": float(lot.unrealized_pnl or 0),
                    "unrealized_pnl_pct": float(lot.unrealized_pnl_pct or 0),
                    "is_long_term": (lot.holding_period or 0) >= 365,
                    "days_held": lot.holding_period or 0,
                }
            )
        return {
            "status": "success",
            "data": {"tax_lots": result, "processing_time_ms": 0},
        }
    except Exception as e:
        logger.error(f"Tax lots endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
