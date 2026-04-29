"""Weekly sprint velocity job — Sundays 23:50 UTC.

Runs just before the POS scheduler (Monday 09:00 UTC) so velocity data is
fresh when the Operating Score computes.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.services import sprint_velocity as sprint_velocity_service

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "sprint_velocity_weekly"


@skip_if_brain_paused(_JOB_ID)
async def _run_sprint_velocity() -> None:
    try:
        entry = await asyncio.to_thread(sprint_velocity_service.record_weekly_velocity)
        logger.info(
            "sprint_velocity_weekly recorded prs_merged=%d measured=%s week=%s-%s",
            entry.prs_merged,
            entry.measured,
            entry.week_start,
            entry.week_end,
        )
    except Exception:
        logger.exception("sprint_velocity_weekly raised — will retry next schedule")


def install(scheduler: AsyncIOScheduler) -> None:
    """Register Sundays 23:50 UTC cron for sprint velocity computation."""
    scheduler.add_job(
        _run_sprint_velocity,
        trigger=CronTrigger(day_of_week="sun", hour=23, minute=50, timezone="UTC"),
        id=_JOB_ID,
        name="Sprint Velocity (weekly)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=600,
    )
    logger.info("sprint_velocity_weekly scheduled (Sunday 23:50 UTC)")
