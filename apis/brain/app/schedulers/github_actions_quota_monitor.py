"""GitHub Actions quota + cache snapshot cron (billing API mirror of Vercel quota).

Runs daily at **06:00 UTC** (`0 6 * * *`), ``max_instances=1``, ``coalesce=true``.

medallion: ops
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._history import run_with_scheduler_record
from app.services.github_actions_quota_monitor import run_github_actions_quota_monitor_tick

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "github_actions_quota_monitor"


async def _run_body() -> None:
    await run_github_actions_quota_monitor_tick()


async def run_github_actions_quota_monitor() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_body,
        metadata={
            "source": "brain_github_actions_quota_monitor",
            "cadence": "0 6 * * * UTC",
        },
        reraise=False,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register Actions billing/cache snapshot job (paired with Studio admin quota API)."""
    scheduler.add_job(
        run_github_actions_quota_monitor,
        trigger=CronTrigger.from_crontab("0 6 * * *", timezone="UTC"),
        id=JOB_ID,
        name="GitHub Actions quota monitor (billing + cache)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job %r registered (06:00 UTC daily)", JOB_ID)
