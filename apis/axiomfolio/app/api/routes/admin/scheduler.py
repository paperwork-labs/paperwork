"""Admin Scheduler API — DB-backed schedule CRUD with Render API sync.

All schedule definitions live in the ``cron_schedule`` PostgreSQL table.
Mutations are automatically pushed to Render cron-job services when
``RENDER_API_KEY`` is configured (production).  In local dev the Render
sync is a no-op and schedules are only stored in the DB.

On first access the catalog is auto-seeded if the table is empty.
Every mutation writes an immutable audit row to ``cron_schedule_audit``.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_admin_user
from app.api.rate_limit import limiter
from app.database import get_db
from app.models.market_data import CronSchedule, CronScheduleAudit, JobRun
from app.models.user import User
from app.services.core.render_sync_service import render_sync_service
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)
router = APIRouter()

_seeded = False
_seed_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ScheduleCreate(BaseModel):
    id: str
    display_name: str
    group: str = "market_data"
    task: str
    description: str | None = None
    cron: str
    timezone: str = "UTC"
    args: list[Any] | None = None
    kwargs: dict[str, Any] | None = None
    enabled: bool = True
    timeout_s: int = 3600
    singleflight: bool = True


class ScheduleUpdate(BaseModel):
    display_name: str | None = None
    cron: str | None = None
    timezone: str | None = None
    args: list[Any] | None = None
    kwargs: dict[str, Any] | None = None
    enabled: bool | None = None
    timeout_s: int | None = None
    singleflight: bool | None = None
    description: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _actor_label(user: User) -> str:
    return user.email or user.username or f"user:{user.id}"


def _ensure_seeded(db: Session) -> None:
    """Sync catalog defaults into DB on first access (once per process)."""
    global _seeded
    if _seeded:
        return
    with _seed_lock:
        if _seeded:
            return
        try:
            from app.scripts.seed_schedules import seed

            result = seed(db)
            _seeded = True
            logger.info("Catalog sync: %s", result)
        except Exception:
            logger.exception("Catalog sync failed")


def _audit(db: Session, schedule_id: str, action: str, actor: str, changes: Any = None) -> None:
    db.add(
        CronScheduleAudit(
            schedule_id=schedule_id,
            action=action,
            actor=actor,
            changes=changes,
        )
    )


def _snapshot(s: CronSchedule) -> dict[str, Any]:
    return {
        "id": s.id,
        "display_name": s.display_name,
        "group": s.group,
        "task": s.task,
        "cron": s.cron,
        "timezone": s.timezone,
        "enabled": s.enabled,
    }


def _last_run_for_task(db: Session, dotted_task: str) -> dict[str, Any] | None:
    simple = dotted_task.rsplit(".", 1)[-1]
    row = (
        db.query(JobRun)
        .filter(JobRun.task_name == simple)
        .order_by(JobRun.started_at.desc())
        .first()
    )
    if not row:
        return None
    return {
        "task_name": row.task_name,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def _schedule_to_dict(s: CronSchedule, db: Session) -> dict[str, Any]:
    return {
        "id": s.id,
        "display_name": s.display_name,
        "group": s.group,
        "task": s.task,
        "description": s.description,
        "cron": s.cron,
        "timezone": s.timezone,
        "args": s.args_json or [],
        "kwargs": s.kwargs_json or {},
        "enabled": s.enabled,
        "timeout_s": s.timeout_s,
        "singleflight": s.singleflight,
        "render_service_id": s.render_service_id,
        "render_synced_at": s.render_synced_at.isoformat() if s.render_synced_at else None,
        "render_sync_error": s.render_sync_error,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        "created_by": s.created_by,
        "last_run": _last_run_for_task(db, s.task),
    }


def _validate_cron(cron: str) -> None:
    parts = cron.strip().split()
    if len(parts) != 5:
        raise HTTPException(
            status_code=400, detail="Cron must be a 5-field expression (m h dom mon dow)"
        )
    try:
        croniter(cron, datetime.now())
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {exc}") from exc


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/schedules")
async def list_schedules(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_seeded(db)
    rows = db.query(CronSchedule).order_by(CronSchedule.group, CronSchedule.id).all()
    schedules = [_schedule_to_dict(r, db) for r in rows]
    return {
        "schedules": schedules,
        "mode": "db",
        "render_sync_enabled": render_sync_service.enabled,
    }


@router.post("/schedules")
@limiter.limit("10/minute")
async def create_schedule(
    request: Request,
    payload: ScheduleCreate,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _validate_cron(payload.cron)

    existing = db.query(CronSchedule).filter(CronSchedule.id == payload.id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Schedule '{payload.id}' already exists")

    actor = _actor_label(admin_user)
    row = CronSchedule(
        id=payload.id,
        display_name=payload.display_name,
        group=payload.group,
        task=payload.task,
        description=payload.description,
        cron=payload.cron,
        timezone=payload.timezone,
        args_json=payload.args or [],
        kwargs_json=payload.kwargs or {},
        enabled=payload.enabled,
        timeout_s=payload.timeout_s,
        singleflight=payload.singleflight,
        created_by=actor,
    )
    db.add(row)
    _audit(db, payload.id, "created", actor, _snapshot(row))
    db.commit()
    db.refresh(row)

    sync_result = render_sync_service.sync_one(row, db)
    return {"status": "ok", "schedule": _schedule_to_dict(row, db), "sync": sync_result}


@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    payload: ScheduleUpdate,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.query(CronSchedule).filter(CronSchedule.id == schedule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")

    actor = _actor_label(admin_user)
    changes: dict[str, dict[str, Any]] = {}

    def _apply(field: str, model_attr: str, new_val: Any) -> None:
        old_val = getattr(row, model_attr)
        if new_val is not None and new_val != old_val:
            changes[field] = {"old": old_val, "new": new_val}
            setattr(row, model_attr, new_val)

    if payload.cron is not None:
        _validate_cron(payload.cron)
    _apply("cron", "cron", payload.cron)
    _apply("display_name", "display_name", payload.display_name)
    _apply("timezone", "timezone", payload.timezone)
    _apply("args", "args_json", payload.args)
    _apply("kwargs", "kwargs_json", payload.kwargs)
    _apply("enabled", "enabled", payload.enabled)
    _apply("timeout_s", "timeout_s", payload.timeout_s)
    _apply("singleflight", "singleflight", payload.singleflight)
    _apply("description", "description", payload.description)

    if changes:
        _audit(db, schedule_id, "updated", actor, changes)

    db.commit()
    db.refresh(row)

    sync_result = render_sync_service.sync_one(row, db)
    return {"status": "ok", "schedule": _schedule_to_dict(row, db), "sync": sync_result}


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.query(CronSchedule).filter(CronSchedule.id == schedule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")

    actor = _actor_label(admin_user)
    _audit(db, schedule_id, "deleted", actor, _snapshot(row))

    if row.render_service_id and render_sync_service.enabled:
        try:
            deleted = render_sync_service.delete_render_cron(row.render_service_id)
        except Exception as exc:
            logger.exception(
                "Render cron deletion failed for schedule_id=%s service_id=%s",
                schedule_id,
                row.render_service_id,
            )
            db.rollback()
            raise HTTPException(
                status_code=502,
                detail="Failed to delete remote Render cron job; schedule not removed",
            ) from exc
        if deleted is False:
            logger.warning(
                "Render cron deletion returned false for schedule_id=%s service_id=%s",
                schedule_id,
                row.render_service_id,
            )
            db.rollback()
            raise HTTPException(
                status_code=502,
                detail="Failed to delete remote Render cron job; schedule not removed",
            )

    db.delete(row)
    db.commit()
    return {"status": "ok", "deleted": schedule_id}


@router.post("/schedules/{schedule_id}/pause")
@limiter.limit("10/minute")
async def pause_schedule(
    request: Request,
    schedule_id: str,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.query(CronSchedule).filter(CronSchedule.id == schedule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")

    actor = _actor_label(admin_user)
    row.enabled = False
    _audit(db, schedule_id, "paused", actor)
    db.commit()

    sync_result = render_sync_service.sync_one(row, db)
    return {"status": "ok", "paused": schedule_id, "sync": sync_result}


@router.post("/schedules/{schedule_id}/resume")
@limiter.limit("10/minute")
async def resume_schedule(
    request: Request,
    schedule_id: str,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.query(CronSchedule).filter(CronSchedule.id == schedule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")

    actor = _actor_label(admin_user)
    row.enabled = True
    _audit(db, schedule_id, "resumed", actor)
    db.commit()

    sync_result = render_sync_service.sync_one(row, db)
    return {"status": "ok", "resumed": schedule_id, "sync": sync_result}


@router.post("/schedules/sync")
@limiter.limit("10/minute")
async def sync_schedules(
    request: Request,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    result = render_sync_service.sync_all(db)
    return {"status": "ok", "sync": result}


@router.post("/schedules/run-now")
@limiter.limit("10/minute")
async def run_now(
    request: Request,
    task: str = Query(..., description="dotted task path"),
    admin_user: User = Depends(get_admin_user),
) -> dict[str, Any]:
    try:
        res = celery_app.send_task(task, args=(), kwargs={})
        return {"status": "ok", "task_id": res.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedules/preview")
async def preview_cron(
    cron: str = Query(..., description="m h dom mon dow"),
    timezone: str = Query("UTC"),
    count: int = Query(5, ge=1, le=20),
    admin_user: User = Depends(get_admin_user),
) -> dict[str, Any]:
    _validate_cron(cron)
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timezone")
    now = datetime.now(tz=tz)
    it = croniter(cron, now)
    runs = [it.get_next(datetime).astimezone(ZoneInfo("UTC")).isoformat() for _ in range(count)]
    return {"next_runs_utc": runs, "tz": timezone}


@router.get("/schedules/history")
async def list_history(
    schedule_id: str | None = Query(None, description="Filter by schedule ID"),
    limit: int = Query(50, ge=1, le=200),
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    q = db.query(CronScheduleAudit).order_by(CronScheduleAudit.timestamp.desc())
    if schedule_id:
        q = q.filter(CronScheduleAudit.schedule_id == schedule_id)
    rows = q.limit(limit).all()
    return {
        "history": [
            {
                "id": r.id,
                "schedule_id": r.schedule_id,
                "action": r.action,
                "actor": r.actor,
                "changes": r.changes,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in rows
        ],
    }


@router.get("/tasks/catalog")
async def list_catalog(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.tasks.job_catalog import CATALOG

    grouped: dict[str, list[dict[str, Any]]] = {}
    for t in CATALOG:
        item = t.to_dict()
        item["last_run"] = _last_run_for_task(db, t.task)
        grouped.setdefault(t.group, []).append(item)
    return {"catalog": grouped}
