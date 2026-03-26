from __future__ import annotations

import asyncio
import json
import functools
import logging
import traceback
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

from celery import current_task

from backend.config import settings
from backend.database import SessionLocal
from backend.models import JobRun
from backend.services.market.market_data_service import market_data_service
from backend.services.notifications.alerts import alert_service
from backend.tasks.schedule_metadata import HookConfig, ScheduleMetadata

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# Shared helpers (extracted from market_data_tasks.py)
# ---------------------------------------------------------------------------


def setup_event_loop() -> asyncio.AbstractEventLoop:
    """Create a fresh event loop for sync task wrappers (caller must close).

    IMPORTANT: Do not set this loop as the global default via asyncio.set_event_loop().
    These tasks run loop.run_until_complete(...) explicitly, and setting a closed loop as
    the process-global default can break unrelated code/tests that use asyncio.
    """
    return asyncio.new_event_loop()


def increment_provider_usage(usage: Dict[str, int], result: dict | None) -> None:
    """Track provider usage statistics from a fetch result."""
    provider = (result or {}).get("provider") or "unknown"
    usage[provider] = usage.get(provider, 0) + 1


def classify_provider_error(error: object) -> str:
    """Categorize provider errors for metrics and retry logic."""
    msg = str(error or "").lower()
    if "429" in msg or "too many" in msg or "rate limit" in msg:
        return "rate_limit"
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    if "connection" in msg or "connect" in msg:
        return "connection"
    if "invalid json" in msg or "json" in msg:
        return "bad_response"
    return "provider_error"


def resolve_history_days(requested_days: int | None) -> int:
    """Resolve snapshot history window using last successful run (min 5 days).
    
    If requested_days is provided, uses that (clamped to minimum of 5).
    Otherwise looks up last successful admin_coverage_backfill run and computes
    the number of days since then, defaulting to 20 if no prior run found.
    """
    minimum_days = 5
    if requested_days is not None:
        try:
            return max(minimum_days, int(requested_days))
        except (TypeError, ValueError):
            pass
    session = SessionLocal()
    try:
        last_run = (
            session.query(JobRun)
            .filter(
                JobRun.task_name == "admin_coverage_backfill",
                JobRun.status == "ok",
            )
            .order_by(
                JobRun.finished_at.desc().nullslast(),
                JobRun.started_at.desc(),
            )
            .first()
        )
        last_ts = None
        if last_run:
            last_ts = last_run.finished_at or last_run.started_at
        if last_ts:
            delta_days = max(0, (datetime.utcnow().date() - last_ts.date()).days)
            return max(minimum_days, delta_days)
    except Exception as e:
        logger.warning("History days lookup failed, using default: %s", e)
    finally:
        session.close()
    return max(minimum_days, 20)


def get_tracked_symbols_safe(session) -> list[str]:
    """Get tracked symbols with fallback to DB if Redis cache is empty.
    
    Args:
        session: SQLAlchemy session
        
    Returns:
        Sorted list of uppercase symbol strings
    """
    from backend.services.market.universe import tracked_symbols, tracked_symbols_from_db
    
    symbols = tracked_symbols(session, redis_client=market_data_service.redis_client)
    symbols = sorted({str(s).upper() for s in (symbols or []) if s})
    if not symbols:
        symbols = sorted({s.upper() for s in tracked_symbols_from_db(session)})
    return symbols


def get_tracked_universe_from_db(session) -> set[str]:
    """Get union of active index constituents and portfolio symbols from DB.
    
    IMPORTANT:
    - We intentionally exclude inactive index constituents, otherwise the tracked universe
      accumulates delisted/removed tickers and coverage will look degraded forever.
      
    Args:
        session: SQLAlchemy session
        
    Returns:
        Set of uppercase symbol strings
    """
    from backend.services.market.universe import tracked_symbols_from_db
    return set(tracked_symbols_from_db(session))


def set_task_status(task_name: str, status: str, payload: dict | None = None) -> None:
    """Publish task status to Redis for monitoring.
    
    Note: This is an alias for _publish_status with error handling.
    The task_run decorator handles this automatically for decorated tasks.
    """
    try:
        _publish_status(task_name, status, payload)
    except Exception as e:
        logger.warning("task_status_set failed for %s: %s", task_name, e)

