"""IaC drift detector cadence.

medallion: ops
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.interval import IntervalTrigger

from app.schedulers._history import run_with_scheduler_record
from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.services.iac_drift import run_drift_check

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "iac_drift_detector"


async def _run_body() -> None:
    run_drift_check()


@skip_if_brain_paused(JOB_ID)
async def run_iac_drift_job() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_body,
        metadata={"source": "iac_drift_detector", "cadence": "30 minutes"},
        reraise=False,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_iac_drift_job,
        trigger=IntervalTrigger(minutes=30),
        id=JOB_ID,
        name="IaC drift detector",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=120,
    )
    logger.info("APScheduler job %r registered (every 30 minutes UTC)", JOB_ID)
