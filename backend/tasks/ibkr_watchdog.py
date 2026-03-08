"""IB Gateway connection watchdog."""
import asyncio
import logging

from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="backend.tasks.ibkr_watchdog.ping_ibkr_connection")
def ping_ibkr_connection(self):
    """Ping IB Gateway every 60s, auto-reconnect on failure, Discord alert on persistent failure."""
    from backend.services.clients.ibkr_client import ibkr_client

    try:
        connected = asyncio.run(ibkr_client._ensure_connected())
        if connected:
            logger.debug("IB Gateway heartbeat OK")
            return {"status": "ok"}

        logger.warning("IB Gateway connection failed, attempting reconnect...")
        asyncio.run(ibkr_client.disconnect())
        reconnected = asyncio.run(ibkr_client._ensure_connected())
        if reconnected:
            logger.info("IB Gateway reconnected successfully")
            return {"status": "reconnected"}

        logger.error("IB Gateway reconnection failed")
        try:
            from backend.services.notifications.order_notifications import (
                send_risk_alert,
            )

            asyncio.run(
                send_risk_alert(
                    "IB Gateway connection lost and reconnection failed",
                    {"symbol": "SYSTEM", "side": "N/A", "quantity": 0},
                )
            )
        except Exception:
            pass
        return {"status": "disconnected"}
    except Exception as e:
        logger.error("IB Gateway watchdog error: %s", e)
        return {"status": "error", "error": str(e)}
