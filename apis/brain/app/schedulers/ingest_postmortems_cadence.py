"""Continuous learning: postmortems + runbook incidents → memory (daily 03:30 UTC)."""

from __future__ import annotations

import logging
import os
from datetime import UTC
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.database import async_session_factory
from app.services.continuous_learning import ingest_postmortems

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "ingest_postmortems_daily"


def _repo_root() -> str:
    return os.environ.get(
        "REPO_ROOT",
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    )


async def _run_ingest_postmortems() -> None:
    try:
        async with async_session_factory() as db:
            report = await ingest_postmortems(db, _repo_root())
        logger.info(
            "ingest_postmortems: created=%d skipped=%d scanned=%s",
            report.get("created", 0),
            report.get("skipped", 0),
            report.get("scanned", 0),
        )
    except Exception:
        logger.exception("ingest_postmortems_cadence raised — will retry next run")


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        _run_ingest_postmortems,
        trigger=CronTrigger(
            hour=3,
            minute=30,
            timezone=UTC,
        ),
        id=_JOB_ID,
        name="Ingest sprint postmortems and runbook incidents",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("ingest_postmortems_cadence installed: 03:30 UTC daily")
