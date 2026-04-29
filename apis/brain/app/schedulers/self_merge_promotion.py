"""Daily Brain self-merge graduation check.

medallion: ops
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._history import run_with_scheduler_record
from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.services.self_merge_gate import eligible_for_promotion, promote

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "self_merge_promotion"


async def _run_body() -> None:
    if not eligible_for_promotion():
        logger.info("self_merge_promotion: not eligible for promotion")
        return
    record = promote()
    if record is None:
        logger.info("self_merge_promotion: eligibility changed before promotion")
        return
    logger.info("Brain promoted from %s to %s", record.from_tier, record.to_tier)


@skip_if_brain_paused(JOB_ID)
async def run_self_merge_promotion_job() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_body,
        metadata={"source": "self_merge_promotion", "cadence": "daily"},
        reraise=False,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_self_merge_promotion_job,
        trigger=CronTrigger(hour=4, minute=15, timezone="UTC"),
        id=JOB_ID,
        name="Brain self-merge promotion gate",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=120,
    )
    logger.info("APScheduler job %r registered (04:15 UTC daily)", JOB_ID)
