"""Continuous learning: merge GitHub API merged PRs into memory (6h)."""

from __future__ import annotations

import logging
import os
from datetime import UTC
from typing import TYPE_CHECKING

from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import async_session_factory
from app.services.continuous_learning import ingest_merged_prs

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


def _repo_root() -> str:
    return os.environ.get(
        "REPO_ROOT",
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    )


async def _run_merged_prs_ingest() -> None:
    try:
        async with async_session_factory() as db:
            report = await ingest_merged_prs(db, _repo_root())
        if report.get("error"):
            logger.warning("merged_prs_ingest: %s", report["error"])
        else:
            logger.info(
                "merged_prs_ingest: created=%d skipped=%d",
                report.get("created", 0),
                report.get("skipped", 0),
            )
    except Exception:
        logger.exception("merged_prs_ingest raised — will retry next interval")


def install(scheduler: AsyncIOScheduler) -> None:
    hours = max(
        1,
        int(getattr(settings, "SCHEDULER_MERGED_PRS_HOURS", 0) or 6),
    )
    scheduler.add_job(
        _run_merged_prs_ingest,
        trigger=IntervalTrigger(hours=hours, timezone=UTC),
        id="merged_prs_ingest",
        name="Brain ingests recently merged PRs as memory",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("merged_prs_ingest installed: every %d hours", hours)
