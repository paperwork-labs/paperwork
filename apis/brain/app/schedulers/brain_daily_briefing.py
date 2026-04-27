"""First production cutover: daily briefing from Brain APScheduler (T1.2).

Replaces the **Brain Daily Trigger** n8n workflow (``0 7 * * *``) that POSTs
``/api/v1/brain/process`` and forwards the reply to ``#daily-briefing`` — see
``infra/hetzner/workflows/retired/brain-daily-trigger.json`` and
``docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md`` (T1.2).
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

_JOB_ID = "brain_daily_briefing"
# Same as ``brain-daily-trigger.json`` (``#daily-briefing``).
_DAILY_BRIEFING_CHANNEL_ID = "C0ALLJWR1HV"
_ORG_ID = "paperwork-labs"
_ORG_NAME = "Paperwork Labs"
# Mirrors n8n request body: ``Generate daily briefing for #daily-briefing``.
_DAILY_MESSAGE = "Generate daily briefing for #daily-briefing"


def _owns_daily_briefing() -> bool:
    return os.getenv("BRAIN_OWNS_DAILY_BRIEFING", "false").lower() in (
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


async def _run_briefing_body() -> None:
    request_id = f"daily-briefing:brain:{datetime.now(timezone.utc).isoformat()}"
    redis_client = None
    try:
        redis_client = get_redis()
    except RuntimeError:
        pass
    async with async_session_factory() as db:
        result = await brain_agent.process(
            db,
            redis_client,
            organization_id=_ORG_ID,
            org_name=_ORG_NAME,
            user_id="brain-scheduler:daily-briefing",
            message=_DAILY_MESSAGE,
            channel="slack",
            channel_id=_DAILY_BRIEFING_CHANNEL_ID,
            request_id=request_id,
        )
        await db.commit()
    out = _format_slack_body(str(result.get("response", "") or ""))
    await slack_outbound.post_message(
        channel_id=_DAILY_BRIEFING_CHANNEL_ID,
        text=out,
        username="EA / Operator",
        icon_emoji=":brain:",
    )


async def run_daily_briefing() -> None:
    """APScheduler entry: Brain process + real ``#daily-briefing`` post."""
    await run_with_scheduler_record(
        _JOB_ID,
        _run_briefing_body,
        metadata={"source": "brain_daily_briefing", "cutover": "T1.2"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the daily-briefing cron when :envvar:`BRAIN_OWNS_DAILY_BRIEFING` is true."""
    if not _owns_daily_briefing():
        logger.info("BRAIN_OWNS_DAILY_BRIEFING is not true — skipping brain_daily_briefing job")
        return
    scheduler.add_job(
        run_daily_briefing,
        trigger=CronTrigger.from_crontab("0 7 * * *", timezone=timezone.utc),
        id=_JOB_ID,
        name="Daily briefing (Brain, ex–Brain Daily Trigger / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("APScheduler job %r registered (07:00 UTC, matches n8n expression)", _JOB_ID)
