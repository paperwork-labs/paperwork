"""Brain-owned weekly strategy check-in (T1.6 / STREAMLINE T1 cutover).

Replaces the **Weekly Strategy Check-in** n8n workflow (``0 9 * * 1``) that
called OpenAI in n8n and posted to ``#all-paperwork-labs`` — see
``infra/hetzner/workflows/retired/weekly-strategy-checkin.json`` and
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

_JOB_ID = "brain_weekly_strategy"
_ORG_ID = "paperwork-labs"
_ORG_NAME = "Paperwork Labs"
_WEEKLY_MESSAGE = (
    "Generate the weekly strategy check-in for this Monday. Consider the current date "
    "and where we should be in the sprint timeline across all Paperwork Labs products.\n\n"
    "Cover: progress vs the sprint plan across products, top risks, priorities for the "
    "coming week, 1-2 short actions for the partnerships co-founder, and any strategic "
    "decisions needed."
)


async def _run_weekly_strategy_body() -> None:
    request_id = f"weekly-strategy:brain:{datetime.now(UTC).isoformat()}"
    redis_client = None
    with contextlib.suppress(RuntimeError):
        redis_client = get_redis()
    async with async_session_factory() as db:
        result = await brain_agent.process(
            db,
            redis_client,
            organization_id=_ORG_ID,
            org_name=_ORG_NAME,
            user_id="brain-scheduler:weekly-strategy",
            message=_WEEKLY_MESSAGE,
            channel="conversations",
            request_id=request_id,
            persona_pin="strategy",
        )
        await db.commit()
    out = (str(result.get("response", "") or "")).strip() or "Brain returned no response."
    date_str = datetime.now(UTC).date().isoformat()
    create_conversation(
        ConversationCreate(
            title=f"Weekly Strategy Check-in — {date_str}",
            body_md=out,
            tags=["sprint-planning"],
            urgency="normal",
            persona="strategy",
            needs_founder_action=False,
        )
    )


async def run_weekly_strategy() -> None:
    """APScheduler entry: strategy persona + Conversations create."""
    await run_with_scheduler_record(
        _JOB_ID,
        _run_weekly_strategy_body,
        metadata={"source": "brain_weekly_strategy", "cutover": "T1.6"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the weekly strategy cron (ex-Weekly Strategy Check-in / n8n)."""
    scheduler.add_job(
        run_weekly_strategy,
        trigger=CronTrigger.from_crontab("0 9 * * 1", timezone=UTC),
        id=_JOB_ID,
        name="Weekly Strategy Check-in (Brain, ex-Weekly Strategy Check-in / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info(
        "APScheduler job %r registered (09:00 UTC Mondays, matches n8n expression)", _JOB_ID
    )
