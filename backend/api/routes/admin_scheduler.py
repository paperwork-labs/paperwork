from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import json

from backend.api.dependencies import get_admin_user
from backend.database import SessionLocal
from backend.models.user import User
from backend.services.market.market_data_service import market_data_service
from backend.tasks.celery_app import celery_app
from backend.tasks.job_catalog import CATALOG
from backend.tasks.schedule_metadata import (
    ScheduleMetadata,
    ScheduleMetadataPatch,
    delete_schedule_metadata,
    load_schedule_metadata,
    metadata_to_options,
    save_schedule_metadata,
)
from backend.tasks.schedule_helpers import build_crontab_schedule
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from croniter import croniter
import redis as redislib

router = APIRouter()


def _actor_label(user: User) -> str:
    return user.email or user.username or f"user:{user.id}"


def _persist_metadata(name: str, meta: ScheduleMetadata | None) -> None:
    save_schedule_metadata(name, meta)


def _parse_cron_and_tz(schedule: Any) -> tuple[Optional[str], Optional[str]]:
    """Extract a 5-field cron expression and timezone from various schedule representations.

    Handles:
    - Celery ``crontab`` objects (local or RedBeat-deserialized)
    - RedBeat JSON schedule dicts (``{"__type__": "crontab", "minute": ...}``)
    - String representations (``<crontab: m h dom mon dow ...>``)
    """
    cron_expr: Optional[str] = None
    tz: Optional[str] = None

    # --- 1. RedBeat JSON dict (comes from Redis definition.schedule) ---
    if isinstance(schedule, dict) and schedule.get("__type__") == "crontab":
        parts = [
            str(schedule.get("minute", "*")),
            str(schedule.get("hour", "*")),
            str(schedule.get("day_of_month", "*")),
            str(schedule.get("month_of_year", "*")),
            str(schedule.get("day_of_week", "*")),
        ]
        cron_expr = " ".join(parts)
        tz = schedule.get("timezone") or schedule.get("tz")
        if tz:
            tz = str(tz)
        return cron_expr, tz

    # --- 2. Celery crontab object (has _orig_* attrs from constructor) ---
    if hasattr(schedule, "_orig_minute"):
        try:
            parts = [
                str(getattr(schedule, "_orig_minute", "*")),
                str(getattr(schedule, "_orig_hour", "*")),
                str(getattr(schedule, "_orig_day_of_month", "*")),
                str(getattr(schedule, "_orig_month_of_year", "*")),
                str(getattr(schedule, "_orig_day_of_week", "*")),
            ]
            cron_expr = " ".join(parts)
        except Exception:
            cron_expr = None

    # --- 3. Fallback: parse the ``<crontab: ...>`` string ---
    if not cron_expr:
        try:
            raw = str(schedule)
            if "<crontab:" in raw:
                cron_expr = raw.split("<crontab:")[1].split("(")[0].strip()
        except Exception:
            pass

    # --- Timezone ---
    try:
        tz_obj = getattr(schedule, "timezone", None) or getattr(schedule, "tz", None)
        if tz_obj:
            tz = str(tz_obj)
    except Exception:
        pass

    return cron_expr, tz


