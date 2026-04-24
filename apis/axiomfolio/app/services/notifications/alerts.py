"""medallion: ops"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from typing import Any, Union

import requests

from app.services.brain.webhook_client import BrainWebhookClient, brain_webhook

AlertDescriptor = Union[str, Sequence[str], None]


class AlertService:
    """Ops alert dispatcher: Brain webhook + optional Prometheus push."""

    def __init__(
        self,
        http_client: Any | None = None,
        brain: BrainWebhookClient | None = None,
    ) -> None:
        self.http = http_client or requests.Session()
        self._brain = brain or brain_webhook
        self.logger = logging.getLogger(__name__)

    def _iter_descriptor_tokens(self, descriptor: AlertDescriptor) -> Iterable[str]:
        if descriptor is None:
            return []
        if isinstance(descriptor, str):
            return [descriptor]
        tokens: list[str] = []
        for item in descriptor:
            if item is None:
                continue
            tokens.append(str(item))
        return tokens

    def send_alert(
        self,
        descriptor: AlertDescriptor,
        title: str,
        description: str,
        *,
        fields: dict[str, str] | None = None,
        severity: str = "info",
    ) -> bool:
        """Send an operational alert to Brain (descriptor tokens are included as routing metadata)."""
        channels = list(self._iter_descriptor_tokens(descriptor))
        if not channels:
            return False
        if not self._brain.webhook_url:
            self.logger.debug("Brain webhook not configured, skipping ops alert")
            return False

        data: dict[str, Any] = {
            "title": title[:256],
            "description": description[:8000],
            "severity": severity,
            "channels": channels,
        }
        if fields:
            data["fields"] = fields

        return self._brain.notify_sync("ops_alert", data, user_id=None)

    def push_prometheus_metric(
        self,
        endpoint: str | None,
        metric: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> bool:
        if not endpoint:
            return False
        label_str = ""
        if labels:
            parts = [f'{key}="{value}"' for key, value in labels.items()]
            label_str = "{%s}" % ",".join(parts)
        body = f"# TYPE {metric} gauge\n{metric}{label_str} {value}\n"
        try:
            resp = self.http.post(
                endpoint,
                data=body,
                timeout=5,
                headers={"Content-Type": "text/plain"},
            )
            resp.raise_for_status()
            return True
        except Exception as exc:  # pragma: no cover - best effort logging
            self.logger.warning("Failed to push Prometheus metric: %s", exc)
            return False


alert_service = AlertService()

__all__ = ["AlertDescriptor", "AlertService", "alert_service"]
