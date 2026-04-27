"""Brain-owned Sprint Kickoff (Track K / n8n cron cutover).

Replaces the **Sprint Kickoff** n8n workflow (``0 7 * * 1``) that POSTs
``/api/v1/brain/process`` to ``#sprints`` and announces in ``#all-paperwork-labs``
— see ``infra/hetzner/workflows/sprint-kickoff.json`` and
``docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md`` (Track K).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import async_session_factory
from app.redis import get_redis
from app.schedulers._history import run_with_scheduler_record
from app.services import agent as brain_agent
from app.services import slack_outbound

logger = logging.getLogger(__name__)

_JOB_ID = "brain_sprint_kickoff"
# Same as ``sprint-kickoff.json`` (``#sprints``).
_SPRINTS_CHANNEL_ID = "C0AM3APFP99"
# Announcement: ``#all-paperwork-labs`` (n8n second node).
_ALL_PAPERWORK_LABS_CHANNEL_ID = "C0AMEQV199P"
_ORG_ID = "paperwork-labs"
_ORG_NAME = "Paperwork Labs"
_SPRINT_MESSAGE = (
    "It's Monday. Generate a 5-day sprint kickoff for Paperwork Labs using the docs hub "
    "(TASKS.md, KNOWLEDGE.md, VENTURE_MASTER_PLAN.md) and recent commits. Return Slack-ready "
    "markdown with sections: Sprint Goals, Engineering Plan, Risk Assessment, Strategic "
    "Priority, Top 3 Priorities. Keep it concise and actionable."
)
_ANNOUNCEMENT_TEXT = (
    ":rocket: New 5-day sprint kickoff just landed in <#C0AM3APFP99|sprints>. "
    "Reply in-thread with a persona name for a focused take."
)


def _owns_sprint_kickoff() -> bool:
    return os.getenv("BRAIN_OWNS_SPRINT_KICKOFF", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


async def _run_sprint_kickoff_body() -> None:
    request_id = f"sprint-kickoff:brain:{datetime.now(timezone.utc).isoformat()}"
    redis_client = None
    try:
        redis_client = get_redis()
    except RuntimeError:
        pass
    async with async_session_factory() as db:
        await brain_agent.process(
            db,
            redis_client,
            organization_id=_ORG_ID,
            org_name=_ORG_NAME,
            user_id="brain-scheduler:sprint-kickoff",
            message=_SPRINT_MESSAGE,
            channel="slack",
            channel_id=_SPRINTS_CHANNEL_ID,
            request_id=request_id,
            persona_pin="strategy",
            slack_username="Sprint Planning",
            slack_icon_emoji=":rocket:",
        )
        await db.commit()
    try:
        await slack_outbound.post_message(
            channel_id=_ALL_PAPERWORK_LABS_CHANNEL_ID,
            text=_ANNOUNCEMENT_TEXT,
            username="Sprint Planning",
            icon_emoji=":rocket:",
        )
    except Exception:
        logger.exception("Sprint kickoff announcement post to #all-paperwork-labs failed")


async def run_sprint_kickoff() -> None:
    """APScheduler entry: strategy persona to ``#sprints`` + ``#all-paperwork-labs`` announcement."""
    await run_with_scheduler_record(
        _JOB_ID,
        _run_sprint_kickoff_body,
        metadata={"source": "brain_sprint_kickoff", "cutover": "T_K"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the sprint kickoff cron when :envvar:`BRAIN_OWNS_SPRINT_KICKOFF` is true."""
    if not _owns_sprint_kickoff():
        logger.info("BRAIN_OWNS_SPRINT_KICKOFF is not true — skipping brain_sprint_kickoff job")
        return
    scheduler.add_job(
        run_sprint_kickoff,
        trigger=CronTrigger.from_crontab("0 7 * * 1", timezone=timezone.utc),
        id=_JOB_ID,
        name="Sprint Kickoff (Brain, ex–Sprint Kickoff / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("APScheduler job %r registered (07:00 UTC Mondays, matches n8n expression)", _JOB_ID)
