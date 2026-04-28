"""Scheduled QA security audit — ex-``qa-security-scan.json`` (WS-19).

The n8n export was webhook-only: it forwarded a body to Brain
``/api/v1/brain/process`` with ``persona_pin=qa`` and let Brain post to ``#qa``.
This job runs the same Brain invocation on a weekly cadence (Monday 14:00 UTC).

medallion: ops
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
from app.services import agent as brain_agent

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "qa_security_scan"
_ORG_ID = "paperwork-labs"
_ORG_NAME = "Paperwork Labs"
_QA_CHANNEL_ID = "C0ALLEKR9FZ"
_DEFAULT_MESSAGE = (
    "Run a security audit on the latest changes. Return critical_issues, high_issues, "
    "medium_issues, test_cases, and pre-merge checklist."
)


async def _run_body() -> None:
    request_id = f"qa-security-scan:brain:{datetime.now(UTC).isoformat()}"
    redis_client = None
    with contextlib.suppress(RuntimeError):
        redis_client = get_redis()
    async with async_session_factory() as db:
        await brain_agent.process(
            db,
            redis_client,
            organization_id=_ORG_ID,
            org_name=_ORG_NAME,
            user_id="brain-scheduler:qa-security-scan",
            message=_DEFAULT_MESSAGE,
            channel="n8n",
            request_id=request_id,
            persona_pin="qa",
            slack_channel_id=_QA_CHANNEL_ID,
            slack_username="QA",
            slack_icon_emoji=":detective:",
        )
        await db.commit()
    logger.info("qa_security_scan: Brain process completed (request_id=%s)", request_id)


async def run_qa_security_scan() -> None:
    await run_with_scheduler_record(
        _JOB_ID,
        _run_body,
        metadata={"source": "qa_security_scan", "cutover": "WS-19"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_qa_security_scan,
        trigger=CronTrigger(day_of_week="mon", hour=14, minute=0, timezone="UTC"),
        id=_JOB_ID,
        name="QA security scan (Brain, ex-qa-security-scan / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("APScheduler job %r registered (Monday 14:00 UTC)", _JOB_ID)
