"""Pydantic models for `apis/brain/data/incidents.json`."""

from __future__ import annotations

from typing import Literal

from pydantic import UUID4, BaseModel, ConfigDict, Field

IncidentKind = Literal["brain-merge-revert", "ci-redness", "deploy-failure"]


class BrainMergeRevertIncident(BaseModel):
    """A Brain safety incident opened when post-merge main CI goes red."""

    incident_id: UUID4
    opened_at: str
    kind: IncidentKind = "brain-merge-revert"
    pr_number_reverted: int
    revert_pr_number: int
    ci_failure_run_url: str
    detected_at: str
    closed_at: str | None = None
    root_cause: str | None = None
    notes: str | None = None


class IncidentsFile(BaseModel):
    """Root document stored at ``incidents.json``."""

    model_config = ConfigDict(populate_by_name=True)

    incident_schema: str = Field(
        default="incidents/v1",
        alias="schema",
        description="Schema id for the incidents file (JSON key: schema).",
    )
    description: str = (
        "Operational incidents recorded by Brain automation. "
        "Rows are append-only unless an operator later enriches root_cause or notes."
    )
    incidents: list[BrainMergeRevertIncident] = Field(default_factory=list)
