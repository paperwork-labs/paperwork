"""Portfolio options endpoints (moved from options.py)."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional
import logging

from app.database import get_db
from app.api.dependencies import get_admin_user, get_current_user
from app.api.middleware.response_cache import redis_response_cache
from app.models import BrokerAccount, Option
from app.models.broker_account import BrokerType
from app.models.user import User
from app.services.silver.market.options_chain_service import (
    get_chain as get_options_chain,
    probe_sources as probe_chain_sources,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Shared options-portfolio builder
# ---------------------------------------------------------------------------
#
# This pure helper is called by both the /unified/portfolio and
# /unified/summary endpoints. Previously the summary endpoint called the
# portfolio endpoint function directly, which triggered a TypeError
# ("missing 1 required positional argument: 'request'") because the
# portfolio endpoint's signature starts with ``request: Request``. That
# surfaced as HTTP 500 on ``GET /portfolio/options/unified/summary`` —
# the root cause of the founder-reported "Failed to load options" card
# on the Positions subtab.
#
# Positions are read ONCE, filtered only by ``user_id`` and optional
# ``account_number``. The filter is broker-agnostic: any broker whose
# sync service wrote an ``Option`` row for the user is surfaced.


def _compute_options_portfolio(
    db: Session, user_id: int, account_id: Optional[str]
) -> Dict[str, Any]:
    """Build the unified options portfolio payload for a single user.

    Returns a dict with ``positions``, ``underlyings``, ``filtering``,
    plus per-broker ``counters`` (``success``, ``skipped_no_config``,
    ``failed``) for observability (per `no-silent-fallback.mdc`).
    """

    query = (
        db.query(Option)
        .join(BrokerAccount, Option.account_id == BrokerAccount.id)
        .filter(Option.user_id == user_id, Option.open_quantity != 0)
    )
    if account_id:
        query = query.filter(BrokerAccount.account_number == account_id)

    positions_models = query.all()

    opt_acct_ids = {p.account_id for p in positions_models}
    opt_accounts_map = {
        a.id: a
        for a in db.query(BrokerAccount)
        .filter(BrokerAccount.id.in_(opt_acct_ids))
        .all()
    }

    def _days_to_expiry(exp: Optional[date]) -> int:
        try:
            if not exp:
                return 0
            return (exp - date.today()).days
        except Exception as e:
            logger.warning("days_to_expiry calculation failed: %s", e)
            return 0

    positions: List[Dict[str, Any]] = []
    underlyings: Dict[str, Dict[str, Any]] = {}
    per_broker_counters: Dict[str, Dict[str, int]] = {}
    for p in positions_models:
        acc = opt_accounts_map.get(p.account_id)
        account_number = acc.account_number if acc else None
        broker_value = acc.broker.value if acc and acc.broker else None
        qty = int(p.open_quantity or 0)
        abs_qty = abs(qty) or 1
        mult = float(p.multiplier or 100)
        cur_price = float(p.current_price or 0)
        total_cost = float(p.total_cost or 0)
        mv = cur_price * abs_qty * mult
        try:
            if mv == 0 and p.total_cost is not None:
                mv = float(abs(p.total_cost))
                if cur_price == 0:
                    cur_price = mv / (abs_qty * mult)
        except Exception as e:
            logger.warning(
                "Options position market value / price derivation failed "
                "(position id=%s): %s",
                getattr(p, "id", None),
                e,
            )
        u_pnl = float(p.unrealized_pnl or 0)
        if u_pnl == 0 and total_cost:
            try:
                u_pnl = mv - abs(total_cost)
            except Exception as e:
                logger.warning(
                    "Options unrealized PnL fallback failed "
                    "(position id=%s): %s",
                    getattr(p, "id", None),
                    e,
                )
        avg_cost = abs(total_cost) / (abs_qty * mult) if qty else 0.0
        sym_value = p.symbol or ""
        if not sym_value:
            try:
                exp = p.expiry_date.isoformat() if p.expiry_date else ""
                sym_value = (
                    f"{p.underlying_symbol or ''} "
                    f"{str(p.option_type or '').upper()} "
                    f"${float(p.strike_price or 0)} {exp}"
                )
            except Exception as e:
                logger.warning(
                    "Could not compose OCC-like symbol for option id=%s: %s",
                    getattr(p, "id", None),
                    e,
                )
                sym_value = p.underlying_symbol or "UNKNOWN"
        pos: Dict[str, Any] = {
            "id": p.id,
            "symbol": sym_value,
            "underlying_symbol": p.underlying_symbol or "",
            "strike_price": float(p.strike_price or 0),
            "expiration_date": (
                p.expiry_date.isoformat() if p.expiry_date else None
            ),
            "option_type": (p.option_type or "").lower(),
            "quantity": qty,
            "average_open_price": avg_cost,
            "current_price": cur_price,
            "market_value": mv,
            "unrealized_pnl": u_pnl,
            "unrealized_pnl_pct": (
                (u_pnl / (float(p.total_cost or 0)) * 100)
                if (p.total_cost and float(p.total_cost) != 0)
                else 0.0
            ),
            "day_pnl": 0.0,
            "account_id": p.account_id,
            "account_number": account_number,
            "broker": broker_value,
            "days_to_expiration": _days_to_expiry(p.expiry_date),
            "multiplier": mult,
            "delta": float(p.delta) if p.delta is not None else None,
            "gamma": float(p.gamma) if p.gamma is not None else None,
            "theta": float(p.theta) if p.theta is not None else None,
            "vega": float(p.vega) if p.vega is not None else None,
            "implied_volatility": (
                float(p.implied_volatility)
                if p.implied_volatility is not None
                else None
            ),
            "underlying_price": (
                float(p.underlying_price) if p.underlying_price is not None else None
            ),
            "cost_basis": float(p.total_cost) if p.total_cost else None,
            "realized_pnl": (
                float(p.realized_pnl) if p.realized_pnl is not None else None
            ),
            "commission": (
                float(p.commission) if p.commission is not None else None
            ),
            "last_updated": (
                p.updated_at or p.last_updated or datetime.now(timezone.utc)
            ).isoformat(),
        }
        positions.append(pos)
        if broker_value:
            bucket = per_broker_counters.setdefault(
                broker_value, {"success": 0, "skipped_no_config": 0, "failed": 0}
            )
            bucket["success"] += 1

        u_sym = pos["underlying_symbol"] or "UNKNOWN"
        if u_sym not in underlyings:
            underlyings[u_sym] = {
                "calls": [],
                "puts": [],
                "total_value": 0.0,
                "total_pnl": 0.0,
            }
        (
            underlyings[u_sym]["calls"]
            if pos["option_type"] == "call"
            else underlyings[u_sym]["puts"]
        ).append(pos)
        underlyings[u_sym]["total_value"] += pos["market_value"]
        underlyings[u_sym]["total_pnl"] += pos["unrealized_pnl"]

    return {
        "positions": positions,
        "underlyings": underlyings,
        "filtering": {
            "applied": bool(account_id),
            "account_id": account_id,
        },
        "broker_counters": per_broker_counters,
    }


@router.get("/accounts", response_model=Dict[str, Any])
@redis_response_cache(ttl_seconds=30)
async def get_option_accounts(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return list of the user's broker accounts that currently hold or allow options.

    An account is considered an "options account" if either:
      * it is flagged ``options_enabled`` (trading authorization has been
        explicitly recorded), OR
      * it currently holds at least one open option position.

    This dual criterion avoids hiding accounts whose sync path did not set
    ``options_enabled`` (Schwab, IBKR, Tastytrade all omit the flag during
    their option sync). Without this, users see "no options accounts"
    despite having synced option rows on disk.
    """
    try:
        from sqlalchemy import exists, or_

        has_open_options = (
            exists()
            .where(Option.account_id == BrokerAccount.id)
            .where(Option.open_quantity != 0)
        )
        accounts = (
            db.query(BrokerAccount)
            .filter(
                BrokerAccount.user_id == user.id,
                BrokerAccount.is_enabled == True,  # noqa: E712
                or_(BrokerAccount.options_enabled.is_(True), has_open_options),
            )
            .all()
        )

        result = []
        for acc in accounts:
            open_opt_count = (
                db.query(Option)
                .filter(
                    Option.account_id == acc.id,
                    Option.open_quantity != 0,
                )
                .count()
            )
            result.append(
                {
                    "account_number": acc.account_number,
                    "broker": acc.broker.value,
                    "account_type": acc.account_type.value,
                    "open_option_positions": open_opt_count,
                }
            )
        return {"status": "success", "data": {"accounts": result}}
    except Exception as e:
        logger.error(f"❌ Options accounts error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/unified/portfolio")
