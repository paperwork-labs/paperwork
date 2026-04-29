"""Daily 09:00 UTC cron — flush Brain's deferred Slack morning queue.

Sends all notifications that were held back by quiet-hours or rate-limit
as a single digest per channel, then clears the queue.

medallion: ops
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.services import slack_router

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "brain_slack_morning_digest"


async def run_morning_digest() -> None:
    result = await slack_router.flush_morning_digest()
    logger.info(
        "slack_morning_digest: flushed — sent=%d skipped=%d",
        result.get("sent", 0),
        result.get("skipped", 0),
    )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_morning_digest,
        trigger=CronTrigger(hour=9, minute=0, timezone="UTC"),
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    logger.info("slack_morning_digest: job registered (09:00 UTC daily)")
