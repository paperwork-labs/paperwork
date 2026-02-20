"""
AxiomFolio V1 - Strategy Manager Service
Coordinates all strategy services and integrates with StrategiesManager.tsx.

Handles user requests like:
"Run ATR Options on TastyTrade, $10k, 20% profit, 80% reinvest"
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass
from sqlalchemy.orm import Session

# Model imports
from backend.models.user import User
from backend.models.strategy import (
    StrategyType,
    StrategyExecution,
    StrategyStatus,
)

# TODO: Re-implement these classes after strategy_integration.py was merged into strategy.py
# from backend.models.strategy_integration import (
#     StrategyServiceRegistry, StrategyExecutionConfig
# )
from backend.database import SessionLocal

# Service imports
# TODO: Re-implement ATROptionsService
# from backend.services.strategies.atr_options_service import ATROptionsService
from backend.services.strategies.dca_service import DCAService
from backend.services.analysis.atr_calculator import atr_calculator
from backend.services.notifications.discord_service import DiscordService

logger = logging.getLogger(__name__)


class BrokerType(Enum):
    TASTYTRADE = "tastytrade"
    IBKR = "ibkr"
    PAPER = "paper"


@dataclass
class StrategyRequest:
    """Strategy execution request from StrategiesManager.tsx"""

    user_id: int
    strategy_type: str  # "atr_options", "dca_conservative", etc.
    broker: str  # "tastytrade", "ibkr"
    starting_capital: float
    profit_target: float  # As percentage (0.20 = 20%)
    stop_loss: Optional[float] = 0.05  # As percentage (0.05 = 5%)
    reinvest_percentage: Optional[float] = 0.80  # 80% reinvestment
    max_position_size: Optional[float] = 0.10  # 10% max per position
    symbols: Optional[List[str]] = None
    custom_params: Optional[Dict[str, Any]] = None


@dataclass
class StrategyExecutionResult:
    """Result of strategy execution"""

    execution_id: int
    status: str  # "SUCCESS", "FAILED", "PENDING"
    strategy_type: str
    broker: str
    position_size: float
    entry_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    profit_target_price: Optional[float] = None
    order_ids: Optional[List[str]] = None
    error_message: Optional[str] = None
    execution_time: Optional[datetime] = None
    estimated_profit: Optional[float] = None
    risk_metrics: Optional[Dict[str, Any]] = None


class StrategyManager:
    """
    Strategy Manager - Central coordinator for all strategy execution.
    Integrates with StrategiesManager.tsx frontend component.
    """

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session or SessionLocal()
        self.discord = DiscordService()

        # Initialize strategy services
        self.services = {
            # TODO: Re-implement ATROptionsService
            # "atr_options": ATROptionsService(self.db),
            "dca_conservative": DCAService(self.db),
            "dca_aggressive": DCAService(self.db),
            # Additional strategies can be registered here
        }

        # Strategy service registry
        # TODO: Re-implement StrategyServiceRegistry after strategy_integration.py merge
        # self.registry = StrategyServiceRegistry(self.db)

    async def execute_strategy(
        self, request: StrategyRequest
    ) -> StrategyExecutionResult:
        """
        Execute strategy based on request from StrategiesManager.tsx.

        Example: "Run ATR Options on TastyTrade, $10k, 20% profit, 80% reinvest"
        """
        try:
            logger.info(
                f"🚀 Executing strategy: {request.strategy_type} for user {request.user_id}"
            )

            # Validate user
            user = self.db.query(User).filter(User.id == request.user_id).first()
            if not user:
                raise ValueError(f"User {request.user_id} not found")

            # Validate strategy type
            if request.strategy_type not in self.services:
                raise ValueError(f"Strategy type {request.strategy_type} not supported")

            # Create strategy execution record
            execution = StrategyExecution(
                user_id=request.user_id,
                strategy_type=(
                    StrategyType.ATR_OPTIONS
                    if "atr" in request.strategy_type
                    else StrategyType.DCA
                ),
                broker=request.broker,
                starting_capital=Decimal(str(request.starting_capital)),
                profit_target=Decimal(str(request.profit_target)),
                stop_loss=(
                    Decimal(str(request.stop_loss)) if request.stop_loss else None
                ),
                status=StrategyStatus.PENDING,
                config_data={
                    "reinvest_percentage": request.reinvest_percentage,
                    "max_position_size": request.max_position_size,
                    "symbols": request.symbols,
                    "custom_params": request.custom_params or {},
                },
            )

            self.db.add(execution)
            self.db.commit()
            self.db.refresh(execution)

            # Execute the strategy
            strategy_service = self.services[request.strategy_type]

            if request.strategy_type == "atr_options":
                result = await self._execute_atr_options_strategy(
                    strategy_service, execution, request
                )
            elif "dca" in request.strategy_type:
                result = await self._execute_dca_strategy(
                    strategy_service, execution, request
                )
            else:
                raise ValueError(
                    f"Strategy execution not implemented for {request.strategy_type}"
                )

            # Update execution record
            execution.status = (
                StrategyStatus.COMPLETED
                if result.status == "SUCCESS"
                else StrategyStatus.FAILED
            )
            execution.execution_summary = {
                "position_size": result.position_size,
                "entry_price": result.entry_price,
                "order_ids": result.order_ids,
                "execution_time": (
                    result.execution_time.isoformat() if result.execution_time else None
                ),
            }
            execution.error_message = result.error_message
            execution.completed_at = datetime.now()

            self.db.commit()

            # Send Discord notification
            await self._send_strategy_notification(user, result)

            return result

        except Exception as e:
            logger.error(f"❌ Strategy execution failed: {e}")

            # Update execution record with error
            if "execution" in locals():
                execution.status = StrategyStatus.FAILED
                execution.error_message = str(e)
                execution.completed_at = datetime.now()
                self.db.commit()

            return StrategyExecutionResult(
                execution_id=execution.id if "execution" in locals() else 0,
                status="FAILED",
                strategy_type=request.strategy_type,
                broker=request.broker,
                position_size=0.0,
                error_message=str(e),
            )

    async def _execute_atr_options_strategy(
        self,
        service: Any,  # ATROptionsService when re-implemented
        execution: StrategyExecution,
        request: StrategyRequest,
    ) -> StrategyExecutionResult:
        """Execute ATR options strategy."""

        try:
            # Get symbols to trade (default to major tech stocks if not specified)
            symbols = request.symbols or ["AAPL", "MSFT", "NVDA", "GOOGL"]

            # Process each symbol
            total_position_size = 0.0
            all_order_ids = []
            execution_details = []

            for symbol in symbols:
                try:
                    # Calculate ATR for the symbol
                    atr_data = await atr_calculator.calculate_options_atr(symbol)

                    if atr_data["atr_value"] == 0:
                        logger.warning(f"⚠️ No ATR data for {symbol}, skipping")
                        continue

                    # Calculate position size based on capital and risk limits
                    symbol_capital = request.starting_capital * (
                        request.max_position_size or 0.10
                    )

                    # Execute options trade
                    trade_result = await service.execute_options_trade(
                        symbol=symbol,
                        capital=symbol_capital,
                        atr_data=atr_data,
                        profit_target=request.profit_target,
                        stop_loss=request.stop_loss,
                        broker=request.broker,
                    )

                    if trade_result.get("status") == "SUCCESS":
                        total_position_size += trade_result.get("position_size", 0)
                        if trade_result.get("order_id"):
                            all_order_ids.append(trade_result["order_id"])

                        execution_details.append(
                            {
                                "symbol": symbol,
                                "position_size": trade_result.get("position_size", 0),
                                "entry_price": trade_result.get("entry_price"),
                                "atr_value": atr_data["atr_value"],
                                "volatility_level": atr_data["volatility_level"],
                            }
                        )

                        logger.info(
                            f"✅ {symbol}: ${trade_result.get('position_size', 0):.2f} position"
                        )

                except Exception as symbol_error:
                    logger.error(f"❌ Error trading {symbol}: {symbol_error}")
                    continue

            if total_position_size > 0:
                return StrategyExecutionResult(
                    execution_id=execution.id,
                    status="SUCCESS",
                    strategy_type=request.strategy_type,
                    broker=request.broker,
                    position_size=total_position_size,
                    order_ids=all_order_ids,
                    execution_time=datetime.now(),
                    estimated_profit=total_position_size * request.profit_target,
                    risk_metrics={
                        "total_symbols": len(symbols),
                        "successful_trades": len(execution_details),
                        "capital_utilized": total_position_size
                        / request.starting_capital,
                        "execution_details": execution_details,
                    },
                )
            else:
                return StrategyExecutionResult(
                    execution_id=execution.id,
                    status="FAILED",
                    strategy_type=request.strategy_type,
                    broker=request.broker,
                    position_size=0.0,
                    error_message="No successful trades executed",
                )

        except Exception as e:
            logger.error(f"❌ ATR options strategy execution failed: {e}")
            return StrategyExecutionResult(
                execution_id=execution.id,
                status="FAILED",
                strategy_type=request.strategy_type,
                broker=request.broker,
                position_size=0.0,
                error_message=str(e),
            )

    async def _execute_dca_strategy(
        self,
        service: DCAService,
        execution: StrategyExecution,
        request: StrategyRequest,
    ) -> StrategyExecutionResult:
        """Execute DCA strategy."""

        try:
            # DCA strategy configuration
            dca_config = {
                "starting_capital": request.starting_capital,
                "investment_frequency": request.custom_params.get(
                    "frequency", "monthly"
                ),
                "investment_amount": request.starting_capital * 0.1,  # 10% monthly
                "rebalance_threshold": 0.05,  # 5% threshold
                "target_allocation": request.custom_params.get(
                    "allocation",
                    {
                        "VTI": 0.60,  # 60% total market
                        "VXUS": 0.30,  # 30% international
                        "BND": 0.10,  # 10% bonds
                    },
                ),
            }

            # Execute DCA rebalancing
            rebalance_result = await service.execute_rebalance(
                user_id=request.user_id, config=dca_config, broker=request.broker
            )

            if rebalance_result.get("status") == "SUCCESS":
                trades = rebalance_result.get("trades", [])
                total_invested = sum(trade.get("amount", 0) for trade in trades)

                return StrategyExecutionResult(
                    execution_id=execution.id,
                    status="SUCCESS",
                    strategy_type=request.strategy_type,
                    broker=request.broker,
                    position_size=total_invested,
                    execution_time=datetime.now(),
                    risk_metrics={
                        "trades_executed": len(trades),
                        "total_invested": total_invested,
                        "allocation_details": trades,
                    },
                )
            else:
                return StrategyExecutionResult(
                    execution_id=execution.id,
                    status="FAILED",
                    strategy_type=request.strategy_type,
                    broker=request.broker,
                    position_size=0.0,
                    error_message=rebalance_result.get("error", "DCA execution failed"),
                )

        except Exception as e:
            logger.error(f"❌ DCA strategy execution failed: {e}")
            return StrategyExecutionResult(
                execution_id=execution.id,
                status="FAILED",
                strategy_type=request.strategy_type,
                broker=request.broker,
                position_size=0.0,
                error_message=str(e),
            )

    async def _send_strategy_notification(
        self, user: User, result: StrategyExecutionResult
    ):
        """Send Discord notification about strategy execution."""
        try:
            if result.status == "SUCCESS":
                message = f"""
