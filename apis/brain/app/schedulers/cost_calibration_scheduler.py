"""Cost calibration scheduler — monthly job to identify uncalibrated dispatch rows.

Stub for Wave L. Phase H will add billing API polling (Anthropic Console,
OpenAI Usage API) to fill actual_cost_cents on matched rows.

medallion: ops
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.database import async_session_factory
from app.schedulers._history import run_with_scheduler_record
from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.services.cost_calibration import find_uncalibrated_rows

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "brain_cost_calibration"


@skip_if_brain_paused(JOB_ID)
async def run_cost_calibration() -> None:
    """Monthly calibration: find rows that need actual_cost_cents filled."""
    await run_with_scheduler_record(
        JOB_ID,
        _run_calibration_body,
        metadata={"source": "cost_calibration", "wave": "Wave L"},
        reraise=False,
    )


async def _run_calibration_body() -> None:
    async with async_session_factory() as db:
        rows = await find_uncalibrated_rows(db)
        if rows:
            logger.info(
                "cost_calibration: %d rows need calibration — "
                "Phase H billing integration will resolve these. "
                "See docs/PR_TSHIRT_SIZING.md for calibration methodology.",
                len(rows),
            )
            for row in rows[:5]:
                logger.info(
                    "cost_calibration: needs-calibration id=%s size=%s model=%s dispatched_at=%s",
                    row["id"],
                    row["t_shirt_size"],
                    row["model_used"],
                    row["dispatched_at"],
                )
        else:
            logger.info("cost_calibration: no rows need calibration")


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the monthly cost calibration job (1st of month, 03:00 UTC)."""
    scheduler.add_job(
        run_cost_calibration,
        trigger=CronTrigger.from_crontab("0 3 1 * *", timezone="UTC"),
        id=JOB_ID,
        name="Cost Calibration (Wave L — stub, Phase H billing integration)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("APScheduler job %r registered (0 3 1 * * UTC)", JOB_ID)
