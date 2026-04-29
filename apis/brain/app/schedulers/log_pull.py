"""Hourly log pull scheduler — Brain-owned logs (WS-69 PR M).

Runs once per hour:
1. Pulls from Vercel + Render APIs into ``app_logs.json``.
2. Runs anomaly detection on the new batch.
3. Creates an alert Episode for any anomaly (push notification wired by PR I).
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.schemas.app_log import Anomaly, AppLog
from app.services import app_logs as app_logs_svc

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "log_pull_hourly"


def _run_pull_sync() -> tuple[int, int, list[AppLog]]:
    """Pull logs from Vercel + Render; return (vercel_count, render_count, new_logs)."""
    since = datetime.now(UTC) - timedelta(hours=1)

    team_id = os.environ.get("VERCEL_TEAM_ID", "").strip()
    vercel_projects_raw = os.environ.get("BRAIN_LOGS_VERCEL_PROJECT_IDS", "").strip()
    render_services_raw = os.environ.get("BRAIN_LOGS_RENDER_SERVICE_IDS", "").strip()

    vercel_project_ids = [p.strip() for p in vercel_projects_raw.split(",") if p.strip()]
    render_service_ids = [s.strip() for s in render_services_raw.split(",") if s.strip()]

    vercel_count = 0
    render_count = 0

    if vercel_project_ids:
        try:
            vercel_count = app_logs_svc.pull_vercel_logs(
                team_id=team_id,
                project_ids=vercel_project_ids,
                since=since,
            )
        except Exception:
            logger.exception("log_pull_hourly: pull_vercel_logs raised — failure ingested")

    if render_service_ids:
        try:
            render_count = app_logs_svc.pull_render_logs(
                service_ids=render_service_ids,
                since=since,
            )
        except Exception:
            logger.exception("log_pull_hourly: pull_render_logs raised — failure ingested")

    # Fetch logs from the past hour for anomaly analysis
    page = app_logs_svc.list_logs(since=since, limit=500)
    return vercel_count, render_count, page.logs


def _fire_anomaly_alert(anomaly: Anomaly) -> None:
    """Record an anomaly alert.

    Creates an alert episode in the Brain memory system.
    PR I will extend this to fire web push notifications to the founder.
    """
    try:
        summary_parts = [
            f"[LOG ANOMALY] kind={anomaly.kind} severity={anomaly.severity}",
            anomaly.description,
        ]
        if anomaly.affected_app:
            summary_parts.append(f"app={anomaly.affected_app}")
        if anomaly.affected_service:
            summary_parts.append(f"service={anomaly.affected_service}")
        summary = " | ".join(summary_parts)
        logger.warning("log_pull_hourly: anomaly detected — %s", summary)

        # Ingest a meta-log entry so the anomaly is visible in the Logs tab
        from app.schemas.app_log import AppLogIngestRequest

        ingest_req = AppLogIngestRequest(
            app="brain",
            service="brain-anomaly-detector",
            severity=anomaly.severity,
            message=summary,
            metadata={
                "anomaly_kind": anomaly.kind,
                "sample_log_ids": anomaly.sample_log_ids,
                "affected_app": anomaly.affected_app,
                "affected_service": anomaly.affected_service,
            },
        )
        app_logs_svc.ingest_log(ingest_req)

        # TODO(PR I): replace with Conversation creation + web push notification
    except Exception:
        logger.exception("log_pull_hourly: _fire_anomaly_alert raised")


@skip_if_brain_paused(_JOB_ID)
async def _run_log_pull() -> None:
    try:
        vercel_count, render_count, new_logs = await asyncio.to_thread(_run_pull_sync)
        logger.info(
            "log_pull_hourly: pulled vercel=%d render=%d; analyzing %d entries",
            vercel_count,
            render_count,
            len(new_logs),
        )
    except Exception:
        logger.exception("log_pull_hourly: pull phase raised unexpectedly")
        return

    try:
        anomalies: list[Anomaly] = await asyncio.to_thread(app_logs_svc.detect_anomalies, new_logs)
        if anomalies:
            logger.warning("log_pull_hourly: %d anomaly(ies) detected", len(anomalies))
            for anomaly in anomalies:
                _fire_anomaly_alert(anomaly)
        else:
            logger.info("log_pull_hourly: no anomalies detected")
    except Exception:
        logger.exception("log_pull_hourly: anomaly detection raised — skipped")


def install(scheduler: AsyncIOScheduler) -> None:
    """Register hourly log pull job."""
    scheduler.add_job(
        _run_log_pull,
        trigger=CronTrigger(minute=30, timezone="UTC"),
        id=_JOB_ID,
        name="Brain Log Pull (hourly)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info("log_pull_hourly scheduled (every hour at :30 UTC)")
