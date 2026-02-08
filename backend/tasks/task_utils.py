from __future__ import annotations

import json
import functools
import traceback
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from celery import current_task

from backend.config import settings
from backend.database import SessionLocal
from backend.models import JobRun
from backend.services.market.market_data_service import market_data_service
from backend.services.alerts import alert_service
from backend.tasks.schedule_metadata import HookConfig, ScheduleMetadata


def task_run(task_name: str, *, lock_key: Optional[Callable[..., Optional[str]]] = None, lock_ttl_seconds: int = 1800):
    """
    Decorator to standardize task execution:
    - Optional Redis lock to prevent duplicate work (by computed key)
    - Write JobRun row with status running/ok/error and counters from returned dict
    - Publish last-run status into Redis key: taskstatus:{task_name}:last
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Optional redis lock
            lock_id: Optional[str] = None
            if lock_key is not None:
                try:
                    key = lock_key(*args, **kwargs)
                    if key:
                        r = market_data_service.redis_client
                        # SETNX + expiry
                        acquired = r.set(name=f"lock:{task_name}:{key}", value="1", nx=True, ex=lock_ttl_seconds)
                        if not acquired:
                            return {"status": "skipped", "reason": "locked", "lock_key": key}
                        lock_id = key
                except Exception:
                    pass
            session = SessionLocal()
            job = JobRun(
                task_name=task_name,
                params=kwargs or {},
                status="running",
                started_at=datetime.utcnow(),
            )
            session.add(job)
            session.commit()
            meta = _active_schedule_metadata()
            hooks = (meta.hooks if meta else None) or _default_hooks()
            # Publish 'running'
            try:
                _publish_status(task_name, "running", {"id": job.id, "params": kwargs})
            except Exception:
                pass
            try:
                result = func(*args, **kwargs)
                counters = None
                if isinstance(result, dict):
                    counters = {k: v for k, v in result.items() if k not in ("status", "error")}
                    # Allow tasks to report non-fatal, bounded error summaries without failing the job.
                    # We store these in JobRun.error for visibility in the Admin Jobs UI.
                    try:
                        nonfatal_error = result.get("error")
                        if nonfatal_error:
                            job.error = str(nonfatal_error)[:10000]
                    except Exception:
                        pass
                job.status = "ok"
                job.finished_at = datetime.utcnow()
                duration = _job_duration_seconds(job)
                if counters is not None:
                    counters["duration_s"] = duration
                    counters["duration_bucket"] = _duration_bucket(duration)
                    job.counters = counters
                session.commit()
                try:
                    _publish_status(task_name, "ok", {"id": job.id, "payload": result})
                except Exception:
                    pass
                _emit_alerts(
                    event="success",
                    task_name=task_name,
                    job=job,
                    hooks=hooks,
                    duration_s=duration,
                    meta=meta,
                    counters=counters,
                )
                if _is_slow_run(duration, meta, hooks):
                    _emit_alerts(
                        event="slow",
                        task_name=task_name,
                        job=job,
                        hooks=hooks,
                        duration_s=duration,
                        meta=meta,
                        counters=counters,
                    )
                return result
            except Exception as exc:
                job.status = "error"
                job.error = f"{exc}\n{traceback.format_exc()}"
                job.finished_at = datetime.utcnow()
                session.commit()
                try:
                    _publish_status(task_name, "error", {"id": job.id, "error": str(exc)})
                except Exception:
                    pass
                _emit_alerts(
                    event="failure",
                    task_name=task_name,
                    job=job,
                    hooks=hooks,
                    duration_s=_job_duration_seconds(job),
                    meta=meta,
                    error=str(exc),
                )
                raise
            finally:
                session.close()
                if lock_id is not None:
                    try:
                        market_data_service.redis_client.delete(f"lock:{task_name}:{lock_id}")
                    except Exception:
                        pass

        return wrapper

    return decorator


def _publish_status(task: str, status: str, payload: dict | None = None) -> None:
    r = market_data_service.redis_client
    r.set(
        f"taskstatus:{task}:last",
        json.dumps({"task": task, "status": status, "ts": datetime.utcnow().isoformat(), "payload": payload or {}}),
    )


def _active_schedule_metadata() -> ScheduleMetadata | None:
    try:
        req = current_task.request
        headers = getattr(req, "headers", None) or {}
        meta_payload = headers.get("schedule_metadata")
        if isinstance(meta_payload, bytes):
            meta_payload = meta_payload.decode("utf-8")
        if isinstance(meta_payload, str):
            meta_payload = json.loads(meta_payload)
        if isinstance(meta_payload, dict):
            return ScheduleMetadata(**meta_payload)
    except Exception:
        return None
    return None


def _default_hooks() -> HookConfig | None:
    system_hook = getattr(settings, "DISCORD_WEBHOOK_SYSTEM_STATUS", None)
    if system_hook:
        return HookConfig(discord_webhook="system_status", alert_on=["failure"])
    return None


def _job_duration_seconds(job: JobRun) -> float:
    if not job.finished_at or not job.started_at:
        return 0.0
    start = job.started_at
    end = job.finished_at
    try:
        if start.tzinfo and not end.tzinfo:
            start = start.replace(tzinfo=None)
        if end.tzinfo and not start.tzinfo:
            end = end.replace(tzinfo=None)
    except Exception:
        pass
    return max((end - start).total_seconds(), 0.0)


def _duration_bucket(duration_s: float) -> str:
    if duration_s < 60:
        return "fast"
    if duration_s < 300:
        return "normal"
    if duration_s < 900:
        return "slow"
    return "very_slow"


def _slow_threshold(meta: ScheduleMetadata | None, hooks: HookConfig | None) -> Optional[float]:
    if hooks and hooks.slow_threshold_s:
        try:
            return float(hooks.slow_threshold_s)
        except (TypeError, ValueError):
            return None
    if meta and meta.safety and meta.safety.timeout_s:
        try:
            return float(meta.safety.timeout_s)
        except (TypeError, ValueError):
            return None
    return None


def _is_slow_run(duration_s: float, meta: ScheduleMetadata | None, hooks: HookConfig | None) -> bool:
    threshold = _slow_threshold(meta, hooks)
    if threshold is None:
        return False
    return duration_s > threshold


def _emit_alerts(
    *,
    event: str,
    task_name: str,
    job: JobRun,
    hooks: HookConfig | None,
    duration_s: float | None,
    meta: ScheduleMetadata | None,
    counters: dict | None = None,
    error: Optional[str] = None,
) -> None:
    if hooks is None:
        return
    endpoint = hooks.prometheus_endpoint
    alert_events = hooks.alert_on or ["failure"]
    labels = {
        "task": task_name,
        "event": event,
        "queue": meta.queue if meta else "default",
    }
    alert_service.push_prometheus_metric(
        endpoint,
        "axiomfolio_task_duration_seconds",
        float(duration_s or 0.0),
        labels,
    )
    if event not in alert_events:
        return
    descriptor: list[str] = []
    if hooks.discord_webhook:
        descriptor.append(hooks.discord_webhook)
    if hooks.discord_channels:
        descriptor.extend(hooks.discord_channels)
    if not descriptor:
        return
    severity = "info"
    if event == "failure":
        severity = "error"
    elif event == "slow":
        severity = "warning"
    fields = {
        "Job ID": str(job.id),
        "Duration": f"{(duration_s or 0):.1f}s",
        "Queue": meta.queue if meta and meta.queue else "default",
    }
    if counters:
        fields["Counters"] = json.dumps(counters)[:1024]
    if error:
        fields["Error"] = (error or "")[:512]
    if meta and meta.notes:
        fields["Notes"] = meta.notes[:512]
    description = f"Task {task_name} reported {event}."
    if hooks and hooks.discord_mentions:
        mentions = " ".join(hooks.discord_mentions)
        if mentions.strip():
            description = f"{description}\n{mentions}"

    alert_service.send_discord(
        descriptor,
        title=f"{task_name}: {event.upper()}",
        description=description,
        fields=fields,
        severity=severity,
    )



