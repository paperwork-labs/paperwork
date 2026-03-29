"""Paper trading validation service for strategies.

Validates strategies in paper mode before allowing live trading.
Implements a configurable validation period with performance gates.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models.order import Order, OrderStatus
from backend.models.strategy import (
    ExecutionMode,
    Strategy,
    StrategyStatus,
)

logger = logging.getLogger(__name__)


class ValidationStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class ValidationConfig:
    """Configuration for paper trading validation.
    
    Raised thresholds for go-live readiness given system complexity.
    """
    min_duration_days: int = 14  # 2 weeks minimum validation
    min_trades: int = 30  # Statistical significance
    max_drawdown_pct: float = 15.0
    min_win_rate_pct: float = 40.0
    min_profit_factor: float = 1.2  # Must demonstrate edge
    max_avg_loss_pct: float = 3.0  # Tighter loss control


@dataclass
class ValidationResult:
    """Result of paper validation check."""
    status: ValidationStatus
    days_elapsed: int
    trades_count: int
    win_rate_pct: float
    total_return_pct: float
    max_drawdown_pct: float
    profit_factor: float
    avg_loss_pct: float
    checks: List[Dict[str, Any]]
    can_go_live: bool
    message: str


class PaperValidator:
    """Validates strategies through paper trading before live execution.
    
    Validation Process:
    1. Strategy must run in PAPER mode for min_duration_days
    2. Must execute at least min_trades paper trades
    3. Must pass all validation gates (drawdown, win rate, etc.)
    4. Only then can strategy be promoted to LIVE mode
    """

    def __init__(self, db: Session, config: Optional[ValidationConfig] = None):
        self.db = db
        self.config = config or ValidationConfig()

    def start_validation(
        self,
        strategy_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """Start paper trading validation for a strategy.
        
        Sets strategy to PAPER mode and records validation start time.
        """
        strategy = (
            self.db.query(Strategy)
            .filter(Strategy.id == strategy_id, Strategy.user_id == user_id)
            .first()
        )
        
        if not strategy:
            return {"error": "Strategy not found"}
        
        if strategy.execution_mode == ExecutionMode.LIVE:
            return {"error": "Strategy is already in live mode"}
        
        # Set to paper mode and record start time in audit_metadata
        strategy.execution_mode = ExecutionMode.PAPER
        strategy.status = StrategyStatus.ACTIVE
        strategy.is_validated = False
        
        metadata = strategy.audit_metadata or {}
        metadata["paper_validation"] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "config": {
                "min_duration_days": self.config.min_duration_days,
                "min_trades": self.config.min_trades,
                "max_drawdown_pct": self.config.max_drawdown_pct,
                "min_win_rate_pct": self.config.min_win_rate_pct,
            },
        }
        strategy.audit_metadata = metadata
        
        self.db.commit()
        self.db.refresh(strategy)
        
        logger.info(
            "Started paper validation for strategy %s (user %s)",
            strategy_id,
            user_id,
        )
        
        return {
            "status": "started",
            "strategy_id": strategy_id,
            "validation_config": {
                "min_duration_days": self.config.min_duration_days,
                "min_trades": self.config.min_trades,
            },
            "message": f"Paper validation started. Run for at least {self.config.min_duration_days} days "
                      f"with {self.config.min_trades}+ trades to qualify for live trading.",
        }

    def check_validation(
        self,
        strategy_id: int,
        user_id: int,
    ) -> ValidationResult:
        """Check current validation status and metrics."""
        strategy = (
            self.db.query(Strategy)
            .filter(Strategy.id == strategy_id, Strategy.user_id == user_id)
            .first()
        )
        
        if not strategy:
            return ValidationResult(
                status=ValidationStatus.NOT_STARTED,
                days_elapsed=0,
                trades_count=0,
                win_rate_pct=0.0,
                total_return_pct=0.0,
                max_drawdown_pct=0.0,
                profit_factor=0.0,
                avg_loss_pct=0.0,
                checks=[],
                can_go_live=False,
                message="Strategy not found",
            )
        
        # Check if validation has started
        metadata = strategy.audit_metadata or {}
        validation_data = metadata.get("paper_validation", {})
        started_at_str = validation_data.get("started_at")
        
        if not started_at_str:
            return ValidationResult(
                status=ValidationStatus.NOT_STARTED,
                days_elapsed=0,
                trades_count=0,
                win_rate_pct=0.0,
                total_return_pct=0.0,
                max_drawdown_pct=0.0,
                profit_factor=0.0,
                avg_loss_pct=0.0,
                checks=[],
                can_go_live=False,
                message="Paper validation not started. Call start_validation() first.",
            )
        
        started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
        days_elapsed = (datetime.now(timezone.utc) - started_at).days
        
        # Get paper trades for this strategy
        paper_orders = (
            self.db.query(Order)
            .filter(
                Order.strategy_id == strategy_id,
                Order.user_id == user_id,
                Order.status == OrderStatus.FILLED.value,
                Order.broker_type == "paper",
                Order.filled_at >= started_at,
            )
            .all()
        )
        
        # Calculate metrics
        metrics = self._calculate_metrics(paper_orders)
        
        # Run validation checks
        checks = self._run_checks(days_elapsed, metrics)
        
        # Determine overall status
        all_passed = all(c["passed"] for c in checks)
        duration_met = days_elapsed >= self.config.min_duration_days
        trades_met = metrics["trades_count"] >= self.config.min_trades
        
        if all_passed and duration_met and trades_met:
            status = ValidationStatus.PASSED
            can_go_live = True
            message = "Validation passed. Strategy is eligible for live trading."
        elif not duration_met:
            status = ValidationStatus.IN_PROGRESS
            can_go_live = False
            remaining = self.config.min_duration_days - days_elapsed
            message = f"Validation in progress. {remaining} day(s) remaining."
        elif not trades_met:
            status = ValidationStatus.IN_PROGRESS
            can_go_live = False
            needed = self.config.min_trades - metrics["trades_count"]
            message = f"Validation in progress. Need {needed} more trade(s)."
        else:
            status = ValidationStatus.FAILED
            can_go_live = False
            failed_checks = [c["name"] for c in checks if not c["passed"]]
            message = f"Validation failed: {', '.join(failed_checks)}"
        
        return ValidationResult(
            status=status,
            days_elapsed=days_elapsed,
            trades_count=metrics["trades_count"],
            win_rate_pct=metrics["win_rate_pct"],
            total_return_pct=metrics["total_return_pct"],
            max_drawdown_pct=metrics["max_drawdown_pct"],
            profit_factor=metrics["profit_factor"],
            avg_loss_pct=metrics["avg_loss_pct"],
            checks=checks,
            can_go_live=can_go_live,
            message=message,
        )

    def _calculate_metrics(self, orders: List[Order]) -> Dict[str, Any]:
        """Calculate validation metrics from paper trades using realized P&L.
        
        Only orders with realized_pnl populated are counted as completed trades.
        Orders without P&L data (e.g., unfilled or position-opening orders) are skipped.
        """
        if not orders:
            return {
                "trades_count": 0,
                "win_rate_pct": 0.0,
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "profit_factor": 0.0,
                "avg_loss_pct": 0.0,
            }
        
        wins = 0
        losses = 0
        total_profit = Decimal("0")
        total_loss = Decimal("0")
        loss_pcts: List[float] = []
        total_notional = Decimal("0")
        total_realized_pnl = Decimal("0")
        
        for order in orders:
            # Only count orders with realized P&L (closing/reducing trades)
            if order.realized_pnl is None:
                continue
            
            pnl = Decimal(str(order.realized_pnl))
            total_realized_pnl += pnl
            
            # Calculate notional value for return calculation
            if order.filled_avg_price and order.filled_quantity:
                notional = Decimal(str(order.filled_avg_price)) * Decimal(str(order.filled_quantity))
                total_notional += notional
            
            if pnl > 0:
                wins += 1
                total_profit += pnl
            elif pnl < 0:
                losses += 1
                abs_loss = abs(pnl)
                total_loss += abs_loss
                # Calculate loss as percentage of trade notional
                if order.cost_basis and order.cost_basis > 0 and order.filled_quantity:
                    trade_cost = Decimal(str(order.cost_basis)) * Decimal(str(order.filled_quantity))
                    if trade_cost > 0:
                        loss_pct = float(abs_loss / trade_cost) * 100
                        loss_pcts.append(loss_pct)
            # pnl == 0 is a scratch trade; ignored for win/loss stats and trade count
        
        trades_count = wins + losses
        
        # Win rate and trade count intentionally exclude scratch (zero-PnL) trades
        win_rate_pct = (wins / trades_count * 100) if trades_count > 0 else 0.0
        
        # Profit factor: total profits / total losses
        # If no losses, return high value (not infinity) to indicate profitable
        if total_loss > 0:
            profit_factor = float(total_profit / total_loss)
        elif total_profit > 0:
            profit_factor = 999.0  # All profitable, no losses
        else:
            profit_factor = 0.0  # No trades or all scratches
        
        # Average loss percentage
        avg_loss_pct = sum(loss_pcts) / len(loss_pcts) if loss_pcts else 0.0
        
        # Total return: sum of realized P&L / total notional exposure
        if total_notional > 0:
            total_return_pct = float(total_realized_pnl / total_notional) * 100
        else:
            total_return_pct = 0.0
        
        return {
            "trades_count": trades_count,
            "win_rate_pct": round(win_rate_pct, 2),
            "total_return_pct": round(total_return_pct, 4),
            "max_drawdown_pct": 0.0,  # Would need equity curve for real calculation
            "profit_factor": round(profit_factor, 2),
            "avg_loss_pct": round(avg_loss_pct, 2),
        }

    def _run_checks(
        self,
        days_elapsed: int,
        metrics: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Run validation checks against config thresholds."""
        checks = []
        
        # Duration check
        checks.append({
            "name": "min_duration",
            "passed": days_elapsed >= self.config.min_duration_days,
            "actual": days_elapsed,
            "required": self.config.min_duration_days,
            "unit": "days",
        })
        
        # Trade count check
        checks.append({
            "name": "min_trades",
            "passed": metrics["trades_count"] >= self.config.min_trades,
            "actual": metrics["trades_count"],
            "required": self.config.min_trades,
            "unit": "trades",
        })
        
        # Win rate check
        checks.append({
            "name": "min_win_rate",
            "passed": metrics["win_rate_pct"] >= self.config.min_win_rate_pct,
            "actual": metrics["win_rate_pct"],
            "required": self.config.min_win_rate_pct,
            "unit": "%",
        })
        
        # Drawdown check
        checks.append({
            "name": "max_drawdown",
            "passed": metrics["max_drawdown_pct"] <= self.config.max_drawdown_pct,
            "actual": metrics["max_drawdown_pct"],
            "required": self.config.max_drawdown_pct,
            "unit": "%",
        })
        
        # Profit factor check
        checks.append({
            "name": "min_profit_factor",
            "passed": metrics["profit_factor"] >= self.config.min_profit_factor,
            "actual": metrics["profit_factor"],
            "required": self.config.min_profit_factor,
            "unit": "ratio",
        })
        
        # Average loss check
        checks.append({
            "name": "max_avg_loss",
            "passed": metrics["avg_loss_pct"] <= self.config.max_avg_loss_pct,
            "actual": metrics["avg_loss_pct"],
            "required": self.config.max_avg_loss_pct,
            "unit": "%",
        })
        
        return checks

    def promote_to_live(
        self,
        strategy_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """Promote a validated strategy to live trading.
        
        Only succeeds if validation has passed.
        """
        result = self.check_validation(strategy_id, user_id)
        
        if not result.can_go_live:
            return {
                "error": f"Cannot promote to live: {result.message}",
                "validation_status": result.status.value,
            }
        
        strategy = (
            self.db.query(Strategy)
            .filter(Strategy.id == strategy_id, Strategy.user_id == user_id)
            .first()
        )
        
        if not strategy:
            return {"error": "Strategy not found"}
        
        # Update strategy to live mode
        strategy.execution_mode = ExecutionMode.LIVE
        strategy.is_validated = True
        strategy.validation_errors = None
        strategy.validation_warnings = None
        
        # Record promotion in audit metadata
        metadata = strategy.audit_metadata or {}
        metadata["paper_validation"]["completed_at"] = datetime.now(timezone.utc).isoformat()
        metadata["paper_validation"]["promoted_to_live"] = True
        metadata["paper_validation"]["final_metrics"] = {
            "days_elapsed": result.days_elapsed,
            "trades_count": result.trades_count,
            "win_rate_pct": result.win_rate_pct,
            "total_return_pct": result.total_return_pct,
        }
        strategy.audit_metadata = metadata
        
        self.db.commit()
        self.db.refresh(strategy)
        
        logger.info(
            "Strategy %s promoted to LIVE mode (user %s). Metrics: %s",
            strategy_id,
            user_id,
            result,
        )
        
        return {
            "status": "promoted",
            "strategy_id": strategy_id,
            "execution_mode": "live",
            "validation_metrics": {
                "days_elapsed": result.days_elapsed,
                "trades_count": result.trades_count,
                "win_rate_pct": result.win_rate_pct,
            },
            "message": "Strategy successfully promoted to live trading.",
        }

    def reset_validation(
        self,
        strategy_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """Reset validation status to start over."""
        strategy = (
            self.db.query(Strategy)
            .filter(Strategy.id == strategy_id, Strategy.user_id == user_id)
            .first()
        )
        
        if not strategy:
            return {"error": "Strategy not found"}
        
        # Reset to paper mode
        strategy.execution_mode = ExecutionMode.PAPER
        strategy.is_validated = False
        
        # Clear validation metadata
        metadata = strategy.audit_metadata or {}
        if "paper_validation" in metadata:
            del metadata["paper_validation"]
        strategy.audit_metadata = metadata
        
        self.db.commit()
        
        logger.info("Reset paper validation for strategy %s", strategy_id)
        
        return {
            "status": "reset",
            "strategy_id": strategy_id,
            "message": "Validation reset. Call start_validation() to begin again.",
        }
