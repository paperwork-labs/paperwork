"""Pydantic models for Brain-owned application logs (WS-69 PR M).

Stored at ``apis/brain/data/app_logs.json``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AppName = Literal["studio", "axiomfolio", "filefree", "launchfree", "distill", "brain"]
Severity = Literal["debug", "info", "warn", "error", "critical"]
LogSource = Literal["push", "pull"]


class AppLog(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="UUID v4")
    app: AppName
    service: str = Field(description="e.g. 'vercel-prod', 'render-brain-api'")
    severity: Severity
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
    at: datetime
    source: LogSource


class AppLogsFile(BaseModel):
    """Root document stored at ``app_logs.json``."""

    model_config = ConfigDict(populate_by_name=True)

    log_schema: str = Field(
        default="app_logs/v1",
        alias="schema",
        description="Schema id (JSON key: schema).",
    )
    description: str = (
        "Brain-owned application logs (WS-69). "
        "Capped at 5000 entries; oldest entries are dropped when the cap is reached."
    )
    logs: list[AppLog] = Field(default_factory=list)
    last_pulled_at: dict[str, str] = Field(
        default_factory=dict,
        description="Per-source ISO8601 timestamp of last successful pull.",
    )


class AppLogIngestRequest(BaseModel):
    """Payload accepted by POST /admin/logs/ingest (server fills id, source, at if absent)."""

    app: AppName
    service: str
    severity: Severity
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
    at: datetime | None = Field(
        default=None,
        description="If omitted the server uses UTC now.",
    )


class AppLogsListPage(BaseModel):
    logs: list[AppLog]
    total_matched: int
    next_cursor: str | None = None


class Anomaly(BaseModel):
    kind: str
    description: str
    severity: Severity
    affected_app: AppName | None = None
    affected_service: str | None = None
    sample_log_ids: list[str] = Field(default_factory=list)
