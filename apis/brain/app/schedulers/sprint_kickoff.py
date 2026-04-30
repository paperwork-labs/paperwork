"""Brain-owned Sprint Kickoff (Track K / n8n cron cutover).

Replaces the **Sprint Kickoff** n8n workflow (``0 7 * * 1``) — see
``infra/hetzner/workflows/retired/sprint-kickoff.json`` and
``docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md`` (Track K).

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

_JOB_ID = "brain_sprint_kickoff"
_ORG_ID = "paperwork-labs"
_ORG_NAME = "Paperwork Labs"
_SPRINT_MESSAGE = (
    "It's Monday. Generate a 5-day sprint kickoff for Paperwork Labs using the docs hub "
    "(TASKS.md, KNOWLEDGE.md, VENTURE_MASTER_PLAN.md) and recent commits. Return "
    "markdown with sections: Sprint Goals, Engineering Plan, Risk Assessment, Strategic "
    "Priority, Top 3 Priorities. Keep it concise and actionable."
)


async def _run_sprint_kickoff_body() -> None:
    request_id = f"sprint-kickoff:brain:{datetime.now(UTC).isoformat()}"
    redis_client = None
    with contextlib.suppress(RuntimeError):
        redis_client = get_redis()
    async with async_session_factory() as db:
        result = await brain_agent.process(
            db,
            redis_client,
            organization_id=_ORG_ID,
            org_name=_ORG_NAME,
            user_id="brain-scheduler:sprint-kickoff",
            message=_SPRINT_MESSAGE,
            channel="conversations",
            request_id=request_id,
            persona_pin="strategy",
        )
        await db.commit()
    response_text = str(result.get("response", "") or "")
    date_iso = datetime.now(UTC).date().isoformat()
    create_conversation(
        ConversationCreate(
            title=f"Sprint Kickoff — {date_iso}",
            body_md=response_text[:8000] or "Brain returned no kickoff.",
            tags=["sprint-planning"],
            urgency="normal",
            persona="strategy",
            needs_founder_action=False,
        )
    )


async def run_sprint_kickoff() -> None:
    await run_with_scheduler_record(
        _JOB_ID,
        _run_sprint_kickoff_body,
        metadata={"source": "brain_sprint_kickoff", "cutover": "T_K"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the sprint kickoff cron (ex-Sprint Kickoff / n8n)."""
    scheduler.add_job(
        run_sprint_kickoff,
        trigger=CronTrigger.from_crontab("0 7 * * 1", timezone=UTC),
        id=_JOB_ID,
        name="Sprint Kickoff (Brain, ex-Sprint Kickoff / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info(
        "APScheduler job %r registered (07:00 UTC Mondays, matches n8n expression)", _JOB_ID
    )
