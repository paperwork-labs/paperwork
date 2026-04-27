"""Brain-owned sprint-lessons ingestion scheduler.

Walks ``docs/sprints/*.md`` every 6 hours and lifts each new bullet under
``## What we learned`` into a memory episode (``source="sprint:lessons"``).

Why we own this in-process:
  • The same APScheduler instance already runs PR-sweep / proactive cadence
    / cost dashboard, so adding one more job avoids spinning up a separate
    cron.
  • Idempotency is enforced inside ``ingest_sprint_lessons`` via SHA1 of
    each lesson under ``source_ref`` — running every 6 hours is cheap
    (one DB query per sprint file, no LLM calls until a new lesson exists).
  • Failures never raise; the next tick is its own retry.

This pairs with the on-demand ``POST /admin/seed-lessons`` endpoint
(triggered by ``scripts/ingest_sprint_lessons.py`` from a GitHub Actions
job after sprint markdown changes merge).
"""

from __future__ import annotations

import logging
import os
from datetime import UTC
from typing import TYPE_CHECKING

from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import async_session_factory
from app.services.seed import ingest_sprint_lessons

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


def _repo_root() -> str:
    return os.environ.get(
        "REPO_ROOT",
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    )


async def _run_sprint_lessons_ingest() -> None:
    """Scheduled entry — never raises.

    A missing ``docs/sprints/`` directory (e.g. on a stripped image) is
    handled gracefully inside ``ingest_sprint_lessons``.
    """
    try:
        async with async_session_factory() as db:
            report = await ingest_sprint_lessons(db, _repo_root())
        logger.info(
            "sprint_lessons_ingest: scanned=%d created=%d skipped=%d",
            report["sprints_scanned"],
            report["created"],
            report["skipped"],
        )
    except Exception:
        logger.exception("sprint_lessons_ingest raised — will retry next interval")


def install(scheduler: AsyncIOScheduler) -> None:
    """Attach the sprint-lessons job to the shared scheduler.

    Defaults to every 6 hours; override with
    ``SCHEDULER_SPRINT_LESSONS_HOURS`` if a sprint pipeline ever needs
    faster freshness.
    """
    hours = max(
        1,
        int(getattr(settings, "SCHEDULER_SPRINT_LESSONS_HOURS", 0) or 6),
    )
    scheduler.add_job(
        _run_sprint_lessons_ingest,
        trigger=IntervalTrigger(hours=hours, timezone=UTC),
        id="sprint_lessons_ingest",
        name="Brain ingests sprint 'What we learned' bullets",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("sprint_lessons_ingest installed: every %d hours", hours)
