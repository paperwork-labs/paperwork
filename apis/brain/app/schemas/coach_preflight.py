from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CoachPreflightRequest(BaseModel):
    action_type: Literal["dispatch", "merge", "plan", "deploy"]
    files_touched: list[str] = Field(default_factory=list, max_length=500)
    personas: list[str] = Field(default_factory=list, max_length=20)
    branch: str | None = Field(default=None, max_length=200)
    pr_number: int | None = None
    pr_path_globs: list[str] = Field(default_factory=list, max_length=50)


class MatchedRule(BaseModel):
    id: str
    confidence: Literal["low", "medium", "high"]
    do: str = Field(..., max_length=2000)
    when: str = Field(..., max_length=1000)
    rationale: str = Field(..., max_length=500)
    severity: Literal["info", "warning", "blocker"]


class RecentIncident(BaseModel):
    incident_id: str
    severity: str
    root_cause: str | None = None
    related_files: list[str] = Field(default_factory=list)
    learned_at: str


class CostPredict(BaseModel):
    vercel_builds_likely: int = 0
    vercel_build_min_estimate: float = 0.0
    agent_compute_estimate_usd: float = 0.0
    note: str | None = None


class CoachPreflightResponse(BaseModel):
    matched_rules: list[MatchedRule]
    recent_incidents: list[RecentIncident]
    predicted_cost: CostPredict
    warnings: list[str] = Field(default_factory=list)
    degraded: bool = False
    degraded_reason: str | None = None
