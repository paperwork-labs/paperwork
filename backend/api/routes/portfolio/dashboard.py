"""Dashboard endpoint that merges summary, positions, dividends for front-end /portfolio/dashboard."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import logging

from backend.database import get_db
from backend.models.user import User
from backend.models.position import Position
from backend.models.trade import Trade
from backend.models.transaction import Dividend, Transaction, TransactionType
from backend.models.portfolio import PortfolioSnapshot
from backend.models.broker_account import BrokerAccount
from backend.models.account_balance import AccountBalance
from backend.models.margin_interest import MarginInterest
from backend.models.options import Option
from backend.api.dependencies import get_current_user
from backend.api.middleware.response_cache import redis_response_cache
from backend.services.portfolio.portfolio_analytics_service import portfolio_analytics_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _datetime_as_utc_aware(dt: datetime) -> datetime:
    """Coerce to timezone-aware UTC so comparisons match ``datetime.now(timezone.utc)``."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.get("/dashboard", response_model=Dict[str, Any])
@redis_response_cache(ttl_seconds=30)
async def get_dashboard(
    request: Request,
    days: int = Query(365, ge=1, le=3650),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Simple dashboard summary until full analytics ready."""
    try:

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

        option_models = db.query(Option).filter(
            Option.user_id == user.id, Option.open_quantity != 0
        ).all()
        options_value = sum(
            float(o.current_price or 0) * abs(o.open_quantity or 0) * (o.multiplier or 100)
            for o in option_models
        )
        options_unrealized = sum(float(o.unrealized_pnl or 0) for o in option_models)
        total_value += options_value

        # dividends last X days
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
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
        broker_accounts = db.query(BrokerAccount).filter(BrokerAccount.user_id == user.id, BrokerAccount.is_enabled == True).all()
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
                "generated_at": datetime.now(timezone.utc).isoformat(),
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
                "last_updated": datetime.now(timezone.utc).isoformat(),
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
@redis_response_cache(ttl_seconds=30)
async def get_performance_history(
    request: Request,
    account_id: Optional[str] = Query(None, description="Filter by account number"),
    period: str = Query("1y", description="30d, 90d, 1y, all"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return portfolio_snapshots time series for the performance chart (aggregate total_value per day)."""
    try:

        account_ids_q = (
            db.query(BrokerAccount.id).filter(BrokerAccount.user_id == user.id, BrokerAccount.is_enabled == True)
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
                    "generated_at": datetime.now(timezone.utc).isoformat(),
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
        now = datetime.now(timezone.utc)
        if period and period.strip().lower() == "ytd":
            query = query.filter(func.extract("year", PortfolioSnapshot.snapshot_date) == now.year)
        elif delta:
            since = now - delta
            # snapshot_date is naive UTC (DateTime without timezone). Comparing it to an
            # offset-aware bound can raise in the ORM/driver (same pattern as dividends/summary).
            since_naive = since.replace(tzinfo=None)
            query = query.filter(PortfolioSnapshot.snapshot_date >= since_naive)

        rows = query.all()
        series = []
        for row in rows:
            tv = row.total_value
            if tv is None:
                logger.warning(
                    "performance/history: null aggregate total_value for user_id=%s period=%s date=%s",
                    user.id,
                    period,
                    row.date,
                )
                continue
            series.append(
                {
                    "date": row.date.isoformat() if hasattr(row.date, "isoformat") else str(row.date),
                    "total_value": float(tv),
                }
            )

        return {
            "status": "success",
            "data": {
                "series": series,
                "period": period,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(
            "performance/history failed for user_id=%s period=%s: %s",
            user.id,
            period,
            e,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/balances", response_model=Dict[str, Any])
async def get_account_balances(
    account_id: Optional[int] = Query(None, description="Filter by broker account ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return latest account balance snapshot per broker account."""
    try:
        broker_ids = [
            r[0]
            for r in db.query(BrokerAccount.id)
            .filter(BrokerAccount.user_id == user.id, BrokerAccount.is_enabled == True)
            .all()
        ]
        if not broker_ids:
            return {"status": "success", "data": {"balances": []}}

        if account_id is not None:
            if account_id not in broker_ids:
                raise HTTPException(status_code=404, detail="Account not found")
            broker_ids = [account_id]

        balances = []
        for bid in broker_ids:
            bal = (
                db.query(AccountBalance)
                .filter(AccountBalance.broker_account_id == bid)
                .order_by(desc(AccountBalance.balance_date))
                .first()
            )
            if not bal:
                continue
            ba = db.query(BrokerAccount).filter(BrokerAccount.id == bid).first()
            balances.append({
                "account_id": bid,
                "broker": ba.broker.value if ba else None,
                "account_number": ba.account_number if ba else None,
                "balance_date": bal.balance_date.isoformat() if bal.balance_date else None,
                "cash_balance": bal.cash_balance,
                "total_cash_value": bal.total_cash_value,
                "settled_cash": bal.settled_cash,
                "available_funds": bal.available_funds,
                "net_liquidation": bal.net_liquidation,
                "gross_position_value": bal.gross_position_value,
                "equity": bal.equity,
                "buying_power": bal.buying_power,
                "initial_margin_req": bal.initial_margin_req,
                "maintenance_margin_req": bal.maintenance_margin_req,
                "cushion": bal.cushion,
                "leverage": bal.leverage,
                "daily_pnl": bal.daily_pnl,
                "unrealized_pnl": bal.unrealized_pnl,
                "realized_pnl": bal.realized_pnl,
                "accrued_dividend": bal.accrued_dividend,
                "accrued_interest": bal.accrued_interest,
                "margin_utilization_pct": bal.margin_utilization_pct,
            })

        return {"status": "success", "data": {"balances": balances}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"balances error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/margin-health", response_model=Dict[str, Any])
async def get_margin_health(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return margin health metrics from latest account balance: cushion, leverage, buying power, and warning flags."""
    try:
        broker_ids = [
            r[0]
            for r in db.query(BrokerAccount.id)
            .filter(BrokerAccount.user_id == user.id, BrokerAccount.is_enabled == True)
            .all()
        ]
        if not broker_ids:
            return {
                "status": "success",
                "data": {
                    "cushion": None,
                    "leverage": None,
                    "buying_power": None,
                    "maintenance_margin_req": None,
                    "margin_warning": False,
                    "margin_critical": False,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
            }

        balances = []
        for bid in broker_ids:
            bal = (
                db.query(AccountBalance)
                .filter(AccountBalance.broker_account_id == bid)
                .order_by(desc(AccountBalance.balance_date))
                .first()
            )
            if bal:
                balances.append(bal)

        if not balances:
            return {
                "status": "success",
                "data": {
                    "cushion": None,
                    "leverage": None,
                    "buying_power": None,
                    "maintenance_margin_req": None,
                    "margin_warning": False,
                    "margin_critical": False,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
            }

        cushions = [float(b.cushion or 0) for b in balances if b.cushion is not None]
        cushion = min(cushions) if cushions else None
        leverage = max(float(b.leverage or 0) for b in balances) if any(b.leverage is not None for b in balances) else None
        buying_power = sum(float(b.buying_power or 0) for b in balances)
        maintenance_margin_req = sum(float(b.maintenance_margin_req or 0) for b in balances)

        margin_warning = cushion is not None and cushion < 0.10
        margin_critical = cushion is not None and cushion < 0.05

        return {
            "status": "success",
            "data": {
                "cushion": round(cushion, 4) if cushion is not None else None,
                "leverage": round(leverage, 4) if leverage is not None else None,
                "buying_power": round(buying_power, 2),
                "maintenance_margin_req": round(maintenance_margin_req, 2),
                "margin_warning": margin_warning,
                "margin_critical": margin_critical,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"margin-health error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/pnl-summary", response_model=Dict[str, Any])
async def get_pnl_summary(
    account_id: Optional[str] = Query(
        None,
        description="Filter by broker account number; if numeric-only, also matches broker_accounts.id",
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return P&L summary: unrealized_pnl, realized_pnl, total_dividends, total_fees, total_return."""
    try:
        acct_ids = [
            r[0]
            for r in db.query(BrokerAccount.id)
            .filter(BrokerAccount.user_id == user.id, BrokerAccount.is_enabled == True)
            .all()
        ]
        if not acct_ids:
            return {
                "status": "success",
                "data": {
                    "unrealized_pnl": 0,
                    "realized_pnl": 0,
                    "total_dividends": 0,
                    "total_fees": 0,
                    "total_return": 0,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
            }

        filter_ref = (account_id or "").strip() or None
        filter_broker_pk: Optional[int] = None
        if filter_ref:
            ba_base = db.query(BrokerAccount).filter(
                BrokerAccount.user_id == user.id,
                BrokerAccount.is_enabled.is_(True),
            )
            if filter_ref.isdigit():
                acc = ba_base.filter(
                    or_(
                        BrokerAccount.account_number == filter_ref,
                        BrokerAccount.id == int(filter_ref),
                    )
                ).first()
            else:
                acc = ba_base.filter(BrokerAccount.account_number == filter_ref).first()
            if acc is None:
                raise HTTPException(status_code=404, detail="Account not found")
            filter_broker_pk = acc.id
            acct_ids = [filter_broker_pk]

        unrealized_q = db.query(func.coalesce(func.sum(Position.unrealized_pnl), 0)).filter(
            Position.user_id == user.id,
            Position.account_id.in_(acct_ids),
        )
        options_unrealized_q = db.query(func.coalesce(func.sum(Option.unrealized_pnl), 0)).filter(
            Option.user_id == user.id,
            Option.open_quantity != 0,
            Option.account_id.in_(acct_ids),
        )
        unrealized_row = unrealized_q.scalar()
        options_unrealized_row = options_unrealized_q.scalar()
        unrealized_pnl = float(unrealized_row or 0) + float(options_unrealized_row or 0)

        realized_row = (
            db.query(func.coalesce(func.sum(Trade.realized_pnl), 0))
            .filter(
                Trade.account_id.in_(acct_ids),
                Trade.realized_pnl.isnot(None),
                Trade.realized_pnl != 0,
            )
            .scalar()
        )
        realized_pnl = float(realized_row or 0)

        dividends_row = (
            db.query(func.coalesce(func.sum(Dividend.total_dividend), 0))
            .filter(Dividend.account_id.in_(acct_ids))
            .scalar()
        )
        total_dividends = float(dividends_row or 0)

        fee_types = (TransactionType.COMMISSION, TransactionType.OTHER_FEE, TransactionType.BROKER_INTEREST_PAID)
        fees_row = (
            db.query(func.coalesce(func.sum(func.abs(Transaction.amount)), 0))
            .filter(
                Transaction.account_id.in_(acct_ids),
                Transaction.transaction_type.in_(fee_types),
            )
            .scalar()
        )
        total_fees = float(fees_row or 0)

        total_return = realized_pnl + unrealized_pnl + total_dividends - total_fees

        return {
            "status": "success",
            "data": {
                "unrealized_pnl": round(unrealized_pnl, 2),
                "realized_pnl": round(realized_pnl, 2),
                "total_dividends": round(total_dividends, 2),
                "total_fees": round(total_fees, 2),
                "total_return": round(total_return, 2),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"pnl-summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/margin-interest", response_model=Dict[str, Any])
async def get_margin_interest(
    account_id: Optional[int] = Query(None, description="Filter by broker account ID"),
    period: str = Query("90d", description="30d, 90d, 1y, all"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return margin/interest accrual records for the user's accounts."""
    try:
        broker_ids = [
            r[0]
            for r in db.query(BrokerAccount.id)
            .filter(BrokerAccount.user_id == user.id, BrokerAccount.is_enabled == True)
            .all()
        ]
        if not broker_ids:
            return {"status": "success", "data": {"margin_interest": []}}

        if account_id is not None:
            if account_id not in broker_ids:
                raise HTTPException(status_code=404, detail="Account not found")
            broker_ids = [account_id]

        query = (
            db.query(MarginInterest)
            .filter(MarginInterest.broker_account_id.in_(broker_ids))
            .order_by(desc(MarginInterest.to_date))
        )

        delta = _parse_period(period)
        if delta:
            since = datetime.now(timezone.utc).date() - delta
            query = query.filter(MarginInterest.to_date >= since)

        rows = query.limit(200).all()
        items = []
        for m in rows:
            items.append({
                "id": m.id,
                "account_id": m.broker_account_id,
                "from_date": m.from_date.isoformat() if m.from_date else None,
                "to_date": m.to_date.isoformat() if m.to_date else None,
                "starting_balance": m.starting_balance,
                "interest_accrued": m.interest_accrued,
                "accrual_reversal": m.accrual_reversal,
                "ending_balance": m.ending_balance,
                "interest_rate": m.interest_rate,
                "daily_rate": m.daily_rate,
                "currency": m.currency,
                "interest_type": m.interest_type,
            })

        return {"status": "success", "data": {"margin_interest": items}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"margin-interest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dividends/summary")
async def get_dividend_summary(
    account_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dividend income analytics: trailing 12m, forward yield, top payers, upcoming ex-dates."""
    try:
        acct_ids = [a.id for a in db.query(BrokerAccount.id).filter(BrokerAccount.user_id == user.id, BrokerAccount.is_enabled == True).all()]
        if not acct_ids:
            return {"status": "success", "data": {}}

        now = datetime.now(timezone.utc)
        one_year_ago = now - timedelta(days=365)
        one_year_ago_date = one_year_ago.date()

        # Push date filter to SQL. pay_date is DateTime (nullable); Postgres
        # coerces both naive and aware values for comparison against the
        # naive boundary. The explicit isnot(None) guard is also enforced in
        # Python below (defence in depth for SQLite tests).
        trailing_divs = (
            db.query(Dividend)
            .filter(
                Dividend.account_id.in_(acct_ids),
                Dividend.pay_date.isnot(None),
                Dividend.pay_date >= one_year_ago.replace(tzinfo=None),
            )
            .all()
        )
        trailing_12m = sum(float(d.total_dividend or 0) for d in trailing_divs)

        by_sym: Dict[str, list] = {}
        for d in trailing_divs:
            by_sym.setdefault(d.symbol, []).append(d)

        top_payers = sorted(
            [
                {
                    "symbol": sym,
                    "annual_income": round(sum(float(d.total_dividend or 0) for d in ds), 2),
                    "payment_count": len(ds),
                }
                for sym, ds in by_sym.items()
            ],
            key=lambda x: -x["annual_income"],
        )[:5]

        total_mv = float(
            db.query(func.coalesce(func.sum(Position.market_value), 0))
            .filter(Position.account_id.in_(acct_ids))
            .scalar()
            or 0
        )
        fwd_yield = round((trailing_12m / total_mv * 100) if total_mv > 0 else 0, 2)

        monthly: Dict[str, float] = {}
        for d in trailing_divs:
            key = d.pay_date.strftime("%Y-%m") if d.pay_date else "unknown"
            monthly[key] = monthly.get(key, 0) + float(d.total_dividend or 0)

        monthly_income = [{"month": k, "amount": round(v, 2)} for k, v in sorted(monthly.items())]

        upcoming: list = []
        for sym, ds in by_sym.items():
            ex_utc: List[datetime] = []
            for d in ds:
                if not d.ex_date:
                    continue
                ed = d.ex_date
                if isinstance(ed, datetime):
                    ex_utc.append(_datetime_as_utc_aware(ed))
                elif isinstance(ed, date):
                    ex_utc.append(
                        datetime.combine(ed, datetime.min.time(), tzinfo=timezone.utc)
                    )
            ex_dates = sorted(ex_utc, reverse=True)
            if len(ex_dates) >= 2:
                gap = (ex_dates[0] - ex_dates[1]).days
                est_next = ex_dates[0] + timedelta(days=gap)
                now_date = now.date()
                est_next_date = est_next.date()
                if est_next_date >= now_date and (est_next_date - now_date).days <= 60:
                    per_share = [float(d.dividend_per_share or 0) for d in ds if d.dividend_per_share]
                    upcoming.append({
                        "symbol": sym,
                        "est_ex_date": est_next.isoformat(),
                        "est_per_share": round(sum(per_share) / len(per_share), 4) if per_share else 0,
                    })

        return {
            "status": "success",
            "data": {
                "trailing_12m_income": round(trailing_12m, 2),
                "estimated_forward_yield_pct": fwd_yield,
                "top_payers": top_payers,
                "upcoming_ex_dates": upcoming[:5],
                "monthly_income": monthly_income,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"dividend-summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/live-summary")
async def get_live_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Live account summary from IB Gateway, falling back to DB."""
    try:
        is_live = False
        summary = {}

        try:
            from backend.services.clients.ibkr_client import ibkr_client
            if ibkr_client.ib and ibkr_client.ib.isConnected():
                gw_data = ibkr_client.get_account_summary()
                if gw_data and gw_data.get("net_liquidation"):
                    summary = gw_data
                    is_live = True
        except Exception as e:
            logger.warning("Live summary: IB Gateway fetch failed, using DB fallback: %s", e)

        if not is_live:
            acct_ids = [a.id for a in db.query(BrokerAccount.id).filter(BrokerAccount.user_id == user.id, BrokerAccount.is_enabled == True).all()]
            if acct_ids:
                bal = (
                    db.query(AccountBalance)
                    .filter(AccountBalance.broker_account_id.in_(acct_ids))
                    .order_by(AccountBalance.balance_date.desc())
                    .first()
                )
                if bal:
                    summary = {
                        "net_liquidation": float(bal.net_liquidation or 0),
                        "buying_power": float(bal.buying_power or 0),
                        "margin_used": float(bal.margin_used or 0) if hasattr(bal, "margin_used") else 0,
                        "available_funds": float(bal.available_funds or 0) if hasattr(bal, "available_funds") else 0,
                        "cushion": float(bal.cushion or 0) if hasattr(bal, "cushion") else 0,
                    }

        summary["is_live"] = is_live
        return {"status": "success", "data": summary}
    except Exception as e:
        logger.error(f"live-summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-metrics")
async def get_risk_metrics(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Computed risk metrics: beta, volatility, sharpe, concentration."""
    try:
        metrics = portfolio_analytics_service.compute_risk_metrics(db, user_id=user.id)
        return {"status": "success", "data": metrics}
    except Exception as e:
        logger.error(f"risk-metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twr")
async def get_twr(
    period: str = Query("1y", description="1y, ytd, all"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Time-Weighted Return."""
    try:
        days = 365
        if period == "ytd":
            days = (datetime.now(timezone.utc) - datetime(datetime.now(timezone.utc).year, 1, 1)).days
        elif period == "all":
            days = 3650
        result = portfolio_analytics_service.compute_twr(db, user_id=user.id, period_days=days)
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"twr error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sector-attribution")
async def get_sector_attribution(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Performance attribution by sector."""
    try:
        result = portfolio_analytics_service.compute_sector_attribution(db, user_id=user.id)
        return {"status": "success", "data": {"sectors": result}}
    except Exception as e:
        logger.error(f"sector-attribution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
