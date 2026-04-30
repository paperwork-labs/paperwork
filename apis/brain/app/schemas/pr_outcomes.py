"""Pydantic models for `apis/brain/data/pr_outcomes.json` (WS-62)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

HorizonLagging = Literal["d7", "d14", "d30"]


class OutcomeH1H24(BaseModel):
    """CI, deploy, and revert flags at the 1h or 24h horizon."""

    ci_pass: bool
    deploy_success: bool
    reverted: bool


class OutcomeLaggingHorizon(BaseModel):
    """Objective-relevant metrics at 7d / 14d / 30d horizons."""

    objective_metric_delta: dict[str, float] = Field(default_factory=dict)


class PrOutcomesOutcomes(BaseModel):
    h1: OutcomeH1H24 | None = None
    h24: OutcomeH1H24 | None = None
    d7: OutcomeLaggingHorizon | None = None
    d14: OutcomeLaggingHorizon | None = None
    d30: OutcomeLaggingHorizon | None = None


class PrOutcome(BaseModel):
    pr_number: int
    merged_at: str
    merged_by_agent: str
    agent_model: str
    subagent_type: str
    branch: str = ""
    ci_status_at_merge: str = "unknown"
    workstream_ids: list[str] = Field(default_factory=list)
    workstream_types: list[str] = Field(default_factory=list)
    outcomes: PrOutcomesOutcomes = Field(default_factory=PrOutcomesOutcomes)


class PrOutcomesFile(BaseModel):
    """Root document stored at ``pr_outcomes.json``."""

    model_config = ConfigDict(populate_by_name=True)

    pr_schema: str = Field(
        default="pr_outcomes/v1",
        alias="schema",
        description="Schema id for the outcomes file (JSON key: schema).",
    )
    description: str = (
        "Per-merged-PR outcome measurements (WS-62). "
        "Appended on merge; horizon fields filled over time."
    )
    outcomes: list[PrOutcome] = Field(default_factory=list)
