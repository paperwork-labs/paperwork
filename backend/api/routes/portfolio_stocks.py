"""Portfolio stocks endpoints for frontend (renamed from holdings)."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, text, extract, case, literal_column
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import csv
import io
import logging

from backend.api.dependencies import get_portfolio_user
from backend.database import get_db
from backend.models.position import Position
from backend.models import BrokerAccount
from backend.models.tax_lot import TaxLot
from backend.models.trade import Trade
from backend.models.user import User
from backend.models.market_data import MarketSnapshot

logger = logging.getLogger(__name__)

router = APIRouter()

TAX_RATE_SHORT_TERM = 0.37
TAX_RATE_LONG_TERM = 0.20


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
        mc = float(s.market_cap) if s.market_cap is not None else None
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
            "sector": s.sector,
            "market_cap": mc,
            "market_cap_label": _market_cap_label(mc),
        }
    return out


def _market_cap_label(market_cap: Optional[float]) -> Optional[str]:
    if market_cap is None:
        return None
    if market_cap >= 200_000_000_000:
        return "Mega Cap"
    if market_cap >= 10_000_000_000:
        return "Large Cap"
    if market_cap >= 2_000_000_000:
        return "Mid Cap"
    if market_cap >= 300_000_000:
        return "Small Cap"
    return "Micro Cap"


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
                BrokerAccount.is_enabled == True,
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
            snap = snapshot_by_symbol.get(p.symbol, {}) if include_market_data else {}
            sector = p.sector or snap.get("sector") or ""
            row: Dict[str, Any] = {
                "id": p.id,
                "symbol": p.symbol,
                "account_number": p.account.account_number if p.account else None,
                "broker": p.account.broker.value if p.account else "UNKNOWN",
                "shares": float(p.quantity),
                "current_price": float(p.current_price or 0),
                "market_value": float(p.market_value or 0),
                "cost_basis": float(p.total_cost_basis) if p.total_cost_basis else None,
                "average_cost": float(p.average_cost) if p.average_cost else None,
                "unrealized_pnl": float(p.unrealized_pnl or 0),
                "unrealized_pnl_pct": float(p.unrealized_pnl_pct or 0),
                "day_pnl": float(p.day_pnl or 0),
                "day_pnl_pct": float(p.day_pnl_pct or 0),
                "sector": sector,
                "industry": p.industry or "",
                "market_cap": snap.get("market_cap"),
                "market_cap_label": snap.get("market_cap_label"),
                "last_updated": (
                    p.position_updated_at.isoformat()
                    if p.position_updated_at
                    else None
                ),
            }
            if include_market_data and snap:
                row.update(snap)
                row["sector"] = sector
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
                    "cost_basis": float(lot.cost_basis or 0),
                    "market_value": float(lot.market_value or 0),
                    "unrealized_pnl": float(lot.unrealized_pnl or 0),
                    "unrealized_pnl_pct": float(lot.unrealized_pnl_pct or 0),
                    "is_long_term": lot.is_long_term,
                    "days_held": lot.holding_period_days,
                    "source": lot.source.value if lot.source else None,
                    "commission": float(lot.commission or 0),
                    "settlement_date": (
                        lot.settlement_date.isoformat()
                        if lot.settlement_date
                        else None
                    ),
                }
            )
        return {
            "status": "success",
            "data": {"tax_lots": result, "processing_time_ms": 0},
        }
    except Exception as e:
        logger.error(f"Tax lots endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tax-lots/tax-summary", response_model=Dict[str, Any])
async def get_tax_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_portfolio_user),
):
    """Aggregate all tax lots into LT vs ST buckets with estimated tax impact."""
    try:
        account_ids = _user_account_ids(db, user.id)
        if not account_ids:
            return {
                "status": "success",
                "data": {"tax_lots": [], "summary": {}},
            }

        lots = (
            db.query(TaxLot)
            .filter(TaxLot.account_id.in_(account_ids))
            .order_by(TaxLot.acquisition_date.desc())
            .all()
        )

        ST_RATE = TAX_RATE_SHORT_TERM
        LT_RATE = TAX_RATE_LONG_TERM

        rows = []
        lt_gains = 0.0
        lt_losses = 0.0
        st_gains = 0.0
        st_losses = 0.0

        for lot in lots:
            days = lot.holding_period_days
            is_lt = lot.is_long_term
            unrealized = float(lot.unrealized_pnl or 0)

            if is_lt:
                if unrealized >= 0:
                    lt_gains += unrealized
                else:
                    lt_losses += unrealized
            else:
                if unrealized >= 0:
                    st_gains += unrealized
                else:
                    st_losses += unrealized

            rows.append({
                "id": lot.id,
                "symbol": lot.symbol,
                "shares": float(lot.quantity or 0),
                "purchase_date": lot.acquisition_date.isoformat() if lot.acquisition_date else None,
                "cost_per_share": float(lot.cost_per_share or 0),
                "cost_basis": float(lot.cost_basis or 0),
                "market_value": float(lot.market_value or 0),
                "unrealized_pnl": unrealized,
                "unrealized_pnl_pct": float(lot.unrealized_pnl_pct or 0),
                "is_long_term": is_lt,
                "days_held": days,
                "approaching_lt": not is_lt and days >= 300,
                "source": lot.source.value if lot.source else None,
                "commission": float(lot.commission or 0),
            })

        estimated_lt_tax = lt_gains * LT_RATE
        estimated_st_tax = st_gains * ST_RATE

        summary = {
            "total_lots": len(rows),
            "lt_lots": sum(1 for r in rows if r["is_long_term"]),
            "st_lots": sum(1 for r in rows if not r["is_long_term"]),
            "lt_unrealized_gains": round(lt_gains, 2),
            "lt_unrealized_losses": round(lt_losses, 2),
            "st_unrealized_gains": round(st_gains, 2),
            "st_unrealized_losses": round(st_losses, 2),
            "estimated_lt_tax": round(estimated_lt_tax, 2),
            "estimated_st_tax": round(estimated_st_tax, 2),
            "estimated_total_tax": round(estimated_lt_tax + estimated_st_tax, 2),
            "net_harvest_potential": round(lt_losses + st_losses, 2),
        }

        return {
            "status": "success",
            "data": {"tax_lots": rows, "summary": summary},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tax summary endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _user_account_ids(db: Session, user_id: int) -> List[int]:
    """Return enabled broker account IDs for the given user."""
    return [
        a.id
        for a in db.query(BrokerAccount.id).filter(
            BrokerAccount.user_id == user_id,
            BrokerAccount.is_enabled == True,
        ).all()
    ]


@router.get("/realized-gains")
def get_realized_gains(
    year: Optional[int] = Query(None),
    account_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_portfolio_user),
):
    """Aggregate realized gains from CLOSED_LOT trade records by symbol and year."""
    try:
        acct_ids = _user_account_ids(db, user.id)
        if not acct_ids:
            return {"status": "success", "data": {"realized_gains": [], "summary_by_year": []}}

        q = db.query(Trade).filter(
            Trade.account_id.in_(acct_ids),
            Trade.status == "CLOSED_LOT",
        )
        if year:
            q = q.filter(extract("year", Trade.execution_time) == year)
        if account_id:
            resolved = (
                db.query(BrokerAccount.id)
                .filter(BrokerAccount.account_number == account_id)
                .scalar()
            )
            if resolved:
                q = q.filter(Trade.account_id == resolved)

        lots = q.all()

        by_sym_year: Dict[tuple, list] = {}
        for lot in lots:
            meta = lot.trade_metadata or {}
            yr = lot.execution_time.year if lot.execution_time else 0
            key = (lot.symbol, yr)
            by_sym_year.setdefault(key, []).append((lot, meta))

        realized_gains = []
        for (sym, yr), items in sorted(by_sym_year.items(), key=lambda x: (-x[0][1], x[0][0])):
            total_pnl = sum(float(lot.realized_pnl or 0) for lot, _ in items)
            total_cost = sum(float(m.get("cost_basis", 0)) for _, m in items)
            total_proceeds = sum(float(lot.total_value or 0) for lot, _ in items)
            total_qty = sum(float(lot.quantity or 0) for lot, _ in items)

            lt_items = [m for _, m in items if m.get("is_long_term")]
            st_items = [m for _, m in items if not m.get("is_long_term")]

            realized_gains.append({
                "symbol": sym,
                "tax_year": yr,
                "realized_pnl": round(total_pnl, 2),
                "cost_basis": round(total_cost, 2),
                "proceeds": round(total_proceeds, 2),
                "shares_sold": round(total_qty, 4),
                "trade_count": len(items),
                "lt_count": len(lt_items),
                "st_count": len(st_items),
                "is_long_term": len(lt_items) > len(st_items),
            })

        year_summary: Dict[int, dict] = {}
        for rg in realized_gains:
            yr = rg["tax_year"]
            s = year_summary.setdefault(yr, {"year": yr, "st_gains": 0, "st_losses": 0, "lt_gains": 0, "lt_losses": 0, "total_realized": 0})
            pnl = rg["realized_pnl"]
            s["total_realized"] += pnl
            if rg["lt_count"] >= rg["st_count"]:
                if pnl >= 0:
                    s["lt_gains"] += pnl
                else:
                    s["lt_losses"] += pnl
            else:
                if pnl >= 0:
                    s["st_gains"] += pnl
                else:
                    s["st_losses"] += pnl

        summary_by_year = []
        for yr, s in sorted(year_summary.items(), reverse=True):
            est_tax = round(s["st_gains"] * TAX_RATE_SHORT_TERM + s["lt_gains"] * TAX_RATE_LONG_TERM, 2)
            summary_by_year.append({**{k: round(v, 2) for k, v in s.items()}, "estimated_tax": est_tax})

        return {"status": "success", "data": {"realized_gains": realized_gains, "summary_by_year": summary_by_year}}
    except Exception as e:
        logger.error(f"Realized gains error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/closed")
def get_closed_positions(
    account_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_portfolio_user),
):
    """Return symbols the user has sold but no longer holds."""
    try:
        acct_ids = _user_account_ids(db, user.id)
        if not acct_ids:
            return {"status": "success", "data": {"closed_positions": []}}

        sell_trades = (
            db.query(Trade)
            .filter(
                Trade.account_id.in_(acct_ids),
                Trade.side == "SELL",
                Trade.status == "FILLED",
            )
            .all()
        )

        open_symbols = set(
            p.symbol
            for p in db.query(Position.symbol)
            .filter(Position.account_id.in_(acct_ids), Position.quantity != 0)
            .all()
        )

        by_sym: Dict[str, list] = {}
        for t in sell_trades:
            if t.symbol not in open_symbols:
                by_sym.setdefault(t.symbol, []).append(t)

        closed = []
        for sym, trades in sorted(by_sym.items()):
            total_pnl = sum(float(t.realized_pnl or 0) for t in trades)
            total_qty = sum(float(t.quantity or 0) for t in trades)
            last_date = max((t.execution_time for t in trades if t.execution_time), default=None)
            closed.append({
                "symbol": sym,
                "total_realized_pnl": round(total_pnl, 2),
                "total_shares_sold": round(total_qty, 4),
                "last_trade_date": last_date.isoformat() if last_date else None,
                "trade_count": len(trades),
            })

        return {"status": "success", "data": {"closed_positions": closed}}
    except Exception as e:
        logger.error(f"Closed positions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tax-report/export")
def export_tax_report(
    year: int = Query(..., description="Tax year"),
    db: Session = Depends(get_db),
    user: User = Depends(get_portfolio_user),
):
    """Generate Schedule D-ready CSV from realized gains."""
    try:
        acct_ids = _user_account_ids(db, user.id)
        lots = (
            db.query(Trade)
            .filter(
                Trade.account_id.in_(acct_ids),
                Trade.status.in_(["CLOSED_LOT", "WASH_SALE"]),
                extract("year", Trade.execution_time) == year,
            )
            .order_by(Trade.execution_time)
            .all()
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Description", "Date Acquired", "Date Sold",
            "Proceeds", "Cost Basis", "Adjustment Code",
            "Adjustment Amount", "Gain or Loss", "Term",
        ])

        for lot in lots:
            meta = lot.trade_metadata or {}
            is_wash = lot.status == "WASH_SALE"
            open_d = meta.get("open_date") or ""
            close_d = meta.get("close_date") or (lot.execution_time.strftime("%Y-%m-%d") if lot.execution_time else "")
            if hasattr(open_d, "strftime"):
                open_d = open_d.strftime("%Y-%m-%d")
            if hasattr(close_d, "strftime"):
                close_d = close_d.strftime("%Y-%m-%d")

            desc = f"{lot.symbol} ({float(lot.quantity or 0):.0f} sh)"
            proceeds = float(lot.total_value or 0)
            cost_basis = float(meta.get("cost_basis", 0))
            gain = float(lot.realized_pnl or 0)
            adj_code = "W" if is_wash else ""
            adj_amt = float(meta.get("wash_sale_loss", 0)) if is_wash else ""
            term = "Long-Term" if meta.get("is_long_term") else "Short-Term"

            writer.writerow([desc, open_d, close_d, f"{proceeds:.2f}", f"{cost_basis:.2f}", adj_code, adj_amt, f"{gain:.2f}", term])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=tax-report-{year}.csv"},
        )
    except Exception as e:
        logger.error(f"Tax report export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