🚀 **Strategy Executed Successfully**

**User:** {user.username}
**Strategy:** {result.strategy_type}
**Broker:** {result.broker}
**Position Size:** ${result.position_size:,.2f}
**Orders:** {len(result.order_ids or [])}
**Estimated Profit:** ${result.estimated_profit:,.2f}

✅ All trades executed successfully!
                """.strip()
            else:
                message = f"""
❌ **Strategy Execution Failed**

**User:** {user.username}
**Strategy:** {result.strategy_type}
**Broker:** {result.broker}
**Error:** {result.error_message}

Please check logs for details.
                """.strip()

            await self.discord.send_strategy_notification(message)

        except Exception as e:
            logger.error(f"❌ Failed to send strategy notification: {e}")

    async def get_user_strategy_executions(
        self, user_id: int, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get recent strategy executions for a user."""
        try:
            executions = (
                self.db.query(StrategyExecution)
                .filter(StrategyExecution.user_id == user_id)
                .order_by(StrategyExecution.created_at.desc())
                .limit(limit)
                .all()
            )

            result = []
            for execution in executions:
                result.append(
                    {
                        "execution_id": execution.id,
                        "strategy_type": execution.strategy_type.value,
                        "broker": execution.broker,
                        "status": execution.status.value,
                        "starting_capital": float(execution.starting_capital),
                        "profit_target": float(execution.profit_target),
                        "created_at": execution.created_at.isoformat(),
                        "completed_at": (
                            execution.completed_at.isoformat()
                            if execution.completed_at
                            else None
                        ),
                        "execution_summary": execution.execution_summary,
                        "error_message": execution.error_message,
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Error getting strategy executions for user {user_id}: {e}")
            return []

    async def get_available_strategies(self) -> List[Dict[str, Any]]:
        """Get list of available strategies for StrategiesManager.tsx."""
        return [
            {
                "strategy_id": "atr_options",
                "name": "ATR Options Strategy",
                "description": "Options trading based on ATR volatility analysis",
                "risk_level": "MEDIUM",
                "min_capital": 1000,
                "supported_brokers": ["tastytrade", "ibkr"],
                "parameters": {
                    "profit_target": {
                        "type": "percentage",
                        "default": 0.20,
                        "min": 0.05,
                        "max": 1.0,
                    },
                    "stop_loss": {
                        "type": "percentage",
                        "default": 0.05,
                        "min": 0.01,
                        "max": 0.20,
                    },
                    "max_position_size": {
                        "type": "percentage",
                        "default": 0.10,
                        "min": 0.01,
                        "max": 0.50,
                    },
                    "symbols": {"type": "list", "default": ["AAPL", "MSFT", "NVDA"]},
                },
            },
            {
                "strategy_id": "dca_conservative",
                "name": "Conservative DCA",
                "description": "Dollar-cost averaging with conservative allocation",
                "risk_level": "LOW",
                "min_capital": 5000,
                "supported_brokers": ["ibkr", "tastytrade"],
                "parameters": {
                    "investment_frequency": {
                        "type": "select",
                        "options": ["weekly", "monthly"],
                        "default": "monthly",
                    },
                    "allocation": {
                        "type": "allocation",
                        "default": {"VTI": 0.60, "VXUS": 0.30, "BND": 0.10},
                    },
                },
            },
            {
                "strategy_id": "dca_aggressive",
                "name": "Aggressive DCA",
                "description": "Dollar-cost averaging with growth-focused allocation",
                "risk_level": "HIGH",
                "min_capital": 5000,
                "supported_brokers": ["ibkr", "tastytrade"],
                "parameters": {
                    "investment_frequency": {
                        "type": "select",
                        "options": ["weekly", "monthly"],
                        "default": "monthly",
                    },
                    "allocation": {
                        "type": "allocation",
                        "default": {"QQQ": 0.50, "VTI": 0.30, "VXUS": 0.20},
                    },
                },
            },
        ]


# =============================================================================
# CONVENIENCE FUNCTIONS FOR API INTEGRATION
# =============================================================================


async def execute_user_strategy(
    user_id: int,
    strategy_type: str,
    broker: str,
    starting_capital: float,
    profit_target: float,
    **kwargs,
) -> StrategyExecutionResult:
    """Convenience function for API endpoints."""

    manager = StrategyManager()
    try:
        request = StrategyRequest(
            user_id=user_id,
            strategy_type=strategy_type,
            broker=broker,
            starting_capital=starting_capital,
            profit_target=profit_target,
            **kwargs,
        )

        return await manager.execute_strategy(request)

    finally:
        manager.db.close()


async def get_user_executions(user_id: int) -> List[Dict[str, Any]]:
    """Get user's strategy execution history."""
    manager = StrategyManager()
    try:
        return await manager.get_user_strategy_executions(user_id)
    finally:
        manager.db.close()


async def get_strategy_options() -> List[Dict[str, Any]]:
    """Get available strategy options for frontend."""
    manager = StrategyManager()
    try:
        return await manager.get_available_strategies()
    finally:
        manager.db.close()
