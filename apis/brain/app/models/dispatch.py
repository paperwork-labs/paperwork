"""Pydantic models for autopilot dispatch entries and results.

medallion: ops
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

DispatchSource = Literal["probe", "goal", "manual"]
DispatchStatus = Literal[
    "pending",
    "dispatched",
    "completed",
    "failed",
]


class DispatchEntry(BaseModel):
    """A single work item queued for autopilot dispatch."""

    task_id: str
    source: DispatchSource
    description: str = ""
    product: str = ""
    persona_id: str = ""
    agent_model: str = "cheap"
    status: DispatchStatus = "pending"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    dispatched_at: datetime | None = None


class DispatchResult(BaseModel):
    """Outcome record appended to agent_dispatch_log.jsonl."""

    task_id: str
    persona_id: str
    agent_model: str
    pr_number: int | None = None
    outcome: str = ""
    duration_ms: int = 0
