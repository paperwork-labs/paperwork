"""REST API for pipeline DAG state — runs, step states, retry, trigger.

All endpoints require admin authentication.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_admin_user
from app.database import SessionLocal
from app.services.pipeline.dag import (
    PIPELINE_DAG,
    STEP_OK,
    STEP_PENDING,
    all_deps_satisfied,
    dag_edges,
    get_ambient_state,
    get_run_state,
    get_step_status,
    list_recent_runs,
    mark_run_meta,
    mark_step,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class DAGNodeResponse(BaseModel):
    name: str
    display_name: str
    deps: list[str]
    timeout_s: int


class DAGEdgeResponse(BaseModel):
    source: str  # "from" is reserved in Python
    target: str


class DAGDefinitionResponse(BaseModel):
    nodes: list[DAGNodeResponse]
    edges: list[DAGEdgeResponse]


class TriggerResponse(BaseModel):
    run_id: str
    status: str
    message: str


class RetryResponse(BaseModel):
    run_id: str
    step: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/dag", response_model=DAGDefinitionResponse)
def get_dag_definition(_user=Depends(get_admin_user)):
    """Return the static DAG topology for frontend rendering."""
    nodes = [
        DAGNodeResponse(
            name=name,
            display_name=step.display_name,
            deps=list(step.deps),
            timeout_s=step.timeout_s,
        )
        for name, step in PIPELINE_DAG.items()
    ]
    edges = [DAGEdgeResponse(source=e["from"], target=e["to"]) for e in dag_edges(PIPELINE_DAG)]
    return DAGDefinitionResponse(nodes=nodes, edges=edges)


@router.get("/runs")
def list_runs(limit: int = 20, _user=Depends(get_admin_user)):
    """List recent pipeline runs (metadata only)."""
    runs = list_recent_runs(limit=min(limit, 100))
    return {"runs": runs}


@router.get("/runs/{run_id}")
def get_run(run_id: str, _user=Depends(get_admin_user)):
    """Full state for a pipeline run — meta + all step states."""
    state = get_run_state(run_id)
    if not state.get("started_at") and state.get("status") == "unknown":
        raise HTTPException(status_code=404, detail=f"Pipeline run {run_id} not found")
    return state


@router.post("/runs/{run_id}/steps/{step}/retry", response_model=RetryResponse)
def retry_step(run_id: str, step: str, _user=Depends(get_admin_user)):
    """Retry a single failed step (deps must already be ok)."""
    if step not in PIPELINE_DAG:
        raise HTTPException(status_code=400, detail=f"Unknown step: {step}")

    current_status = get_step_status(run_id, step)
    if current_status == STEP_OK:
        return RetryResponse(
            run_id=run_id,
            step=step,
            status="already_ok",
            message=f"Step {step} is already ok — nothing to retry",
        )

    if not all_deps_satisfied(run_id, step, PIPELINE_DAG):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot retry {step}: upstream dependencies are not all ok",
        )

    mark_step(run_id, step, STEP_PENDING)

    from app.tasks.market.coverage import retry_pipeline_step

    try:
        retry_pipeline_step.delay(run_id, step)
    except Exception as exc:
        logger.warning("Failed to dispatch retry for step %s in run %s: %s", step, run_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return RetryResponse(
        run_id=run_id,
        step=step,
        status="queued",
        message=f"Step {step} queued for retry on worker",
    )


@router.get("/ambient")
def get_ambient(_user=Depends(get_admin_user), session: Session = Depends(_get_db)):
    """Synthetic pipeline state from the latest individual task runs.

    Used as a fallback when no real pipeline run exists so the DAG always
    reflects reality.
    """
    return get_ambient_state(session)


@router.post("/trigger", response_model=TriggerResponse)
def trigger_pipeline(_user=Depends(get_admin_user)):
    """Trigger a new pipeline run via Celery (async).

    When the DAG pipeline is enabled, pre-register ``run_id`` in Redis as
    ``queued`` so the UI can subscribe immediately, then dispatch the task with
    that id.
    """
    from app.config import settings
    from app.tasks.market.coverage import daily_bootstrap

    try:
        if settings.PIPELINE_DAG_ENABLED:
            run_id = f"manual-{uuid.uuid4().hex[:12]}"
            now_iso = datetime.now(UTC).isoformat()
            mark_run_meta(
                run_id,
                status="queued",
                started_at=now_iso,
                triggered_by="admin",
            )
            daily_bootstrap.delay(pipeline_run_id=run_id)
            return TriggerResponse(
                run_id=run_id,
                status="dispatched",
                message="Pipeline run queued; worker will pick it up shortly.",
            )
        result = daily_bootstrap.delay()
        return TriggerResponse(
            run_id=str(result.id) if result.id else "legacy",
            status="dispatched",
            message="Pipeline run dispatched (legacy sequential mode).",
        )
    except Exception as exc:
        logger.warning("Failed to trigger pipeline: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Active tasks / Stop-all (operator kill switch)
# ---------------------------------------------------------------------------


class ActiveTaskInfo(BaseModel):
    id: str
    name: str | None = None
    worker: str | None = None
    started: float | None = None
    dag_step: str | None = None


class ActiveTasksResponse(BaseModel):
    tasks: list[ActiveTaskInfo]
    total: int
    inspect_ok: bool = True


class StopAllResponse(BaseModel):
    revoked: int
    purged: int
    message: str


@router.get("/active-tasks", response_model=ActiveTasksResponse)
def get_active_tasks(_user=Depends(get_admin_user)):
    """List currently executing Celery tasks across all workers."""
    from app.services.pipeline.dag import celery_task_to_dag_step
    from app.tasks.celery_app import celery_app

    try:
        inspector = celery_app.control.inspect(timeout=5.0)
        active: dict[str, list[dict[str, Any]]] | None = inspector.active()
    except Exception as exc:
        logger.warning("Failed to inspect active tasks: %s", exc)
        return ActiveTasksResponse(tasks=[], total=0, inspect_ok=False)

    if not active:
        return ActiveTasksResponse(tasks=[], total=0)

    tasks: list[ActiveTaskInfo] = []
    for worker_name, worker_tasks in active.items():
        for t in worker_tasks:
            task_name = t.get("name")
            tasks.append(
                ActiveTaskInfo(
                    id=t.get("id", ""),
                    name=task_name,
                    worker=worker_name,
                    started=t.get("time_start"),
                    dag_step=celery_task_to_dag_step(task_name),
                )
            )

    return ActiveTasksResponse(tasks=tasks, total=len(tasks))


@router.post("/stop-all", response_model=StopAllResponse)
def stop_all_tasks(_user=Depends(get_admin_user)):
    """Revoke all active Celery tasks and purge the broker queue."""
    from app.tasks.celery_app import celery_app

    revoked = 0
    try:
        inspector = celery_app.control.inspect(timeout=3.0)
        active: dict[str, list[dict[str, Any]]] | None = inspector.active()
        if active:
            for worker_tasks in active.values():
                for t in worker_tasks:
                    task_id = t.get("id")
                    if task_id:
                        celery_app.control.revoke(
                            task_id,
                            terminate=True,
                            signal="SIGTERM",
                        )
                        revoked += 1
    except Exception as exc:
        logger.warning("Error revoking active tasks: %s", exc)

    purged = 0
    try:
        purged = celery_app.control.purge() or 0
    except Exception as exc:
        logger.warning("Error purging queue: %s", exc)

    logger.info("stop_all: revoked=%d active tasks, purged=%d queued", revoked, purged)
    return StopAllResponse(
        revoked=revoked,
        purged=purged,
        message=f"Revoked {revoked} running tasks, purged {purged} queued messages.",
    )


class RevokeTaskResponse(BaseModel):
    revoked: int
    task_name: str
    message: str


@router.post("/tasks/revoke", response_model=RevokeTaskResponse)
def revoke_task_by_name(
    task_name: str = Query(..., description="Celery task name or task-run key to revoke"),
    _user=Depends(get_admin_user),
):
    """Revoke all active Celery tasks matching the given name."""
    from app.services.pipeline.dag import celery_task_to_dag_step
    from app.tasks.celery_app import celery_app

    revoked = 0
    try:
        inspector = celery_app.control.inspect(timeout=3.0)
        active: dict[str, list[dict[str, Any]]] | None = inspector.active()
        if active:
            for worker_tasks in active.values():
                for t in worker_tasks:
                    t_name = t.get("name", "")
                    t_id = t.get("id")
                    if not t_id:
                        continue
                    dag_step = celery_task_to_dag_step(t_name)
                    if t_name == task_name or dag_step == task_name:
                        celery_app.control.revoke(
                            t_id,
                            terminate=True,
                            signal="SIGTERM",
                        )
                        revoked += 1
    except Exception as exc:
        logger.warning("Error revoking task %s: %s", task_name, exc)
        raise HTTPException(status_code=503, detail="Cannot reach Celery workers")

    logger.info("revoke_task: name=%s, revoked=%d", task_name, revoked)
    return RevokeTaskResponse(
        revoked=revoked,
        task_name=task_name,
        message=f"Revoked {revoked} instance(s) of {task_name}."
        if revoked > 0
        else f"No active tasks matching '{task_name}'.",
    )
