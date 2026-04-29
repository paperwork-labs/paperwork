"""Pydantic schemas for app_logs/v1 — Brain-owned application log ingestion (WS-69 PR M).

Brain is the first-class owner of all application logs. No third-party vendor.
Apps push high-signal events; Brain also pulls from Vercel/Render APIs hourly.

medallion: ops
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["debug", "info", "warn", "error", "critical"]

_SEVERITY_ORDER: dict[str, int] = {
    "debug": 0,
    "info": 1,
    "warn": 2,
    "error": 3,
    "critical": 4,
}


def severity_gte(severity: str, minimum: str) -> bool:
    """Return True when *severity* is at or above *minimum*."""
    return _SEVERITY_ORDER.get(severity, 0) >= _SEVERITY_ORDER.get(minimum, 0)


class AppLogEntry(BaseModel):
    id: str = Field(..., description="UUID — used for dedup on re-ingest")
    app: str = Field(
        ...,
        description="Logical application name, e.g. 'studio', 'brain', 'axiomfolio'",
    )
    service: str = Field(
        ...,
        description="Render service name or Vercel project slug that emitted the log",
    )
    severity: Severity = Field(..., description="Log severity level")
    message: str = Field(..., description="Human-readable log message")
    attrs: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Structured key-value attributes (request_id, user_id, duration_ms, …)",
    )
    source: Literal["push", "vercel-pull", "render-pull"] = Field(
        ...,
        description="How this entry arrived: pushed by app or pulled by Brain from a provider API",
    )
    occurred_at: datetime = Field(
        ...,
        description="When the event actually happened (timezone-aware UTC preferred)",
    )
    ingested_at: datetime = Field(
        ...,
        description="When Brain stored this entry",
    )


class AppLogsFile(BaseModel):
    schema_: str = Field(
        default="app_logs/v1",
        alias="schema",
        description="Schema version sentinel",
    )
    logs: list[AppLogEntry] = Field(default_factory=list)
    window_start: datetime | None = Field(
        None,
        description="Earliest occurred_at in the store after the last eviction",
    )
    window_end: datetime | None = Field(
        None,
        description="Latest occurred_at in the store",
    )
    last_anomaly_fire: dict[str, str] = Field(
        default_factory=dict,
        description="Idempotency map: '(app,service)' → ISO8601 last-fired timestamp",
    )

    model_config = {"populate_by_name": True}
