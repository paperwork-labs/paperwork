"""Nightly pipeline orchestrator with step tracking.

The nightly pipeline runs 10 steps in sequence:
1. IBKR sync (positions, balances)
2. Market data fetch (OHLCV for all tracked symbols)
3. Indicator computation (stage, RS, TTM, etc.)
4. Market snapshot update
5. Market snapshot history append
6. Regime engine update
7. Strategy evaluation (active strategies)
8. Signal generation
9. Position reconciliation
10. Cleanup (stale data, logs)
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, Optional

import redis
from celery import shared_task

from backend.config import settings

logger = logging.getLogger(__name__)

_PIPELINE_RUN_KEY = "pipeline:current_run"
_PIPELINE_RUN_TTL_S = 172800  # 48h


def _pipeline_redis() -> Optional[redis.Redis]:
    url = getattr(settings, "REDIS_URL", None) or ""
    if not url.strip():
        return None
    try:
        return redis.from_url(url, decode_responses=True)
    except Exception as e:
        logger.warning("Pipeline orchestrator Redis unavailable: %s", e)
        return None


class PipelineStep(Enum):
    """Pipeline step identifiers."""

    IBKR_SYNC = "ibkr_sync"
    MARKET_DATA_FETCH = "market_data_fetch"
    INDICATOR_COMPUTE = "indicator_compute"
    SNAPSHOT_UPDATE = "snapshot_update"
    HISTORY_APPEND = "history_append"
    REGIME_UPDATE = "regime_update"
    STRATEGY_EVAL = "strategy_eval"
    SIGNAL_GEN = "signal_gen"
    RECONCILIATION = "reconciliation"
    CLEANUP = "cleanup"


class StepStatus(Enum):
    """Status of a pipeline step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of a single pipeline step."""

    step: PipelineStep
    status: StepStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    records_processed: Optional[int] = None


def _initial_pending_steps() -> Dict[PipelineStep, StepResult]:
    return {step: StepResult(step=step, status=StepStatus.PENDING) for step in PipelineStep}


@dataclass
class PipelineRun:
    """Tracks a complete pipeline run."""

    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"  # running, completed, failed
    steps: Dict[PipelineStep, StepResult] = field(default_factory=_initial_pending_steps)


def _serialize_run(run: PipelineRun) -> str:
    return json.dumps(
        {
            "run_id": run.run_id,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "status": run.status,
            "steps": {
                step.value: {
                    "status": res.status.value,
                    "started_at": res.started_at.isoformat() if res.started_at else None,
                    "completed_at": res.completed_at.isoformat() if res.completed_at else None,
                    "duration_ms": res.duration_ms,
                    "error": res.error,
                    "records_processed": res.records_processed,
                }
                for step, res in run.steps.items()
            },
        }
    )


def _deserialize_run(raw: str) -> Optional[PipelineRun]:
    try:
        data = json.loads(raw)
        steps: Dict[PipelineStep, StepResult] = {}
        for step in PipelineStep:
            payload = data.get("steps", {}).get(step.value)
            if not payload:
                steps[step] = StepResult(step=step, status=StepStatus.PENDING)
                continue
            steps[step] = StepResult(
                step=step,
                status=StepStatus(payload["status"]),
                started_at=(
                    datetime.fromisoformat(payload["started_at"])
                    if payload.get("started_at")
                    else None
                ),
                completed_at=(
                    datetime.fromisoformat(payload["completed_at"])
                    if payload.get("completed_at")
                    else None
                ),
                duration_ms=payload.get("duration_ms"),
                error=payload.get("error"),
                records_processed=payload.get("records_processed"),
            )
        return PipelineRun(
            run_id=data["run_id"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
            ),
            status=data.get("status", "running"),
            steps=steps,
        )
    except Exception as e:
        logger.warning("Failed to deserialize pipeline run from Redis: %s", e)
        return None


def _persist_run(run: PipelineRun) -> None:
    r = _pipeline_redis()
    if r is None:
        return
    try:
        r.setex(_PIPELINE_RUN_KEY, _PIPELINE_RUN_TTL_S, _serialize_run(run))
    except Exception as e:
        logger.warning("Failed to persist pipeline run: %s", e)


def get_current_run() -> Optional[PipelineRun]:
    """Load latest pipeline run status from Redis (shared across Celery workers)."""
    r = _pipeline_redis()
    if r is None:
        return None
    try:
        raw = r.get(_PIPELINE_RUN_KEY)
        if not raw:
            return None
        return _deserialize_run(raw)
    except Exception as e:
        logger.warning("Failed to read pipeline run from Redis: %s", e)
        return None


class PipelineOrchestrator:
    """Orchestrates the nightly pipeline execution."""

    STEP_ORDER = [
        PipelineStep.IBKR_SYNC,
        PipelineStep.MARKET_DATA_FETCH,
        PipelineStep.INDICATOR_COMPUTE,
        PipelineStep.SNAPSHOT_UPDATE,
        PipelineStep.HISTORY_APPEND,
        PipelineStep.REGIME_UPDATE,
        PipelineStep.STRATEGY_EVAL,
        PipelineStep.SIGNAL_GEN,
        PipelineStep.RECONCILIATION,
        PipelineStep.CLEANUP,
    ]

    def __init__(self) -> None:
        self.step_handlers: Dict[PipelineStep, Callable[[], int]] = {
            PipelineStep.IBKR_SYNC: self._run_ibkr_sync,
            PipelineStep.MARKET_DATA_FETCH: self._run_market_data_fetch,
            PipelineStep.INDICATOR_COMPUTE: self._run_indicator_compute,
            PipelineStep.SNAPSHOT_UPDATE: self._run_snapshot_update,
            PipelineStep.HISTORY_APPEND: self._run_history_append,
            PipelineStep.REGIME_UPDATE: self._run_regime_update,
            PipelineStep.STRATEGY_EVAL: self._run_strategy_eval,
            PipelineStep.SIGNAL_GEN: self._run_signal_gen,
            PipelineStep.RECONCILIATION: self._run_reconciliation,
            PipelineStep.CLEANUP: self._run_cleanup,
        }

    def run_full_pipeline(self, run_id: str) -> PipelineRun:
        """Execute the full nightly pipeline."""
        run = PipelineRun(run_id=run_id, started_at=datetime.utcnow())
        _persist_run(run)

        logger.info("Starting nightly pipeline run %s", run_id)

        failed = False
        for step in self.STEP_ORDER:
            if failed:
                run.steps[step].status = StepStatus.SKIPPED
                _persist_run(run)
                continue

            result = self._execute_step(step)
            run.steps[step] = result
            _persist_run(run)

            if result.status == StepStatus.FAILED:
                failed = True
                logger.error("Pipeline step %s failed: %s", step.value, result.error)

        run.completed_at = datetime.utcnow()
        run.status = "failed" if failed else "completed"
        _persist_run(run)

        duration_s = (run.completed_at - run.started_at).total_seconds()
        logger.info(
            "Pipeline run %s %s in %.1fs",
            run_id,
            run.status,
            duration_s,
        )

        return run

    def _execute_step(self, step: PipelineStep) -> StepResult:
        """Execute a single pipeline step with tracking."""
        result = StepResult(step=step, status=StepStatus.RUNNING, started_at=datetime.utcnow())

        handler = self.step_handlers.get(step)
        if not handler:
            result.status = StepStatus.SKIPPED
            result.error = "No handler registered"
            return result

        try:
            records = handler()
            result.status = StepStatus.COMPLETED
            result.records_processed = records
        except Exception as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
            logger.exception("Step %s failed", step.value)
        finally:
            result.completed_at = datetime.utcnow()
            if result.started_at:
                result.duration_ms = int(
                    (result.completed_at - result.started_at).total_seconds() * 1000
                )

        return result

    def _run_ibkr_sync(self) -> int:
        """Step 1: Sync IBKR positions and balances."""
        # Wire to backend.tasks.portfolio.sync.sync_all_ibkr_accounts (or .delay()) when orchestrating for real.
        logger.info("Running IBKR sync")
        return 0

    def _run_market_data_fetch(self) -> int:
        """Step 2: Fetch market data for all tracked symbols."""
        # Wire to market backfill / coverage tasks (e.g. daily_bootstrap chain) when orchestrating for real.
        logger.info("Running market data fetch")
        return 0

    def _run_indicator_compute(self) -> int:
        """Step 3: Compute indicators for all symbols."""
        # Wire to backend.tasks.market.indicators.recompute_universe when orchestrating for real.
        logger.info("Running indicator computation")
        return 0

    def _run_snapshot_update(self) -> int:
        """Step 4: Update market snapshots."""
        logger.info("Running snapshot update")
        return 0

    def _run_history_append(self) -> int:
        """Step 5: Append to snapshot history."""
        # Wire to backend.tasks.market.history.record_daily when orchestrating for real.
        logger.info("Running history append")
        return 0

    def _run_regime_update(self) -> int:
        """Step 6: Update market regime."""
        # Wire to backend.tasks.market.regime.compute_daily when orchestrating for real.
        logger.info("Running regime update")
        return 0

    def _run_strategy_eval(self) -> int:
        """Step 7: Evaluate active strategies."""
        logger.info("Running strategy evaluation")
        return 0

    def _run_signal_gen(self) -> int:
        """Step 8: Generate trading signals."""
        logger.info("Running signal generation")
        return 0

    def _run_reconciliation(self) -> int:
        """Step 9: Reconcile positions."""
        # Wire to backend.tasks.portfolio.reconciliation.reconcile_positions when orchestrating for real.
        logger.info("Running position reconciliation")
        return 0

    def _run_cleanup(self) -> int:
        """Step 10: Cleanup stale data."""
        # Wire to backend.tasks.market.maintenance.prune_old_bars / audit tasks when orchestrating for real.
        logger.info("Running cleanup")
        return 0


@shared_task(name="pipeline.nightly", time_limit=3600, soft_time_limit=3500)
def run_nightly_pipeline() -> dict:
    """Celery task for nightly pipeline."""
    run_id = f"nightly-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"

    orchestrator = PipelineOrchestrator()
    result = orchestrator.run_full_pipeline(run_id)

    return {
        "run_id": result.run_id,
        "status": result.status,
        "duration_ms": int((result.completed_at - result.started_at).total_seconds() * 1000)
        if result.completed_at
        else None,
        "steps": {
            step.value: {
                "status": res.status.value,
                "duration_ms": res.duration_ms,
                "records_processed": res.records_processed,
                "error": res.error,
            }
            for step, res in result.steps.items()
        },
    }
