"""Live portfolio endpoint to satisfy frontend `/api/v1/portfolio/live` requests.
Uses IB Gateway for real-time data when connected; falls back to DB when offline.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models import BrokerAccount
from app.models.account_balance import AccountBalance
from app.models.broker_account import BrokerType
from app.models.position import Position
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

# IBKR account summary tags we care about
LIVE_SUMMARY_TAGS = [
    "DailyPnL",
    "UnrealizedPnL",
    "NetLiquidation",
    "BuyingPower",
    "MaintMarginReq",
    "AvailableFunds",
]


def _float_from_summary(summary: dict, tag: str) -> float:
    """Extract float from IBKR account summary item."""
    item = summary.get(tag)
    if not item:
        return 0.0
    try:
        return float(item.get("value", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


@router.get("/live/summary", response_model=dict[str, Any])
async def get_live_summary(
    account_id: str | None = Query(None, description="Filter by account number"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Live account summary (DailyPnL, UnrealizedPnL, NetLiquidation, BuyingPower, MaintMarginReq).
    Uses IB Gateway when connected; falls back to DB when offline."""
    try:
        from app.services.clients.ibkr_client import ibkr_client

        is_live = False
        summary: dict[str, Any] = {}

        # Try IB Gateway when connected (no auto-connect to avoid blocking)
        if ibkr_client.is_connected():
            try:
                accounts = ibkr_client.managed_accounts or []
                if not accounts:
                    accounts = await ibkr_client.discover_managed_accounts()
                if account_id:
                    accounts = [a for a in accounts if a == account_id]
                if not accounts:
                    rows = (
                        db.query(BrokerAccount.account_number)
                        .filter(BrokerAccount.broker == BrokerType.IBKR)
                        .distinct()
                        .all()
                    )
                    accounts = [r[0] for r in rows if r[0]]

                net_liq = 0.0
                daily_pnl = 0.0
                unrealized_pnl = 0.0
                buying_power = 0.0
                maint_margin = 0.0
                available_funds = 0.0

                for acc in accounts:
                    gw = await ibkr_client.get_account_summary(acc)
                    if not gw:
                        continue
                    net_liq += _float_from_summary(gw, "NetLiquidation")
                    daily_pnl += _float_from_summary(gw, "DailyPnL")
                    unrealized_pnl += _float_from_summary(gw, "UnrealizedPnL")
                    buying_power += _float_from_summary(gw, "BuyingPower")
                    maint_margin += _float_from_summary(gw, "MaintMarginReq")
                    available_funds += _float_from_summary(gw, "AvailableFunds")
                    is_live = True

                if is_live:
                    summary = {
                        "net_liquidation": net_liq,
                        "daily_pnl": daily_pnl,
                        "unrealized_pnl": unrealized_pnl,
                        "buying_power": buying_power,
                        "maint_margin_req": maint_margin,
                        "available_funds": available_funds,
                    }
            except Exception as e:
                logger.warning("IB Gateway summary failed, falling back to DB: %s", e)

        if not is_live:
            q = (
                db.query(AccountBalance)
                .join(BrokerAccount, AccountBalance.broker_account_id == BrokerAccount.id)
                .filter(BrokerAccount.user_id == current_user.id, BrokerAccount.is_enabled == True)
            )
            if account_id:
                q = q.filter(BrokerAccount.account_number == account_id)
            bal = q.order_by(AccountBalance.balance_date.desc()).first()
            if bal:
                summary = {
                    "net_liquidation": float(bal.net_liquidation or 0),
                    "daily_pnl": float(bal.daily_pnl or 0),
                    "unrealized_pnl": float(bal.unrealized_pnl or 0),
                    "buying_power": float(bal.buying_power or 0),
                    "maint_margin_req": float(bal.maintenance_margin_req or 0),
                    "available_funds": float(bal.available_funds or 0),
                }

        summary["is_live"] = is_live
        return {"status": "success", "data": summary}
    except Exception as e:
        logger.error("live/summary error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/live/positions", response_model=dict[str, Any])
