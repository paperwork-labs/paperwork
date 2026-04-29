"""Pydantic models for Brain-generated workstream candidates (WS-63)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SourceSignal = Literal[
    "objective_gap",
    "pos_pillar_below_70",
    "procedural_rule_demand",
    "stack_audit_replace",
    "pr_outcome_regression",
]
EstimatedImpact = Literal["low", "medium", "high", "critical"]
CandidateStatus = Literal["proposed", "approved_to_workstream", "rejected", "superseded"]


class WorkstreamCandidate(BaseModel):
    """One Brain-generated workstream proposal awaiting founder review."""

    candidate_id: str = Field(..., min_length=1)
    proposed_at: datetime
    title: str = Field(..., min_length=3, max_length=100)
    why_now: str = Field(..., min_length=1)
    source_signal: SourceSignal
    source_ref: str = Field(..., min_length=1)
    estimated_effort_days: float = Field(..., ge=0)
    estimated_impact: EstimatedImpact
    score: float = Field(..., ge=0, le=100)
    status: CandidateStatus = "proposed"
    promoted_workstream_id: str | None = None
    founder_reason: str | None = None

    @field_validator("title")
    @classmethod
    def _title_max_100(cls, value: str) -> str:
        if len(value) > 100:
            raise ValueError("title must be <=100 chars")
        return value

    @field_validator("score")
    @classmethod
    def _score_bounds(cls, value: float) -> float:
        if value < 0 or value > 100:
            raise ValueError("score must be in [0, 100]")
        return value


class WorkstreamCandidatesFile(BaseModel):
    """Root document stored at ``apis/brain/data/workstream_candidates.json``."""

    model_config = ConfigDict(populate_by_name=True)

    candidate_schema: Literal["workstream_candidates/v1"] = Field(
        default="workstream_candidates/v1",
        alias="schema",
        serialization_alias="schema",
    )
    description: str = (
        "Brain-generated workstream proposals (Phase G2). Founder reviews + promotes "
        "to apps/studio/src/data/workstreams.json."
    )
    version: Literal[1] = 1
    generated_at: datetime | None = None
    candidates: list[WorkstreamCandidate] = Field(default_factory=list)
    history: list[WorkstreamCandidate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_candidate_ids(self) -> WorkstreamCandidatesFile:
        ids = [c.candidate_id for c in [*self.candidates, *self.history]]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate_id values must be unique across candidates and history")
        return self
