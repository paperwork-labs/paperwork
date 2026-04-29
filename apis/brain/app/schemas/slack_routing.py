"""Pydantic models for slack_routing.yaml.

medallion: ops
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Severity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


_SEVERITY_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2}


def severity_gte(a: str, threshold: str) -> bool:
    """Return True when severity *a* is greater than or equal to *threshold*."""
    return _SEVERITY_ORDER.get(a, 0) >= _SEVERITY_ORDER.get(threshold, 0)


class QuietHours(BaseModel):
    start: str = "22:00"
    end: str = "09:00"
    timezone: str = "UTC"
    weekends_quiet: bool = True

    @field_validator("start", "end", mode="before")
    @classmethod
    def _validate_time(cls, v: Any) -> str:
        if not isinstance(v, str) or len(v) != 5 or v[2] != ":":
            raise ValueError(f"Time must be HH:MM, got {v!r}")
        h, m = v.split(":")
        if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
            raise ValueError(f"Invalid time {v!r}")
        return v


class SlackRoutingConfig(BaseModel):
    schema_: str = Field("slack_routing/v1", alias="schema")
    description: str = ""
    default_channel: str = "#ops"
    channels: dict[str, str] = Field(default_factory=dict)
    dedup_window_minutes: int = 60
    rate_limit_per_hour: int = 30
    quiet_hours: QuietHours = Field(default_factory=QuietHours)
    quiet_severity_threshold: str = "high"

    model_config = {"populate_by_name": True}

    def channel_for(self, event_type: str) -> str:
        return self.channels.get(event_type, self.default_channel)


class RoutingAction(StrEnum):
    new_post = "new_post"
    thread_reply = "thread_reply"
    defer_to_digest = "defer_to_digest"
    defer_to_morning = "defer_to_morning"


class RoutingDecision(BaseModel):
    action: RoutingAction
    channel: str
    thread_ts: str | None = None
    reason: str = ""
    dedup_key: str = ""