def _paused_payload_to_schedule(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert paused payload stored in Redis into schedule summary."""
    if not data.get("name"):
        return None
    meta = data.get("metadata")
    cron = data.get("cron")
    tz = data.get("timezone")
    return {
        "name": data["name"],
        "task": data.get("task"),
        "schedule": data.get("schedule"),
        "cron": cron,
        "timezone": tz,
        "args": data.get("args") or [],
        "kwargs": data.get("kwargs") or {},
        "enabled": False,
        "source": "paused",
        "last_run": None,
        "metadata": meta,
        "status": "paused",
    }


class ScheduleCreate(BaseModel):
    name: str
    task: str
    cron: str  # "m h dom mon dow"
    timezone: str = "UTC"
    args: Optional[List[Any]] = None  # type: ignore
    kwargs: Optional[Dict[str, Any]] = None
    enabled: bool = True
    metadata: Optional[ScheduleMetadataPatch] = None


class ScheduleUpdate(BaseModel):
    cron: Optional[str] = None
    timezone: Optional[str] = None
    args: Optional[List[Any]] = None  # type: ignore
    kwargs: Optional[Dict[str, Any]] = None
    metadata: Optional[ScheduleMetadataPatch] = None


def _last_run_for_task(dotted_task: str) -> Dict[str, Any] | None:
    """Look up the most recent JobRun row for a dotted task path."""
    try:
        simple = dotted_task.split(".")[-1]
        from backend.database import SessionLocal
        from backend.models.market_data import JobRun
        db = SessionLocal()
        try:
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
                "started_at": getattr(row.started_at, "isoformat", lambda: None)(),
                "finished_at": getattr(row.finished_at, "isoformat", lambda: None)(),
            }
        finally:
            db.close()
    except Exception:
        return None


def _read_redbeat_entries() -> List[Dict[str, Any]]:
    """Read active and paused RedBeat entries directly from Redis.

    Uses the ``redbeat::schedule`` sorted set (active entries) and
    ``redbeat:paused:*`` keys (paused entries).  This avoids relying on
    ``RedBeatScheduler.rdb`` which may not exist in all redbeat versions.
    """
    r = _get_redis()
    out: List[Dict[str, Any]] = []

    # --- Active entries from the sorted set ---
    schedule_keys = r.zrange("redbeat::schedule", 0, -1)
    for raw_key in schedule_keys or []:
        key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
        try:
            defn_raw = r.hget(key, "definition")
            meta_raw = r.hget(key, "meta")
            if not defn_raw:
                continue
            defn = json.loads(defn_raw.decode() if isinstance(defn_raw, bytes) else defn_raw)
            meta_json = json.loads(meta_raw.decode() if isinstance(meta_raw, bytes) else meta_raw) if meta_raw else {}

            sched = defn.get("schedule") or {}
            cron_expr, tz = _parse_cron_and_tz(sched)
            task_path = defn.get("task", "")
            name = defn.get("name", key.replace("redbeat:", ""))

            last_run_at_raw = meta_json.get("last_run_at")
            last_run_at = None
            if isinstance(last_run_at_raw, dict):
                try:
                    from datetime import datetime as _dt
                    last_run_at = _dt(
                        year=last_run_at_raw.get("year", 1970),
                        month=last_run_at_raw.get("month", 1),
                        day=last_run_at_raw.get("day", 1),
                        hour=last_run_at_raw.get("hour", 0),
                        minute=last_run_at_raw.get("minute", 0),
                        second=last_run_at_raw.get("second", 0),
                    ).isoformat() + "Z"
                except Exception:
                    pass

            sched_meta = load_schedule_metadata(name)
            out.append(
                {
                    "name": name,
                    "task": task_path,
                    "schedule": str(sched) if sched else None,
                    "cron": cron_expr,
                    "timezone": tz or "UTC",
                    "args": defn.get("args") or [],
                    "kwargs": defn.get("kwargs") or {},
                    "enabled": defn.get("enabled", True),
                    "source": "redbeat",
                    "last_run": _last_run_for_task(task_path),
                    "last_run_at": last_run_at,
                    "total_run_count": meta_json.get("total_run_count", 0),
                    "metadata": sched_meta.model_dump() if sched_meta else None,
                    "status": "active" if defn.get("enabled", True) else "disabled",
                }
            )
        except Exception:
            continue

    # --- Paused entries ---
    for pkey in r.scan_iter(match="redbeat:paused:*"):
        try:
            praw = r.get(pkey)
            if not praw:
                continue
            data = json.loads(praw)
            paused_entry = _paused_payload_to_schedule(data)
            if paused_entry:
                out.append(paused_entry)
        except Exception:
            continue

    return out


@router.get("/schedules")
async def list_schedules(
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """List schedules from RedBeat (Redis) if available; fallback to static config."""
    out: List[Dict[str, Any]] = []
    mode = "static"

    # --- Try RedBeat (reads directly from Redis) ---
    try:
        redbeat_entries = _read_redbeat_entries()
        if redbeat_entries:
            out.extend(redbeat_entries)
            mode = "redbeat"
    except Exception:
        pass

    # --- Merge static beat_schedule entries not already covered ---
    existing_tasks = {entry["task"] for entry in out if entry.get("task")}
    existing_names = {entry["name"] for entry in out if entry.get("name")}
    static_schedules = celery_app.conf.beat_schedule or {}
    for name, spec in static_schedules.items():
        task_path = spec.get("task", "")
        if task_path in existing_tasks or name in existing_names:
            continue
        sched_obj = spec.get("schedule")
        cron_expr, tz = _parse_cron_and_tz(sched_obj) if sched_obj else (None, None)
        out.append(
            {
                "name": name,
                "task": task_path,
                "schedule": str(sched_obj) if sched_obj else None,
                "cron": cron_expr,
                "timezone": tz or "UTC",
                "args": spec.get("args") or [],
                "kwargs": spec.get("kwargs") or {},
                "enabled": True,
                "source": "static",
                "last_run": _last_run_for_task(task_path),
                "last_run_at": None,
                "total_run_count": None,
                "metadata": None,
                "status": "active",
            }
        )

    return {"schedules": out, "mode": mode}


@router.post("/schedules")
async def create_schedule(
    payload: ScheduleCreate,
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Create a schedule in RedBeat from cron string and timezone."""
    try:
        from redbeat import schedulers as rb
    except Exception:
        raise HTTPException(status_code=400, detail="RedBeat not enabled")
    try:
        minute, hour, dom, mon, dow = payload.cron.split()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid cron format")
    try:
        actor = _actor_label(admin_user)
        meta = None
        if payload.metadata:
            meta = payload.metadata.apply(None)
            if meta:
                meta.touch_audit(actor, is_create=True)
        options = metadata_to_options(meta)
        schedule = build_crontab_schedule(
            minute=minute,
            hour=hour,
            day_of_month=dom,
            month_of_year=mon,
            day_of_week=dow,
            timezone=payload.timezone,
        )
        entry = rb.RedBeatSchedulerEntry(
            name=payload.name,
            task=payload.task,
            schedule=schedule,
            args=payload.args or (),
            kwargs=payload.kwargs or {},
            options=options,
            app=celery_app,
        )
        entry.save()
        _persist_metadata(payload.name, meta)
        return {"status": "ok", "name": payload.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/schedules/{name}")
async def update_schedule(
    name: str,
    payload: ScheduleUpdate,
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Update a RedBeat schedule: delete and recreate with new spec (simple approach)."""
    try:
        from redbeat import schedulers as rb
    except Exception:
        raise HTTPException(status_code=400, detail="RedBeat not enabled")
    # Fetch current entry to get task and existing args if not overriding
    try:
        key = f"redbeat:{name}:task"
        current = rb.RedBeatSchedulerEntry.from_key(key, app=celery_app)
    except Exception:
        raise HTTPException(status_code=404, detail="schedule not found")
    cron = payload.cron
    tz = payload.timezone
    if not cron:
        # Attempt to stringify current schedule; require cron provided to avoid ambiguity
        raise HTTPException(status_code=400, detail="cron is required for update")
    try:
        minute, hour, dom, mon, dow = cron.split()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid cron format")
    try:
        actor = _actor_label(admin_user)
        existing_meta = load_schedule_metadata(name)
        meta = existing_meta
        if payload.metadata:
            meta = payload.metadata.apply(existing_meta)
            if meta:
                meta.touch_audit(actor, is_create=existing_meta is None)
        options = metadata_to_options(meta)
        # Delete and recreate
        current.delete()
        schedule = build_crontab_schedule(
            minute=minute,
            hour=hour,
            day_of_month=dom,
            month_of_year=mon,
            day_of_week=dow,
            timezone=tz or "UTC",
        )
        entry = rb.RedBeatSchedulerEntry(
            name=name,
            task=current.task,
            schedule=schedule,
            args=payload.args if payload.args is not None else (current.args or ()),
            kwargs=payload.kwargs if payload.kwargs is not None else (current.kwargs or {}),
            options=options,
            app=celery_app,
        )
        entry.save()
        _persist_metadata(name, meta)
        return {"status": "ok", "name": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/schedules/{name}")
async def delete_schedule(
    name: str,
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Delete a RedBeat schedule by name."""
    try:
        from redbeat import schedulers as rb
        e = rb.RedBeatSchedulerEntry.from_key(f"redbeat:{name}:task", app=celery_app)
        e.delete()
        _persist_metadata(name, None)
        return {"status": "ok", "deleted": name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks/catalog")
async def list_catalog(
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Return job catalog grouped by kind."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    # helper: fetch last run by simple task name
    def _last_run(simple_task: str) -> Dict[str, Any] | None:
        try:
            from backend.database import SessionLocal
            from backend.models.market_data import JobRun
            db = SessionLocal()
            try:
                row = (
                    db.query(JobRun)
                    .filter(JobRun.task_name == simple_task)
                    .order_by(JobRun.started_at.desc())
                    .first()
                )
                if not row:
                    return None
                return {
                    "task_name": row.task_name,
                    "status": row.status,
                    "started_at": getattr(row.started_at, "isoformat", lambda: None)(),
                    "finished_at": getattr(row.finished_at, "isoformat", lambda: None)(),
                }
            finally:
                db.close()
        except Exception:
            return None
    for t in CATALOG:
        item = t.to_dict()
        # dotted task path -> simple name at the end
        simple = (t.task or "").split(".")[-1]
        item["last_run"] = _last_run(simple)
        grouped.setdefault(t.group, []).append(item)
    return {"catalog": grouped}


@router.post("/schedules/run-now")
async def run_now(
    task: str = Query(..., description="dotted task path"),
    args: Optional[List[Any]] = None,
    kwargs: Optional[Dict[str, Any]] = None,
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Immediately enqueue a task (one-off) on Celery."""
    try:
        res = celery_app.send_task(task, args=(args or ()), kwargs=(kwargs or {}))
        return {"status": "ok", "task_id": res.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedules/preview")
async def preview_cron(
    cron: str = Query(..., description="m h dom mon dow"),
    timezone: str = Query("UTC"),
    count: int = Query(5, ge=1, le=20),
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Return next N run times for the given cron+timezone."""
    try:
        minute, hour, dom, mon, dow = cron.split()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid cron format")
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid timezone")
    # Build a cron string for croniter (5-field)
    expr = f"{minute} {hour} {dom} {mon} {dow}"
    now = datetime.now(tz=tz)
    it = croniter(expr, now)
    out: List[str] = []
    for _ in range(count):
        dt = it.get_next(datetime)
        out.append(dt.astimezone(ZoneInfo("UTC")).isoformat())
    return {"next_runs_utc": out, "tz": timezone}


def _get_redis() -> redislib.Redis:
    # Use same URL as broker/result; prefer CELERY_BROKER_URL then REDIS_URL
    from backend.config import settings
    url = getattr(settings, "CELERY_BROKER_URL", None) or getattr(settings, "REDIS_URL", None)
    if not url:
        raise RuntimeError("Redis URL is not configured; set CELERY_BROKER_URL or REDIS_URL")
    return redislib.from_url(url)


@router.post("/schedules/pause")
async def pause_schedule(
    name: str = Query(...),
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Pause a RedBeat schedule by deleting it and storing definition under redbeat:paused:{name}."""
    try:
        from redbeat import schedulers as rb
        key = f"redbeat:{name}:task"
        e = rb.RedBeatSchedulerEntry.from_key(key, app=celery_app)
        # Extract cronish string from schedule string best-effort is not reliable; require re-creation via resume payload
        cron_expr, tz = _parse_cron_and_tz(e.schedule)
        payload = {
            "name": e.name,
            "task": e.task,
            "args": e.args or [],
            "kwargs": e.kwargs or {},
            "schedule": str(e.schedule),
            "cron": cron_expr,
            "timezone": tz,
        }
        meta = load_schedule_metadata(name)
        if meta:
            payload["metadata"] = meta.model_dump()
        r = _get_redis()
        r.set(f"redbeat:paused:{name}", json.dumps(payload))
        e.delete()
        return {"status": "ok", "paused": name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/schedules/resume")
async def resume_schedule(
    name: str = Query(...),
    cron: Optional[str] = Query(None, description="optional override cron 'm h dom mon dow'"),
    timezone: Optional[str] = Query(None),
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Resume a paused schedule by recreating it (cron required if not previously stored)."""
    try:
        r = _get_redis()
        raw = r.get(f"redbeat:paused:{name}")
        if not raw:
            raise HTTPException(status_code=404, detail="paused schedule not found")
        data = json.loads(raw)
        task = data.get("task")
        args = data.get("args") or []
        kwargs = data.get("kwargs") or {}
        stored_meta = data.get("metadata")
        meta_patch = ScheduleMetadataPatch(**stored_meta) if stored_meta else None
        if not cron:
            cron = data.get("cron")
        if not cron:
            raise HTTPException(status_code=400, detail="cron required to resume")
        tz_value = timezone or data.get("timezone") or "UTC"
        # Recreate
        await create_schedule(
            ScheduleCreate(
                name=name,
                task=task,
                cron=cron,
                timezone=tz_value,
                args=args,
                kwargs=kwargs,
                metadata=meta_patch,
            ),
            admin_user,
        )
        r.delete(f"redbeat:paused:{name}")
        return {"status": "ok", "resumed": name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/schedules/export")
async def export_schedules(
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Export RedBeat schedules as JSON."""
    try:
        from redbeat import schedulers as rb
        scheduler = rb.RedBeatScheduler(app=celery_app)
        entries = list(scheduler.rdb.scan_iter(match="redbeat:*:task"))
        out: List[Dict[str, Any]] = []
        for key in entries:
            try:
                e = rb.RedBeatSchedulerEntry.from_key(key.decode() if isinstance(key, bytes) else key, app=celery_app)
                cron_expr, tz = _parse_cron_and_tz(e.schedule)
                meta = load_schedule_metadata(e.name)
                out.append(
                    {
                        "name": e.name,
                        "task": e.task,
                        "schedule": str(e.schedule),
                        "cron": cron_expr,
                        "timezone": tz,
                        "args": e.args or [],
                        "kwargs": e.kwargs or {},
                        "metadata": meta.model_dump() if meta else None,
                    }
                )
            except Exception:
                continue
        return {"schedules": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedules/import")
async def import_schedules(
    payload: Dict[str, Any],
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Import schedules from JSON list (name, task, cron, timezone, args, kwargs)."""
    try:
        items = payload.get("schedules") or []
        created = 0
        for it in items:
            try:
                meta_data = it.get("metadata")
                meta_patch = ScheduleMetadataPatch(**meta_data) if meta_data else None
                await create_schedule(
                    ScheduleCreate(
                        name=it["name"],
                        task=it["task"],
                        cron=it.get("cron") or "* * * * *",
                        timezone=it.get("timezone") or "UTC",
                        args=it.get("args") or [],
                        kwargs=it.get("kwargs") or {},
                        metadata=meta_patch,
                    ),
                    admin_user,
                )
                created += 1
            except Exception:
                continue
        return {"status": "ok", "created": created}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


