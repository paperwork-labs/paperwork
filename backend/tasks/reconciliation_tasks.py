"""Reconciliation Celery tasks."""

import logging
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="backend.tasks.reconciliation_tasks.reconcile_orders", soft_time_limit=300, time_limit=360)
def reconcile_orders(self, lookback_hours: int = 24):
    """Match filled Orders to Trades. Runs after broker sync."""
    from backend.database import SessionLocal
    from backend.services.reconciliation import reconciliation_service

    db = SessionLocal()
    try:
        result = reconciliation_service.reconcile_fills(db, lookback_hours=lookback_hours)
        logger.info(
            "Reconciliation: %d matched, %d unmatched of %d total",
            result["matched"],
            result["unmatched"],
            result["total_orders"],
        )
        return result
    finally:
        db.close()
