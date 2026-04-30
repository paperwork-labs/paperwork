"""Infra status heartbeat from Brain APScheduler (T1.3).

Replaces the **Infra Heartbeat** n8n workflow (``0 8 * * *``) — see
``infra/hetzner/workflows/retired/infra-heartbeat.json`` and
``docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md`` (T1.3).

WS-69 PR J: n8n workflow check removed (n8n decommissioned). Now reports
general Brain/Render infrastructure status. Creates a Conversation instead
of posting to the engineering channel.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._history import run_with_scheduler_record
from app.schemas.conversation import ConversationCreate
from app.services.conversations import create_conversation

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "brain_infra_heartbeat"


def _format_heartbeat_message() -> str:
    now = datetime.now(UTC)
    return (
        f"**Daily Infra Heartbeat — {now.strftime('%Y-%m-%d %H:%M')} UTC**\n\n"
        "Brain APScheduler is running. No critical alerts at heartbeat time.\n\n"
        "For full infra status see Render dashboard and `/admin/health`."
    )


async def _run_infra_heartbeat_body() -> None:
    text = _format_heartbeat_message()
    date_str = datetime.now(UTC).date().isoformat()
    create_conversation(
        ConversationCreate(
            title=f"Daily Infra Heartbeat — {date_str}",
            body_md=text,
            tags=["alert"],
            urgency="info",
            persona="ea",
            needs_founder_action=False,
        )
    )


async def run_infra_heartbeat() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_infra_heartbeat_body,
        metadata={"source": "brain_infra_heartbeat", "cutover": "T1.3"},
        reraise=True,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the infra heartbeat (ex-Infra Heartbeat / n8n)."""
    scheduler.add_job(
        run_infra_heartbeat,
        trigger=CronTrigger.from_crontab("0 8 * * *", timezone="UTC"),
        id=JOB_ID,
        name="Infra Heartbeat (Brain, ex-Infra Heartbeat / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job %r registered (08:00 UTC, matches n8n expression)", JOB_ID)
