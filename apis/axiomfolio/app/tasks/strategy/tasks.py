"""Celery tasks for strategy rule evaluation."""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app
from app.tasks.utils.task_utils import task_run
from app.database import SessionLocal
from app.models.strategy import Strategy, StrategyStatus, StrategyRun, RunStatus, ExecutionMode
from app.models.market_data import MarketSnapshot
from app.models.signals import Signal, SignalType, SignalStatus
from app.services.gold.strategy.rule_evaluator import (
    RuleEvaluator,
    ConditionGroup,
    Condition,
    ConditionOperator,
    LogicalOperator,
)
from app.services.gold.strategy.signal_generator import SignalGenerator
from app.services.gold.strategy.context_builder import snapshot_to_context, get_regime_context
from sqlalchemy import func

logger = logging.getLogger(__name__)

_evaluator = RuleEvaluator()
_signal_gen = SignalGenerator()


def _parse_rules_from_config(parameters: dict, key: str = "entry_rules") -> ConditionGroup | None:
    """Build a ConditionGroup from the strategy's parameters dict.

    Supports both new format (entry_rules/exit_rules) and legacy (rules).
    """
    rules = parameters.get(key) or parameters.get("rules")
    if not rules or not isinstance(rules, dict):
        return None
    return _parse_group(rules)


def _parse_group(data: dict) -> ConditionGroup:
    logic = LogicalOperator(data.get("logic", "and"))
    conditions = [
        Condition(
            field=c["field"],
            operator=ConditionOperator(c["operator"]),
            value=c["value"],
            value_high=c.get("value_high"),
        )
        for c in data.get("conditions", [])
    ]
    groups = [_parse_group(g) for g in data.get("groups", [])]
    return ConditionGroup(logic=logic, conditions=conditions, groups=groups)


@celery_app.task(name="app.tasks.strategy_tasks.evaluate_strategies_task", soft_time_limit=600, time_limit=660)
@task_run("strategy_evaluation")
def evaluate_strategies_task() -> dict:
    """Find all active strategies, run RuleEvaluator against latest snapshot data."""
    db = SessionLocal()
    try:
        strategies = (
            db.query(Strategy)
            .filter(Strategy.status == StrategyStatus.ACTIVE)
            .all()
        )
        if not strategies:
            logger.info("No active strategies to evaluate")
            return {"evaluated": 0, "total_signals": 0}

        latest_ids = (
            db.query(func.max(MarketSnapshot.id).label("id"))
            .filter(
                MarketSnapshot.analysis_type == "technical_snapshot",
                MarketSnapshot.is_valid.is_(True),
            )
            .group_by(MarketSnapshot.symbol)
            .subquery()
        )
        snapshots = (
            db.query(MarketSnapshot)
            .join(latest_ids, MarketSnapshot.id == latest_ids.c.id)
            .all()
        )
        # Build context with aliases and regime included
        snapshot_contexts = {
            s.symbol: snapshot_to_context(s, include_regime=True, db=db)
            for s in snapshots
        }

        total_signals = 0
        results = []
        pending_order_ids: list[int] = []

        for strategy in strategies:
            started = datetime.now(timezone.utc)
            group = _parse_rules_from_config(strategy.parameters or {})
            if group is None:
                logger.warning(
                    "Strategy %s (%s) has no valid rules in parameters, skipping",
                    strategy.id,
                    strategy.name,
                )
                continue

            universe_symbols = list(snapshot_contexts.keys())
            if strategy.allowed_sectors:
                universe_symbols = [
                    sym for sym in universe_symbols
                    if snapshot_contexts[sym].get("sector") in strategy.allowed_sectors
                ]
            if strategy.excluded_symbols:
                excluded = set(strategy.excluded_symbols)
                universe_symbols = [sym for sym in universe_symbols if sym not in excluded]

            strategy_type = (strategy.parameters or {}).get("strategy_type", "")
            is_short = strategy_type == "short" or "short" in (strategy.name or "").lower()

            matches = []
            for sym in universe_symbols:
                ctx = snapshot_contexts[sym]
                result = _evaluator.evaluate(group, ctx)
                if result.matched:
                    matches.append({
                        "symbol": sym,
                        "action": "sell_short" if is_short else "buy",
                        "strength": 1.0,
                        "context": result.details,
                        "regime_state": ctx.get("regime_state"),
                        "regime_multiplier": ctx.get("regime_multiplier"),
                        "scan_tier": ctx.get("scan_tier"),
                        "action_label": ctx.get("action_label"),
                        "stage_label": ctx.get("stage_label"),
                        "ext_pct": ctx.get("ext_pct"),
                        "ema10_dist_n": ctx.get("ema10_dist_n"),
                        "sma150_slope": ctx.get("sma150_slope"),
                    })

            signals = _signal_gen.generate_signals(db, strategy, matches)
            total_signals += len(signals)

            run = StrategyRun(
                strategy_id=strategy.id,
                run_date=started,
                status=RunStatus.COMPLETED,
                execution_mode=strategy.execution_mode or ExecutionMode.PAPER,
                universe_size=len(universe_symbols),
                candidates_found=len(matches),
                signals_generated=len(signals),
                started_at=started,
                completed_at=datetime.now(timezone.utc),
            )
            db.add(run)
            db.flush()

            persisted_signals = _persist_signals(db, strategy, run, signals, snapshot_contexts)

            strategy.last_run_at = started
            strategy.last_run_status = RunStatus.COMPLETED

            auto_orders = 0
            if (
                strategy.auto_execute
                and persisted_signals
                and _is_auto_trading_enabled()
                and (strategy.execution_mode or ExecutionMode.PAPER) == ExecutionMode.LIVE
            ):
                n, _oids = _auto_execute_signals(db, strategy, persisted_signals)
                auto_orders = n
                pending_order_ids.extend(_oids)

            results.append({
                "strategy_id": strategy.id,
                "name": strategy.name,
                "universe": len(universe_symbols),
                "matches": len(matches),
                "signals": len(signals),
                "auto_orders": auto_orders,
            })

        db.commit()

        if pending_order_ids:
            try:
                from app.tasks.portfolio.orders import execute_order_task

                for oid in pending_order_ids:
                    execute_order_task.delay(oid)
            except Exception:
                logger.exception(
                    "Failed to queue execute_order_task for order ids: %s",
                    pending_order_ids,
                )

        logger.info(
            "Strategy evaluation complete: %d strategies, %d total signals",
            len(results),
            total_signals,
        )
        return {"evaluated": len(results), "total_signals": total_signals, "details": results}
    except Exception:
        db.rollback()
        logger.exception("Strategy evaluation task failed")
        raise
    finally:
        db.close()


