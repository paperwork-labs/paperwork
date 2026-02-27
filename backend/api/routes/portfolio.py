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


@router.get("/symbols")
async def get_portfolio_symbols(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return a map of held symbols with basic position data.
    Used by Brain pages to highlight portfolio holdings."""
    from backend.models.position import Position

    account_ids = [
        r[0]
        for r in db.query(BrokerAccount.id)
        .filter(BrokerAccount.user_id == user.id)
        .all()
    ]

    if not account_ids:
        return {"data": {}}

    positions = (
        db.query(Position)
        .filter(Position.account_id.in_(account_ids), Position.quantity != 0)
        .all()
    )

    result: Dict[str, Any] = {}
    for p in positions:
        sym = p.symbol
        if sym not in result:
            result[sym] = {
                "symbol": sym,
                "quantity": 0,
                "cost_basis": 0,
                "market_value": 0,
                "unrealized_pnl": 0,
            }
        result[sym]["quantity"] += float(p.quantity or 0)
        result[sym]["cost_basis"] += float(p.total_cost_basis or 0)
        result[sym]["market_value"] += float(p.market_value or 0)
        result[sym]["unrealized_pnl"] += float(p.unrealized_pnl or 0)

    return {"data": result}


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


# NOTE: /statements endpoint removed -- use portfolio_statements.py instead.


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
                "status": "error",
                "error": "No tax lots retrieved - check FlexQuery configuration",
                "data": {"tax_lots_synced": 0},
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
            "status": "success",
            "data": {
                "message": f"Synced {result['total']} official tax lots",
                "synced": result,
                "account_id": payload.account_id,
                "source": "ibkr_flexquery_official",
            },
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
            "status": "success",
            "data": {
                "analytics": analytics,
                "features": {
                    "portfolio_metrics": "Performance & risk analysis",
                    "tax_opportunities": "Tax loss harvesting & optimization",
                    "asset_allocation": "Allocation breakdown & concentration risk",
                    "performance_attribution": "Top contributors & detractors",
                },
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


@router.get("/insights")
async def get_portfolio_insights(
    user_id: int | None = Query(None, description="User ID (optional)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Lightweight portfolio insights from local DB data.

    Returns tax-loss harvesting candidates, positions approaching long-term
    status, and concentration risk warnings.  No live broker connection needed.
    """
    from backend.api.dependencies import get_portfolio_user
    from backend.models.position import Position
    from backend.models.tax_lot import TaxLot

    try:
        user = get_portfolio_user(user_id, db)

        account_ids = [
            a.id
            for a in db.query(BrokerAccount)
            .filter(BrokerAccount.user_id == user.id)
            .all()
        ]
        if not account_ids:
            return {"status": "success", "data": {"harvest_candidates": [], "approaching_lt": [], "concentration_warnings": []}}

        positions = (
            db.query(Position)
            .filter(Position.account_id.in_(account_ids))
            .all()
        )
        tax_lots = (
            db.query(TaxLot)
            .filter(TaxLot.account_id.in_(account_ids))
            .all()
        )

        total_value = sum(float(p.market_value or 0) for p in positions)

        harvest_candidates = []
        for lot in tax_lots:
            unrealized = float(lot.unrealized_pnl or 0)
            if unrealized < -1000:
                harvest_candidates.append({
                    "symbol": lot.symbol,
                    "unrealized_pnl": unrealized,
                    "shares": float(lot.quantity or 0),
                    "days_held": lot.holding_period or 0,
                })
        harvest_candidates.sort(key=lambda x: x["unrealized_pnl"])

        approaching_lt = []
        for lot in tax_lots:
            days = lot.holding_period or 0
            if 300 <= days < 365:
                approaching_lt.append({
                    "symbol": lot.symbol,
                    "days_held": days,
                    "days_to_lt": 365 - days,
                    "shares": float(lot.quantity or 0),
                    "unrealized_pnl": float(lot.unrealized_pnl or 0),
                })
        approaching_lt.sort(key=lambda x: x["days_to_lt"])

        concentration_warnings = []
        if total_value > 0:
            for p in positions:
                mv = float(p.market_value or 0)
                pct = (mv / total_value) * 100
                if pct > 20:
                    concentration_warnings.append({
                        "symbol": p.symbol,
                        "market_value": mv,
                        "pct_of_portfolio": round(pct, 1),
                    })
        concentration_warnings.sort(key=lambda x: -x["pct_of_portfolio"])

        return {
            "status": "success",
            "data": {
                "harvest_candidates": harvest_candidates[:5],
                "approaching_lt": approaching_lt[:5],
                "concentration_warnings": concentration_warnings[:5],
                "total_positions": len(positions),
                "total_tax_lots": len(tax_lots),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Portfolio insights error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
