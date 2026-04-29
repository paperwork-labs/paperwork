"""Brain audit runner scheduler — dispatches enabled audits per cadence.

Each enabled audit runs per its cadence:
  - weekly  → Mondays 07:00 UTC
  - monthly → 1st of month 07:00 UTC
  - quarterly → 1st of Jan/Apr/Jul/Oct 07:00 UTC

Weekly digest posts Mondays 09:00 UTC (after all weekly audit runs complete).

medallion: ops
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._kill_switch_guard import skip_if_brain_paused

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


@skip_if_brain_paused("audit_runner_weekly")
async def _run_weekly_audits() -> None:
    from app.services.audits import load_registry, run_audit

    registry = await asyncio.to_thread(load_registry)
    enabled_weekly = [d for d in registry if d.enabled and d.cadence == "weekly"]
    for defn in enabled_weekly:
        try:
            run = await asyncio.to_thread(run_audit, defn.id)
            logger.info(
                "audit_runner: completed %s — %d finding(s)",
                defn.id,
                len(run.findings),
            )
        except Exception:
            logger.exception("audit_runner: failed to run audit %s", defn.id)


@skip_if_brain_paused("audit_runner_monthly")
async def _run_monthly_audits() -> None:
    from app.services.audits import load_registry, run_audit

    registry = await asyncio.to_thread(load_registry)
    enabled_monthly = [d for d in registry if d.enabled and d.cadence == "monthly"]
    for defn in enabled_monthly:
        try:
            run = await asyncio.to_thread(run_audit, defn.id)
            logger.info(
                "audit_runner: completed %s (monthly) — %d finding(s)",
                defn.id,
                len(run.findings),
            )
        except Exception:
            logger.exception("audit_runner: failed to run monthly audit %s", defn.id)


@skip_if_brain_paused("audit_runner_quarterly")
async def _run_quarterly_audits() -> None:
    from app.services.audits import load_registry, run_audit

    registry = await asyncio.to_thread(load_registry)
    enabled_quarterly = [d for d in registry if d.enabled and d.cadence == "quarterly"]
    for defn in enabled_quarterly:
        try:
            run = await asyncio.to_thread(run_audit, defn.id)
            logger.info(
                "audit_runner: completed %s (quarterly) — %d finding(s)",
                defn.id,
                len(run.findings),
            )
        except Exception:
            logger.exception("audit_runner: failed to run quarterly audit %s", defn.id)


@skip_if_brain_paused("audit_weekly_digest")
async def _post_weekly_digest() -> None:
    from app.services.audits import weekly_audit_digest

    try:
        digest = await asyncio.to_thread(weekly_audit_digest)
        logger.info(
            "audit_runner: weekly digest queued — %d info finding(s)",
            digest.get("finding_count", 0),
        )
    except Exception:
        logger.exception("audit_runner: weekly_audit_digest failed")


def install(scheduler: AsyncIOScheduler) -> None:
    """Register audit cron jobs on the shared Brain scheduler."""
    scheduler.add_job(
        _run_weekly_audits,
        trigger=CronTrigger(day_of_week="mon", hour=7, minute=0, timezone="UTC"),
        id="audit_runner_weekly",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _run_monthly_audits,
        trigger=CronTrigger(day=1, hour=7, minute=15, timezone="UTC"),
        id="audit_runner_monthly",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _run_quarterly_audits,
        trigger=CronTrigger(month="1,4,7,10", day=1, hour=7, minute=30, timezone="UTC"),
        id="audit_runner_quarterly",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _post_weekly_digest,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0, timezone="UTC"),
        id="audit_weekly_digest",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("audit_runner: installed weekly/monthly/quarterly/digest jobs")
