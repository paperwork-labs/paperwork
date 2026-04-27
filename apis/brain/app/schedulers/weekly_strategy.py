"""Brain-owned weekly strategy check-in (T1.6 / STREAMLINE T1 cutover).

Replaces the **Weekly Strategy Check-in** n8n workflow (``0 9 * * 1``) that
called OpenAI in n8n and posted to ``#all-paperwork-labs`` — see
``infra/hetzner/workflows/retired/weekly-strategy-checkin.json`` and
``docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md``.

Cutover path uses :func:`app.services.agent.process` with ``persona_pin="strategy"``
(``app/personas/specs/strategy.yaml``) per Streamline T2 unified persona vocabulary,
not a standalone OpenAI node in n8n.
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

_JOB_ID = "brain_weekly_strategy"
# Same as ``weekly-strategy-checkin.json`` (``#all-paperwork-labs``).
_WEEKLY_STRATEGY_CHANNEL_ID = "C0AMEQV199P"
_ORG_ID = "paperwork-labs"
_ORG_NAME = "Paperwork Labs"
# Matches n8n user prompt + thread-router footnote from the Format node.
_WEEKLY_MESSAGE = (
    "Generate the weekly strategy check-in for this Monday. Consider the current date "
    "and where we should be in the sprint timeline across all Paperwork Labs products.\n\n"
    "Cover: progress vs the sprint plan across products, top risks, priorities for the "
    "coming week, 1-2 short actions for the partnerships co-founder, and any strategic "
    "decisions needed. Format for Slack with clear sections.\n\n"
    "_Thread router: reply with a persona name for a focused take._"
)


def _owns_weekly_strategy() -> bool:
    return os.getenv("BRAIN_OWNS_WEEKLY_STRATEGY", "false").lower() in (
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


async def _run_weekly_strategy_body() -> None:
    request_id = f"weekly-strategy:brain:{datetime.now(timezone.utc).isoformat()}"
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
            user_id="brain-scheduler:weekly-strategy",
            message=_WEEKLY_MESSAGE,
            channel="slack",
            channel_id=_WEEKLY_STRATEGY_CHANNEL_ID,
            request_id=request_id,
            persona_pin="strategy",
        )
        await db.commit()
    out = _format_slack_body(str(result.get("response", "") or ""))
    date = datetime.now(timezone.utc).date().isoformat()
    text = f"*Weekly Strategy Check-in — {date}*\n\n{out}"
    await slack_outbound.post_message(
        channel_id=_WEEKLY_STRATEGY_CHANNEL_ID,
        text=text,
        username="Strategy",
        icon_emoji=":brain:",
    )


async def run_weekly_strategy() -> None:
    """APScheduler entry: Brain process (strategy persona) + ``#all-paperwork-labs`` post."""
    await run_with_scheduler_record(
        _JOB_ID,
        _run_weekly_strategy_body,
        metadata={"source": "brain_weekly_strategy", "cutover": "T1.6"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the weekly strategy cron when :envvar:`BRAIN_OWNS_WEEKLY_STRATEGY` is true."""
    if not _owns_weekly_strategy():
        logger.info("BRAIN_OWNS_WEEKLY_STRATEGY is not true — skipping brain_weekly_strategy job")
        return
    scheduler.add_job(
        run_weekly_strategy,
        trigger=CronTrigger.from_crontab("0 9 * * 1", timezone=timezone.utc),
        id=_JOB_ID,
        name="Weekly Strategy Check-in (Brain, ex–Weekly Strategy Check-in / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("APScheduler job %r registered (09:00 UTC Mondays, matches n8n expression)", _JOB_ID)
