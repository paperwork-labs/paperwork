"""Brain Weekly Trigger cutover (T1.5 — Brain Weekly): weekly plan summary via APScheduler.

Replaces the **Brain Weekly Trigger** n8n workflow (``0 18 * * 0``) that POSTs
``/api/v1/brain/process`` and forwards the reply to Slack — see
``infra/hetzner/workflows/retired/brain-weekly-trigger.json`` and
``docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md``.
"""

from __future__ import annotations

import contextlib
import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.database import async_session_factory
from app.redis import get_redis
from app.schedulers._history import run_with_scheduler_record
from app.services import agent as brain_agent
from app.services import slack_outbound

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "brain_weekly_briefing"
# Same as ``brain-weekly-trigger.json`` (``#all-paperwork-labs``).
_WEEKLY_CHANNEL_ID = "C0AMEQV199P"
_ORG_ID = "paperwork-labs"
_ORG_NAME = "Paperwork Labs"
# Mirrors n8n request body: ``Generate weekly plan summary for #all-paperwork-labs``.
_WEEKLY_MESSAGE = "Generate weekly plan summary for #all-paperwork-labs"


def _owns_weekly_briefing() -> bool:
    return os.getenv("BRAIN_OWNS_BRAIN_WEEKLY", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _format_slack_body(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        text = "Brain returned no response."
    if len(text) > 3900:
        return text[:3900] + "\n\n_(truncated)_"
    return text


async def _run_weekly_body() -> None:
    request_id = f"weekly-briefing:brain:{datetime.now(UTC).isoformat()}"
    redis_client = None
    with contextlib.suppress(RuntimeError):
        redis_client = get_redis()
    async with async_session_factory() as db:
        result = await brain_agent.process(
            db,
            redis_client,
            organization_id=_ORG_ID,
            org_name=_ORG_NAME,
            user_id="brain-scheduler:weekly-briefing",
            message=_WEEKLY_MESSAGE,
            channel="slack",
            channel_id=_WEEKLY_CHANNEL_ID,
            request_id=request_id,
        )
        await db.commit()
    out = _format_slack_body(str(result.get("response", "") or ""))
    await slack_outbound.post_message(
        channel_id=_WEEKLY_CHANNEL_ID,
        text=out,
        username="EA / Operator",
        icon_emoji=":brain:",
    )


async def run_weekly_briefing() -> None:
    """APScheduler entry: Brain process + real weekly channel post."""
    await run_with_scheduler_record(
        _JOB_ID,
        _run_weekly_body,
        metadata={"source": "brain_weekly_briefing", "cutover": "T1.5-brain-weekly"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the weekly briefing cron when :envvar:`BRAIN_OWNS_BRAIN_WEEKLY` is true."""
    if not _owns_weekly_briefing():
        logger.info("BRAIN_OWNS_BRAIN_WEEKLY is not true — skipping brain_weekly_briefing job")
        return
    scheduler.add_job(
        run_weekly_briefing,
        trigger=CronTrigger.from_crontab("0 18 * * 0", timezone=UTC),
        id=_JOB_ID,
        name="Weekly plan summary (Brain, ex-Brain Weekly Trigger / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("APScheduler job %r registered (18:00 UTC Sunday, matches n8n expression)", _JOB_ID)
