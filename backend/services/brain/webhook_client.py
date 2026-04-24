"""Webhook client for notifying Brain of AxiomFolio events.

medallion: ops
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


class BrainWebhookClient:
    """Client for sending webhooks to Paperwork Brain."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def webhook_url(self) -> Optional[str]:
        return getattr(settings, "BRAIN_WEBHOOK_URL", None)

    @property
    def webhook_secret(self) -> Optional[str]:
        return getattr(settings, "BRAIN_WEBHOOK_SECRET", None)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    def _sign(self, body_bytes: bytes) -> Dict[str, str]:
        """Compute HMAC-SHA256 signature over body and return auth headers."""
        headers: Dict[str, str] = {}
        if self.webhook_secret:
            sig = hmac.new(
                self.webhook_secret.encode(),
                body_bytes,
                hashlib.sha256,
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={sig}"
        return headers

    async def notify(
        self,
        event: str,
        data: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> bool:
        """Send event to Brain webhook."""
        if not self.webhook_url:
            logger.debug("Brain webhook not configured, skipping notification")
            return False

        payload = {
            "event": event,
            "data": data,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "axiomfolio",
        }

        body_bytes = json.dumps(payload, default=str).encode()
        headers = self._sign(body_bytes)
        headers["Content-Type"] = "application/json"

        try:
            client = await self._get_client()
            base_url = self.webhook_url.rstrip("/")
            response = await client.post(
                f"{base_url}/api/v1/webhooks/axiomfolio",
                content=body_bytes,
                headers=headers,
            )
            if response.status_code >= 400:
                logger.warning(
                    "Brain webhook failed: %s %s",
                    response.status_code,
                    response.text[:200],
                )
                return False
            logger.info("Brain webhook sent: %s", event)
            return True
        except Exception as e:
            logger.warning("Brain webhook error: %s", e)
            return False

    def notify_sync(
        self,
        event: str,
        data: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> bool:
        """Same as notify() using a synchronous HTTP client (Celery / sync callers)."""
        if not self.webhook_url:
            logger.debug("Brain webhook not configured, skipping notification")
            return False

        payload = {
            "event": event,
            "data": data,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "axiomfolio",
        }

        body_bytes = json.dumps(payload, default=str).encode()
        headers = self._sign(body_bytes)
        headers["Content-Type"] = "application/json"

        try:
            base_url = self.webhook_url.rstrip("/")
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{base_url}/api/v1/webhooks/axiomfolio",
                    content=body_bytes,
                    headers=headers,
                )
            if response.status_code >= 400:
                logger.warning(
                    "Brain webhook failed: %s %s",
                    response.status_code,
                    response.text[:200],
                )
                return False
            logger.info("Brain webhook sent: %s", event)
            return True
        except Exception as e:
            logger.warning("Brain webhook error: %s", e)
            return False

    # Convenience methods for common events
    async def trade_executed(self, order_data: Dict[str, Any], user_id: int) -> bool:
        return await self.notify("trade_executed", order_data, user_id)

    async def position_closed(self, position_data: Dict[str, Any], user_id: int) -> bool:
        return await self.notify("position_closed", position_data, user_id)

    async def stop_triggered(self, order_data: Dict[str, Any], user_id: int) -> bool:
        return await self.notify("stop_triggered", order_data, user_id)

    async def risk_gate_activated(self, risk_data: Dict[str, Any], user_id: Optional[int] = None) -> bool:
        return await self.notify("risk_gate_activated", risk_data, user_id)

    async def scan_alert(self, scan_data: Dict[str, Any], user_id: Optional[int] = None) -> bool:
        return await self.notify("scan_alert", scan_data, user_id)

    async def regime_change(self, regime_data: Dict[str, Any], user_id: Optional[int] = None) -> bool:
        return await self.notify("regime_change", regime_data, user_id)

    async def exit_alert(self, exit_data: Dict[str, Any], user_id: Optional[int] = None) -> bool:
        return await self.notify("exit_alert", exit_data, user_id)

    async def approval_required(self, order_data: Dict[str, Any], user_id: int) -> bool:
        return await self.notify("approval_required", order_data, user_id)

    async def approval_expired(self, data: Dict[str, Any], user_id: Optional[int] = None) -> bool:
        return await self.notify("approval_expired", data, user_id)


# Singleton instance
brain_webhook = BrainWebhookClient()
