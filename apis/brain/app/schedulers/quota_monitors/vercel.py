"""Poll Vercel team deployment volume + build minutes; snapshot + quota alarms.

medallion: ops
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._history import run_with_scheduler_record
from app.services.vercel_quota_monitor import run_vercel_quota_monitor_tick

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "vercel_quota_monitor"


async def _run_body() -> None:
    await run_vercel_quota_monitor_tick()


async def run_vercel_quota_monitor() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_body,
        metadata={"source": "vercel_quota_monitor"},
        reraise=False,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_vercel_quota_monitor,
        trigger=CronTrigger(hour="*/6", minute=0, timezone="UTC"),
        id=JOB_ID,
        name="Vercel quota monitor",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("APScheduler job %r registered (CronTrigger */6 hour UTC)", JOB_ID)
