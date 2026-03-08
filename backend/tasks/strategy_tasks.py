"""Celery tasks for strategy rule evaluation."""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from backend.tasks.celery_app import celery_app
from backend.database import SessionLocal
from backend.models.strategy import Strategy, StrategyStatus, StrategyRun, RunStatus, ExecutionMode
from backend.models.market_data import MarketSnapshot
from backend.services.strategy.rule_evaluator import (
    RuleEvaluator,
    ConditionGroup,
    Condition,
    ConditionOperator,
    LogicalOperator,
)
from backend.services.strategy.signal_generator import SignalGenerator
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


def _snapshot_to_context(snap: MarketSnapshot) -> dict:
    ctx: dict = {"symbol": snap.symbol}
    skip = {"id", "raw_analysis", "created_at", "updated_at", "metadata"}
    for col in snap.__table__.columns:
        if col.name in skip:
            continue
        val = getattr(snap, col.name, None)
        if val is not None:
            ctx[col.name] = val
    return ctx


@celery_app.task(name="backend.tasks.strategy_tasks.evaluate_strategies_task")
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
        snapshot_contexts = {s.symbol: _snapshot_to_context(s) for s in snapshots}

        total_signals = 0
        results = []

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

            matches = []
            for sym in universe_symbols:
                ctx = snapshot_contexts[sym]
                result = _evaluator.evaluate(group, ctx)
                if result.matched:
                    matches.append({
                        "symbol": sym,
                        "action": "buy",
                        "strength": 1.0,
                        "context": result.details,
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

            strategy.last_run_at = started
            strategy.last_run_status = RunStatus.COMPLETED

            results.append({
                "strategy_id": strategy.id,
                "name": strategy.name,
                "universe": len(universe_symbols),
                "matches": len(matches),
                "signals": len(signals),
            })

        db.commit()
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
