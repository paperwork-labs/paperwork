"""
Market data retention, job-run recovery, and quality audit tasks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from celery import shared_task

from backend.config import settings
from backend.database import SessionLocal
from backend.models import PriceData
from backend.models.market_data import JobRun
from backend.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)

STALE_JOB_RUN_MINUTES = 45


@shared_task(
    soft_time_limit=600,
    time_limit=720,
)
@task_run("admin_retention_enforce")
def prune_old_bars(max_days_5m: int = 90) -> dict:
    """Delete 5m bars older than max_days_5m to control storage."""
    session = SessionLocal()
    try:
        from backend.services.notifications.alerts import alert_service

        effective_days = int(max_days_5m or settings.RETENTION_MAX_DAYS_5M)
        cutoff = datetime.utcnow() - timedelta(days=effective_days)
        deleted = (
            session.query(PriceData)
            .filter(PriceData.interval == "5m", PriceData.date < cutoff)
            .delete(synchronize_session=False)
        )
        session.commit()
        deleted_count = int(deleted or 0)
        warn_threshold = int(settings.RETENTION_DELETE_WARN_THRESHOLD or 0)
        warning = None
        if warn_threshold and deleted_count >= warn_threshold:
            warning = f"Retention deleted {deleted_count} rows (>= {warn_threshold})"
            alert_service.send_alert(
                "system_status",
                title="Market Data Retention Spike",
                description="5m retention deleted more rows than expected.",
                fields={
                    "deleted": str(deleted_count),
                    "threshold": str(warn_threshold),
                    "cutoff": cutoff.isoformat(),
                },
                severity="warning",
            )
        return {
            "status": "ok",
            "deleted": deleted_count,
            "cutoff": cutoff.isoformat(),
            "warning": warning,
        }
    finally:
        session.close()


def recover_jobs_impl(stale_minutes: int = STALE_JOB_RUN_MINUTES) -> dict:
    """Mark JobRun rows stuck in running as cancelled. Returns counts."""
    session = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)
        now = datetime.now(timezone.utc)
        msg = (
            f"Marked cancelled: run exceeded stale threshold ({stale_minutes} min). "
            "Process likely terminated (cron timeout, OOM, or worker restart)."
        )
        cancelled_count = (
            session.query(JobRun)
            .filter(JobRun.status == "running", JobRun.started_at < cutoff)
            .update(
                {
                    JobRun.status: "cancelled",
                    JobRun.finished_at: now,
                    JobRun.error: msg,
                },
                synchronize_session=False,
            )
        )
        session.commit()
        return {
            "cancelled_count": cancelled_count,
            "stale_minutes": stale_minutes,
            "cutoff": cutoff.isoformat(),
        }
    finally:
        session.close()


@shared_task(
    soft_time_limit=120,
    time_limit=180,
)
@task_run("admin_recover_stale_job_runs")
def recover_jobs(stale_minutes: int = STALE_JOB_RUN_MINUTES) -> dict:
    """Mark job runs stuck in RUNNING as cancelled so jobs list and health can go green."""
    return recover_jobs_impl(stale_minutes=stale_minutes)


@shared_task(
    soft_time_limit=300,
    time_limit=360,
)
@task_run("admin_market_data_audit")
def audit_quality(sample_limit: int = 25) -> dict:
    """Cache-warmer: calls AdminHealthService.compute_audit_metrics() to
    refresh the canonical audit cache. The service owns the computation
    (including the analysis_type='technical_snapshot' filter) and writes
    the result to Redis with a 5-min TTL.
    """
    from backend.services.market.admin_health_service import AdminHealthService

    session = SessionLocal()
    try:
        svc = AdminHealthService()
        return svc.compute_audit_metrics(session)
    finally:
        session.close()
