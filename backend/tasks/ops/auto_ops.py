"""Auto-Ops Agent -- LLM-powered health check and self-remediation.

Uses OpenAI GPT-4o-mini to intelligently analyze system health and decide
on remediation actions. Falls back to rule-based logic if LLM not configured.

Architecture:
- LLM Brain: Analyzes health, queries DB, searches web, dispatches fixes
- Risk Taxonomy: safe/moderate auto-execute, risky/critical require approval
- Approval Queue: AgentAction model tracks pending approvals

Guardrails:
- Exponential backoff cooldown per dimension (15m → 30m → 60m → 120m cap).
- Retries up to 6 times per dimension. After 6 failures, escalates via Brain
  webhook alert and pauses remediation until the dimension returns to green.
- Regime compute only fires during market-adjacent hours (06:00-22:00 ET),
  unless regime is >72h stale.
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

BACKOFF_SEQUENCE = (900, 1800, 3600, 7200)  # 15m, 30m, 60m, 2h cap
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


def _set_cooldown(dimension: str, retry_count: int = 0) -> None:
    """Set backoff cooldown from explicit sequence: 15m, 30m, 60m, 2h (cap)."""
    idx = min(retry_count, len(BACKOFF_SEQUENCE) - 1)
    r = _redis()
    r.setex(_cooldown_key(dimension), BACKOFF_SEQUENCE[idx], "1")


def _increment_retries(dimension: str) -> int:
    """Increment retry counter. Returns new count. Never expires — clears on green."""
    r = _redis()
    key = _retry_key(dimension)
    count = r.incr(key)
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
        ("backend.tasks.market.backfill.constituents", {}),
        ("backend.tasks.market.coverage.health_check", {}),
        ("backend.tasks.market.backfill.stale_daily", {}),
    ],
    "stage_quality": [
        ("backend.tasks.market.indicators.recompute_universe", {"batch_size": 50}),
        ("backend.tasks.market.indicators.repair_stage_history", {"days": 120}),
    ],
    "jobs": [
        ("backend.tasks.market.maintenance.recover_jobs", {"stale_minutes": 120}),
    ],
    "audit": [
        ("backend.tasks.market.coverage.daily_bootstrap", {"history_days": 5, "history_batch_size": 25}),
        ("backend.tasks.market.history.record_daily", {}),
        ("backend.tasks.market.maintenance.audit_quality", {}),
    ],
    "regime": [
        ("backend.tasks.market.regime.compute_daily", {}),
    ],
    "fundamentals": [
        ("backend.tasks.market.fundamentals.fill_missing", {"limit_per_run": 500}),
    ],
    "ibkr_gateway": [
        ("backend.tasks.ibkr_watchdog.ping_ibkr_connection", {}),
    ],
    "portfolio_sync": [
        ("backend.tasks.account_sync.sync_all_ibkr_accounts", {}),
        ("backend.tasks.account_sync.sync_all_schwab_accounts", {}),
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


_HEALTH_ALERT_COOLDOWN_KEY = f"{REDIS_PREFIX}:health_alert_cooldown"
_HEALTH_ALERT_COOLDOWN_S = 900  # 15 min


def _fire_health_alert(health: dict) -> None:
    """Send a Brain webhook when composite health is RED (with cooldown)."""
    r = _redis()
    if r and r.exists(_HEALTH_ALERT_COOLDOWN_KEY):
        return
    try:
        from backend.services.brain.webhook_client import brain_webhook
        brain_webhook.notify_sync("health_alert", {
            "composite_status": health.get("composite_status"),
            "composite_reason": health.get("composite_reason"),
            "checked_at": health.get("checked_at"),
        })
        if r:
            r.setex(_HEALTH_ALERT_COOLDOWN_KEY, _HEALTH_ALERT_COOLDOWN_S, "1")
    except Exception as exc:
        logger.warning("auto-ops: health alert webhook failed: %s", exc)


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
        health_svc.refresh_provider_probe()
        health = health_svc.get_composite_health(session)
        # Pre-market readiness check (weekday mornings 7:00-9:29 ET)
        try:
            from zoneinfo import ZoneInfo
            et_now = datetime.now(ZoneInfo("America/New_York"))
            if et_now.weekday() < 5 and 7 <= et_now.hour < 10 and et_now.hour * 60 + et_now.minute < 570:
                readiness = health_svc.check_pre_market_readiness(session)
                if not readiness.get("ready"):
                    logger.warning("auto-ops: pre-market NOT ready: %s", readiness.get("gaps"))
        except Exception as exc:
            logger.warning("auto-ops: pre-market readiness check failed: %s", exc)
    finally:
        session.close()

    composite = health.get("composite_status", "unknown")

    if composite == "red":
        _fire_health_alert(health)

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
    """Rule-based remediation fallback."""
    from backend.services.market.admin_health_service import BROKER_DIMS

    composite = health.get("composite_status", "unknown")
    dimensions = health.get("dimensions", {})
    market_only = health.get("market_only_mode", True)

    actions_taken = []
    skipped = []

    for dim_name, dim_data in dimensions.items():
        status = dim_data.get("status", "unknown")
        if status in ("green", "ok"):
            _clear_retries(dim_name)
            continue
        if status in ("warning", "yellow") and dim_name not in ("fundamentals", "coverage", "stage_quality"):
            _clear_retries(dim_name)
            continue

        if market_only and dim_name in BROKER_DIMS:
            _clear_retries(dim_name)
            skipped.append({"dimension": dim_name, "reason": "not_in_scope"})
            continue

        if _is_on_cooldown(dim_name):
            skipped.append({"dimension": dim_name, "reason": "cooldown"})
            continue

        retry_count = _get_retries(dim_name)

        if retry_count >= 6:
            skipped.append({"dimension": dim_name, "reason": "max_retries_exceeded"})
            try:
                _fire_health_alert({
                    "composite_status": "red",
                    "composite_reason": f"Escalation: {dim_name} failed {retry_count} consecutive remediation attempts",
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass
            continue

        if dim_name == "regime" and not _is_market_adjacent_hours():
            age_hours = float(dim_data.get("age_hours", 0) or 0)
            if age_hours < 72:
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

        retry_count = _get_retries(dim_name)
        _set_cooldown(dim_name, retry_count=retry_count)
        _increment_retries(dim_name)
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
        "details": {
            "actions": actions_taken,
            "skipped": skipped,
        },
    }

    if actions_taken:
        logger.info("auto-ops: remediated %d dimensions: %s",
                     len(actions_taken),
                     [a["dimension"] for a in actions_taken])
    else:
        logger.info("auto-ops: all dimensions green or on cooldown")

    return summary
