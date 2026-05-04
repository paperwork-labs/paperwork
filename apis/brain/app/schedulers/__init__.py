"""In-process schedulers owned by Brain.

See ``pr_sweep.py`` for the PR-sweep job that replaced the
``auto-merge-sweep.yaml`` GitHub Actions workflow in Track B, Week 1.

Only one scheduler instance per process — ``start()``/``shutdown()`` are
called from ``app.main``'s lifespan context. Do not start schedulers from
routers or services; that would break clean shutdown.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .pr_sweep import shutdown_scheduler as shutdown_scheduler
from .pr_sweep import start_scheduler as _start_scheduler

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


def start_scheduler() -> AsyncIOScheduler | None:
    """Start the shared Brain scheduler and register package-level jobs."""
    scheduler = _start_scheduler()
    if scheduler is None:
        return None
    try:
        from app.schedulers import iac_drift

        iac_drift.install(scheduler)
    except Exception:
        logger.exception("Failed to install iac_drift_detector job")
    try:
        from app.schedulers import self_merge_promotion

        self_merge_promotion.install(scheduler)
    except Exception:
        logger.exception("Failed to install self_merge_promotion job")
    try:
        from app.schedulers import self_prioritization

        self_prioritization.install(scheduler)
    except Exception:
        logger.exception("Failed to install self_prioritization job")
    try:
        from app.schedulers import self_improvement

        self_improvement.install(scheduler)
    except Exception:
        logger.exception("Failed to install self_improvement_weekly_retro job")
    try:
        from app.schedulers import anomaly_detection

        anomaly_detection.install(scheduler)
    except Exception:
        logger.exception("Failed to install anomaly_detection_hourly job")
    try:
        from app.schedulers import sprint_velocity

        sprint_velocity.install(scheduler)
    except Exception:
        logger.exception("Failed to install sprint_velocity_weekly job")
    try:
        from app.schedulers import vercel_billing_monitor

        vercel_billing_monitor.install(scheduler)
    except Exception:
        logger.exception("Failed to install vercel_billing_monitor_hourly job")
    try:
        from app.schedulers import kg_validation

        kg_validation.install(scheduler)
    except Exception:
        logger.exception("Failed to install kg_self_validation_daily job")
    try:
        from app.schedulers import audit_runner

        audit_runner.install(scheduler)
    except Exception:
        logger.exception("Failed to install audit_runner jobs")
    try:
        from app.schedulers import log_pull

        log_pull.install(scheduler)
    except Exception:
        logger.exception("Failed to install app_log_pull_hourly job")
    try:
        from app.schedulers import cost_calibration_scheduler

        cost_calibration_scheduler.install(scheduler)
    except Exception:
        logger.exception("Failed to install cost_calibration monthly job")
    try:
        from app.schedulers import expense_monthly_close

        expense_monthly_close.install(scheduler)
    except Exception:
        logger.exception("Failed to install expense_monthly_close job")
    try:
        from app.schedulers import ux_probe_runner

        ux_probe_runner.install(scheduler)
    except Exception:
        logger.exception("Failed to install ux_probe_runner job")
    try:
        from app.schedulers import probe_failure_dispatcher

        probe_failure_dispatcher.install(scheduler)
    except Exception:
        logger.exception("Failed to install probe_failure_dispatcher job")
    try:
        from app.schedulers import autopilot_dispatcher

        autopilot_dispatcher.install(scheduler)
    except Exception:
        logger.exception("Failed to install brain_autopilot_dispatcher job")
    return scheduler
