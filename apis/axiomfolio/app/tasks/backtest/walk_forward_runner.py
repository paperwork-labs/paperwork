"""Celery wrapper that executes a :class:`WalkForwardStudy`.

Lives on the ``heavy`` queue because a 50-trial / 5-split study can run
30+ minutes. Time limits match the row's expectation (set in
``job_catalog.py``); the lock is implicit (one row per Celery task) — a
study row can only be enqueued once.

Strategy resolution
-------------------
The route validates ``strategy_class`` against
:data:`STRATEGY_REGISTRY`. Each registry entry is a builder callable that
takes a parameter dict and returns ``(entry_rules, exit_rules)`` for the
existing :class:`BacktestEngine`. Adding a new bookable strategy means
appending one entry; we deliberately keep this list short because every
entry is a public surface a paying customer can run a study against.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from celery import shared_task
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.walk_forward_study import WalkForwardStatus, WalkForwardStudy
from app.services.backtest.regime_attribution import db_regime_lookup
from app.services.backtest.walk_forward import (
    StrategyBuilder,
    WalkForwardOptimizer,
    build_default_runner,
)
from app.services.strategy.rule_evaluator import (
    Condition,
    ConditionGroup,
    ConditionOperator,
    LogicalOperator,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------


def _stage2_breakout_builder(
    params: dict[str, Any],
) -> tuple[ConditionGroup, ConditionGroup]:
    """Reference Stage-2 breakout strategy.

    Parameters consumed:

    - ``rsi_max``  (int):   max RSI(14) accepted on entry — guards against
                              chasing exhausted moves.
    - ``vol_ratio_min`` (float): minimum volume ratio (today/avg) required
                                  for breakout confirmation.
    - ``stop_atr_mult`` (float): exit when ``current_price`` falls more
                                 than ``mult * atr14`` below ``ema21``.
    """
    rsi_max = float(params.get("rsi_max", 70))
    vol_min = float(params.get("vol_ratio_min", 1.5))
    stop_mult = float(params.get("stop_atr_mult", 2.0))

    entry = ConditionGroup(
        logic=LogicalOperator.AND,
        conditions=[
            Condition(field="stage", operator=ConditionOperator.EQ, value="2A"),
            Condition(field="rsi14", operator=ConditionOperator.LT, value=rsi_max),
            Condition(
                field="vol_ratio_20",
                operator=ConditionOperator.GTE,
                value=vol_min,
            ),
        ],
    )
    exit_ = ConditionGroup(
        logic=LogicalOperator.OR,
        conditions=[
            Condition(
                field="stage", operator=ConditionOperator.IN, value=["3A", "3B", "4A", "4B", "4C"]
            ),
            Condition(field="rsi14", operator=ConditionOperator.GT, value=85),
        ],
    )
    # ``stop_mult`` is consumed by exit_cascade in production; for the
    # rules-engine we approximate it as a hard-stop on extension below
    # ema21 normalized by ATR. This keeps the param meaningful even when
    # the engine cannot model true trailing stops.
    exit_.conditions.append(
        Condition(
            field="ema21_dist_atr",
            operator=ConditionOperator.LT,
            value=-stop_mult,
        )
    )
    return entry, exit_


STRATEGY_REGISTRY: dict[str, StrategyBuilder] = {
    "stage2_breakout": _stage2_breakout_builder,
}


def list_strategy_classes() -> list[str]:
    return sorted(STRATEGY_REGISTRY.keys())


def get_strategy_builder(name: str) -> StrategyBuilder:
    if name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy_class '{name}'. Available: {list_strategy_classes()}")
    return STRATEGY_REGISTRY[name]


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


@shared_task(
    bind=True,
    name="backtest.walk_forward_run",
    queue="heavy",
    time_limit=3600,
    soft_time_limit=3300,
    acks_late=True,
)
def run_walk_forward_study(self, study_id: int) -> dict:
    """Drive one ``WalkForwardStudy`` row to ``COMPLETED`` (or ``FAILED``).

    Failure modes are tracked on the row itself — never silently zeroed.
    The frontend polls the row by id to surface progress + results.
    """
    db: Session = SessionLocal()
    try:
        study = db.query(WalkForwardStudy).filter(WalkForwardStudy.id == study_id).first()
        if not study:
            logger.error("walk_forward_study %s not found — aborting task", study_id)
            return {"error": "study_not_found", "study_id": study_id}

        # Idempotency guard: never restart a study that already finished.
        # ``acks_late`` + a duplicated trigger would otherwise spawn parallel
        # work and overwrite results.
        if study.status in (
            WalkForwardStatus.COMPLETED,
            WalkForwardStatus.FAILED,
            WalkForwardStatus.RUNNING,
        ):
            logger.info(
                "walk_forward_study %s already in status %s — skipping",
                study_id,
                study.status.value,
            )
            return {
                "skipped": True,
                "study_id": study_id,
                "status": study.status.value,
            }

        study.status = WalkForwardStatus.RUNNING
        study.started_at = datetime.now(UTC)
        db.commit()

        try:
            builder = get_strategy_builder(study.strategy_class)
            regime_lookup = db_regime_lookup(db)
            runner = build_default_runner(db, builder, regime_lookup=regime_lookup)

            def progress_cb(completed: int, total: int) -> None:
                # Cheap update — single row, single column. We commit so
                # the polling endpoint sees progress without waiting for
                # the task to finish.
                study.total_trials = completed
                db.commit()

            optimizer = WalkForwardOptimizer(
                runner=runner,
                objective_name=study.objective,
                n_trials=study.n_trials,
                progress_callback=progress_cb,
            )
            result = optimizer.optimize(
                param_space=study.param_space,
                symbols=list(study.symbols),
                dataset_start=study.dataset_start.date(),
                dataset_end=study.dataset_end.date(),
                train_window_days=study.train_window_days,
                test_window_days=study.test_window_days,
                n_splits=study.n_splits,
                regime_filter=study.regime_filter,
            )

            study.best_params = result.best_params
            study.best_score = result.best_score
            study.total_trials = result.total_trials
            study.per_split_results = [s.to_dict() for s in result.per_split_results]
            study.regime_attribution = result.regime_attribution
            study.status = WalkForwardStatus.COMPLETED
            study.completed_at = datetime.now(UTC)
            db.commit()

            logger.info(
                "walk_forward_study %s completed: best_score=%.4f, trials=%d, failed=%d",
                study.id,
                float(result.best_score),
                result.total_trials,
                result.failed_trials,
            )
            return {
                "study_id": study.id,
                "status": "completed",
                "best_score": float(result.best_score),
                "total_trials": result.total_trials,
            }
        except Exception as e:
            logger.exception("walk_forward_study %s failed: %s", study_id, e)
            study.status = WalkForwardStatus.FAILED
            study.error_message = str(e)[:1000]
            study.completed_at = datetime.now(UTC)
            db.commit()
            return {"study_id": study.id, "status": "failed", "error": str(e)}
    finally:
        db.close()
