"""Pipeline DAG definition, topological sort, and Redis state helpers.

The nightly pipeline is a static DAG of 12 steps. Each step declares its
upstream dependencies. The orchestrator walks the DAG in topological order,
tracking per-step state in Redis so runs can resume after failure and
individual steps can be retried without re-running the entire pipeline.

Redis key layout (TTL = 7 days):
    pipeline:{run_id}:meta     -> JSON {status, started_at, finished_at, triggered_by}
    pipeline:{run_id}:{step}   -> JSON {status, started_at, finished_at, duration_s, error, counters}
    pipeline:runs              -> sorted set of run_ids by started_at (score = unix ts)

medallion: ops
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

_RUN_TTL_S = 7 * 86400  # 7 days
_RUNS_INDEX_KEY = "pipeline:runs"
_RUNS_INDEX_MAX = 100

# Max age (seconds) a meta row may stay ``queued`` before _classify_stale_queued
# escalates it to ``error`` when Celery inspect is falsy (None/empty) or every
# worker reports no active tasks; younger queued runs may become ``waiting`` via
# _WAITING_SURFACE_AFTER_S when workers are busy. Raised from 120s to 900s so
# heavy-queue tasks do not spuriously trip the timeout (KNOWLEDGE D81 / R37).
_QUEUED_TIMEOUT_S = 900

# Once a run has been ``queued`` for this long, surface it as ``waiting``
# (with the currently-running task name + age) instead of ``queued`` so
# operators see "your job is behind X" instead of "queued forever".
_WAITING_SURFACE_AFTER_S = 30

# Inspect timeout when classifying a stale queued run.  Kept short because
# this runs inline on every read of run state.
_INSPECT_TIMEOUT_S = 1.5


# ---------------------------------------------------------------------------
# DAG node definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepDef:
    """Metadata for a single pipeline step."""

    deps: tuple[str, ...]
    task_path: str
    timeout_s: int
    display_name: str


PIPELINE_DAG: dict[str, StepDef] = {
    "constituents": StepDef(
        deps=(),
        task_path="app.tasks.market.backfill.constituents",
        timeout_s=300,
        display_name="Index Constituents",
    ),
    "tracked_cache": StepDef(
        deps=("constituents",),
        task_path="app.tasks.market.backfill.tracked_cache",
        timeout_s=120,
        display_name="Tracked Universe",
    ),
    "daily_bars": StepDef(
        deps=("tracked_cache",),
        task_path="app.tasks.market.backfill.daily_bars",
        timeout_s=3600,
        display_name="Daily Bars (Per-Symbol)",
    ),
    "indicators": StepDef(
        deps=("daily_bars",),
        task_path="app.tasks.market.indicators.recompute_universe",
        timeout_s=3600,
        display_name="Indicators + Stages",
    ),
    "regime": StepDef(
        deps=("daily_bars",),
        task_path="app.tasks.market.regime.compute_daily",
        timeout_s=600,
        display_name="Market Regime",
    ),
    "scan_overlay": StepDef(
        deps=("indicators", "regime"),
        task_path="app.tasks.market.coverage._run_scan_overlay",
        timeout_s=600,
        display_name="Scan Overlay",
    ),
    "snapshot_history": StepDef(
        deps=("indicators",),
        task_path="app.tasks.market.history.snapshot_last_n_days",
        timeout_s=1800,
        display_name="Snapshot History",
    ),
    "exit_cascade": StepDef(
        deps=("indicators",),
        task_path="app.tasks.market.coverage._evaluate_exit_cascade_all",
        timeout_s=600,
        display_name="Exit Cascade",
    ),
    "strategy_eval": StepDef(
        deps=("indicators", "regime"),
        task_path="app.tasks.strategy.tasks.evaluate_strategies_task",
        timeout_s=660,
        display_name="Strategy Evaluation",
    ),
    "health_check": StepDef(
        deps=("indicators",),
        task_path="app.tasks.market.coverage.health_check",
        timeout_s=180,
        display_name="Coverage Health",
    ),
    "mv_refresh": StepDef(
        deps=("indicators", "snapshot_history"),
        task_path="app.tasks.market.maintenance.refresh_market_mvs",
        timeout_s=360,
        display_name="MV Refresh",
    ),
    "warm_dashboard": StepDef(
        deps=("mv_refresh",),
        task_path="app.tasks.market.maintenance.warm_dashboard_cache",
        timeout_s=120,
        display_name="Dashboard Cache Warm",
    ),
    "audit": StepDef(
        deps=("indicators", "snapshot_history", "mv_refresh"),
        task_path="app.tasks.market.maintenance.audit_quality",
        timeout_s=360,
        display_name="Data Audit",
    ),
    "digest": StepDef(
        deps=("indicators", "regime", "scan_overlay"),
        task_path="app.tasks.intelligence.tasks.generate_daily_digest_task",
        timeout_s=600,
        display_name="Daily Digest",
    ),
}


# ---------------------------------------------------------------------------
# Topological sort (Kahn's algorithm)
# ---------------------------------------------------------------------------


def resolve_execution_order(
    dag: dict[str, StepDef],
    steps: Sequence[str] | None = None,
) -> list[str]:
    """Return step names in a valid topological execution order.

    If *steps* is provided, only those steps (plus their transitive upstream
    dependencies) are included in the result.

    Raises ``ValueError`` if the graph contains a cycle.
    """
    if steps is not None:
        needed = _transitive_deps(dag, steps)
    else:
        needed = set(dag.keys())

    # Sort to guarantee deterministic iteration regardless of set/dict ordering
    ordered_needed = sorted(needed)

    in_degree: dict[str, int] = {s: 0 for s in ordered_needed}
    for name in ordered_needed:
        for dep in dag[name].deps:
            if dep in needed:
                in_degree[name] += 1

    queue: deque[str] = deque(s for s in ordered_needed if in_degree[s] == 0)
    order: list[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for downstream in ordered_needed:
            step_def = dag[downstream]
            if node in step_def.deps:
                in_degree[downstream] -= 1
                if in_degree[downstream] == 0:
                    queue.append(downstream)

    if len(order) != len(needed):
        missing = needed - set(order)
        raise ValueError(f"Cycle detected in pipeline DAG involving: {missing}")

    return order


def _transitive_deps(dag: dict[str, StepDef], roots: Sequence[str]) -> set[str]:
    """Collect *roots* plus all their transitive upstream dependencies."""
    result: set[str] = set()
    stack = list(roots)
    while stack:
        name = stack.pop()
        if name in result:
            continue
        if name not in dag:
            raise ValueError(f"Unknown pipeline step: {name}")
        result.add(name)
        for dep in dag[name].deps:
            if dep not in result:
                stack.append(dep)
    return result


def dag_edges(dag: dict[str, StepDef]) -> list[dict[str, str]]:
    """Return list of {from, to} edge dicts for frontend rendering."""
    edges = []
    for name, step_def in dag.items():
        for dep in step_def.deps:
            edges.append({"from": dep, "to": name})
    return edges


# ---------------------------------------------------------------------------
# Step status constants
# ---------------------------------------------------------------------------

STEP_PENDING = "pending"
STEP_RUNNING = "running"
STEP_OK = "ok"
STEP_ERROR = "error"
STEP_SKIPPED = "skipped"

TERMINAL_STATUSES = frozenset({STEP_OK, STEP_ERROR, STEP_SKIPPED})

# Run-level status (Redis ``meta.status``) constants.  Step statuses use
# the ``STEP_*`` constants above; run statuses additionally include the
# computed-on-read ``waiting`` and ``partial`` values.
RUN_QUEUED = "queued"
RUN_RUNNING = "running"
RUN_WAITING = "waiting"
RUN_OK = "ok"
RUN_ERROR = "error"
RUN_PARTIAL = "partial"
RUN_UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Redis state helpers
# ---------------------------------------------------------------------------


def _redis_client():
    """Lazy import to avoid circular dependency with market_data_service."""
    from app.services.market.market_data_service import infra

    return infra.redis_client


def _meta_key(run_id: str) -> str:
    return f"pipeline:{run_id}:meta"


def _step_key(run_id: str, step: str) -> str:
    return f"pipeline:{run_id}:{step}"


def mark_run_meta(
    run_id: str,
    *,
    status: str,
    started_at: str | None = None,
    finished_at: str | None = None,
    triggered_by: str = "celery_beat",
) -> None:
    """Create or update pipeline run metadata in Redis."""
    r = _redis_client()
    key = _meta_key(run_id)
    try:
        existing_raw = r.get(key)
        existing = json.loads(existing_raw) if existing_raw else {}
    except Exception:
        existing = {}

    now_iso = datetime.now(UTC).isoformat()
    existing["run_id"] = run_id
    existing["status"] = status
    if started_at:
        existing["started_at"] = started_at
    elif "started_at" not in existing:
        existing["started_at"] = now_iso
    if finished_at:
        existing["finished_at"] = finished_at
    existing["triggered_by"] = triggered_by
    existing["updated_at"] = now_iso

    try:
        pipe = r.pipeline()
        pipe.set(key, json.dumps(existing), ex=_RUN_TTL_S)
        pipe.zadd(
            _RUNS_INDEX_KEY,
            {run_id: _iso_to_ts(existing["started_at"])},
        )
        pipe.zcard(_RUNS_INDEX_KEY)
        results = pipe.execute()
        runs_count = results[-1]
        if runs_count > _RUNS_INDEX_MAX:
            r.zremrangebyrank(_RUNS_INDEX_KEY, 0, runs_count - _RUNS_INDEX_MAX - 1)
    except Exception as e:
        logger.warning("Failed to persist pipeline run meta for %s: %s", run_id, e)


def mark_step(
    run_id: str,
    step: str,
    status: str,
    *,
    error: str | None = None,
    counters: dict[str, Any] | None = None,
    duration_s: float | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> None:
    """Write per-step state to Redis."""
    now_iso = datetime.now(UTC).isoformat()
    payload = {
        "status": status,
        "started_at": started_at or now_iso,
        "finished_at": finished_at,
        "duration_s": round(duration_s, 2) if duration_s is not None else None,
        "error": _truncate(error, 2000) if error else None,
        "counters": counters,
        "updated_at": now_iso,
    }
    try:
        _redis_client().set(
            _step_key(run_id, step),
            json.dumps(payload, default=str),
            ex=_RUN_TTL_S,
        )
    except Exception as e:
        logger.warning("Failed to persist pipeline step %s/%s: %s", run_id, step, e)


def get_step_status(run_id: str, step: str) -> str | None:
    """Return the status string for a step, or None if not recorded."""
    try:
        raw = _redis_client().get(_step_key(run_id, step))
        if raw:
            return json.loads(raw).get("status")
    except Exception as e:
        logger.warning("Failed to read pipeline step %s/%s: %s", run_id, step, e)
    return None


def get_step_state(run_id: str, step: str) -> dict[str, Any] | None:
    """Return full state dict for a step."""
    try:
        raw = _redis_client().get(_step_key(run_id, step))
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning("Failed to read pipeline step %s/%s: %s", run_id, step, e)
    return None


def all_deps_satisfied(
    run_id: str,
    step: str,
    dag: dict[str, StepDef],
) -> bool:
    """True if every dependency of *step* has status 'ok'."""
    step_def = dag.get(step)
    if not step_def:
        return False
    for dep in step_def.deps:
        if get_step_status(run_id, dep) != STEP_OK:
            return False
    return True


def _inspect_active_tasks() -> dict[str, list[dict[str, Any]]] | None:
    """Return Celery ``inspect().active()`` or None if no worker reachable.

    Wrapped here so we can mock it cleanly in tests.
    """
    try:
        # Lazy import — keeps `dag.py` importable from environments that
        # don't have Celery configured (admin scripts, tests).
        from app.tasks.celery_app import celery_app

        inspector = celery_app.control.inspect(timeout=_INSPECT_TIMEOUT_S)
        return inspector.active()
    except Exception as e:
        # Missing broker / idle workers is expected during frequent polls.
        if isinstance(e, (BrokenPipeError, ConnectionError, TimeoutError)):
            logger.debug("Celery inspect unavailable: %s", e)
        else:
            logger.warning("Failed to inspect Celery workers: %s", e)
        return None


def _classify_stale_queued(meta: dict[str, Any]) -> dict[str, Any]:
    """Reclassify a ``queued`` run based on Celery worker reachability.

    Truth table (queued runs only — other statuses are returned untouched):

    | Age                 | Workers reachable | Workers busy | Resulting status |
    |---------------------|-------------------|--------------|------------------|
    | <30s                | n/a               | n/a          | ``queued``       |
    | 30s..900s           | yes               | yes          | ``waiting``      |
    | 30s..900s           | yes               | no           | ``queued``       |
    | 30s..900s           | no                | n/a          | ``queued``       |
    | >900s               | yes               | yes          | ``waiting``      |
    | >900s               | yes               | no           | ``queued``       |
    | >900s               | no                | n/a          | ``error``        |

    The ``waiting`` shape adds a ``current_task`` (longest-running active
    task on any worker) and ``waiting_for_s`` (run age) so the UI can
    show "your run is queued behind ``repair_stage_history`` (running for
    173s)" instead of generic "queued".
    """
    if meta.get("status") != RUN_QUEUED:
        return meta
    started = meta.get("started_at")
    if not started:
        return meta
    try:
        age_s = time.time() - datetime.fromisoformat(started).timestamp()
    except Exception:
        return meta

    if age_s < _WAITING_SURFACE_AFTER_S:
        return meta

    active = _inspect_active_tasks()

    # No worker reachable. Within timeout, hold queued so transient
    # broker glitches do not flap the row.  Past timeout, escalate.
    if not active:
        if age_s > _QUEUED_TIMEOUT_S:
            return {
                **meta,
                "status": RUN_ERROR,
                "error": "Queued but never started \u2014 worker may be down",
            }
        return meta

    # Worker(s) reachable. If anything is running, surface the longest-
    # running task so the operator knows what is blocking.
    busiest: dict[str, Any] | None = None
    busiest_age: float = 0.0
    now = time.time()
    for worker_name, tasks in active.items():
        for t in tasks or ():
            time_start = t.get("time_start")
            try:
                t_age = now - float(time_start) if time_start else 0.0
            except (TypeError, ValueError):
                t_age = 0.0
            if busiest is None or t_age > busiest_age:
                busiest = {
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "worker": worker_name,
                    "running_for_s": round(t_age, 1),
                }
                busiest_age = t_age

    if busiest is not None:
        return {
            **meta,
            "status": RUN_WAITING,
            "waiting_for_s": round(age_s, 1),
            "current_task": busiest,
            # Important: do NOT set ``error``.  ``waiting`` is healthy
            # backpressure, not a failure.
            "error": None,
        }

    # Workers reachable but idle and nothing running for our run.
    # Within the timeout we keep ``queued`` (broker may just be slow);
    # past it we escalate so the operator notices.
    if age_s > _QUEUED_TIMEOUT_S:
        return {
            **meta,
            "status": RUN_ERROR,
            "error": (
                "Queued but never started \u2014 workers idle, broker "
                "may be misrouting (check task queue routes)"
            ),
        }
    return meta


# Backward-compat alias for any external callers that imported the
# private name.  Internal callers all use ``_classify_stale_queued``.
_expire_stale_queued = _classify_stale_queued


def get_run_state(
    run_id: str,
    dag: dict[str, StepDef] | None = None,
) -> dict[str, Any]:
    """Load full pipeline run state (meta + all steps) from Redis."""
    if dag is None:
        dag = PIPELINE_DAG

    r = _redis_client()
    result: dict[str, Any] = {"run_id": run_id, "steps": {}}

    try:
        meta_raw = r.get(_meta_key(run_id))
        if meta_raw:
            result.update(_classify_stale_queued(json.loads(meta_raw)))
        else:
            result["status"] = RUN_UNKNOWN
            result["started_at"] = None
    except Exception as e:
        logger.warning("Failed to read pipeline meta for %s: %s", run_id, e)
        result["status"] = RUN_UNKNOWN
        result["started_at"] = None

    for step_name in dag:
        state = get_step_state(run_id, step_name)
        result["steps"][step_name] = state or {"status": STEP_PENDING}

    return result


def list_recent_runs(limit: int = 20) -> list[dict[str, Any]]:
    """Return metadata for the most recent pipeline runs."""
    r = _redis_client()
    runs: list[dict[str, Any]] = []
    try:
        run_ids = r.zrevrange(_RUNS_INDEX_KEY, 0, limit - 1)
        if not run_ids:
            return []
        pipe = r.pipeline()
        for rid in run_ids:
            rid_str = rid if isinstance(rid, str) else rid.decode()
            pipe.get(_meta_key(rid_str))
        results = pipe.execute()
        for raw in results:
            if raw:
                try:
                    runs.append(_classify_stale_queued(json.loads(raw)))
                except Exception:
                    continue
    except Exception as e:
        logger.warning("Failed to list pipeline runs: %s", e)
    return runs


# ---------------------------------------------------------------------------
# Ambient state — synthetic run from latest individual JobRuns
# ---------------------------------------------------------------------------

_STEP_TO_TASK_NAME: dict[str, str] = {
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
    "mv_refresh": "admin_refresh_market_mvs",
    "warm_dashboard": "admin_warm_dashboard",
    "audit": "admin_market_data_audit",
    "digest": "intelligence_daily_digest",
}

_TASK_PATH_TO_STEP: dict[str, str] = {
    step_def.task_path: step_name for step_name, step_def in PIPELINE_DAG.items()
}

_CELERY_NAME_OVERRIDES: dict[str, str] = {
    "app.tasks.strategy_tasks.evaluate_strategies_task": "strategy_eval",
    "app.tasks.intelligence_tasks.generate_daily_digest": "digest",
}


def celery_task_to_dag_step(task_name: str | None) -> str | None:
    """Map a Celery registered task name to the corresponding DAG step name.

    Checks module-path-based mapping first (covers @shared_task defaults),
    then explicit overrides for tasks with custom ``name=`` registrations.
    """
    if not task_name:
        return None
    return _TASK_PATH_TO_STEP.get(task_name) or _CELERY_NAME_OVERRIDES.get(task_name)


_JOBRUN_STATUS_MAP: dict[str, str] = {
    "ok": STEP_OK,
    "error": STEP_ERROR,
    "running": STEP_RUNNING,
}


def get_ambient_state(session: Any) -> dict[str, Any]:
    """Build a synthetic pipeline run state from the latest JobRun per step.

    Used as a fallback when no real pipeline run exists so the DAG always
    reflects reality.  Accepts a SQLAlchemy ``Session``.
    """
    from sqlalchemy import desc

    from app.models.market_data import JobRun

    steps: dict[str, Any] = {}
    overall_statuses: list[str] = []

    for step_name, task_name in _STEP_TO_TASK_NAME.items():
        row = (
            session.query(JobRun)
            .filter(JobRun.task_name == task_name)
            .order_by(desc(JobRun.started_at))
            .first()
        )
        if row is None:
            steps[step_name] = {"status": STEP_PENDING}
            overall_statuses.append(STEP_PENDING)
            continue

        status = _JOBRUN_STATUS_MAP.get(row.status, STEP_PENDING)
        duration_s: float | None = None
        if row.started_at and row.finished_at:
            duration_s = round((row.finished_at - row.started_at).total_seconds(), 2)

        steps[step_name] = {
            "status": status,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "duration_s": duration_s,
            "error": str(row.error)[:200] if row.error else None,
            "counters": row.counters if hasattr(row, "counters") and row.counters else None,
        }
        overall_statuses.append(status)

    ok_count = overall_statuses.count(STEP_OK)
    err_count = overall_statuses.count(STEP_ERROR)
    if err_count == 0 and ok_count == len(overall_statuses):
        run_status = "ok"
    elif err_count > 0:
        run_status = "partial"
    else:
        run_status = "partial"

    return {
        "run_id": "ambient",
        "status": run_status,
        "started_at": None,
        "finished_at": None,
        "triggered_by": "ambient",
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso_to_ts(iso_str: str) -> float:
    """Convert ISO timestamp to Unix timestamp for sorted set scoring."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.timestamp()
    except Exception:
        return time.time()


def _truncate(s: str | None, max_len: int) -> str | None:
    if s and len(s) > max_len:
        return s[:max_len] + "..."
    return s
