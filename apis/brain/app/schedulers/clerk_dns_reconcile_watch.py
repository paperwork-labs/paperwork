"""Periodic Clerk + Cloudflare DNS verification (``reconcile_clerk_dns --check-only``).

Runs every **30 minutes** on the shared Brain APScheduler. Complements the
pre-deploy guard: drift after a bad Cloudflare import is surfaced to Slack
without waiting for the next Vercel deploy.

medallion: ops
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.interval import IntervalTrigger

from app.schedulers._history import run_with_scheduler_record
from app.services.clerk_dns_watch import run_clerk_dns_check_only_tick

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "clerk_dns_reconcile_watch"


async def _run_body() -> None:
    await run_clerk_dns_check_only_tick()


async def run_clerk_dns_reconcile_watch_job() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_body,
        metadata={
            "source": "clerk_dns_reconcile_watch",
            "cadence": "30 minutes",
        },
        reraise=False,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_clerk_dns_reconcile_watch_job,
        trigger=IntervalTrigger(minutes=30),
        id=JOB_ID,
        name="Clerk DNS reconcile (check-only)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=120,
    )
    logger.info("APScheduler job %r registered (every 30 minutes UTC)", JOB_ID)
