"""Hourly Vercel on-demand budget poll — fires Slack alerts at 50/75/90/100%.

medallion: ops
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.services.vercel_billing_monitor import run

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "vercel_billing_monitor_hourly"


async def _tick() -> None:
    result = run()
    if not result.get("ok"):
        logger.warning("vercel_billing_monitor: skipped (%s)", result.get("reason"))
        return
    alerts = result.get("alerts", [])
    if alerts:
        # Slack routing handled by services.slack_router once that lands;
        # for now we log structured so log-shipper can pick it up.
        for a in alerts:
            pct = a.get("pct")
            if pct is None:
                logger.warning(
                    "vercel_budget_alert severity=%s level=%s spent=%.2f budget=%.2f msg=%s",
                    a["severity"],
                    a.get("level", ""),
                    a["spent_usd"],
                    a["budget_usd"],
                    a.get("message", ""),
                )
            else:
                logger.warning(
                    "vercel_budget_alert severity=%s pct=%.1f spent=%.2f budget=%.2f",
                    a["severity"],
                    pct,
                    a["spent_usd"],
                    a["budget_usd"],
                )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        _tick,
        CronTrigger(minute=0),
        id=_JOB_ID,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )
