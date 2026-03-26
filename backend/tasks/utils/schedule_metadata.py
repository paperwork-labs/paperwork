from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import json

import redis
from pydantic import BaseModel, Field

from backend.config import settings


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
    """Optional alert integrations."""

    discord_webhook: Optional[str] = None
    discord_channels: List[str] = Field(default_factory=list)
    discord_mentions: List[str] = Field(default_factory=list)
    prometheus_endpoint: Optional[str] = None
    alert_on: List[str] = Field(default_factory=lambda: ["failure"])
    slow_threshold_s: Optional[float] = None


class ScheduleMetadata(BaseModel):
    """Rich metadata persisted alongside each RedBeat schedule."""

    queue: Optional[str] = None
    priority: Optional[int] = None
    dependencies: List[str] = Field(default_factory=list)
    maintenance_windows: List[MaintenanceWindow] = Field(default_factory=list)
    preflight_checks: List[str] = Field(default_factory=list)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    hooks: HookConfig = Field(default_factory=HookConfig)
    notes: Optional[str] = None
    audit: Dict[str, Any] = Field(default_factory=dict)

    def touch_audit(self, actor: str, *, is_create: bool = False) -> None:
        now = datetime.utcnow().isoformat() + "Z"
        audit = dict(self.audit or {})
        if is_create or "created_at" not in audit:
            audit["created_at"] = now
            audit["created_by"] = actor
        audit["updated_at"] = now
        audit["updated_by"] = actor
        self.audit = audit


class ScheduleMetadataPatch(BaseModel):
    """Partial metadata payload used when creating/updating via API."""

    queue: Optional[str] = None
    priority: Optional[int] = None
    dependencies: Optional[List[str]] = None
    maintenance_windows: Optional[List[MaintenanceWindow]] = None
    preflight_checks: Optional[List[str]] = None
    safety: Optional[SafetyConfig] = None
    hooks: Optional[HookConfig] = None
    notes: Optional[str] = None

    def apply(self, base: ScheduleMetadata | None) -> ScheduleMetadata:
        data: Dict[str, Any] = {}
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


def metadata_to_options(meta: ScheduleMetadata | None) -> Dict[str, Any]:
    """Translate metadata into Celery apply_async options."""
    if not meta:
        return {}
    options: Dict[str, Any] = {}
    if meta.queue:
        options["queue"] = meta.queue
    if meta.priority is not None:
        options["priority"] = meta.priority
    # Propagate metadata for workers that want to inspect headers
    options["headers"] = {"schedule_metadata": meta.model_dump()}
    return options


def _redis_client(client: Optional[redis.Redis] = None) -> redis.Redis:
    if client:
        return client
    url = getattr(settings, "CELERY_BROKER_URL", None) or getattr(settings, "REDIS_URL", None)
    return redis.from_url(url)


def load_schedule_metadata(name: str, client: Optional[redis.Redis] = None) -> Optional[ScheduleMetadata]:
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
    name: str, meta: Optional[ScheduleMetadata], *, client: Optional[redis.Redis] = None
) -> None:
    """Persist metadata blob; delete key if meta is None."""
    store = _redis_client(client)
    try:
        if meta is None:
            store.delete(meta_key(name))
            return
        store.set(meta_key(name), json.dumps(meta.model_dump()))
    except Exception:
        pass


def delete_schedule_metadata(name: str, client: Optional[redis.Redis] = None) -> None:
    save_schedule_metadata(name, None, client=client)


__all__ = [
    "HookConfig",
    "MaintenanceWindow",
    "ScheduleMetadata",
    "ScheduleMetadataPatch",
    "SafetyConfig",
    "delete_schedule_metadata",
    "load_schedule_metadata",
    "meta_key",
    "metadata_to_options",
    "save_schedule_metadata",
]

