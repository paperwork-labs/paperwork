"""Infra health monitor from Brain APScheduler (interval, T1).

Replaces the **Infra Health Check** n8n workflow (30-minute interval) — see
``infra/hetzner/workflows/retired/infra-health-check.json`` and
``docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md``.

WS-69 PR J: n8n workflow check removed (n8n decommissioned). Now uses
Brain's ``system_health`` service to probe Render/Vercel/Neon/Upstash.
Creates a Conversation on alert; quiet otherwise.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from apscheduler.triggers.interval import IntervalTrigger

from app.schedulers._history import SchedulerRunSkipped, run_with_scheduler_record
from app.schemas.conversation import ConversationCreate
from app.services.conversations import create_conversation

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "brain_infra_health"
_REDIS_PREFIX = "brain:infra_health:"
_DEFAULT_REMINDER_HOURS = 4

_mem_last_alert_at: datetime | None = None


async def _get_redis_or_none() -> Any:
    try:
        from app.redis import get_redis

        return get_redis()
    except RuntimeError:
        return None


async def _load_last_alert_at(redis: Any) -> datetime | None:
    global _mem_last_alert_at
    if redis is None:
        return _mem_last_alert_at
    try:
        raw = await redis.get(f"{_REDIS_PREFIX}last_alert_at")
        if not raw:
            return None
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return _mem_last_alert_at


async def _save_last_alert_at(redis: Any, at: datetime) -> None:
    global _mem_last_alert_at
    _mem_last_alert_at = at
    if redis is None:
        return
    try:
        await redis.set(
            f"{_REDIS_PREFIX}last_alert_at",
            at.astimezone(UTC).isoformat(),
        )
    except Exception:
        logger.debug("infra_health: redis write failed; memory fallback", exc_info=True)


async def _probe_render_health() -> tuple[bool, list[str]]:
    """Probe Render API for service health. Returns (healthy, issues)."""
    import httpx

    from app.config import settings

    api_key = (settings.RENDER_API_KEY or "").strip()
    if not api_key:
        return True, []

    issues: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://api.render.com/v1/services",
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            )
        if r.status_code == 200:
            services = r.json()
            for svc in services if isinstance(services, list) else []:
                item = svc.get("service") or svc
                name = item.get("name", "?")
                status = item.get("suspended", "not_suspended")
                if status != "not_suspended":
                    issues.append(f"Render service {name!r} is suspended")
        elif r.status_code >= 400:
            issues.append(f"Render API returned {r.status_code}")
    except Exception as exc:
        issues.append(f"Render API probe failed: {exc}")

    return len(issues) == 0, issues


async def _run_infra_health_body() -> None:
    now = datetime.now(UTC)
    redis = await _get_redis_or_none()

    healthy, issues = await _probe_render_health()

    if healthy:
        raise SchedulerRunSkipped()

    last_alert_at = await _load_last_alert_at(redis)
    reminder_delta = timedelta(hours=_DEFAULT_REMINDER_HOURS)
    if last_alert_at is not None and (now - last_alert_at) < reminder_delta:
        raise SchedulerRunSkipped()

    body = "**Infra Health Check — Issues Detected**\n\n"
    body += "\n".join(f"- {issue}" for issue in issues)
    body += "\n\nCheck Render dashboard and `/admin/health` for details."

    create_conversation(
        ConversationCreate(
            title="Infra Health Alert",
            body_md=body,
            tags=["alert"],
            urgency="high",
            persona="ea",
            needs_founder_action=True,
        )
    )
    await _save_last_alert_at(redis, now)


async def run_infra_health() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_infra_health_body,
        metadata={"source": "brain_infra_health", "cutover": "T1_interval"},
        reraise=True,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register 30m Infra Health (ex-Infra Health Check / n8n)."""
    scheduler.add_job(
        run_infra_health,
        trigger=IntervalTrigger(minutes=30),
        id=JOB_ID,
        name="Infra Health Check (Brain, ex-Infra Health Check / n8n, IntervalTrigger)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job %r registered (30m interval, IntervalTrigger)", JOB_ID)
