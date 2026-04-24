from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import redis
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)

META_KEY_TEMPLATE = "redbeat:meta:{name}"


def meta_key(name: str) -> str:
    return META_KEY_TEMPLATE.format(name=name)


class MaintenanceWindow(BaseModel):
    """Defines an allowed run window (ISO8601 strings)."""

    start: str
    end: str
    timezone: str = "UTC"


class SafetyConfig(BaseModel):
    """Execution guard rails that can be enforced before dispatch."""

    singleflight: bool = True
    max_concurrency: int = 1
    timeout_s: int = 3600
    retries: int = 0
    backoff_s: int = 0


class HookConfig(BaseModel):
    """Optional alert hooks (Brain ops_alert + Prometheus).

    Fields ``discord_*`` are legacy JSON keys from RedBeat metadata; values are sent as routing metadata on Brain ``ops_alert``, not to Discord URLs.
    """

    discord_webhook: str | None = None
    discord_channels: list[str] = Field(default_factory=list)
    discord_mentions: list[str] = Field(default_factory=list)
    prometheus_endpoint: str | None = None
    alert_on: list[str] = Field(default_factory=lambda: ["failure"])
    slow_threshold_s: float | None = None


class ScheduleMetadata(BaseModel):
    """Rich metadata persisted alongside each RedBeat schedule."""

    queue: str | None = None
    priority: int | None = None
    dependencies: list[str] = Field(default_factory=list)
    maintenance_windows: list[MaintenanceWindow] = Field(default_factory=list)
    preflight_checks: list[str] = Field(default_factory=list)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    hooks: HookConfig = Field(default_factory=HookConfig)
    notes: str | None = None
    audit: dict[str, Any] = Field(default_factory=dict)

    def touch_audit(self, actor: str, *, is_create: bool = False) -> None:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        audit = dict(self.audit or {})
        if is_create or "created_at" not in audit:
            audit["created_at"] = now
            audit["created_by"] = actor
        audit["updated_at"] = now
        audit["updated_by"] = actor
        self.audit = audit


class ScheduleMetadataPatch(BaseModel):
    """Partial metadata payload used when creating/updating via API."""

    queue: str | None = None
    priority: int | None = None
    dependencies: list[str] | None = None
    maintenance_windows: list[MaintenanceWindow] | None = None
    preflight_checks: list[str] | None = None
    safety: SafetyConfig | None = None
    hooks: HookConfig | None = None
    notes: str | None = None

    def apply(self, base: ScheduleMetadata | None) -> ScheduleMetadata:
        data: dict[str, Any] = {}
        if base is not None:
            data.update(base.model_dump())
        payload = self.model_dump(exclude_unset=True)
        # Nested models need special handling to convert to dict
        if "safety" in payload and isinstance(payload["safety"], SafetyConfig):
            payload["safety"] = payload["safety"].dict()
        if "hooks" in payload and isinstance(payload["hooks"], HookConfig):
            payload["hooks"] = payload["hooks"].dict()
        data.update(payload)
        return ScheduleMetadata(**data)


def metadata_to_options(meta: ScheduleMetadata | None) -> dict[str, Any]:
    """Translate metadata into Celery apply_async options."""
    if not meta:
        return {}
    options: dict[str, Any] = {}
    if meta.queue:
        options["queue"] = meta.queue
    if meta.priority is not None:
        options["priority"] = meta.priority
    # Propagate metadata for workers that want to inspect headers
    options["headers"] = {"schedule_metadata": meta.model_dump()}
    return options


def _redis_client(client: redis.Redis | None = None) -> redis.Redis:
    if client:
        return client
    url = getattr(settings, "CELERY_BROKER_URL", None) or getattr(settings, "REDIS_URL", None)
    return redis.from_url(url)


def load_schedule_metadata(
    name: str, client: redis.Redis | None = None
) -> ScheduleMetadata | None:
    """Load metadata blob for a schedule if present."""
    try:
        raw = _redis_client(client).get(meta_key(name))
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return ScheduleMetadata(**data)
    except Exception:
        return None


def save_schedule_metadata(
    name: str, meta: ScheduleMetadata | None, *, client: redis.Redis | None = None
) -> None:
    """Persist metadata blob; delete key if meta is None."""
    store = _redis_client(client)
    try:
        if meta is None:
            store.delete(meta_key(name))
            return
        store.set(meta_key(name), json.dumps(meta.model_dump()))
    except Exception as e:
        logger.warning("save_schedule_metadata failed for %s: %s", name, e)


def delete_schedule_metadata(name: str, client: redis.Redis | None = None) -> None:
    save_schedule_metadata(name, None, client=client)


__all__ = [
    "HookConfig",
    "MaintenanceWindow",
    "SafetyConfig",
    "ScheduleMetadata",
    "ScheduleMetadataPatch",
    "delete_schedule_metadata",
    "load_schedule_metadata",
    "meta_key",
    "metadata_to_options",
    "save_schedule_metadata",
]
