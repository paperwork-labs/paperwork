"""Auto-Ops Agent -- periodic health check and self-remediation.

Checks AdminHealthService dimensions every 15 minutes and dispatches
the appropriate remediation tasks when a dimension goes red/yellow.

Guardrails:
- Redis cooldown (30 min per dimension) prevents remediation loops.
- Max-retry counter (3 attempts) escalates to a warning instead of retrying.
- Regime compute only fires during market-adjacent hours (06:00-22:00 ET).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from celery import shared_task

from backend.database import SessionLocal
from backend.services.market.market_data_service import market_data_service
from backend.tasks.task_utils import task_run

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = 1800  # 30 minutes
MAX_RETRIES_BEFORE_ESCALATE = 3
REDIS_PREFIX = "auto_ops"


def _redis():
    return market_data_service.redis_client


def _cooldown_key(dimension: str) -> str:
    return f"{REDIS_PREFIX}:cooldown:{dimension}"


def _retry_key(dimension: str) -> str:
    return f"{REDIS_PREFIX}:retries:{dimension}"


def _is_on_cooldown(dimension: str) -> bool:
    r = _redis()
    return r.exists(_cooldown_key(dimension)) > 0


def _set_cooldown(dimension: str) -> None:
    r = _redis()
    r.setex(_cooldown_key(dimension), COOLDOWN_SECONDS, "1")


def _increment_retries(dimension: str) -> int:
    """Increment retry counter. Returns new count. Counter auto-expires after 6 hours."""
    r = _redis()
    key = _retry_key(dimension)
    count = r.incr(key)
    r.expire(key, 21600)
    return count


def _clear_retries(dimension: str) -> None:
    r = _redis()
    r.delete(_retry_key(dimension))


def _get_retries(dimension: str) -> int:
    r = _redis()
    val = r.get(_retry_key(dimension))
    return int(val) if val else 0


def _is_market_adjacent_hours() -> bool:
    """True if current time is between 06:00 and 22:00 US/Eastern."""
    try:
        from zoneinfo import ZoneInfo
        et_now = datetime.now(ZoneInfo("America/New_York"))
        return 6 <= et_now.hour < 22
    except Exception:
        return True


REMEDIATION_MAP = {
    "coverage": [
        ("backend.tasks.market_data_tasks.monitor_coverage_health", {}),
        ("backend.tasks.market_data_tasks.backfill_stale_daily_tracked", {}),
    ],
    "stage_quality": [
        ("backend.tasks.market_data_tasks.recompute_indicators_universe", {"batch_size": 50}),
    ],
    "jobs": [
        ("backend.tasks.market_data_tasks.recover_stale_job_runs", {"stale_minutes": 120}),
    ],
    "audit": [
        ("backend.tasks.market_data_tasks.bootstrap_daily_coverage_tracked", {"history_days": 5, "history_batch_size": 25}),
        ("backend.tasks.market_data_tasks.record_daily_history", {}),
    ],
    "regime": [
        ("backend.tasks.market_data_tasks.compute_daily_regime", {}),
    ],
}


@shared_task(
    name="backend.tasks.auto_ops_tasks.auto_remediate_health",
    soft_time_limit=60,
    time_limit=90,
)
@task_run("auto_ops_health_check")
def auto_remediate_health() -> dict:
    """Check all health dimensions and dispatch fixes for any that are not green."""
    from backend.services.market.admin_health_service import AdminHealthService

    session = SessionLocal()
    try:
        health_svc = AdminHealthService()
        health = health_svc.get_composite_health(session)
    finally:
        session.close()

    composite = health.get("composite_status", "unknown")
    dimensions = health.get("dimensions", {})

    actions_taken = []
    skipped = []
    escalated = []

    for dim_name, dim_data in dimensions.items():
        status = dim_data.get("status", "unknown")
        if status == "green":
            _clear_retries(dim_name)
            continue

        if _is_on_cooldown(dim_name):
            skipped.append({"dimension": dim_name, "reason": "cooldown"})
            continue

        retry_count = _get_retries(dim_name)
        if retry_count >= MAX_RETRIES_BEFORE_ESCALATE:
            escalated.append({
                "dimension": dim_name,
                "status": status,
                "retries": retry_count,
            })
            logger.warning(
                "auto-ops: dimension %s has been %s for %d consecutive checks, escalating",
                dim_name, status, retry_count,
            )
            _set_cooldown(dim_name)
            continue

        if dim_name == "regime" and not _is_market_adjacent_hours():
            skipped.append({"dimension": dim_name, "reason": "outside_market_hours"})
            continue

        tasks_to_dispatch = REMEDIATION_MAP.get(dim_name, [])
        if not tasks_to_dispatch:
            skipped.append({"dimension": dim_name, "reason": "no_remediation_defined"})
            continue

        from backend.tasks.celery_app import celery_app

        dispatched = []
        for task_name, kwargs in tasks_to_dispatch:
            try:
                result = celery_app.send_task(task_name, kwargs=kwargs)
                dispatched.append({"task": task_name, "task_id": result.id})
                logger.info(
                    "auto-ops: dispatched %s for dimension %s (status=%s)",
                    task_name, dim_name, status,
                )
            except Exception as exc:
                logger.warning(
                    "auto-ops: failed to dispatch %s for %s: %s",
                    task_name, dim_name, exc,
                )

        _increment_retries(dim_name)
        _set_cooldown(dim_name)
        actions_taken.append({
            "dimension": dim_name,
            "status": status,
            "dispatched": dispatched,
        })

    summary = {
        "composite_status": composite,
        "actions_taken": len(actions_taken),
        "skipped": len(skipped),
        "escalated": len(escalated),
        "details": {
            "actions": actions_taken,
            "skipped": skipped,
            "escalated": escalated,
        },
    }

    if actions_taken:
        logger.info("auto-ops: remediated %d dimensions: %s",
                     len(actions_taken),
                     [a["dimension"] for a in actions_taken])
    elif escalated:
        logger.warning("auto-ops: %d dimensions escalated, 0 remediated", len(escalated))
    else:
        logger.info("auto-ops: all dimensions green or on cooldown")

    return summary
