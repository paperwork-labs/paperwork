"""
Auto-Backtest Pipeline.

Automatically runs backtests when strategies are created or updated.
Provides confidence scoring and veto gates before a strategy goes live.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from celery import shared_task
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.backtest import StrategyBacktest, BacktestStatus
from app.models.strategy import Strategy, StrategyStatus
from app.services.gold.strategy.backtest_engine import BacktestEngine, BacktestResult
from app.services.gold.strategy.rule_evaluator import ConditionGroup

logger = logging.getLogger(__name__)


# Veto gate thresholds
VETO_MIN_SHARPE = 0.5
VETO_MAX_DRAWDOWN = 0.30  # 30%
VETO_MIN_WIN_RATE = 0.35
VETO_MIN_PROFIT_FACTOR = 1.2
VETO_MIN_TRADES = 20  # Need enough trades for statistical significance


@shared_task(
    bind=True,
    name="strategy.auto_backtest",
    time_limit=300,  # 5 minutes max
    soft_time_limit=270,
)
def run_auto_backtest(
    self,
    strategy_id: int,
    triggered_by: str = "auto",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    initial_capital: float = 100000,
) -> dict:
    """
    Run backtest for a strategy and store results.

    Args:
        strategy_id: ID of strategy to backtest
        triggered_by: "auto", "manual", "api"
        start_date: ISO date string, defaults to 2 years ago
        end_date: ISO date string, defaults to yesterday
        initial_capital: Starting capital for backtest

    Returns:
        Dict with backtest_id and summary
    """
    db: Session = SessionLocal()
    start_time = datetime.now(timezone.utc)

    try:
        # Load strategy
        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not strategy:
            logger.error("Strategy %s not found", strategy_id)
            return {"error": f"Strategy {strategy_id} not found"}

        # Parse dates
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
        else:
            end_dt = datetime.now(timezone.utc) - timedelta(days=1)

        if start_date:
            start_dt = datetime.fromisoformat(start_date)
        else:
            start_dt = end_dt - timedelta(days=730)  # 2 years

        # Create backtest record
        backtest = StrategyBacktest(
            strategy_id=strategy_id,
            user_id=strategy.user_id,
            status=BacktestStatus.RUNNING,
            start_date=start_dt,
            end_date=end_dt,
            initial_capital=initial_capital,
            triggered_by=triggered_by,
            strategy_snapshot=_snapshot_strategy(strategy),
        )
        db.add(backtest)
        db.commit()
        db.refresh(backtest)

        logger.info(
            "Starting backtest %s for strategy %s (%s to %s)",
            backtest.id,
            strategy_id,
            start_dt.date(),
            end_dt.date(),
        )

        # Run the backtest
        engine = BacktestEngine(slippage_bps=5.0, commission_per_trade=1.0)

        # Get universe from strategy
        universe = _get_strategy_universe(strategy)

        # Get entry/exit rules from strategy parameters and convert to ConditionGroup
        entry_rules_json = strategy.parameters.get("entry_rules", []) if strategy.parameters else []
        exit_rules_json = strategy.parameters.get("exit_rules", []) if strategy.parameters else []
        
        try:
            entry_rules = ConditionGroup.from_json(entry_rules_json)
            exit_rules = ConditionGroup.from_json(exit_rules_json)
        except ValueError as e:
            logger.error("Invalid strategy rules for %s: %s", strategy_id, e)
            backtest.status = BacktestStatus.FAILED
            backtest.error_message = f"Invalid rules: {e}"
            backtest.completed_at = datetime.now(timezone.utc)
            db.commit()
            return {"error": str(e), "status": "failed"}

        result = engine.run(
            db=db,
            symbols=universe,
            entry_rules=entry_rules,
            exit_rules=exit_rules,
            start_date=start_dt.date(),
            end_date=end_dt.date(),
            initial_capital=initial_capital,
        )

        # Store results
        _store_backtest_results(db, backtest, result)

        # Apply veto gates
        veto_passed, veto_reasons = _check_veto_gates(result)
        backtest.passed_veto_gates = veto_passed
        backtest.veto_reasons = veto_reasons

        # Calculate confidence score
        backtest.confidence_score = _calculate_confidence(result, veto_passed)

        # Update status
        backtest.status = BacktestStatus.COMPLETED
        backtest.completed_at = datetime.now(timezone.utc)
        backtest.execution_time_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )

        db.commit()

        logger.info(
            "Backtest %s completed: return=%.2f%%, sharpe=%.2f, veto=%s, confidence=%.0f",
            backtest.id,
            float(backtest.total_return_pct or 0),
            float(backtest.sharpe_ratio or 0),
            "PASS" if veto_passed else "FAIL",
            float(backtest.confidence_score or 0),
        )

        return {
            "backtest_id": backtest.id,
            "status": "completed",
            "total_return_pct": float(backtest.total_return_pct or 0),
            "sharpe_ratio": float(backtest.sharpe_ratio or 0),
            "max_drawdown_pct": float(backtest.max_drawdown_pct or 0),
            "total_trades": backtest.total_trades,
            "win_rate": float(backtest.win_rate or 0),
            "passed_veto_gates": veto_passed,
            "confidence_score": float(backtest.confidence_score or 0),
        }

    except Exception as e:
        logger.exception("Backtest failed for strategy %s: %s", strategy_id, e)

        # Update backtest status if it was created
        if "backtest" in locals():
            backtest.status = BacktestStatus.FAILED
            backtest.error_message = str(e)
            backtest.completed_at = datetime.now(timezone.utc)
            db.commit()

        return {"error": str(e), "status": "failed"}

    finally:
        db.close()


def _snapshot_strategy(strategy: Strategy) -> dict:
    """Capture strategy configuration at time of backtest."""
    return {
        "name": strategy.name,
        "type": strategy.strategy_type.value if strategy.strategy_type else None,
        "status": strategy.status.value if strategy.status else None,
        "parameters": strategy.parameters,
        "stop_loss_pct": float(strategy.stop_loss_pct) if strategy.stop_loss_pct else None,
        "take_profit_pct": float(strategy.take_profit_pct) if strategy.take_profit_pct else None,
        "max_positions": strategy.max_positions,
    }


def _get_strategy_universe(strategy: Strategy) -> list:
    """Get list of symbols to backtest."""
    universe = []

    # From universe_filter
    if strategy.universe_filter:
        universe.extend(strategy.universe_filter.get("symbols", []))

    # Fallback to default universe
    if not universe:
        universe = ["SPY", "QQQ", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META"]

    return universe


def _store_backtest_results(
    db: Session,
    backtest: StrategyBacktest,
    result: BacktestResult,
) -> None:
    """Store backtest results in the database."""
    metrics = result.metrics

    # Core metrics
    backtest.final_capital = metrics.final_capital
    backtest.total_return_pct = metrics.total_return_pct
    backtest.max_drawdown_pct = metrics.max_drawdown_pct
    backtest.sharpe_ratio = metrics.sharpe_ratio
    backtest.sortino_ratio = metrics.sortino_ratio

    # Trade statistics
    backtest.total_trades = metrics.total_trades
    backtest.win_rate = metrics.win_rate
    backtest.profit_factor = metrics.profit_factor
    backtest.avg_trade_pnl = metrics.avg_trade_pnl
    backtest.max_win = metrics.max_win
    backtest.max_loss = metrics.max_loss

    # Calculate winning/losing trades
    if result.trades:
        backtest.winning_trades = sum(1 for t in result.trades if t.pnl > 0)
        backtest.losing_trades = sum(1 for t in result.trades if t.pnl < 0)

    # Raw data for charting
    backtest.equity_curve = result.equity_curve
    backtest.trades_json = [
        {
            "symbol": t.symbol,
            "side": t.side,
            "quantity": t.quantity,
            "price": t.price,
            "date": t.date,
            "pnl": t.pnl,
        }
        for t in result.trades
    ]
    backtest.daily_returns = result.daily_returns

    # Stats
    backtest.bars_processed = len(result.equity_curve) if result.equity_curve else 0


def _check_veto_gates(result: BacktestResult) -> tuple:
    """
    Check if backtest passes minimum quality gates.

    Returns (passed: bool, reasons: list)
    """
    reasons = []
    metrics = result.metrics

    if metrics.sharpe_ratio is not None and metrics.sharpe_ratio < VETO_MIN_SHARPE:
        reasons.append(f"Sharpe ratio {metrics.sharpe_ratio:.2f} < {VETO_MIN_SHARPE}")

    if metrics.max_drawdown_pct is not None and metrics.max_drawdown_pct > VETO_MAX_DRAWDOWN * 100:
        reasons.append(
            f"Max drawdown {metrics.max_drawdown_pct:.1f}% > {VETO_MAX_DRAWDOWN * 100:.0f}%"
        )

    if metrics.win_rate is not None and metrics.win_rate < VETO_MIN_WIN_RATE:
        reasons.append(f"Win rate {metrics.win_rate:.1%} < {VETO_MIN_WIN_RATE:.0%}")

    if metrics.profit_factor is not None and metrics.profit_factor < VETO_MIN_PROFIT_FACTOR:
        reasons.append(f"Profit factor {metrics.profit_factor:.2f} < {VETO_MIN_PROFIT_FACTOR}")

    if metrics.total_trades < VETO_MIN_TRADES:
        reasons.append(f"Only {metrics.total_trades} trades (need {VETO_MIN_TRADES}+ for significance)")

    passed = len(reasons) == 0
    return passed, reasons


def _calculate_confidence(result: BacktestResult, veto_passed: bool) -> float:
    """
    Calculate confidence score (0-100) for the strategy.

    Higher = more confident the strategy will perform.
    """
    if not veto_passed:
        return 0.0

    metrics = result.metrics
    score = 50.0  # Start at neutral

    # Sharpe ratio (max +20)
    if metrics.sharpe_ratio:
        sharpe_bonus = min(metrics.sharpe_ratio * 10, 20)
        score += sharpe_bonus

    # Win rate (max +15)
    if metrics.win_rate:
        if metrics.win_rate > 0.5:
            score += (metrics.win_rate - 0.5) * 30  # Up to +15

    # Profit factor (max +10)
    if metrics.profit_factor and metrics.profit_factor > 1.5:
        score += min((metrics.profit_factor - 1.5) * 5, 10)

    # Trade count (max +5)
    if metrics.total_trades > 50:
        score += 5
    elif metrics.total_trades > 30:
        score += 3

    # Drawdown penalty (max -15)
    if metrics.max_drawdown_pct and metrics.max_drawdown_pct > 15:
        score -= min((metrics.max_drawdown_pct - 15) / 2, 15)

    return max(0, min(100, score))


@shared_task(
    bind=True,
    name="strategy.trigger_auto_backtest",
    time_limit=30,
    soft_time_limit=25,
)
def trigger_auto_backtest_on_change(
    self,
    strategy_id: int,
    change_type: str = "update",
) -> dict:
    """
    Called when strategy is created/updated to trigger backtest.

    This is a lightweight task that checks if backtest is needed
    and queues the actual backtest task.
    """
    db: Session = SessionLocal()

    try:
        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not strategy:
            return {"skipped": True, "reason": "Strategy not found"}

        # Only backtest active or draft strategies
        if strategy.status not in [StrategyStatus.ACTIVE, StrategyStatus.DRAFT]:
            return {"skipped": True, "reason": f"Strategy status is {strategy.status.value}"}

        # Check if recent backtest exists (within last hour)
        recent_backtest = (
            db.query(StrategyBacktest)
            .filter(
                StrategyBacktest.strategy_id == strategy_id,
                StrategyBacktest.created_at >= datetime.now(timezone.utc) - timedelta(hours=1),
                StrategyBacktest.status == BacktestStatus.COMPLETED,
            )
            .first()
        )

        if recent_backtest:
            return {
                "skipped": True,
                "reason": "Recent backtest exists",
                "backtest_id": recent_backtest.id,
            }

        # Queue the backtest
        task = run_auto_backtest.delay(strategy_id, triggered_by="auto")

        logger.info(
            "Queued auto-backtest for strategy %s (change: %s), task_id=%s",
            strategy_id,
            change_type,
            task.id,
        )

        return {
            "queued": True,
            "task_id": task.id,
            "strategy_id": strategy_id,
        }

    finally:
        db.close()
