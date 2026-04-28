"""Scheduled cheap-agent sprint generation (1-day buckets, LA timezone).

Runs a few times per day, persists sprints for Studio review, and stores a
memory episode (``source=agent_sprint:generated``) for continuous learning.

Does **not** auto-dispatch agents — founder reviews tasks first.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import async_session_factory
from app.schemas.agent_tasks import AgentSprintRecord
from app.services.agent_sprint_store import append_sprint, in_flight_task_ids, new_sprint_id
from app.services.agent_task_generator import generate
from app.services.memory import store_episode
from app.services.sprint_planner import parallelizability_score, select_sprint_bucket

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_LA = ZoneInfo("America/Los_Angeles")


async def run_agent_sprint_tick(*, reason: str = "schedule") -> dict[str, Any]:
    """One planning cycle: generate → filter in-flight → bucket → persist → episode."""
    all_tasks = await generate()
    inflight = in_flight_task_ids()
    fresh = [t for t in all_tasks if t.task_id not in inflight]
    max_tasks = max(1, int(getattr(settings, "BRAIN_AGENT_SPRINT_MAX_TASKS", 8) or 8))
    day_cap = max(30, int(getattr(settings, "BRAIN_AGENT_SPRINT_DAY_CAP_MINUTES", 480) or 480))

    bucket = select_sprint_bucket(fresh, max_tasks=max_tasks, day_cap_minutes=day_cap)
    if not bucket:
        logger.info("agent_sprint_tick: no tasks to schedule (reason=%s)", reason)
        return {"ok": True, "skipped": True, "reason": "no_tasks", "candidates": len(fresh)}

    total_minutes = sum(t.estimated_minutes for t in bucket)
    score = parallelizability_score(bucket)
    sid = new_sprint_id()
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    record = AgentSprintRecord(
        sprint_id=sid,
        generated_at=now,
        timezone=str(_LA),
        tasks=bucket,
        total_minutes=total_minutes,
        parallelizability_score=score,
        status="pending_review",
    )
    append_sprint(record)

    summary = (
        f"Generated cheap-agent sprint {sid[:8]} with {len(bucket)} tasks "
        f"({total_minutes} min est., parallelizability={score})."
    )
    try:
        async with async_session_factory() as db:
            await store_episode(
                db,
                organization_id="paperwork-labs",
                source="agent_sprint:generated",
                summary=summary,
                full_context=json.dumps(
                    {
                        "sprint_id": sid,
                        "reason": reason,
                        "task_ids": [t.task_id for t in bucket],
                        "titles": [t.title for t in bucket],
                    },
                    indent=2,
                )[:8000],
                source_ref=f"agent_sprint:{sid}",
                importance=0.45,
                skip_embedding=True,
                metadata={"sprint_id": sid, "task_count": len(bucket), "reason": reason},
            )
            await db.commit()
    except Exception:
        logger.exception("agent_sprint_tick: memory episode failed (sprint still persisted)")
    logger.info(
        "agent_sprint_tick: sprint %s tasks=%d minutes=%d (reason=%s)",
        sid,
        len(bucket),
        total_minutes,
        reason,
    )
    return {
        "ok": True,
        "skipped": False,
        "sprint_id": sid,
        "task_count": len(bucket),
        "total_minutes": total_minutes,
        "parallelizability_score": score,
    }


async def _run_agent_sprint_job() -> None:
    try:
        await run_agent_sprint_tick(reason="apscheduler")
    except Exception:
        logger.exception("agent_sprint_scheduler job raised — will retry next tick")


def install(scheduler: AsyncIOScheduler) -> None:
    """Every 4 hours on America/Los_Angeles wall clock (6 ticks/day)."""
    if not getattr(settings, "BRAIN_OWNS_AGENT_SPRINT_SCHEDULER", False):
        logger.info(
            "BRAIN_OWNS_AGENT_SPRINT_SCHEDULER=false — agent sprint scheduler not installed"
        )
        return
    scheduler.add_job(
        _run_agent_sprint_job,
        trigger=CronTrigger(hour="*/4", minute=0, timezone=_LA),
        id="brain_agent_sprint_planner",
        name="Brain cheap-agent sprint planner (1-day buckets)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("brain_agent_sprint_planner installed: Cron */4 hour America/Los_Angeles")
