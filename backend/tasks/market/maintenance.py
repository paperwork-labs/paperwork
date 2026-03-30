"""
Market data retention, job-run recovery, and quality audit tasks.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from celery import shared_task
from sqlalchemy import func

from backend.config import settings
from backend.database import SessionLocal
from backend.models import PriceData
from backend.models.market_data import JobRun, MarketSnapshotHistory
from backend.services.market.market_data_service import market_data_service
from backend.tasks.utils.task_utils import _get_tracked_symbols_safe, task_run

logger = logging.getLogger(__name__)

STALE_JOB_RUN_MINUTES = 120


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
        cutoff = datetime.now(timezone.utc) - timedelta(days=effective_days)
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
    """Audit market data coverage and snapshot history consistency."""
    session = SessionLocal()
    try:
        tracked = _get_tracked_symbols_safe(session)
        tracked_set = set(tracked)
        latest_daily_date = (
            session.query(func.max(PriceData.date))
            .filter(PriceData.interval == "1d")
            .scalar()
        )
        daily_symbols = set()
        if latest_daily_date:
            daily_rows = (
                session.query(PriceData.symbol)
                .filter(
                    PriceData.interval == "1d",
                    PriceData.date == latest_daily_date,
                )
                .distinct()
                .all()
            )
            daily_symbols = {str(s[0]).upper() for s in daily_rows if s and s[0]}
        missing_latest_daily = sorted(tracked_set - daily_symbols)

        latest_history_date = (
            session.query(func.max(MarketSnapshotHistory.as_of_date)).scalar()
        )
        history_symbols = set()
        if latest_history_date:
            history_rows = (
                session.query(MarketSnapshotHistory.symbol)
                .filter(MarketSnapshotHistory.as_of_date == latest_history_date)
                .distinct()
                .all()
            )
            history_symbols = {str(s[0]).upper() for s in history_rows if s and s[0]}
        missing_history = sorted(tracked_set - history_symbols)

        payload = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tracked_total": len(tracked_set),
            "latest_daily_date": latest_daily_date.isoformat()
            if hasattr(latest_daily_date, "isoformat")
            else str(latest_daily_date)
            if latest_daily_date
            else None,
            "latest_daily_symbol_count": len(daily_symbols),
            "missing_latest_daily_count": len(missing_latest_daily),
            "missing_latest_daily_sample": missing_latest_daily[:sample_limit],
            "latest_snapshot_history_date": latest_history_date.isoformat()
            if hasattr(latest_history_date, "isoformat")
            else str(latest_history_date)
            if latest_history_date
            else None,
            "latest_snapshot_history_symbol_count": len(history_symbols),
            "missing_snapshot_history_count": len(missing_history),
            "missing_snapshot_history_sample": missing_history[:sample_limit],
        }
        try:
            market_data_service.redis_client.set(
                "market_audit:last", json.dumps(payload), ex=86400
            )
        except Exception as e:
            logger.warning("redis_audit_cache failed: %s", e)
        return payload
    finally:
        session.close()
