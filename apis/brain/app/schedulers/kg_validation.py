"""Daily KG self-validation job — 06:00 UTC (WS-52)."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.services import kg_validation as kg_validation_svc

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "kg_self_validation_daily"


@skip_if_brain_paused(_JOB_ID)
async def _run_kg_validation() -> None:
    try:
        run = await asyncio.to_thread(kg_validation_svc.validate)
        await asyncio.to_thread(kg_validation_svc.record_validation_run, run)
        logger.info(
            "kg_self_validation_daily: passed=%s violations=%d summary=%s",
            run.passed,
            len(run.violations),
            run.summary,
        )
    except Exception:
        logger.exception("kg_self_validation_daily raised — will retry next schedule")


def install(scheduler: AsyncIOScheduler) -> None:
    """Register daily 06:00 UTC cron for KG self-validation."""
    scheduler.add_job(
        _run_kg_validation,
        trigger=CronTrigger(hour=6, minute=0, timezone="UTC"),
        id=_JOB_ID,
        name="KG self-validation (daily)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=600,
    )
    logger.info("kg_self_validation_daily scheduled (06:00 UTC daily)")
