"""Exit evaluation task - evaluates exit rules for open positions nightly.

This task runs the 9-tier exit cascade for long positions and 4-tier cascade
for short positions, generating exit signals when positions should be reduced
or closed.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from celery import shared_task

from app.database import SessionLocal
from app.models.market_data import MarketSnapshot
from app.models.order import Order, OrderStatus
from app.models.position import Position, PositionStatus, PositionType
from app.models.signals import Signal, SignalStatus, SignalType
from app.services.execution.exit_cascade import (
    CascadeResult,
    ExitAction,
    PositionContext,
    evaluate_exit_cascade,
)
from app.services.market.regime_engine import get_current_and_previous_regime
from app.services.strategy.exit_cascade_planner import build_exit_planner_context

logger = logging.getLogger(__name__)


def _auto_submit_exit_order(order_id: int, exit_tier: str) -> None:
    """Queue exit order for execution after circuit breaker check.

    Args:
        order_id: Database ID of the order to submit
        exit_tier: Exit tier that triggered this order (for logging)
    """
    from app.services.risk.circuit_breaker import circuit_breaker

    # Check circuit breaker - exits are allowed in tier 2 but not tier 3
    allowed, reason, tier = circuit_breaker.can_trade(is_exit=True)

    if not allowed:
        logger.warning(
            "Circuit breaker blocked exit order %s: %s",
            order_id,
            reason,
        )
        return

    try:
        from app.tasks.portfolio.orders import execute_order_task

        execute_order_task.delay(order_id)
        logger.info(
            "Exit order %s queued for execution (tier: %s, cb_tier: %s)",
            order_id,
            exit_tier,
            tier,
        )
    except Exception as e:
        logger.error("Failed to queue exit order %s: %s", order_id, e)


def _build_position_context(
    position: Position,
    snapshot: MarketSnapshot,
    regime_state: str,
    previous_regime_state: str | None = None,
) -> PositionContext | None:
    """Build PositionContext from Position and MarketSnapshot.

    Returns None if required data is missing.
    """
    if not snapshot or not snapshot.current_price:
        logger.warning("No snapshot data for %s, skipping exit evaluation", position.symbol)
        return None

    # Calculate days held from position creation
    days_held = 0
    if position.created_at:
        delta = datetime.now(UTC) - position.created_at.replace(tzinfo=UTC)
        days_held = delta.days

    # Determine side from position type
    side = "LONG"
    if position.position_type in (
        PositionType.SHORT,
        PositionType.OPTION_SHORT,
        PositionType.FUTURE_SHORT,
    ):
        side = "SHORT"

    # Calculate P&L %
    # For shorts: profit when price drops (entry - current) / entry
    # For longs: profit when price rises (current - entry) / entry
    pnl_pct = 0.0
    if position.average_cost and float(position.average_cost) > 0:
        current = float(snapshot.current_price)
        entry = float(position.average_cost)
        if side == "SHORT":
            pnl_pct = ((entry - current) / entry) * 100
        else:
            pnl_pct = ((current - entry) / entry) * 100

    # Get required snapshot fields with defaults
    atr_14 = float(snapshot.atr_14 or 0)
    atrp_14 = float(snapshot.atrp_14 or 0)
    stage_label = snapshot.stage_label or "2B"
    ext_pct = float(snapshot.ext_pct or 0)
    sma150_slope = float(snapshot.sma150_slope or 0)
    ema10_dist_n = float(snapshot.ema10_dist_n or 0)
    rs_mansfield = float(snapshot.rs_mansfield_pct or 0)
    current_stage_days = int(snapshot.current_stage_days or 0)

    return PositionContext(
        symbol=position.symbol,
        side=side,
        entry_price=float(position.average_cost or snapshot.current_price),
        current_price=float(snapshot.current_price),
        atr_14=atr_14,
        atrp_14=atrp_14,
        stage_label=stage_label,
        previous_stage_label=snapshot.previous_stage_label,
        current_stage_days=current_stage_days,
        ext_pct=ext_pct,
        sma150_slope=sma150_slope,
        ema10_dist_n=ema10_dist_n,
        rs_mansfield=rs_mansfield,
        regime_state=regime_state,
        previous_regime_state=previous_regime_state,
        days_held=days_held,
        pnl_pct=pnl_pct,
    )


def _action_to_signal_type(action: ExitAction) -> SignalType:
    """Map ExitAction to SignalType."""
    if action == ExitAction.EXIT:
        return SignalType.EXIT
    elif action in (ExitAction.REDUCE_25, ExitAction.REDUCE_50):
        return SignalType.SCALE_OUT
    return SignalType.ALERT


def _create_exit_signal(
    db,
    position: Position,
    cascade_result: CascadeResult,
    snapshot: MarketSnapshot,
    planner_context: dict,
) -> Signal | None:
    """Create a Signal record for the exit recommendation."""
    from app.models.strategy import RunStatus, Strategy, StrategyRun

    # Try to find the strategy that opened this position
    # For now, create a placeholder strategy_run_id if no strategy
    strategy_id = getattr(position, "strategy_id", None)

    if not strategy_id:
        # Position not strategy-attributed, log but don't persist signal
        logger.info(
            "Exit signal for %s (%s via %s): %s - position not strategy-attributed",
            position.symbol,
            cascade_result.final_action.value,
            cascade_result.final_tier,
            cascade_result.final_reason,
        )
        return None

    # Get strategy and its latest run for exit signals
    strategy = db.query(Strategy).get(strategy_id)
    if not strategy:
        return None

    # Get the latest strategy run for this strategy
    latest_run = (
        db.query(StrategyRun)
        .filter(StrategyRun.strategy_id == strategy_id)
        .order_by(StrategyRun.started_at.desc())
        .first()
    )

    # If no strategy run exists, create a placeholder for exit evaluations
    if not latest_run:
        latest_run = StrategyRun(
            strategy_id=strategy_id,
            status=RunStatus.COMPLETED,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            run_type="exit_evaluation",
        )
        db.add(latest_run)
        db.flush()  # Get ID
        logger.info("Created placeholder StrategyRun %s for exit signals", latest_run.id)

    # Check if we already have an active exit signal for this position
    existing = (
        db.query(Signal)
        .filter(
            Signal.strategy_id == strategy_id,
            Signal.symbol == position.symbol,
            Signal.signal_type.in_([SignalType.EXIT, SignalType.SCALE_OUT]),
            Signal.status == SignalStatus.PENDING,
        )
        .first()
    )
    if existing:
        logger.debug("Exit signal already pending for %s, skipping", position.symbol)
        return None

    signal = Signal(
        strategy_id=strategy_id,
        strategy_run_id=latest_run.id,
        symbol=position.symbol,
        signal_type=_action_to_signal_type(cascade_result.final_action),
        signal_strength=cascade_result.signals[0].urgency / 10.0 if cascade_result.signals else 0.5,
        generated_at=datetime.now(UTC),
        entry_price=float(position.average_cost or snapshot.current_price),
        current_price=float(snapshot.current_price),
        status=SignalStatus.PENDING,
        audit_metadata={
            "exit_tier": cascade_result.final_tier,
            "exit_action": cascade_result.final_action.value,
            "exit_reason": cascade_result.final_reason,
            "planner_context": planner_context,
            "all_signals": [
                {"tier": s.tier, "action": s.action.value, "reason": s.reason, "urgency": s.urgency}
                for s in cascade_result.signals
            ],
        },
    )
    db.add(signal)
    return signal


def _create_exit_order(
    db,
    position: Position,
    cascade_result: CascadeResult,
    snapshot: MarketSnapshot,
) -> Order | None:
    """Create an order for the exit if auto-execute is enabled."""
    strategy_id = getattr(position, "strategy_id", None)
    if not strategy_id:
        return None

    from app.models.strategy import Strategy

    strategy = db.query(Strategy).get(strategy_id)
    if not strategy or not strategy.auto_execute:
        return None

    # Determine quantity to sell
    qty = float(position.quantity or 0)
    if cascade_result.final_action == ExitAction.REDUCE_25:
        qty = qty * 0.25
    elif cascade_result.final_action == ExitAction.REDUCE_50:
        qty = qty * 0.50
    # ExitAction.EXIT = full quantity

    if qty <= 0:
        return None

    side = "sell" if position.position_type != PositionType.SHORT else "buy"  # Buy to cover shorts

    order = Order(
        symbol=position.symbol,
        side=side,
        order_type="market",
        status=OrderStatus.PREVIEW.value,
        quantity=int(qty),
        source="exit_cascade",
        strategy_id=strategy_id,
        position_id=position.id,
        user_id=position.user_id,
        created_by=f"exit_cascade:{cascade_result.final_tier}",
        broker_type="ibkr",
    )
    db.add(order)
    return order


@shared_task(
    name="app.tasks.strategy.exit_evaluation.evaluate_exits_task",
    soft_time_limit=600,
    time_limit=660,
)
def evaluate_exits_task() -> dict:
    """Evaluate exit rules for all open positions.

    Runs the 9-tier exit cascade for longs and 4-tier for shorts.
    Generates exit signals and optionally creates exit orders.
    """
    db = SessionLocal()
    try:
        # Get current and previous regime for transition detection
        regime_row, prev_regime_row = get_current_and_previous_regime(db)
        regime_state = regime_row.regime_state if regime_row else "R3"
        previous_regime_state = prev_regime_row.regime_state if prev_regime_row else None

        # Load all open positions
        positions = (
            db.query(Position)
            .filter(
                Position.status == PositionStatus.OPEN,
                Position.quantity > 0,
                Position.instrument_type == "STOCK",  # Equity only for now
            )
            .all()
        )

        if not positions:
            logger.info("No open positions to evaluate for exits")
            return {"evaluated": 0, "signals": 0, "orders": 0}

        # Build symbol -> latest snapshot map
        symbols = list(set(p.symbol for p in positions))
        snapshots = {}
        for sym in symbols:
            snap = (
                db.query(MarketSnapshot)
                .filter(
                    MarketSnapshot.symbol == sym,
                    MarketSnapshot.analysis_type == "technical_snapshot",
                )
                .order_by(MarketSnapshot.analysis_timestamp.desc())
                .first()
            )
            if snap:
                snapshots[sym] = snap

        evaluated = 0
        signals_created = 0
        orders_created = 0
        exit_recommendations = []
        # Queue execute_order_task only after db.commit() so workers see persisted rows.
        pending_exit_order_submits: list[tuple[int, str]] = []

        for position in positions:
            snapshot = snapshots.get(position.symbol)
            if not snapshot:
                continue

            # Build context
            ctx = _build_position_context(position, snapshot, regime_state, previous_regime_state)
            if not ctx:
                continue

            # Run exit cascade
            result = evaluate_exit_cascade(ctx)
            planner_context = {}
            if position.account is not None:
                planner_context = build_exit_planner_context(position.account)
            evaluated += 1

            # Only act on non-HOLD results
            if result.final_action != ExitAction.HOLD:
                exit_recommendations.append(
                    {
                        "symbol": position.symbol,
                        "action": result.final_action.value,
                        "tier": result.final_tier,
                        "reason": result.final_reason,
                        "pnl_pct": ctx.pnl_pct,
                    }
                )

                # Create exit signal
                signal = _create_exit_signal(
                    db,
                    position,
                    result,
                    snapshot,
                    planner_context,
                )
                if signal:
                    signals_created += 1

                # Create exit order if auto-execute
                order = _create_exit_order(db, position, result, snapshot)
                if order:
                    orders_created += 1
                    db.flush()  # Get order.id
                    logger.info(
                        "Exit order created: %s %s %d shares (%s via %s)",
                        order.side,
                        position.symbol,
                        order.quantity,
                        result.final_action.value,
                        result.final_tier,
                    )
                    pending_exit_order_submits.append((order.id, result.final_tier))

        db.commit()

        for order_id, exit_tier in pending_exit_order_submits:
            _auto_submit_exit_order(order_id, exit_tier)

        # Notify Brain of exit alerts
        if exit_recommendations:
            from app.services.brain.webhook_client import brain_webhook

            brain_webhook.notify_sync(
                "exit_alert",
                {
                    "count": len(exit_recommendations),
                    "signals_created": signals_created,
                    "orders_created": orders_created,
                    "recommendations": exit_recommendations,
                },
            )

            logger.info(
                "Exit evaluation complete: %d positions, %d exit recommendations, %d signals, %d orders",
                evaluated,
                len(exit_recommendations),
                signals_created,
                orders_created,
            )
            for rec in exit_recommendations:
                logger.info(
                    "  %s: %s via %s - %s (P&L: %.1f%%)",
                    rec["symbol"],
                    rec["action"],
                    rec["tier"],
                    rec["reason"],
                    rec["pnl_pct"],
                )
        else:
            logger.info("Exit evaluation complete: %d positions, all holding", evaluated)

        return {
            "evaluated": evaluated,
            "signals": signals_created,
            "orders": orders_created,
            "recommendations": exit_recommendations,
        }
    except Exception:
        db.rollback()
        logger.exception("Exit evaluation task failed")
        raise
    finally:
        db.close()
