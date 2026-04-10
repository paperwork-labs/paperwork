"""Pipeline orchestrator — executes the DAG with resume, skip, and retry.

Usage from ``daily_bootstrap``::

    from backend.services.pipeline.orchestrator import run_pipeline
    return run_pipeline(run_id=str(uuid4()))

The orchestrator walks the topologically-sorted DAG.  For each step it:
  1. Skips if already "ok" in Redis (resume-from-failure).
  2. Marks "skipped" if any upstream dep failed or was skipped (cascade).
  3. Calls the step callable, marks "ok" or "error".
  4. Continues to the next independent branch on error (no hard abort).

``SoftTimeLimitExceeded`` is re-raised after marking the step as
error/timeout so that the outer Celery task wrapper can handle it.
"""
from __future__ import annotations

import importlib
import logging
import time as _time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence

from celery.exceptions import SoftTimeLimitExceeded

from backend.services.pipeline.dag import (
    PIPELINE_DAG,
    STEP_ERROR,
    STEP_OK,
    STEP_PENDING,
    STEP_RUNNING,
    STEP_SKIPPED,
    StepDef,
    all_deps_satisfied,
    get_step_status,
    mark_run_meta,
    mark_step,
    resolve_execution_order,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step callable resolution
# ---------------------------------------------------------------------------

_STEP_KWARGS: Dict[str, Dict[str, Any]] = {
    "indicators": {"batch_size": 50},
    "digest": {"deliver_brain": True},
    "snapshot_history": {"days": 20, "batch_size": 25},
}


def _resolve_callable(task_path: str) -> Callable[..., Any]:
    """Import and return the callable identified by a dotted path."""
    module_path, _, func_name = task_path.rpartition(".")
    mod = importlib.import_module(module_path)
    fn = getattr(mod, func_name)
    return fn


def _call_step(step_name: str, step_def: StepDef, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Call a step's task function and return its result dict."""
    fn = _resolve_callable(step_def.task_path)
    kwargs = {}
    kwargs.update(_STEP_KWARGS.get(step_name, {}))
    if params:
        step_params = params.get(step_name, {})
        if isinstance(step_params, dict):
            kwargs.update(step_params)
    result = fn(**kwargs)
    if not isinstance(result, dict):
        result = {"status": "ok", "raw": result}
    return result


# ---------------------------------------------------------------------------
# Step summary (reused from coverage.py for backward compat)
# ---------------------------------------------------------------------------

_STEP_TO_LEGACY_NAME: Dict[str, str] = {
    "constituents": "market_indices_constituents_refresh",
    "tracked_cache": "market_universe_tracked_refresh",
    "daily_bars": "admin_backfill_daily",
    "indicators": "admin_indicators_recompute_universe",
    "regime": "compute_daily_regime",
    "scan_overlay": "scan_overlay",
    "snapshot_history": "admin_snapshots_history_backfill",
    "exit_cascade": "exit_cascade_evaluation",
    "strategy_eval": "strategy_evaluation",
    "health_check": "admin_coverage_refresh",
    "audit": "admin_market_data_audit",
    "warm_dashboard": "admin_warm_dashboard",
    "digest": "intelligence_digest",
}


def _summarize(step_name: str, result: Optional[Dict[str, Any]]) -> str:
    """Produce a one-line summary for a completed step."""
    from backend.tasks.market.coverage import _summarize_bootstrap_step

    legacy = _STEP_TO_LEGACY_NAME.get(step_name, step_name)
    try:
        return _summarize_bootstrap_step(legacy, result)
    except Exception:
        return (result or {}).get("status", "ok")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(
    run_id: str,
    *,
    steps: Optional[Sequence[str]] = None,
    params: Optional[Dict[str, Any]] = None,
    triggered_by: str = "celery_beat",
    dag: Optional[Dict[str, StepDef]] = None,
) -> Dict[str, Any]:
    """Execute the pipeline DAG with full state tracking.

    Args:
        run_id: Unique identifier for this run (typically a UUID or JobRun id).
        steps: Optional subset of step names to execute. Their transitive
            upstream deps are automatically included.
        params: Per-step kwargs overrides, keyed by step name.
        triggered_by: Label for the trigger source (celery_beat, admin, retry).
        dag: Override DAG definition (useful for testing).

    Returns:
        A rollup dict compatible with the old ``daily_bootstrap`` return format.
    """
    if dag is None:
        dag = PIPELINE_DAG

    now_iso = datetime.now(timezone.utc).isoformat()
    mark_run_meta(run_id, status="running", started_at=now_iso, triggered_by=triggered_by)

    execution_order = resolve_execution_order(dag, steps)
    logger.info(
        "Pipeline %s starting — %d steps: %s",
        run_id,
        len(execution_order),
        " -> ".join(execution_order),
    )

    rollup_steps: List[Dict[str, Any]] = []
    step_results: Dict[str, str] = {}  # step_name -> final status
    pipeline_start = _time.monotonic()

    for step_name in execution_order:
        step_def = dag[step_name]

        # 1) Resume: already completed successfully
        existing_status = get_step_status(run_id, step_name)
        if existing_status == STEP_OK:
            logger.info("Pipeline %s: step %s already ok — skipping", run_id, step_name)
            step_results[step_name] = STEP_OK
            rollup_steps.append({
                "name": _STEP_TO_LEGACY_NAME.get(step_name, step_name),
                "summary": "Resumed (already ok)",
                "result": {"status": "ok", "resumed": True},
                "duration_s": 0.0,
            })
            continue

        # 2) Cascade skip: any dep failed or was skipped
        failed_deps = [
            dep for dep in step_def.deps
            if step_results.get(dep) in (STEP_ERROR, STEP_SKIPPED)
        ]
        if failed_deps:
            reason = f"dependency failed: {', '.join(failed_deps)}"
            mark_step(run_id, step_name, STEP_SKIPPED, error=reason)
            step_results[step_name] = STEP_SKIPPED
            logger.info("Pipeline %s: step %s skipped — %s", run_id, step_name, reason)
            rollup_steps.append({
                "name": _STEP_TO_LEGACY_NAME.get(step_name, step_name),
                "summary": f"Skipped ({reason})",
                "result": {"status": "skipped", "reason": reason},
                "duration_s": 0.0,
            })
            continue

        # 3) Verify deps are truly ok in Redis (handles retry scenarios)
        if not all_deps_satisfied(run_id, step_name, dag):
            reason = "upstream dependencies not satisfied in Redis"
            mark_step(run_id, step_name, STEP_SKIPPED, error=reason)
            step_results[step_name] = STEP_SKIPPED
            logger.info("Pipeline %s: step %s skipped — %s", run_id, step_name, reason)
            rollup_steps.append({
                "name": _STEP_TO_LEGACY_NAME.get(step_name, step_name),
                "summary": f"Skipped ({reason})",
                "result": {"status": "skipped", "reason": reason},
                "duration_s": 0.0,
            })
            continue

        # 4) Execute
        t0 = _time.monotonic()
        started_iso = datetime.now(timezone.utc).isoformat()
        mark_step(run_id, step_name, STEP_RUNNING, started_at=started_iso)
        logger.info("Pipeline %s: step %s starting", run_id, step_name)

        try:
            result = _call_step(step_name, step_def, params)
            duration = _time.monotonic() - t0
            finished_iso = datetime.now(timezone.utc).isoformat()

            is_error = isinstance(result, dict) and result.get("status") == "error"
            final_status = STEP_ERROR if is_error else STEP_OK

            mark_step(
                run_id, step_name, final_status,
                counters=result if isinstance(result, dict) else None,
                duration_s=duration,
                started_at=started_iso,
                finished_at=finished_iso,
                error=result.get("error") if is_error and isinstance(result, dict) else None,
            )
            step_results[step_name] = final_status
            logger.info(
                "Pipeline %s: step %s %s in %.1fs",
                run_id, step_name, final_status, duration,
            )
            rollup_steps.append({
                "name": _STEP_TO_LEGACY_NAME.get(step_name, step_name),
                "summary": _summarize(step_name, result),
                "result": result,
                "duration_s": round(duration, 2),
            })

        except SoftTimeLimitExceeded:
            duration = _time.monotonic() - t0
            mark_step(
                run_id, step_name, STEP_ERROR,
                error="timeout (SoftTimeLimitExceeded)",
                duration_s=duration,
                started_at=started_iso,
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            step_results[step_name] = STEP_ERROR
            logger.warning(
                "Pipeline %s: step %s timed out after %.1fs",
                run_id, step_name, duration,
            )
            _finalize_run(run_id, rollup_steps, step_results, pipeline_start)
            raise

        except Exception as exc:
            duration = _time.monotonic() - t0
            mark_step(
                run_id, step_name, STEP_ERROR,
                error=str(exc),
                duration_s=duration,
                started_at=started_iso,
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            step_results[step_name] = STEP_ERROR
            logger.warning(
                "Pipeline %s: step %s failed in %.1fs: %s",
                run_id, step_name, duration, exc,
            )
            rollup_steps.append({
                "name": _STEP_TO_LEGACY_NAME.get(step_name, step_name),
                "summary": f"Error: {str(exc)[:120]}",
                "result": {"status": "error", "error": str(exc)},
                "duration_s": round(duration, 2),
            })

    return _finalize_run(run_id, rollup_steps, step_results, pipeline_start)


def _finalize_run(
    run_id: str,
    rollup_steps: List[Dict[str, Any]],
    step_results: Dict[str, str],
    pipeline_start: float,
) -> Dict[str, Any]:
    """Compute final run status and persist to Redis."""
    total = len(step_results)
    ok_count = sum(1 for s in step_results.values() if s == STEP_OK)
    err_count = sum(1 for s in step_results.values() if s == STEP_ERROR)
    skip_count = sum(1 for s in step_results.values() if s == STEP_SKIPPED)

    if err_count == 0 and skip_count == 0:
        status = "ok"
    elif ok_count == 0 and err_count > 0:
        status = "error"
    else:
        status = "partial"

    finished_iso = datetime.now(timezone.utc).isoformat()
    mark_run_meta(run_id, status=status, finished_at=finished_iso)

    total_duration = _time.monotonic() - pipeline_start

    rollup: Dict[str, Any] = {
        "status": status,
        "run_id": run_id,
        "steps": rollup_steps,
        "steps_ok": ok_count,
        "steps_error": err_count,
        "steps_skipped": skip_count,
        "steps_total": total,
        "duration_s": round(total_duration, 2),
        "overall_summary": "; ".join(
            s["summary"] for s in rollup_steps if s.get("summary")
        ),
    }
    logger.info(
        "Pipeline %s finished — status=%s, ok=%d, error=%d, skipped=%d, %.1fs",
        run_id, status, ok_count, err_count, skip_count, total_duration,
    )
    return rollup
