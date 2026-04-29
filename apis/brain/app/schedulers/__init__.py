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

from .pr_sweep import get_scheduler, shutdown_scheduler
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
    return scheduler


__all__ = ["get_scheduler", "shutdown_scheduler", "start_scheduler"]
