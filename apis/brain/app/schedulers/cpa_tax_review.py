"""Scheduled CPA tax review (WS-19, weekly Thursday 13:00 UTC).

Runs Brain with persona_pin=cpa on a weekly cadence.
Output is stored in the Brain Conversations stream (WS-69 PR J).

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

_JOB_ID = "cpa_tax_review"
_ORG_ID = "paperwork-labs"
_ORG_NAME = "Paperwork Labs"
_DEFAULT_MESSAGE = "Run CPA tax review on latest filings and flag any Circular 230 issues."


async def _run_body() -> None:
    request_id = f"cpa-tax-review:brain:{datetime.now(UTC).isoformat()}"
    redis_client = None
    with contextlib.suppress(RuntimeError):
        redis_client = get_redis()
    async with async_session_factory() as db:
        await brain_agent.process(
            db,
            redis_client,
            organization_id=_ORG_ID,
            org_name=_ORG_NAME,
            user_id="brain-scheduler:cpa-tax-review",
            message=_DEFAULT_MESSAGE,
            channel="conversations",
            request_id=request_id,
            persona_pin="cpa",
        )
        await db.commit()
    logger.info("cpa_tax_review: Brain process completed (request_id=%s)", request_id)


async def run_cpa_tax_review() -> None:
    await run_with_scheduler_record(
        _JOB_ID,
        _run_body,
        metadata={"source": "cpa_tax_review", "cutover": "WS-19"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_cpa_tax_review,
        trigger=CronTrigger(day_of_week="thu", hour=13, minute=0, timezone="UTC"),
        id=_JOB_ID,
        name="CPA tax review (Brain, weekly Thursday)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job %r registered (Thursday 13:00 UTC)", _JOB_ID)
