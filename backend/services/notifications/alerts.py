from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

import requests

from backend.config import settings


def _discord_alias_map() -> Dict[str, Optional[str]]:
    return {
        "signals": settings.DISCORD_WEBHOOK_SIGNALS,
        "portfolio": settings.DISCORD_WEBHOOK_PORTFOLIO_DIGEST,
        "portfolio_digest": settings.DISCORD_WEBHOOK_PORTFOLIO_DIGEST,
        "morning": settings.DISCORD_WEBHOOK_MORNING_BREW,
        "morning_brew": settings.DISCORD_WEBHOOK_MORNING_BREW,
        "playground": settings.DISCORD_WEBHOOK_PLAYGROUND,
        "system": settings.DISCORD_WEBHOOK_SYSTEM_STATUS,
        "system_status": settings.DISCORD_WEBHOOK_SYSTEM_STATUS,
    }


DiscordDescriptor = Union[str, Sequence[str], None]


class AlertService:
    """Lightweight alert dispatcher for Discord webhooks + Prometheus push endpoints."""

    def __init__(self, http_client: Optional[Any] = None) -> None:
        self.http = http_client or requests.Session()
        self.logger = logging.getLogger(__name__)

    def _iter_descriptor_tokens(self, descriptor: DiscordDescriptor) -> Iterable[str]:
        if descriptor is None:
            return []
        if isinstance(descriptor, str):
            return [descriptor]
        tokens: List[str] = []
        for item in descriptor:
            if item is None:
                continue
            tokens.append(str(item))
        return tokens

    def _resolve_discord_targets(self, descriptor: DiscordDescriptor) -> List[str]:
        tokens: List[str] = []
        for raw in self._iter_descriptor_tokens(descriptor):
            for segment in str(raw).split(","):
                segment = segment.strip()
                if segment:
                    tokens.append(segment)
        if not tokens:
            return []
        aliases = _discord_alias_map()
        urls: List[str] = []
        for token in tokens:
            if token.lower().startswith("http"):
                urls.append(token)
                continue
            key = token.replace("-", "_").lower()
            resolved = aliases.get(key)
            if resolved:
                urls.append(resolved)
        return [url for url in urls if url]

    def send_discord(
        self,
        descriptor: DiscordDescriptor,
        title: str,
        description: str,
        *,
        fields: Optional[Dict[str, str]] = None,
        severity: str = "info",
    ) -> bool:
        urls = self._resolve_discord_targets(descriptor)
        if not urls:
            return False

        color_map = {"info": 0x3B82F6, "warning": 0xF59E0B, "error": 0xEF4444}
        embed = {
            "title": title[:256],
            "description": description[:1800],
            "color": color_map.get(severity, color_map["info"]),
        }
        if fields:
            embed["fields"] = [{"name": k[:256], "value": str(v)[:1024]} for k, v in fields.items()]

        payload = {"embeds": [embed]}
        success = False
        for url in urls:
            try:
                response = self.http.post(url, json=payload, timeout=5)
                response.raise_for_status()
                success = True
            except Exception as exc:  # pragma: no cover - best effort logging
                self.logger.warning("Failed to post Discord alert: %s", exc)
        return success

    def push_prometheus_metric(
        self,
        endpoint: Optional[str],
        metric: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
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


__all__ = ["AlertService", "alert_service"]

