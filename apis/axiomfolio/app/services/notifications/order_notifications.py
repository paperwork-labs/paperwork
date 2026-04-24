"""Order-related notifications via Brain webhook.

medallion: ops
"""

import logging
from typing import Any, Dict, List

from app.services.brain.webhook_client import brain_webhook

logger = logging.getLogger(__name__)


def _user_id(order_data: Dict[str, Any]) -> int | None:
    raw = order_data.get("user_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


async def send_trade_execution(order_data: Dict[str, Any]) -> None:
    """Notify Brain when an order is filled or updated."""
    uid = _user_id(order_data)
    try:
        if uid is not None:
            await brain_webhook.trade_executed(order_data, uid)
        else:
            await brain_webhook.notify("trade_executed", order_data, user_id=None)
    except Exception as e:
        logger.warning("Failed to send trade notification to Brain: %s", e)


async def send_risk_alert(violation_msg: str, order_data: Dict[str, Any]) -> None:
    """Notify Brain when a risk gate blocks an order."""
    uid = _user_id(order_data)
    payload = {
        "violation": violation_msg,
        "order": order_data,
    }
    try:
        await brain_webhook.risk_gate_activated(payload, user_id=uid)
    except Exception as e:
        logger.warning("Failed to send risk alert to Brain: %s", e)


async def send_order_summary(orders: List[Dict[str, Any]], period: str = "daily") -> None:
    """Send a periodic order summary digest to Brain."""
    if not orders:
        return
    filled = [o for o in orders if o.get("status") == "filled"]
    cancelled = [o for o in orders if o.get("status") == "cancelled"]
    errored = [o for o in orders if o.get("status") in ("error", "rejected")]
    payload = {
        "period": period,
        "filled_count": len(filled),
        "cancelled_count": len(cancelled),
        "error_count": len(errored),
        "total_count": len(orders),
    }
    try:
        await brain_webhook.notify("order_summary", payload, user_id=None)
    except Exception as e:
        logger.warning("Failed to send order summary to Brain: %s", e)
