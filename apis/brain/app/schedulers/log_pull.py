"""Hourly log-pull + anomaly-detection job — WS-69 PR M.

Pulls logs from Vercel and Render APIs then evaluates error-rate anomalies.
Runs every hour at :10 UTC (offset from anomaly_detection_hourly at :05).

Missing API tokens emit structured warnings and do not crash the scheduler.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.services import app_logs as app_logs_svc

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "app_log_pull_hourly"


@skip_if_brain_paused(_JOB_ID)
async def _run_log_pull() -> None:
    # Pull Vercel logs
    try:
        vercel_entries = await asyncio.to_thread(app_logs_svc.pull_vercel_logs)
        if vercel_entries:
            added = await asyncio.to_thread(app_logs_svc.ingest_logs, vercel_entries)
            logger.info(
                "%s: vercel pull done pulled=%d added=%d",
                _JOB_ID,
                len(vercel_entries),
                added,
                extra={"component": "log_pull", "source": "vercel", "added": added},
            )
    except Exception:
        logger.exception("%s: vercel pull raised — continuing", _JOB_ID)

    # Pull Render logs
    try:
        render_entries = await asyncio.to_thread(app_logs_svc.pull_render_logs)
        if render_entries:
            added = await asyncio.to_thread(app_logs_svc.ingest_logs, render_entries)
            logger.info(
                "%s: render pull done pulled=%d added=%d",
                _JOB_ID,
                len(render_entries),
                added,
                extra={"component": "log_pull", "source": "render", "added": added},
            )
    except Exception:
        logger.exception("%s: render pull raised — continuing", _JOB_ID)

    # Evaluate anomalies
    try:
        fired = await asyncio.to_thread(app_logs_svc.evaluate_log_anomalies)
        if fired > 0:
            logger.info(
                "%s: anomaly evaluation fired %d alert(s)",
                _JOB_ID,
                fired,
                extra={"component": "log_pull", "op": "anomaly_eval", "fired": fired},
            )
    except Exception:
        logger.exception("%s: anomaly evaluation raised — retry next hour", _JOB_ID)


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the hourly log-pull job on *scheduler*."""
    scheduler.add_job(
        _run_log_pull,
        trigger=CronTrigger(minute=10, timezone="UTC"),
        id=_JOB_ID,
        name="App Log Pull + Anomaly Detection (hourly)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info("%s scheduled (every hour at :10 UTC)", _JOB_ID)