def _is_auto_trading_enabled() -> bool:
    """Kill-switch check: admin can disable auto-trading globally."""
    return os.getenv("ENABLE_AUTO_TRADING", "false").lower() in ("true", "1", "yes")


def _persist_signals(
    db,
    strategy: Strategy,
    run: StrategyRun,
    raw_signals: list,
    snapshot_contexts: dict,
) -> list[Signal]:
    """Persist generated signals to the Signal table."""
    persisted = []
    now = datetime.now(timezone.utc)
    for sig in raw_signals:
        sym = sig["symbol"]
        action = (sig.get("action") or "buy").lower()
        ctx = snapshot_contexts.get(sym, {})
        current_price = ctx.get("current_price", 0) or 0
        if action in ("sell_short", "short"):
            stype = SignalType.ENTRY
        elif action == "sell":
            stype = SignalType.EXIT
        else:
            stype = SignalType.ENTRY
        signal_obj = Signal(
            strategy_id=strategy.id,
            strategy_run_id=run.id,
            symbol=sym,
            signal_type=stype,
            signal_strength=sig.get("strength", 1.0),
            generated_at=now,
            entry_price=current_price,
            current_price=current_price,
            rsi=ctx.get("rsi_14"),
            sector=ctx.get("sector"),
            company_name=ctx.get("company_name"),
            market_cap=ctx.get("market_cap"),
            status=SignalStatus.PENDING,
            audit_metadata={"action": action},
        )
        db.add(signal_obj)
        persisted.append(signal_obj)
    db.flush()
    return persisted


def _order_side_from_signal(sig: Signal) -> str:
    """Map persisted signal intent to broker order side."""
    meta = sig.audit_metadata or {}
    action = (meta.get("action") or "buy").lower()
    if action in ("sell_short", "short", "sell"):
        return "sell"
    return "buy"


