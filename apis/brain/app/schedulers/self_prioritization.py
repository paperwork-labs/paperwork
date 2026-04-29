"""Daily Brain self-prioritization candidate generation (Phase G2)."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.services import self_prioritization as self_prioritization_service

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "brain_self_prioritization_daily"


@skip_if_brain_paused(JOB_ID)
async def _run_self_prioritization() -> None:
    try:
        candidates = await asyncio.to_thread(self_prioritization_service.propose_candidates)
        await asyncio.to_thread(self_prioritization_service.record_candidates, candidates)
        logger.info("brain_self_prioritization_daily recorded %d candidates", len(candidates))
    except Exception:
        logger.exception("brain_self_prioritization_daily raised -- will retry next schedule")


def install(scheduler: AsyncIOScheduler) -> None:
    """Register daily 08:00 UTC candidate generation."""
    scheduler.add_job(
        _run_self_prioritization,
        trigger=CronTrigger(hour=8, minute=0, timezone="UTC"),
        id=JOB_ID,
        name="Brain self-prioritization candidate generation",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("brain_self_prioritization_daily scheduled (08:00 UTC daily)")
