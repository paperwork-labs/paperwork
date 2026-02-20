"""
AxiomFolio V1 - Clean Portfolio Routes
Replaces the MASSIVE 168KB portfolio.py with focused, single-responsibility endpoints.

BEFORE: 168KB file doing EVERYTHING
AFTER: Clean, focused endpoints with proper separation of concerns
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import logging
from datetime import datetime, timedelta

# dependencies
from backend.database import get_db
from backend.models.user import User
from backend.models import BrokerAccount

# Auth dependency (to be implemented)
from backend.api.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class FlexSyncRequest(BaseModel):
    account_id: str


# =============================================================================
# TAX LOT ENDPOINTS (Clean & Focused)
# =============================================================================


@router.get("/tax-lots")
async def get_tax_lots(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    account_id: Optional[str] = Query(None, description="Filter by account number"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get user's tax lots.
    CLEAN: Only tax lot data, optionally filtered by symbol.
    """
    try:
        from backend.services.portfolio.tax_lot_service import TaxLotService

        tls = TaxLotService(db)
        tax_lots_models = []
        if account_id:
            # Map human account_number to internal broker_account.id
            acc = (
                db.query(BrokerAccount)
                .filter(
                    BrokerAccount.user_id == user.id,
                    BrokerAccount.account_number == account_id,
                )
                .first()
            )
            if not acc:
                raise HTTPException(status_code=404, detail="Account not found")
            tax_lots_models = await tls.get_tax_lots_for_account(
                user.id, acc.id, symbol=symbol
            )
        else:
            tax_lots_models = await tls.get_tax_lots_for_user(user.id, symbol=symbol)
        # Serialize for JSON
        tax_lots = []
        for tl in tax_lots_models:
            tax_lots.append(
                {
                    "lot_id": tl.id,
                    "symbol": tl.symbol,
                    "quantity": float(tl.quantity or 0),
                    "cost_per_share": (
                        float(tl.cost_per_share or 0)
                        if tl.cost_per_share is not None
                        else 0
                    ),
                    "acquisition_date": (
                        tl.acquisition_date.isoformat() if tl.acquisition_date else None
                    ),
                    "days_held": getattr(tl, "holding_period_days", 0),
                    "is_long_term": bool(getattr(tl, "is_long_term", False)),
                }
            )

        return {
            "user_id": user.id,
            "symbol_filter": symbol,
            "account_filter": account_id,
            "tax_lots": tax_lots,
            "total_lots": len(tax_lots),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Tax lots error for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tax-lots/summary")
async def get_tax_lots_summary(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get tax lots summary by symbol.
    CLEAN: Only summary data, properly aggregated.
    """
    try:
        from backend.services.portfolio.csv_import_service import (
            get_user_tax_lots_summary,
        )

        summary = await get_user_tax_lots_summary(user.id)

        return summary

    except Exception as e:
        logger.error(f"❌ Tax lots summary error for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# TRANSACTION ENDPOINTS (Clean & Focused)
# =============================================================================


@router.get("/statements")
async def get_statements(
    days: int = Query(30, ge=1, le=3650),
    user_id: int | None = Query(None, description="User ID (optional)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return unified transaction statements for last N days to power Transactions.tsx."""
    try:
        from backend.models.transaction import Transaction

        # resolve user
        user = (
            db.query(User).first()
            if user_id is None
            else db.query(User).filter(User.id == user_id).first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        cutoff = datetime.utcnow() - timedelta(days=days)

        q = (
            db.query(Transaction)
            .filter(
                Transaction.account_id.in_(
                    db.query(BrokerAccount.id).filter(BrokerAccount.user_id == user.id)
                ),
                Transaction.transaction_date >= cutoff,
            )
            .order_by(Transaction.transaction_date.desc())
        )
        rows = q.all()

        account_ids = {t.account_id for t in rows}
        accounts_by_id = {
            a.id: a
            for a in db.query(BrokerAccount).filter(
                BrokerAccount.id.in_(account_ids)
            ).all()
        }

        txs = []
        for t in rows:
            is_buy = (
                t.transaction_type.name if t.transaction_type else ""
            ).upper() == "BUY"
            is_sell = (
                t.transaction_type.name if t.transaction_type else ""
            ).upper() == "SELL"
            acc = accounts_by_id.get(t.account_id)
            txs.append(
                {
                    "id": t.id,
                    "date": (
                        t.transaction_date.date().isoformat()
                        if t.transaction_date
                        else None
                    ),
                    "time": (
                        t.transaction_date.time().isoformat(timespec="seconds")
                        if t.transaction_date
                        else None
                    ),
                    "symbol": t.symbol,
                    "description": t.description,
                    "type": (
                        "BUY"
                        if is_buy
                        else (
                            "SELL"
                            if is_sell
                            else (
                                t.transaction_type.name
                                if t.transaction_type
                                else "OTHER"
                            )
                        )
                    ),
                    "action": t.action,
                    "quantity": float(t.quantity or 0),
                    "price": float(t.trade_price or 0),
                    "amount": float(t.amount or 0),
                    "commission": float(t.commission or 0),
                    "fees": float(
                        (t.other_fees or 0)
                        + (t.third_party_commission or 0)
                        + (t.clearing_commission or 0)
                    ),
                    "net_amount": float(t.net_amount or 0),
                    "currency": t.currency,
                    "exchange": t.listing_exchange,
                    "order_id": t.order_id,
                    "execution_id": t.execution_id,
                    "contract_type": t.asset_category,
                    "account": acc.account_number if acc else None,
                    "settlement_date": (
                        t.settlement_date.isoformat() if t.settlement_date else None
                    ),
                    "source": t.source,
                }
            )

        buys = [x for x in txs if x["type"] == "BUY"]
        sells = [x for x in txs if x["type"] == "SELL"]
        summary = {
            "total_transactions": len(txs),
            "total_value": sum(abs(x["amount"]) for x in txs),
            "total_commission": sum(x["commission"] for x in txs),
            "total_fees": sum(x["fees"] for x in txs),
            "buy_count": len(buys),
            "sell_count": len(sells),
            "date_range": days,
            "net_buy_value": sum(abs(x["amount"]) for x in buys),
            "net_sell_value": sum(abs(x["amount"]) for x in sells),
        }

        return {"status": "success", "data": {"transactions": txs, "summary": summary}}
    except Exception as e:
        logger.error(f"❌ Statements error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FLEXQUERY ENDPOINTS (Official IBKR Tax Lots)
# =============================================================================


@router.get("/flexquery/status")
async def get_flexquery_status(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get FlexQuery configuration status.
    Returns setup instructions if not configured.
    """
    try:
        from backend.services.clients.ibkr_flexquery_client import flexquery_client

        if not flexquery_client.token or not flexquery_client.query_id:
            return {
                "configured": False,
                "setup_instructions": flexquery_client.get_setup_instructions(),
                "status": "FlexQuery not configured - setup required",
            }

        return {
            "configured": True,
            "status": "FlexQuery ready for official IBKR tax lots",
            "token_configured": bool(flexquery_client.token),
            "query_id_configured": bool(flexquery_client.query_id),
        }

    except Exception as e:
        logger.error(f"❌ FlexQuery status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flexquery/sync-tax-lots")
async def sync_official_tax_lots(
    payload: FlexSyncRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Sync official IBKR tax lots via FlexQuery.
    This gets the REAL tax lot data from IBKR Tax Optimizer.
    """
    try:
        from backend.services.clients.ibkr_flexquery_client import flexquery_client

        # Get official tax lots from IBKR
        official_tax_lots = await flexquery_client.get_official_tax_lots(
            payload.account_id
        )

        if not official_tax_lots:
            return {
                "success": False,
                "message": "No tax lots retrieved - check FlexQuery configuration",
                "tax_lots_synced": 0,
            }

        # Persist to DB
        from backend.services.portfolio.tax_lot_service import TaxLotService
        from backend.models.broker_account import BrokerAccount

        broker_account = (
            db.query(BrokerAccount)
            .filter(
                BrokerAccount.user_id == user.id,
                BrokerAccount.account_number == payload.account_id,
            )
            .first()
        )
        if not broker_account:
            raise HTTPException(status_code=404, detail="Broker account not found")

        tls = TaxLotService(db)
        result = await tls.sync_official_tax_lots(
            user.id, broker_account, official_tax_lots
        )

        return {
            "success": True,
            "message": f"Synced {result['total']} official tax lots",
            "synced": result,
            "account_id": payload.account_id,
            "source": "ibkr_flexquery_official",
        }

    except Exception as e:
        logger.error(f"❌ FlexQuery sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PORTFOLIO ANALYTICS ENDPOINTS (Snowball Analytics Style)
# =============================================================================


@router.get("/analytics/{account_id}")
async def get_portfolio_analytics(
    account_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get comprehensive portfolio analytics (Snowball Analytics style).

    Returns:
    - Portfolio performance & risk metrics
    - Tax optimization opportunities
    - Asset allocation analysis
    - Performance attribution
    """
    try:
        from backend.services.portfolio.portfolio_analytics_service import (
            portfolio_analytics_service,
        )

        analytics = await portfolio_analytics_service.get_portfolio_analytics(
            account_id
        )

        return {
            "success": True,
            "analytics": analytics,
            "features": {
                "portfolio_metrics": "Performance & risk analysis",
                "tax_opportunities": "Tax loss harvesting & optimization",
                "asset_allocation": "Allocation breakdown & concentration risk",
                "performance_attribution": "Top contributors & detractors",
            },
        }

    except Exception as e:
        logger.error(f"❌ Portfolio analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tax-optimization/{account_id}")
async def get_tax_optimization_opportunities(
    account_id: str, user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get tax optimization opportunities for the account.
    Identifies tax loss harvesting, wash sale warnings, etc.
    """
    try:
        from backend.services.clients.ibkr_flexquery_client import flexquery_client

        # Get official tax lots
        tax_lots = await flexquery_client.get_official_tax_lots(account_id)

        # Analyze for tax opportunities
        opportunities = []
        total_tax_loss_harvest = 0

        for lot in tax_lots:
            unrealized_pnl = lot.get("unrealized_pnl", 0)
            days_held = lot.get("days_held", 0)

            # Tax loss harvesting (losses > $1000)
            if unrealized_pnl < -1000:
                total_tax_loss_harvest += abs(unrealized_pnl)
                opportunities.append(
                    {
                        "type": "tax_loss_harvest",
                        "symbol": lot.get("symbol"),
                        "unrealized_loss": unrealized_pnl,
                        "estimated_tax_savings": abs(unrealized_pnl)
                        * 0.24,  # 24% tax rate
                        "recommendation": f"Harvest ${abs(unrealized_pnl):,.0f} loss",
                    }
                )

            # Long-term capital gains opportunity
            elif 300 <= days_held <= 365 and unrealized_pnl > 0:
                opportunities.append(
                    {
                        "type": "ltcg_timing",
                        "symbol": lot.get("symbol"),
                        "days_to_ltcg": 365 - days_held,
                        "unrealized_gain": unrealized_pnl,
                        "recommendation": f"Wait {365 - days_held} days for LTCG treatment",
                    }
                )

        return {
            "account_id": account_id,
            "total_opportunities": len(opportunities),
            "total_tax_loss_harvest_amount": total_tax_loss_harvest,
            "estimated_total_tax_savings": total_tax_loss_harvest * 0.24,
            "opportunities": opportunities,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Tax optimization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/{account_id}")
async def get_performance_metrics(
    account_id: str,
    period: str = "ytd",  # ytd, 1y, 3y, 5y, all
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get detailed performance metrics for the account.
    Includes risk-adjusted returns, drawdown analysis, etc.
    """
    try:
        from backend.services.clients.ibkr_client import ibkr_client
        from backend.services.clients.ibkr_flexquery_client import flexquery_client

        # Get current positions and tax lots
        positions = await ibkr_client.get_positions(account_id)
        tax_lots = await flexquery_client.get_official_tax_lots(account_id)

        # Calculate performance metrics
        total_value = sum(pos.get("market_value", 0) for pos in positions)
        total_cost_basis = sum(lot.get("cost_basis", 0) for lot in tax_lots)
        total_return = (
            ((total_value - total_cost_basis) / total_cost_basis * 100)
            if total_cost_basis > 0
            else 0
        )

        # Risk metrics (simplified - would need historical data for accuracy)
        volatility = 15.0  # Default estimate
        sharpe_ratio = max(0, total_return - 2.0) / volatility if volatility > 0 else 0

        # Best/worst performers
        performance_by_symbol = {}
        for lot in tax_lots:
            symbol = lot.get("symbol")
            pnl_pct = lot.get("unrealized_pnl_pct", 0)
            if symbol:
                if symbol not in performance_by_symbol:
                    performance_by_symbol[symbol] = []
                performance_by_symbol[symbol].append(pnl_pct)

        # Average performance by symbol
        avg_performance = {
            symbol: sum(pnls) / len(pnls)
            for symbol, pnls in performance_by_symbol.items()
        }

        best_performers = sorted(
            avg_performance.items(), key=lambda x: x[1], reverse=True
        )[:5]
        worst_performers = sorted(avg_performance.items(), key=lambda x: x[1])[:5]

        return {
            "account_id": account_id,
            "period": period,
            "total_return_pct": total_return,
            "total_value": total_value,
            "total_cost_basis": total_cost_basis,
            "risk_metrics": {
                "volatility": volatility,
                "sharpe_ratio": sharpe_ratio,
                "max_drawdown": min(
                    [lot.get("unrealized_pnl_pct", 0) for lot in tax_lots], default=0
                ),
            },
            "best_performers": [
                {"symbol": s, "return_pct": p} for s, p in best_performers
            ],
            "worst_performers": [
                {"symbol": s, "return_pct": p} for s, p in worst_performers
            ],
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Performance metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
