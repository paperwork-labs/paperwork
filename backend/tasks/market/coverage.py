"""
Coverage Monitoring Tasks
=========================

Celery tasks for data coverage health monitoring.
"""

import logging
from celery import shared_task

from backend.database import SessionLocal
from backend.tasks.task_utils import task_run

logger = logging.getLogger(__name__)


@shared_task(
    name="backend.tasks.market.coverage.monitor_coverage_health",
    soft_time_limit=120,
    time_limit=180,
)
@task_run("monitor_coverage_health")
def monitor_coverage_health() -> dict:
    """Check data coverage health and return status.

    Measures:
    - Daily bar fill percentage
    - Snapshot fill percentage  
    - Stale symbol count
    """
    session = SessionLocal()
    try:
        from backend.services.market.market_data_service import market_data_service
        from backend.services.market.universe import tracked_symbols

        tracked = tracked_symbols(session, redis_client=market_data_service.redis_client)
        tracked_total = len(tracked)

        if tracked_total == 0:
            return {"status": "no_tracked_symbols", "tracked_total": 0}

        coverage = market_data_service.coverage.get_cached_or_compute(session)

        return {
            "status": "ok",
            "tracked_total": tracked_total,
            "daily_fill_pct": coverage.get("daily_fill_pct", 0),
            "snapshot_fill_pct": coverage.get("snapshot_fill_pct", 0),
            "stale_count": len(coverage.get("stale_symbols", [])),
            "stale_sample": coverage.get("stale_symbols", [])[:10],
        }

    except Exception:
        logger.exception("monitor_coverage_health failed")
        raise
    finally:
        session.close()
