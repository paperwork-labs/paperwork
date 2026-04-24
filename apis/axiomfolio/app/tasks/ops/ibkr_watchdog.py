"""IB Gateway connection watchdog.

Runs every 5 minutes per ``job_catalog.py`` to detect and self-heal IB
Gateway disconnects. Skips silently when no enabled IBKR ``BrokerAccount``
exists for any user, because attempting ``_ensure_connected`` against
``127.0.0.1:7497`` in that case generates noisy ``SoftTimeLimitExceeded``
tracebacks every 5 minutes and serves no purpose.
"""

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _has_enabled_ibkr_account() -> bool:
    """Return True if at least one user has an enabled IBKR BrokerAccount.

    Failure to query the DB returns ``False`` so that the watchdog skips —
    a missed heartbeat is preferable to a misleading reconnection attempt
    against an unreachable gateway when configuration is unknown.
    """
    try:
        from app.database import SessionLocal
        from app.models.broker_account import BrokerAccount, BrokerType

        db = SessionLocal()
        try:
            row = (
                db.query(BrokerAccount.id)
                .filter(
                    BrokerAccount.broker == BrokerType.IBKR,
                    BrokerAccount.is_enabled.is_(True),
                )
                .first()
            )
            return row is not None
        finally:
            db.close()
    except Exception as e:
        logger.warning("ibkr_watchdog: account lookup failed, skipping ping: %s", e)
        return False


def _perform_ping() -> dict:
    """Implementation of the IB Gateway heartbeat. Pulled out of the Celery
    task wrapper so unit tests can call it without needing Celery binding."""
    if not _has_enabled_ibkr_account():
        logger.debug("ibkr_watchdog: no enabled IBKR account; skipping heartbeat")
        return {"status": "skipped", "reason": "no_enabled_ibkr_account"}

    from app.services.clients.ibkr_client import ibkr_client

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
            from app.services.notifications.order_notifications import (
                send_risk_alert,
            )

            asyncio.run(
                send_risk_alert(
                    "IB Gateway connection lost and reconnection failed",
                    {"symbol": "SYSTEM", "side": "N/A", "quantity": 0},
                )
            )
        except Exception as e:
            logger.warning("Failed to send IB Gateway disconnect alert: %s", e)
        return {"status": "disconnected"}
    except Exception as e:
        logger.error("IB Gateway watchdog error: %s", e)
        return {"status": "error", "error": str(e)}


@celery_app.task(
    bind=True,
    name="app.tasks.ibkr_watchdog.ping_ibkr_connection",
    soft_time_limit=30,
    time_limit=60,
)
def ping_ibkr_connection(self):
    """Ping IB Gateway each scheduled run (every 5 minutes per job_catalog); auto-reconnect on failure, Brain alert on persistent failure."""
    return _perform_ping()
