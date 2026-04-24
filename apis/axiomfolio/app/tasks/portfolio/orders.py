from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.database import SessionLocal
from app.models.order import Order, OrderStatus
from app.models.position import Position, PositionStatus
from app.services.execution.order_manager import OrderManager
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

STALE_SUBMITTED_THRESHOLD = timedelta(hours=1)


def _attribute_position_to_strategy(db, order: Order) -> int | None:
    """When a strategy-generated order fills, attribute the position to that strategy.

    Returns the position ID if attributed, None otherwise.
    """
    if not order.strategy_id:
        return None

    if order.status != OrderStatus.FILLED.value:
        return None

    # Find the position for this symbol/user
    position = (
        db.query(Position)
        .filter(
            Position.symbol == order.symbol,
            Position.user_id == order.user_id,
            Position.status == PositionStatus.OPEN,
        )
        .first()
    )

    if not position:
        logger.debug(
            "No open position for %s user_id=%d to attribute to strategy %d",
            order.symbol,
            order.user_id,
            order.strategy_id,
        )
        return None

    # Only attribute if not already attributed or if this is a new fill
    if position.strategy_id is None:
        position.strategy_id = order.strategy_id
        position.entry_signal_id = order.signal_id
        db.add(position)
        db.commit()
        logger.info(
            "Attributed position %s (id=%d) to strategy_id=%d",
            order.symbol,
            position.id,
            order.strategy_id,
        )
        return position.id

    return None


@celery_app.task(bind=True, max_retries=3, soft_time_limit=120, time_limit=180)
def execute_order_task(self, order_id: int) -> dict:
    """Submit a previewed order via the OrderManager."""
    db = SessionLocal()
    try:
        from app.models.order import Order

        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": f"Order {order_id} not found"}
        om = OrderManager()
        result = asyncio.run(om.submit(db, order_id, user_id=order.user_id))

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
        raise self.retry(exc=exc, countdown=2**self.request.retries)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, soft_time_limit=120, time_limit=180)
def monitor_open_orders_task(self) -> dict:
    """Poll all SUBMITTED / PARTIALLY_FILLED orders and detect stale ones."""
    db = SessionLocal()
    try:
        om = OrderManager()
        open_orders = (
            db.query(Order)
            .filter(
                Order.status.in_(
                    [
                        OrderStatus.SUBMITTED.value,
                        OrderStatus.PARTIALLY_FILLED.value,
                    ]
                )
            )
            .all()
        )

        if not open_orders:
            logger.debug("monitor_open_orders_task: no open orders")
            return {"polled": 0, "changed": 0, "stale": 0}

        polled = 0
        changed = 0
        stale = 0
        now = datetime.now(UTC)

        for order in open_orders:
            old_status = order.status
            result = asyncio.run(om.poll_status(db, order.id, user_id=order.user_id))
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

                # Attribute position to strategy when order fills
                if new_status == OrderStatus.FILLED.value:
                    _attribute_position_to_strategy(db, order)

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
        raise self.retry(exc=exc, countdown=2**self.request.retries)
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.portfolio.orders.sweep_stale_approvals",
    bind=True,
    time_limit=30,
    soft_time_limit=25,
    max_retries=1,
)
def sweep_stale_approvals(self) -> dict:
    """Auto-reject orders stuck in PENDING_APPROVAL beyond timeout."""
    from app.services.execution.approval_service import ApprovalService

    db = SessionLocal()
    try:
        expired = ApprovalService.expire_stale_approvals(db)
        return {"expired_count": len(expired), "orders": expired}
    except Exception as exc:
        logger.exception("sweep_stale_approvals raised")
        raise self.retry(exc=exc, countdown=10)
    finally:
        db.close()
