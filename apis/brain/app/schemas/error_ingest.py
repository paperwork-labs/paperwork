"""Schemas for unified Paperwork error ingestion."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ErrorEnv = Literal["production", "preview"]
ErrorSeverity = Literal["error", "warning"]


class ErrorIngestRequest(BaseModel):
    product: str = Field(..., min_length=1)
    env: ErrorEnv
    message: str = Field(..., min_length=1)
    stack: str | None = None
    url: str | None = None
    user_agent: str | None = None
    severity: ErrorSeverity
    context: dict[str, Any] | None = None
    fingerprint: str | None = Field(default=None, min_length=1)


class ErrorIngestRecord(ErrorIngestRequest):
    id: str
    ingested_at: datetime
    fingerprint: str


class ErrorIngestResponse(BaseModel):
    success: bool
    fingerprint: str
    id: str


class ErrorAggregate(BaseModel):
    fingerprint: str
    count: int
    first_seen: datetime
    last_seen: datetime
    products_affected: list[str]
    message: str
    severity: ErrorSeverity


class ErrorAggregatesFile(BaseModel):
    schema_: str = Field(default="error_aggregates/v1", alias="schema")
    fingerprints: dict[str, ErrorAggregate] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}
