"""Continuous learning: decision markdown → memory (daily 03:00 UTC)."""

from __future__ import annotations

import logging
import os
from datetime import UTC
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.database import async_session_factory
from app.services.continuous_learning import ingest_decisions

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "ingest_decisions_daily"


def _repo_root() -> str:
    return os.environ.get(
        "REPO_ROOT",
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    )


async def _run_ingest_decisions() -> None:
    try:
        async with async_session_factory() as db:
            report = await ingest_decisions(db, _repo_root())
        logger.info(
            "ingest_decisions: created=%d skipped=%d scanned=%s",
            report.get("created", 0),
            report.get("skipped", 0),
            report.get("scanned", 0),
        )
    except Exception:
        logger.exception("ingest_decisions_cadence raised — will retry next run")


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        _run_ingest_decisions,
        trigger=CronTrigger(
            hour=3,
            minute=0,
            timezone=UTC,
        ),
        id=_JOB_ID,
        name="Ingest decision docs (ADR) into memory",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("ingest_decisions_cadence installed: 03:00 UTC daily")
