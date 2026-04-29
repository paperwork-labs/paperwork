"""Pydantic schemas for the decommissions data file (WS-48).

Schema version: decommissions/v1
Source of truth: apis/brain/data/decommissions.json
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — pydantic requires runtime availability
from typing import Literal

from pydantic import BaseModel, Field


class DecommissionEntry(BaseModel):
    """A single decommissioned (or proposed-to-decommission) entity."""

    id: str = Field(..., description="Unique slug, e.g. 'apps-paperworklabs-com'")
    domain: str = Field(..., description="Primary domain/subdomain being decommissioned")
    vercel_project: str | None = Field(None, description="Vercel project name/id if applicable")
    clerk_instance: str | None = Field(
        None, description="Clerk instance id if a dedicated one existed"
    )
    decommissioned_at: datetime | None = Field(
        None, description="UTC timestamp when decommission completed"
    )
    decommissioned_by: str | None = Field(None, description="GitHub login or 'brain' for automated")
    reason: str = Field(..., description="Human-readable rationale")
    status: Literal["proposed", "scheduled", "done"] = Field(
        ..., description="Current lifecycle stage"
    )
    notes: str = Field("", description="Additional context, links to PRs, runbooks, etc.")
    last_30d_traffic_check: datetime | None = Field(
        None, description="When last analytics check ran; null = not yet checked"
    )
    blockers: list[str] = Field(
        default_factory=list, description="Reasons decommission cannot proceed yet"
    )


class DecommissionsFile(BaseModel):
    """Top-level schema for decommissions.json."""

    schema_: str = Field("decommissions/v1", alias="schema")
    description: str = Field("")
    entries: list[DecommissionEntry] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