async def get_live_positions(
    account_id: str | None = Query(None, description="Filter by account number"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Live positions with real-time market values from IB Gateway when connected.
    Falls back to DB positions when offline."""
    try:
        from app.services.clients.ibkr_client import ibkr_client

        is_live = False
        positions: list[dict[str, Any]] = []

        if ibkr_client.is_connected():
            try:
                accounts = ibkr_client.managed_accounts or []
                if not accounts:
                    accounts = await ibkr_client.discover_managed_accounts()
                if account_id:
                    accounts = [a for a in accounts if a == account_id]
                if not accounts:
                    rows = (
                        db.query(BrokerAccount.account_number)
                        .filter(BrokerAccount.broker == BrokerType.IBKR)
                        .distinct()
                        .all()
                    )
                    accounts = [r[0] for r in rows if r[0]]

                for acc in accounts:
                    live_pos = await ibkr_client.get_positions(acc)
                    for p in live_pos:
                        positions.append(
                            {
                                "account": p.get("account"),
                                "symbol": p.get("symbol"),
                                "position": p.get("position"),
                                "position_value": p.get("market_value"),
                                "unrealized_pnl": p.get("unrealized_pnl"),
                                "contract_type": p.get("contract_type"),
                                "currency": p.get("currency", "USD"),
                            }
                        )
                        is_live = True
            except Exception as e:
                logger.warning("IB Gateway positions failed, falling back to DB: %s", e)

        if not is_live:
            query = (
                db.query(Position)
                .join(BrokerAccount, Position.account_id == BrokerAccount.id)
                .filter(Position.user_id == current_user.id, BrokerAccount.is_enabled == True)
            )
            if account_id:
                query = query.filter(BrokerAccount.account_number == account_id)
            for p in query.all():
                acc = db.query(BrokerAccount).filter(BrokerAccount.id == p.account_id).first()
                acc_key = acc.account_number if acc else ""
                positions.append(
                    {
                        "account": acc_key,
                        "symbol": p.symbol,
                        "position": float(p.quantity or 0),
                        "position_value": float(p.market_value or 0),
                        "unrealized_pnl": float(p.unrealized_pnl or 0),
                        "contract_type": (
                            "OPT"
                            if (p.instrument_type or "").upper().startswith("OPTION")
                            else "STK"
                        ),
                        "currency": "USD",
                    }
                )

        return {
            "status": "success",
            "data": {"positions": positions, "is_live": is_live},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("live/positions error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/live", response_model=dict[str, Any])
async def get_live_portfolio(
    account_id: str | None = Query(
        None, description="Filter by account number (e.g., IBKR_ACCOUNT)"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregated live portfolio snapshot for React dashboard."""
    try:
        query = (
            db.query(Position)
            .join(BrokerAccount, Position.account_id == BrokerAccount.id)
            .filter(Position.user_id == current_user.id, BrokerAccount.is_enabled == True)
        )
        if account_id:
            query = query.filter(BrokerAccount.account_number == account_id)
        positions_models = query.all()

        acct_ids = {p.account_id for p in positions_models}
        accounts_map = {
            a.id: a for a in db.query(BrokerAccount).filter(BrokerAccount.id.in_(acct_ids)).all()
        }

        # Build accounts mapping like Snowball Analytics style expected by frontend
        accounts: dict[str, Any] = {}
        for p in positions_models:
            acc = accounts_map.get(p.account_id)
            if not acc:
                continue
            acc_key = acc.account_number
            if acc_key not in accounts:
                accounts[acc_key] = {
                    "account_summary": {
                        "account_name": getattr(acc, "account_name", acc.account_number),
                        "account_type": (
                            acc.account_type.value
                            if getattr(acc, "account_type", None)
                            else "taxable"
                        ),
                        "broker": (acc.broker.value if getattr(acc, "broker", None) else "IBKR"),
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
                        if p.instrument_type and p.instrument_type.upper().startswith("OPTION")
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
        total_value = sum(acc["account_summary"]["net_liquidation"] for acc in accounts.values())
        total_unreal = sum(acc["account_summary"]["unrealized_pnl"] for acc in accounts.values())
        summary = {
            "total_market_value": total_value,
            "total_cost_basis": None,
            "unrealized_pnl": total_unreal,
            "unrealized_pnl_pct": ((total_unreal / total_value * 100) if total_value else 0.0),
        }

        return {
            "accounts": accounts,
            "portfolio_summary": summary,
            "last_updated": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error(f"❌ Live portfolio error for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
