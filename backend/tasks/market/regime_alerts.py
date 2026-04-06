"""Real-time regime alert tasks."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import redis
from celery import shared_task

from backend.config import settings
from backend.database import SessionLocal
from backend.models.market_data import MarketRegime
from backend.services.market.regime_monitor import RegimeMonitor
from backend.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)

_REGIME_STATE_TTL_S = 172800  # 48h — covers holiday gaps


def _regime_redis() -> Optional[redis.Redis]:
    try:
        from backend.services.market.market_data_service import market_data_service
        return market_data_service.redis_client
    except Exception as e:
        logger.warning("Regime alerts Redis client failed: %s", e)
        return None


def _persist_regime_day_state(
    r: redis.Redis, day_key: str, vix_open: Optional[float], alerts_sent: set[str]
) -> None:
    prefix = f"regime_monitor:day:{day_key}"
    pipe = r.pipeline()
    if vix_open is not None:
        pipe.setex(f"{prefix}:vix_open", _REGIME_STATE_TTL_S, str(vix_open))
    pipe.delete(f"{prefix}:alerts_sent")
    if alerts_sent:
        pipe.sadd(f"{prefix}:alerts_sent", *alerts_sent)
        pipe.expire(f"{prefix}:alerts_sent", _REGIME_STATE_TTL_S)
    pipe.execute()


@shared_task(
    name="market.check_regime_alerts",
    time_limit=60,
    soft_time_limit=55,
)
@task_run("check_regime_alerts")
def check_regime_alerts() -> dict:
    """Check for regime alerts (run every 5 min during market hours).

    Returns dict with any alerts triggered.
    """
    db = SessionLocal()
    try:
        monitor = RegimeMonitor(db)
        day_key = datetime.now(timezone.utc).date().isoformat()
        r = _regime_redis()
        prefix = f"regime_monitor:day:{day_key}"
        vix_open: Optional[float] = None
        alerts_sent: set[str] = set()
        if r is not None:
            try:
                raw_open = r.get(f"{prefix}:vix_open")
                if raw_open is not None:
                    vix_open = float(raw_open)
                alerts_sent = set(r.smembers(f"{prefix}:alerts_sent") or [])
            except Exception as e:
                logger.warning("Failed to load regime monitor state from Redis: %s", e)
        monitor.restore_day_state(vix_open, alerts_sent)

        # Get current VIX (placeholder - would fetch from data provider)
        # For now, get from latest regime record
        latest = db.query(MarketRegime).order_by(MarketRegime.as_of_date.desc()).first()

        alerts = []

        if latest and latest.vix_spot is not None:
            current_vix = float(latest.vix_spot)
            if monitor.snapshot_day_state()[0] is None:
                monitor.set_vix_open(current_vix)
            vix_alerts = monitor.check_vix(current_vix)
            alerts.extend(vix_alerts)

        regime_alert = monitor.check_regime_shift()
        if regime_alert:
            alerts.append(regime_alert)

        if r is not None:
            try:
                vo, sent = monitor.snapshot_day_state()
                _persist_regime_day_state(r, day_key, vo, sent)
            except Exception as e:
                logger.warning("Failed to persist regime monitor state to Redis: %s", e)

        if alerts:
            logger.info("Regime alerts triggered: %d", len(alerts))
            for alert in alerts:
                logger.warning(
                    "ALERT [%s] %s: %s",
                    alert.severity.upper(),
                    alert.alert_type,
                    alert.message,
                )

            regime_shifts = [a for a in alerts if a.alert_type == "regime_shift"]
            if regime_shifts:
                from backend.services.brain.webhook_client import brain_webhook
                for shift in regime_shifts:
                    brain_webhook.notify_sync(
                        "regime_change",
                        {
                            "alert_type": shift.alert_type,
                            "severity": shift.severity,
                            "message": shift.message,
                            "current_value": shift.current_value,
                            "threshold": shift.threshold,
                        },
                    )

        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "alerts": [
                {
                    "type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message,
                    "value": a.current_value,
                }
                for a in alerts
            ],
        }
    finally:
        db.close()
