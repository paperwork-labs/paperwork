"""Auto-Ops Agent -- LLM-powered health check and self-remediation.

Uses OpenAI GPT-4o-mini to intelligently analyze system health and decide
on remediation actions. Falls back to rule-based logic if LLM not configured.

Architecture:
- LLM Brain: Analyzes health, queries DB, searches web, dispatches fixes
- Risk Taxonomy: safe/moderate auto-execute, risky/critical require approval
- Approval Queue: AgentAction model tracks pending approvals

Guardrails:
- Redis cooldown (30 min per dimension) prevents remediation loops.
- Max-retry counter (3 attempts) escalates to a warning instead of retrying.
- Regime compute only fires during market-adjacent hours (06:00-22:00 ET).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from celery import shared_task

from backend.config import settings
from backend.database import SessionLocal
from backend.services.market.market_data_service import market_data_service
from backend.tasks.utils.task_utils import task_run

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
        ("backend.tasks.market.coverage.health_check", {}),
        ("backend.tasks.market.backfill.stale_daily", {}),
    ],
    "stage_quality": [
        ("backend.tasks.market.indicators.recompute_universe", {"batch_size": 50}),
    ],
    "jobs": [
        ("backend.tasks.market.maintenance.recover_jobs", {"stale_minutes": 120}),
    ],
    "audit": [
        ("backend.tasks.market.coverage.daily_bootstrap", {"history_days": 5, "history_batch_size": 25}),
        ("backend.tasks.market.history.record_daily", {}),
    ],
    "regime": [
        ("backend.tasks.market.regime.compute_daily", {}),
    ],
    "fundamentals": [
        ("backend.tasks.market.fundamentals.fill_missing", {}),
    ],
}


async def _run_llm_agent(health: dict) -> dict:
    """Run the LLM-powered agent brain."""
    from backend.services.agent.brain import AgentBrain
    
    session = SessionLocal()
    try:
        brain = AgentBrain(db=session)
        result = await brain.analyze_and_act(health)
        return result
    finally:
        session.close()


def _run_llm_agent_sync(health: dict) -> dict:
    """Synchronous wrapper for the async LLM agent."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(_run_llm_agent(health))


@shared_task(
    name="backend.tasks.auto_ops_tasks.auto_remediate_health",
    soft_time_limit=120,
    time_limit=180,
)
@task_run("auto_ops_health_check")
def auto_remediate_health() -> dict:
    """Check all health dimensions and dispatch fixes for any that are not green.
    
    Uses LLM-powered agent when OPENAI_API_KEY is configured, otherwise
    falls back to rule-based remediation logic.
    """
    from backend.services.market.admin_health_service import AdminHealthService

    session = SessionLocal()
    try:
        health_svc = AdminHealthService()
        health = health_svc.get_composite_health(session)
    finally:
        session.close()

    composite = health.get("composite_status", "unknown")
    
    if settings.OPENAI_API_KEY:
        logger.info("auto-ops: using LLM agent (composite=%s)", composite)
        try:
            result = _run_llm_agent_sync(health)
            result["mode"] = "llm"
            return result
        except Exception as e:
            logger.warning("auto-ops: LLM agent failed, falling back to rules: %s", e)
    
    return _rule_based_remediation(health)


def _rule_based_remediation(health: dict) -> dict:
    """Rule-based remediation fallback (legacy logic)."""
    composite = health.get("composite_status", "unknown")
    dimensions = health.get("dimensions", {})

    actions_taken = []
    skipped = []
    escalated = []

    for dim_name, dim_data in dimensions.items():
        status = dim_data.get("status", "unknown")
        if status in ("green", "ok"):
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
        "mode": "rule_based",
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
