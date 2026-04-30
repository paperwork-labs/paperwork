"""Brain Weekly Trigger cutover (T1.5 — Brain Weekly): weekly plan summary via APScheduler.

Replaces the **Brain Weekly Trigger** n8n workflow (``0 18 * * 0``) that POSTs
``/api/v1/brain/process`` and forwarded the reply to Slack — see
``infra/hetzner/workflows/retired/brain-weekly-trigger.json`` and
``docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md``.

WS-69 PR J: Slack post removed; output lands in the Brain Conversations stream.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.database import async_session_factory
from app.redis import get_redis
from app.schedulers._history import run_with_scheduler_record
from app.schemas.conversation import ConversationCreate
from app.services import agent as brain_agent
from app.services.conversations import create_conversation

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "brain_weekly_briefing"
_ORG_ID = "paperwork-labs"
_ORG_NAME = "Paperwork Labs"
_WEEKLY_MESSAGE = "Generate weekly plan summary for Paperwork Labs."


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
            channel="conversations",
            request_id=request_id,
        )
        await db.commit()
    out = (str(result.get("response", "") or "")).strip() or "Brain returned no response."
    date_str = datetime.now(UTC).date().isoformat()
    create_conversation(
        ConversationCreate(
            title=f"Weekly Plan Summary — {date_str}",
            body_md=out,
            tags=["weekly-plan"],
            urgency="info",
            persona="ea",
            needs_founder_action=False,
        )
    )


async def run_weekly_briefing() -> None:
    """APScheduler entry: Brain process + Conversations create."""
    await run_with_scheduler_record(
        _JOB_ID,
        _run_weekly_body,
        metadata={"source": "brain_weekly_briefing", "cutover": "T1.5-brain-weekly"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the weekly briefing cron (ex-Brain Weekly Trigger / n8n)."""
    scheduler.add_job(
        run_weekly_briefing,
        trigger=CronTrigger.from_crontab("0 18 * * 0", timezone=UTC),
        id=_JOB_ID,
        name="Weekly plan summary (Brain, ex-Brain Weekly Trigger / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job %r registered (18:00 UTC Sunday, matches n8n expression)", _JOB_ID)
