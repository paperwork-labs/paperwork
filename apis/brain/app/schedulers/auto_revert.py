"""APScheduler entry point for Brain post-merge auto-revert checks.

medallion: ops
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC
from typing import TYPE_CHECKING

from apscheduler.triggers.interval import IntervalTrigger

from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.services.auto_revert import run_auto_revert_check

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "brain_auto_revert"


@skip_if_brain_paused(JOB_ID)
async def run_auto_revert_job() -> None:
    incidents = await asyncio.to_thread(run_auto_revert_check)
    if incidents:
        logger.warning(
            "auto_revert: recorded %d incident(s): reverted_prs=%s",
            len(incidents),
            [i.pr_number_reverted for i in incidents],
        )
    else:
        logger.info("auto_revert: no post-merge main CI failures detected")


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_auto_revert_job,
        trigger=IntervalTrigger(minutes=5, timezone=UTC),
        id=JOB_ID,
        name="Brain auto-revert on post-merge main CI failure",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job %r registered (every 5 minutes UTC)", JOB_ID)
