"""Deliver intelligence briefs to Brain webhook.

medallion: silver
"""

from __future__ import annotations

import logging
from typing import Any

from backend.services.brain.webhook_client import brain_webhook

logger = logging.getLogger(__name__)


async def deliver_daily_digest_brain(brief: dict[str, Any]) -> bool:
    """Send the daily digest payload to Brain."""
    if not brain_webhook.webhook_url:
        logger.info("No BRAIN_WEBHOOK_URL configured, skipping daily digest delivery")
        return False
    try:
        ok = await brain_webhook.notify("daily_digest", brief, user_id=None)
        if ok:
            logger.info("Daily digest delivered to Brain")
        return ok
    except Exception as e:
        logger.error("Brain digest delivery failed: %s", e)
        return False


async def deliver_weekly_brief_brain(brief: dict[str, Any]) -> bool:
    """Send the weekly brief payload to Brain."""
    if not brain_webhook.webhook_url:
        logger.info("No BRAIN_WEBHOOK_URL configured, skipping weekly brief delivery")
        return False
    try:
        ok = await brain_webhook.notify("weekly_brief", brief, user_id=None)
        if ok:
            logger.info("Weekly brief delivered to Brain")
        return ok
    except Exception as e:
        logger.error("Brain weekly brief delivery failed: %s", e)
        return False


# Backward-compatible names for Celery task signatures / callers
deliver_daily_digest_discord = deliver_daily_digest_brain
deliver_weekly_brief_discord = deliver_weekly_brief_brain
