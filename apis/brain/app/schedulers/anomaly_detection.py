"""Hourly anomaly detection job — WS-50 Phase D.

Calls ``compute_anomalies()`` then ``auto_resolve_alerts()`` once per hour.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.services import anomaly_detection as anomaly_svc

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "anomaly_detection_hourly"


@skip_if_brain_paused(_JOB_ID)
async def _run_anomaly_detection() -> None:
    try:
        file = await asyncio.to_thread(anomaly_svc.compute_anomalies)
        open_count = sum(1 for a in file.alerts if a.resolved_at is None)
        logger.info(
            "anomaly_detection_hourly: computed alerts total=%d open=%d",
            len(file.alerts),
            open_count,
        )
    except Exception:
        logger.exception("anomaly_detection_hourly: compute_anomalies raised — retry next hour")

    try:
        resolved = await asyncio.to_thread(anomaly_svc.auto_resolve_alerts)
        if resolved > 0:
            logger.info("anomaly_detection_hourly: auto-resolved %d alert(s)", resolved)
    except Exception:
        logger.exception("anomaly_detection_hourly: auto_resolve_alerts raised — retry next hour")


def install(scheduler: AsyncIOScheduler) -> None:
    """Register hourly anomaly detection job."""
    scheduler.add_job(
        _run_anomaly_detection,
        trigger=CronTrigger(minute=5, timezone="UTC"),
        id=_JOB_ID,
        name="Anomaly Detection (hourly)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info("anomaly_detection_hourly scheduled (every hour at :05 UTC)")