@redis_response_cache(ttl_seconds=30)
async def get_unified_options_portfolio(
    request: Request,
    account_id: Optional[str] = Query(
        None, description="Filter by account number (e.g., IBKR_ACCOUNT)"
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Unified options positions (all brokers) with optional account filter."""
    try:
        data = _compute_options_portfolio(db, user.id, account_id)
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error("Options unified portfolio error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/unified/summary")
async def get_unified_options_summary(
    account_id: Optional[str] = Query(
        None, description="Filter by account number (e.g., IBKR_ACCOUNT)"
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Aggregate summary for options positions (all brokers)."""
    try:
        # Build the portfolio payload directly from the shared helper. This
        # replaces the previous call to ``get_unified_options_portfolio``
        # (the decorated FastAPI handler) which raised TypeError because the
        # Request argument could not be supplied from Python code. That bug
        # manifested as HTTP 500 on this endpoint, which bubbled up to the
        # frontend as the "Failed to load options" card on the Positions
        # subtab — the screenshot bug reported by the founder.
        portfolio = _compute_options_portfolio(db, user.id, account_id)
        positions: List[Dict[str, Any]] = portfolio["positions"]
        total_value = sum(abs(p.get("market_value", 0.0)) for p in positions)
        total_pnl = sum(p.get("unrealized_pnl", 0.0) for p in positions)
        calls = [p for p in positions if p.get("option_type") == "call"]
        puts = [p for p in positions if p.get("option_type") == "put"]

        summary = {
            "total_positions": len(positions),
            "total_market_value": total_value,
            "total_unrealized_pnl": total_pnl,
            "total_unrealized_pnl_pct": (
                (total_pnl / total_value * 100) if total_value else 0.0
            ),
            "total_day_pnl": 0.0,
            "total_day_pnl_pct": 0.0,
            "calls_count": len(calls),
            "puts_count": len(puts),
            "expiring_this_week": sum(
                1 for p in positions if (p.get("days_to_expiration", 0) <= 7)
            ),
            "expiring_this_month": sum(
                1 for p in positions if (p.get("days_to_expiration", 0) <= 30)
            ),
            "underlyings_count": len(portfolio["underlyings"]),
            "avg_days_to_expiration": (
                (
                    sum(p.get("days_to_expiration", 0) for p in positions)
                    / len(positions)
                )
                if positions
                else 0
            ),
            "net_delta": sum(
                (p.get("delta") or 0) * p.get("quantity", 0)
                for p in positions
            ),
            "net_theta": sum(
                (p.get("theta") or 0) * p.get("quantity", 0) * p.get("multiplier", 100)
                for p in positions
            ),
            "underlyings": list(portfolio["underlyings"].keys()),
        }
        return {
            "status": "success",
            "data": {
                "summary": summary,
                "filtering": portfolio["filtering"],
                "broker_counters": portfolio["broker_counters"],
            },
        }
    except Exception as e:
        logger.error("Options summary error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chain/sources", response_model=Dict[str, Any])
async def get_option_chain_sources(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Report which option-chain data sources are available for this user.

    Used by the frontend to decide whether the chain tab should render data,
    an empty state, or a broker-connection CTA — without hardcoding any
    single broker (e.g., IBKR) into the UI.
    """
    try:
        sources = probe_chain_sources(db=db, user_id=user.id)
        any_available = any(s["available"] for s in sources)
        return {
            "status": "success",
            "data": {
                "sources": sources,
                "any_available": any_available,
            },
        }
    except Exception as e:
        logger.error("Option chain sources probe failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chain/{symbol}", response_model=Dict[str, Any])
async def get_option_chain(
    symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch an option chain from the first available source.

    Source priority: IBKR gateway (if connected), then Yahoo Finance
    (yfinance; free, broker-agnostic). Never returns a silent empty — if
    no source is available we return an explicit ``source: "none"``
    payload so the frontend can render a broker-honest empty state.
    """
    try:
        result = await get_options_chain(symbol, user_id=user.id, db=db)
        return {"status": "success", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Option chain error for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=Dict[str, Any])
async def get_options_history(
    account_id: Optional[str] = Query(None, description="Filter by account number"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return exercised/assigned/expired options history for the authenticated user."""
    try:
        from sqlalchemy import or_

        query = db.query(Option).filter(Option.user_id == user.id)
        if account_id:
            acct = (
                db.query(BrokerAccount)
                .filter(
                    BrokerAccount.account_number == account_id,
                    BrokerAccount.user_id == user.id,
                )
                .first()
            )
            if not acct:
                return {
                    "status": "success",
                    "data": {"history": [], "total": 0},
                }
            query = query.filter(Option.account_id == acct.id)

        query = query.filter(
            or_(
                Option.open_quantity == 0,
                Option.open_quantity.is_(None),
            )
        )

        options = query.order_by(Option.expiry_date.desc()).all()

        history_items = []
        for opt in options:
            exercised = getattr(opt, "exercised_quantity", 0) or 0
            assigned = getattr(opt, "assigned_quantity", 0) or 0
            event_type = (
                "exercised" if exercised > 0
                else "assigned" if assigned > 0
                else "expired"
            )
            closed_qty = int(exercised + assigned)
            history_items.append({
                "id": opt.id,
                "symbol": opt.symbol,
                "underlying_symbol": opt.underlying_symbol,
                "option_type": opt.option_type,
                "strike_price": float(opt.strike_price) if opt.strike_price else None,
                "expiry_date": opt.expiry_date.isoformat() if opt.expiry_date else None,
                "event_type": event_type,
                "exercised_quantity": exercised,
                "assigned_quantity": assigned,
                "original_quantity": float(closed_qty) if closed_qty > 0 else None,
                "cost_basis": float(opt.total_cost or 0),
                "realized_pnl": float(opt.realized_pnl or 0),
                "commission": float(opt.commission or 0),
                "data_source": opt.data_source,
            })

        return {
            "status": "success",
            "data": {
                "history": history_items,
                "total": len(history_items),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Options history error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gateway-status", response_model=Dict[str, Any])
async def get_gateway_status(
    user: User = Depends(get_current_user),
):
    """Check IB Gateway connection status."""
    try:
        from app.services.clients.ibkr_client import ibkr_client, IBKR_AVAILABLE

        if not IBKR_AVAILABLE:
            return {
                "status": "success",
                "data": {
                    "connected": False,
                    "available": False,
                    "message": "ib_insync not installed",
                },
            }

        status = ibkr_client.get_status()
        return {
            "status": "success",
            "data": {
                "connected": ibkr_client.is_connected(),
                "available": True,
                "host": ibkr_client.host,
                "port": ibkr_client.port,
                "client_id": ibkr_client.client_id,
                "accounts": status.get("accounts", []),
                "vnc_url": "http://localhost:6080",
            },
        }
    except Exception as e:
        return {
            "status": "success",
            "data": {"connected": False, "available": False, "error": str(e)},
        }


@router.post("/gateway-connect")
async def gateway_connect(
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Manually trigger IB Gateway reconnection.

    Loads per-user gateway credentials from the vault when available,
    falling back to global env vars.
    """
    import asyncio
    import concurrent.futures

    gw_host: str | None = None
    gw_port: int | None = None
    gw_client_id: int | None = None
    try:
        from app.services.portfolio.account_credentials_service import account_credentials_service
        ibkr_accounts = (
            db.query(BrokerAccount)
            .filter(
                BrokerAccount.broker == BrokerType.IBKR,
                BrokerAccount.is_enabled.is_(True),
            )
            .all()
        )
        for acct in ibkr_accounts:
            gw = account_credentials_service.get_ibkr_gateway_credentials(acct.id, db)
            if gw:
                gw_host = gw.get("gateway_host") or gw_host
                gw_port = int(gw["gateway_port"]) if gw.get("gateway_port") else gw_port
                gw_client_id = int(gw["gateway_client_id"]) if gw.get("gateway_client_id") else gw_client_id
                break
    except Exception as exc:
        logger.debug("No per-user gateway creds found, using defaults: %s", exc)

    def _sync_probe():
        """Probe gateway connectivity in a worker thread without keeping the IB instance."""
        from ib_insync import IB, util
        util.patchAsyncio()

        from app.services.clients.ibkr_client import ibkr_client

        host = gw_host or ibkr_client.host
        port = gw_port or ibkr_client.port
        cid = gw_client_id or ibkr_client.client_id

        ib = IB()
        try:
            ib.connect(host=host, port=port, clientId=cid, timeout=15, readonly=True)
            ok = ib.isConnected()
            managed = ib.managedAccounts() or [] if ok else []
            ib.disconnect()
            return ok, host, port, cid, managed
        except Exception as e:
            logger.warning(
                "IBKR gateway connectivity probe failed (host=%s port=%s client_id=%s): %s",
                host,
                port,
                cid,
                e,
            )
            try:
                ib.disconnect()
            except Exception:
                pass  # Best-effort cleanup; connection may not exist
            return False, host, port, cid, []

    try:
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            ok, host, port, cid, managed = await loop.run_in_executor(pool, _sync_probe)

        if ok:
            from app.services.clients.ibkr_client import ibkr_client
            ibkr_client.host = host
            ibkr_client.port = port
            ibkr_client.client_id = cid
            ibkr_client.managed_accounts = managed
            ibkr_client.connection_health["status"] = "connected"
            ibkr_client.retry_count = 0
            ibkr_client.connected = False

        return {"status": "connected" if ok else "failed", "connected": ok}
    except Exception as e:
        return {"status": "error", "error": str(e), "connected": False}
