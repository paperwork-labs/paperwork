"""Pydantic models for cheap-agent task specs and sprint bundles."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AgentType = Literal["shell", "generalPurpose", "browser-use"]
ModelHint = Literal["composer-2-fast", "gpt-5.5-medium"]
SourceKind = Literal["pr", "issue", "founder-action", "tracker"]


class AgentTaskSpec(BaseModel):
    task_id: str
    title: str = Field(..., max_length=80)
    scope: str
    estimated_minutes: int
    agent_type: AgentType
    model_hint: ModelHint
    depends_on: list[str] = Field(default_factory=list)
    touches_paths: list[str] = Field(default_factory=list)
    source: dict[str, Any]


class AgentSprintRecord(BaseModel):
    sprint_id: str
    generated_at: str
    timezone: str
    tasks: list[AgentTaskSpec]
    total_minutes: int
    parallelizability_score: float
    status: Literal["pending_review", "dispatched", "completed", "superseded"] = "pending_review"


class AgentSprintDayMetrics(BaseModel):
    tasks_generated_today: int
    sprints_generated_today: int
    average_sprint_size: float
