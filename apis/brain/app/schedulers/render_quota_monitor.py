"""Render quota monitor cron (every 6h UTC).

medallion: ops
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._history import run_with_scheduler_record
from app.services.render_quota_monitor import run_render_quota_monitor_tick

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "render_quota_monitor"


async def _run_body() -> None:
    await run_render_quota_monitor_tick()


async def run_render_quota_monitor_job() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_body,
        metadata={
            "source": "render_quota_monitor",
            "cadence": "0 */6 * * * UTC",
        },
        reraise=False,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_render_quota_monitor_job,
        trigger=CronTrigger(hour="*/6", minute=0, timezone="UTC"),
        id=JOB_ID,
        name="Render quota monitor",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("APScheduler job %r registered (CronTrigger */6 hour UTC)", JOB_ID)