def _auto_execute_signals(
    db,
    strategy: Strategy,
    signals: list[Signal],
) -> tuple[int, list[int]]:
    """Create orders for each signal when auto_execute is enabled.

    Returns (count, order_ids). Celery execution is queued by the caller after commit.
    
    Note: Orders are created with PREVIEW status so OrderManager.submit() will accept them.
    The user_id is inherited from the strategy owner.
    
    All auto-orders are validated through RiskGate before creation.
    """
    from app.models.order import Order, OrderStatus
    from app.services.execution.risk_gate import RiskGate, RiskViolation
    from app.services.execution.broker_base import OrderRequest

    risk_gate = RiskGate()
    count = 0
    order_ids: list[int] = []
    
    # Get portfolio equity for risk checks
    portfolio_equity = _get_user_portfolio_equity(db, strategy.user_id)
    params = strategy.parameters or {}
    risk_budget = params.get("risk_budget", 1000.0)
    
    for sig in signals:
        try:
            order_side = _order_side_from_signal(sig)
            quantity = _compute_position_size(db, strategy, sig)
            
            # Skip order creation when position size is zero (Stage cap blocks entry)
            if quantity <= 0:
                logger.info(
                    "Skipping auto-order for %s: position size is 0 (Stage cap or sizing constraint)",
                    sig.symbol,
                )
                continue
            
            # Build OrderRequest for RiskGate validation
            price_estimate = float(sig.entry_price) if sig.entry_price else 0.0
            req = OrderRequest.from_user_input(
                symbol=sig.symbol,
                side=order_side,
                order_type="market",
                quantity=quantity,
            )
            
            # Validate through RiskGate before creating order
            try:
                warnings = risk_gate.check(
                    req=req,
                    price_estimate=price_estimate,
                    db=db,
                    portfolio_equity=portfolio_equity,
                    risk_budget=float(risk_budget),
                )
                if warnings:
                    logger.info(
                        "RiskGate warnings for %s: %s",
                        sig.symbol, "; ".join(warnings),
                    )
            except RiskViolation as rv:
                logger.warning(
                    "RiskGate rejected auto-order for %s: %s",
                    sig.symbol, str(rv),
                )
                continue
            
            order = Order(
                symbol=sig.symbol,
                side=order_side,
                order_type="market",
                status=OrderStatus.PREVIEW.value,  # Must be PREVIEW for OrderManager.submit()
                quantity=quantity,
                source="strategy",
                strategy_id=strategy.id,
                signal_id=sig.id,
                user_id=strategy.user_id,  # Required for OrderManager operations
                created_by=f"strategy:{strategy.id}",
                broker_type="ibkr",
            )
            db.add(order)
            db.flush()
            order_ids.append(order.id)
            sig.is_executed = True
            sig.status = SignalStatus.TRIGGERED
            count += 1
            logger.info(
                "Auto-order created for signal %s %s (side=%s, qty=%s) from strategy %s",
                sig.signal_type.value,
                sig.symbol,
                order_side,
                quantity,
                strategy.name,
            )
        except Exception:
            logger.exception("Failed to auto-create order for signal %s", sig.id)
    db.flush()
    return count, order_ids


def _get_user_portfolio_equity(db, user_id: int) -> float | None:
    """Lookup total portfolio equity for a user."""
    if not user_id:
        return None
    try:
        from app.models.account_balance import AccountBalance
        balance = (
            db.query(AccountBalance)
            .filter(AccountBalance.user_id == user_id)
            .order_by(AccountBalance.as_of_date.desc())
            .first()
        )
        if balance and balance.total_value:
            return float(balance.total_value)
    except Exception as e:
        logger.warning("Failed to lookup portfolio equity for user %s: %s", user_id, e)
    return None


def _compute_position_size(db, strategy: Strategy, signal: Signal) -> float:
    """Compute position size using Stage Analysis sizing formula when possible.
    
    Falls back to strategy parameters or defaults if sizing data unavailable.
    """
    from app.services.gold.position_sizing import compute_position_size
    from app.services.silver.regime.regime_engine import get_current_regime
    from app.models.market_data import MarketSnapshot
    
    params = strategy.parameters or {}
    
    # Honor explicit fixed size from strategy params
    fixed = params.get("position_size") or params.get("quantity")
    if fixed:
        return float(fixed)
    
    # Try Stage Analysis sizing
    sym = signal.symbol.upper()
    snap = (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.symbol == sym,
            MarketSnapshot.analysis_type == "technical_snapshot",
        )
        .order_by(MarketSnapshot.analysis_timestamp.desc())
        .first()
    )
    
    if snap and snap.atrp_14 and snap.stage_label and signal.entry_price:
        regime = get_current_regime(db)
        regime_state = regime.regime_state if regime else "R3"
        
        # Use strategy risk budget or default 1% of typical account ($100k = $1k risk)
        risk_budget = params.get("risk_budget", 1000.0)
        stop_multiplier = params.get("stop_multiplier", 2.0)
        
        result = compute_position_size(
            risk_budget=float(risk_budget),
            atrp_14=float(snap.atrp_14),
            stop_multiplier=float(stop_multiplier),
            regime_state=regime_state,
            stage_label=snap.stage_label,
            current_price=float(signal.entry_price),
        )
        
        if result.shares > 0:
            logger.debug(
                "Sizing %s: stage=%s, regime=%s, cap=%.0f%%, shares=%d",
                sym, snap.stage_label, regime_state, result.stage_cap * 100, result.shares
            )
            return float(result.shares)
        else:
            logger.warning(
                "Sizing %s: stage=%s in regime=%s has 0%% cap, skipping",
                sym, snap.stage_label, regime_state
            )
            return 0  # Stage cap blocks this entry
    
    # Fallback to simple max_value sizing
    max_value = params.get("max_position_value", 5_000)
    if signal.entry_price and signal.entry_price > 0:
        return max(1, int(max_value / signal.entry_price))
    return 1


def _compute_default_quantity(strategy: Strategy, signal: Signal) -> float:
    """Legacy wrapper - use _compute_position_size for new code."""
    params = strategy.parameters or {}
    fixed = params.get("position_size") or params.get("quantity")
    if fixed:
        return float(fixed)
    max_value = params.get("max_position_value", 5_000)
    if signal.entry_price and signal.entry_price > 0:
        return max(1, int(max_value / signal.entry_price))
    return 1
