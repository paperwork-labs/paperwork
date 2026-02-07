"""
AxiomFolio V1 - Clean Strategies Routes
Integrates with StrategiesManager.tsx frontend component.

Handles user requests like:
"Run ATR Options on TastyTrade, $10k, 20% profit, 80% reinvest"
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import logging
from datetime import datetime

# dependencies
from backend.database import get_db
from backend.models.user import User
from backend.services.strategies.strategy_manager import (
    StrategyManager,
    StrategyRequest,
)

# Auth dependency (to be implemented)
from backend.api.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class StrategyExecutionRequest(BaseModel):
    """Request model for strategy execution from StrategiesManager.tsx"""

    strategy_type: str = Field(
        ..., description="Strategy type (atr_options, dca_conservative, etc.)"
    )
    broker: str = Field(..., description="Broker to use (tastytrade, ibkr)")
    starting_capital: float = Field(..., gt=0, description="Starting capital in USD")
    profit_target: float = Field(
        ..., gt=0, le=1, description="Profit target as percentage (0.20 = 20%)"
    )
    stop_loss: Optional[float] = Field(
        0.05, gt=0, le=1, description="Stop loss as percentage (0.05 = 5%)"
    )
    reinvest_percentage: Optional[float] = Field(
        0.80, ge=0, le=1, description="Reinvestment percentage (0.80 = 80%)"
    )
    max_position_size: Optional[float] = Field(
        0.10, gt=0, le=1, description="Max position size as percentage (0.10 = 10%)"
    )
    symbols: Optional[List[str]] = Field(None, description="Specific symbols to trade")
    custom_params: Optional[Dict[str, Any]] = Field(
        None, description="Strategy-specific parameters"
    )


class StrategyExecutionResponse(BaseModel):
    """Response model for strategy execution"""

    execution_id: int
    status: str
    strategy_type: str
    broker: str
    position_size: float
    entry_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    profit_target_price: Optional[float] = None
    order_ids: Optional[List[str]] = None
    error_message: Optional[str] = None
    execution_time: Optional[str] = None
    estimated_profit: Optional[float] = None
    risk_metrics: Optional[Dict[str, Any]] = None


# =============================================================================
# STRATEGY EXECUTION ENDPOINTS
# =============================================================================


@router.post("/execute", response_model=StrategyExecutionResponse)
async def execute_strategy(
    request: StrategyExecutionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrategyExecutionResponse:
    """
    Execute a trading strategy.

    Examples:
    - ATR Options: "Run ATR Options on TastyTrade, $10k, 20% profit, 80% reinvest"
    - DCA: "Run Conservative DCA on IBKR, $25k, monthly rebalancing"
    """
    try:
        logger.info(
            f"🚀 Strategy execution request: {request.strategy_type} for user {user.id}"
        )

        # Convert request to internal format
        strategy_request = StrategyRequest(
            user_id=user.id,
            strategy_type=request.strategy_type,
            broker=request.broker,
            starting_capital=request.starting_capital,
            profit_target=request.profit_target,
            stop_loss=request.stop_loss,
            reinvest_percentage=request.reinvest_percentage,
            max_position_size=request.max_position_size,
            symbols=request.symbols,
            custom_params=request.custom_params,
        )

        # Execute strategy
        manager = StrategyManager(db)
        result = await manager.execute_strategy(strategy_request)

        # Convert result to response format
        return StrategyExecutionResponse(
            execution_id=result.execution_id,
            status=result.status,
            strategy_type=result.strategy_type,
            broker=result.broker,
            position_size=result.position_size,
            entry_price=result.entry_price,
            stop_loss_price=result.stop_loss_price,
            profit_target_price=result.profit_target_price,
            order_ids=result.order_ids,
            error_message=result.error_message,
            execution_time=(
                result.execution_time.isoformat() if result.execution_time else None
            ),
            estimated_profit=result.estimated_profit,
            risk_metrics=result.risk_metrics,
        )

    except Exception as e:
        logger.error(f"❌ Strategy execution failed for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# STRATEGY MANAGEMENT ENDPOINTS
# =============================================================================


@router.get("/available")
async def get_available_strategies(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get available strategies for StrategiesManager.tsx.
    Returns strategy definitions with parameters, limits, and configuration options.
    """
    try:
        from backend.services.strategies.strategy_manager import get_strategy_options

        strategies = await get_strategy_options()

        return {
            "user_id": user.id,
            "available_strategies": strategies,
            "total_strategies": len(strategies),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Error getting available strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions")
async def get_strategy_executions(
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get user's strategy execution history.
    Shows past executions with results and performance.
    """
    try:
        manager = StrategyManager(db)
        executions = await manager.get_user_strategy_executions(user.id, limit=limit)

        return {
            "user_id": user.id,
            "executions": executions,
            "count": len(executions),
            "limit": limit,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Error getting strategy executions for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions/{execution_id}")
async def get_strategy_execution_details(
    execution_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get detailed information about a specific strategy execution.
    """
    try:
        from backend.models.strategy_integration import StrategyExecution

        execution = (
            db.query(StrategyExecution)
            .filter(
                StrategyExecution.id == execution_id,
                StrategyExecution.user_id == user.id,
            )
            .first()
        )

        if not execution:
            raise HTTPException(status_code=404, detail="Strategy execution not found")

        return {
            "execution_id": execution.id,
            "user_id": execution.user_id,
            "strategy_type": execution.strategy_type.value,
            "broker": execution.broker,
            "status": execution.status.value,
            "starting_capital": float(execution.starting_capital),
            "profit_target": float(execution.profit_target),
            "stop_loss": float(execution.stop_loss) if execution.stop_loss else None,
            "created_at": execution.created_at.isoformat(),
            "completed_at": (
                execution.completed_at.isoformat() if execution.completed_at else None
            ),
            "execution_summary": execution.execution_summary,
            "config_data": execution.config_data,
            "error_message": execution.error_message,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting execution details for {execution_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# STRATEGY CONFIGURATION ENDPOINTS
# =============================================================================


@router.get("/atr-options/config")
async def get_atr_options_config(
    symbol: str, user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get ATR options strategy configuration for a specific symbol.
    Used by StrategiesManager.tsx to show suggested parameters.
    """
    try:
        from backend.services.analysis.atr_calculator import atr_calculator

        # Get ATR data for the symbol
        atr_data = await atr_calculator.calculate_options_atr(symbol)

        # Suggest configuration based on ATR analysis
        suggested_config = {
            "symbol": symbol,
            "atr_data": atr_data,
            "suggested_profit_target": (
                0.15 if atr_data["volatility_level"] == "LOW" else 0.25
            ),
            "suggested_stop_loss": (
                0.03 if atr_data["volatility_level"] == "LOW" else 0.08
            ),
            "suggested_position_size": atr_data.get("position_size_factor", 0.10),
            "suggested_strikes": atr_data.get("suggested_strikes", []),
            "risk_assessment": {
                "volatility_level": atr_data["volatility_level"],
                "options_multiplier": atr_data.get("options_multiplier", 1.0),
                "recommended_capital": (
                    5000 if atr_data["volatility_level"] == "LOW" else 10000
                ),
            },
        }

        return {
            "user_id": user.id,
            "strategy_type": "atr_options",
            "symbol": symbol,
            "configuration": suggested_config,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Error getting ATR options config for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dca/config")
async def get_dca_config(
    strategy_variant: str = "conservative", user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get DCA strategy configuration.
    Used by StrategiesManager.tsx for DCA strategy setup.
    """
    try:
        # DCA strategy configurations
        dca_configs = {
            "conservative": {
                "name": "Conservative DCA",
                "risk_level": "LOW",
                "suggested_allocation": {
                    "VTI": 0.60,  # 60% Total Stock Market
                    "VXUS": 0.30,  # 30% International
                    "BND": 0.10,  # 10% Bonds
                },
                "investment_frequency": "monthly",
                "rebalance_threshold": 0.05,
                "min_capital": 5000,
                "suggested_monthly_investment": 1000,
            },
            "aggressive": {
                "name": "Aggressive DCA",
                "risk_level": "HIGH",
                "suggested_allocation": {
                    "QQQ": 0.50,  # 50% Tech-heavy NASDAQ
                    "VTI": 0.30,  # 30% Total Market
                    "VXUS": 0.20,  # 20% International
                },
                "investment_frequency": "monthly",
                "rebalance_threshold": 0.03,
                "min_capital": 10000,
                "suggested_monthly_investment": 2000,
            },
        }

        if strategy_variant not in dca_configs:
            raise HTTPException(
                status_code=400, detail=f"Unknown DCA variant: {strategy_variant}"
            )

        return {
            "user_id": user.id,
            "strategy_type": f"dca_{strategy_variant}",
            "configuration": dca_configs[strategy_variant],
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting DCA config for {strategy_variant}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# STRATEGY MONITORING ENDPOINTS
# =============================================================================


@router.get("/performance")
async def get_strategies_performance(
    days: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get performance summary of all user's strategies.
    Shows ROI, win rate, and other key metrics.
    """
    try:
        from backend.models.strategy_integration import (
            StrategyExecution,
            StrategyStatus,
        )

        # Get completed executions in the specified period
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=days)

        executions = (
            db.query(StrategyExecution)
            .filter(
                StrategyExecution.user_id == user.id,
                StrategyExecution.status == StrategyStatus.COMPLETED,
                StrategyExecution.completed_at >= cutoff_date,
            )
            .all()
        )

        # Calculate performance metrics
        total_executions = len(executions)
        successful_executions = [
            e
            for e in executions
            if e.execution_summary and e.execution_summary.get("status") == "SUCCESS"
        ]

        performance_summary = {
            "period_days": days,
            "total_executions": total_executions,
            "successful_executions": len(successful_executions),
            "success_rate": (
                len(successful_executions) / total_executions
                if total_executions > 0
                else 0
            ),
            "total_capital_deployed": sum(
                float(e.starting_capital) for e in executions
            ),
            "strategies_breakdown": {},
        }

        # Group by strategy type
        by_strategy = {}
        for execution in executions:
            strategy_type = execution.strategy_type.value
            if strategy_type not in by_strategy:
                by_strategy[strategy_type] = {
                    "executions": 0,
                    "successful": 0,
                    "total_capital": 0,
                }

            by_strategy[strategy_type]["executions"] += 1
            by_strategy[strategy_type]["total_capital"] += float(
                execution.starting_capital
            )

            if execution in successful_executions:
                by_strategy[strategy_type]["successful"] += 1

        performance_summary["strategies_breakdown"] = by_strategy

        return {
            "user_id": user.id,
            "performance_summary": performance_summary,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Error getting strategies performance for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
