"""Weekly Brain self-improvement retro job — Mondays 08:30 UTC."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.services import self_improvement as self_improvement_service

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "self_improvement_weekly_retro"


@skip_if_brain_paused(_JOB_ID)
async def _run_self_improvement() -> None:
    try:
        retro = await asyncio.to_thread(self_improvement_service.compute_weekly_retro)
        await asyncio.to_thread(self_improvement_service.record_retro, retro)
        logger.info(
            "self_improvement_weekly_retro recorded week_ending=%s pos_change=%.2f",
            retro.week_ending.strftime("%Y-%m-%dT%H:%M:%SZ"),
            retro.summary.pos_total_change,
        )
    except Exception:
        logger.exception("self_improvement_weekly_retro raised — will retry next schedule")


def install(scheduler: AsyncIOScheduler) -> None:
    """Register Mondays 08:30 UTC cron for weekly Brain retrospectives."""
    scheduler.add_job(
        _run_self_improvement,
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=30, timezone="UTC"),
        id=_JOB_ID,
        name="Brain weekly self-improvement retro",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("self_improvement_weekly_retro scheduled (Monday 08:30 UTC)")
