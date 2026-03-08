from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from backend.tasks.celery_app import celery_app
from backend.database import SessionLocal
from backend.models.order import Order, OrderStatus
from backend.services.execution.order_manager import OrderManager

logger = logging.getLogger(__name__)

STALE_SUBMITTED_THRESHOLD = timedelta(hours=1)


@celery_app.task(bind=True, max_retries=3)
def execute_order_task(self, order_id: int) -> dict:
    """Submit a previewed order via the OrderManager."""
    db = SessionLocal()
    try:
        om = OrderManager()
        result = asyncio.run(om.submit(db, order_id))

        if "error" in result:
            logger.error("execute_order_task order_id=%s failed: %s", order_id, result["error"])
        else:
            logger.info(
                "execute_order_task order_id=%s status=%s broker_order_id=%s",
                order_id,
                result.get("status"),
                result.get("broker_order_id"),
            )
        return result
    except Exception as exc:
        logger.exception("execute_order_task order_id=%s raised", order_id)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def monitor_open_orders_task(self) -> dict:
    """Poll all SUBMITTED / PARTIALLY_FILLED orders and detect stale ones."""
    db = SessionLocal()
    try:
        om = OrderManager()
        open_orders = (
            db.query(Order)
            .filter(
                Order.status.in_([
                    OrderStatus.SUBMITTED.value,
                    OrderStatus.PARTIALLY_FILLED.value,
                ])
            )
            .all()
        )

        if not open_orders:
            logger.debug("monitor_open_orders_task: no open orders")
            return {"polled": 0, "changed": 0, "stale": 0}

        polled = 0
        changed = 0
        stale = 0
        now = datetime.now(timezone.utc)

        for order in open_orders:
            old_status = order.status
            result = asyncio.run(om.poll_status(db, order.id))
            polled += 1

            if "error" in result:
                logger.warning(
                    "monitor_open_orders: poll failed order_id=%s: %s",
                    order.id,
                    result["error"],
                )
                continue

            new_status = result.get("status")
            if new_status != old_status:
                changed += 1
                logger.info(
                    "monitor_open_orders: order_id=%s %s -> %s",
                    order.id,
                    old_status,
                    new_status,
                )

            if (
                order.submitted_at
                and old_status == OrderStatus.SUBMITTED.value
                and (now - order.submitted_at) > STALE_SUBMITTED_THRESHOLD
            ):
                stale += 1
                logger.warning(
                    "monitor_open_orders: STALE order_id=%s submitted_at=%s (>1h ago)",
                    order.id,
                    order.submitted_at.isoformat(),
                )

        summary = {"polled": polled, "changed": changed, "stale": stale}
        logger.info("monitor_open_orders_task: %s", summary)
        return summary
    except Exception as exc:
        logger.exception("monitor_open_orders_task raised")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
    finally:
        db.close()
