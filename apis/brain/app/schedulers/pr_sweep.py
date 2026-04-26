"""Brain-owned PR sweep scheduler.

Replaces ``.github/workflows/auto-merge-sweep.yaml``. Runs in-process via
APScheduler's ``AsyncIOScheduler`` so we keep a single authority (Brain) for
PR decisions. No external cron, no GitHub Actions schedule, no extra infra.

Cadence defaults to 30 minutes (configurable via
``SCHEDULER_PR_SWEEP_MINUTES``) — enough to keep the queue moving without
burning Anthropic tokens on idle repos.

Safety:
- Single scheduler per process. If Render scales ``brain-api`` to multiple
  instances, gate this with ``BRAIN_SCHEDULER_ENABLED=false`` on the replicas
  or add a Redis-backed lock (future Track I concern; not needed for the
  current 1-replica deploy).
- Jobs never raise — exceptions are logged, the next tick retries.
"""

from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.schedulers import apscheduler_db, n8n_mirror
from app.database import async_session_factory
from app.services.pr_merge_sweep import merge_ready_prs
from app.services.pr_review import sweep_open_prs

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _run_pr_sweep() -> None:
    """Scheduled entry point: review new PR heads, then merge anything ready.

    Swallows all exceptions. The next tick is its own retry.
    """
    try:
        async with async_session_factory() as db:
            review_report: dict[str, Any] = await sweep_open_prs(db, limit=30)
        logger.info(
            "pr_sweep review: reviewed=%d skipped=%d errors=%d scanned=%d",
            len(review_report.get("reviewed", [])),
            len(review_report.get("skipped", [])),
            len(review_report.get("errors", [])),
            review_report.get("scanned", 0),
        )
    except Exception:
        logger.exception("pr_sweep review raised — will retry next interval")

    try:
        merge_report: dict[str, Any] = await merge_ready_prs(limit=50)
        logger.info(
            "pr_sweep merge: merged=%d skipped=%d errors=%d",
            len(merge_report.get("merged", [])),
            len(merge_report.get("skipped", [])),
            len(merge_report.get("errors", [])),
        )
    except Exception:
        logger.exception("pr_sweep merge raised — will retry next interval")


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


def start_scheduler() -> AsyncIOScheduler | None:
    """Create and start the singleton scheduler.

    Returns the scheduler (or ``None`` if disabled). Idempotent — calling
    twice is a warning, not an error.
    """
    global _scheduler
    if not settings.BRAIN_SCHEDULER_ENABLED:
        logger.info("BRAIN_SCHEDULER_ENABLED=false — skipping APScheduler startup")
        return None
    if _scheduler is not None:
        logger.warning("start_scheduler() called twice; returning existing instance")
        return _scheduler

    minutes = max(1, int(settings.SCHEDULER_PR_SWEEP_MINUTES or 30))
    jobstores = apscheduler_db.build_sqlalchemy_jobstores()
    sched = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")
    sched.add_job(
        _run_pr_sweep,
        trigger=IntervalTrigger(minutes=minutes),
        id="pr_sweep",
        name="Brain PR sweep",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )

    # Track C: proactive persona cadence runs on the same scheduler so we keep
    # a single lifecycle.
    try:
        from app.schedulers import proactive_cadence

        proactive_cadence.install(sched)
    except Exception:
        logger.exception("Failed to install proactive_cadence job")

    try:
        from app.schedulers import cost_dashboard

        cost_dashboard.install(sched)
    except Exception:
        logger.exception("Failed to install cfo_cost_dashboard job")

    try:
        from app.schedulers import qa_weekly_report

        qa_weekly_report.install(sched)
    except Exception:
        logger.exception("Failed to install qa_weekly_report job")

    try:
        from app.schedulers import cfo_friday_digest

        cfo_friday_digest.install(sched)
    except Exception:
        logger.exception("Failed to install cfo_friday_digest job")

    try:
        from app.schedulers import sprint_lessons

        sprint_lessons.install(sched)
    except Exception:
        logger.exception("Failed to install sprint_lessons job")

    try:
        from app.schedulers import brain_daily_briefing

        brain_daily_briefing.install(sched)
    except Exception:
        logger.exception("Failed to install brain_daily_briefing job")

    try:
        n8n_mirror.install(sched)
    except Exception:
        logger.exception("Failed to install n8n_mirror shadow jobs")

    sched.start()
    _scheduler = sched
    logger.info("APScheduler started: pr_sweep every %d min + proactive_cadence hourly", minutes)
    return sched


async def shutdown_scheduler() -> None:
    """Gracefully stop the scheduler on app shutdown."""
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down cleanly")
    except Exception:
        logger.exception("APScheduler shutdown raised")
    finally:
        _scheduler = None
