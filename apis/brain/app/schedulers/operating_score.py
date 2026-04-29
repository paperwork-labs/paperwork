"""Weekly Paperwork Operating Score (POS) job — Mondays 09:00 UTC."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.services import operating_score as operating_score_service

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "operating_score_weekly"


@skip_if_brain_paused(_JOB_ID)
async def _run_operating_score() -> None:
    try:
        entry = await asyncio.to_thread(operating_score_service.compute_score)
        await asyncio.to_thread(operating_score_service.record_score, entry)
        logger.info(
            "operating_score_weekly recorded total=%.2f gates_l4=%s",
            entry.total,
            entry.gates.l4_pass,
        )
    except Exception:
        logger.exception("operating_score_weekly raised — will retry next schedule")


def install(scheduler: AsyncIOScheduler) -> None:
    """Register Mondays 09:00 UTC cron for POS recomputation."""
    scheduler.add_job(
        _run_operating_score,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0, timezone="UTC"),
        id=_JOB_ID,
        name="Paperwork Operating Score (weekly)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=600,
    )
    logger.info("operating_score_weekly scheduled (Monday 09:00 UTC)")
