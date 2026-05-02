"""Pydantic schemas for the unified Employee surface (WS-82 PR-2a).

Covers create / update / response / list-item shapes for the employees table,
plus the parsed result from the naming ceremony LLM call.

medallion: brain
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — needed at runtime by Pydantic
from typing import Any

from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
    """Used for initial seeding and programmatic creation."""

    slug: str
    kind: str = Field(..., description="ai_persona | human | system")
    role_title: str
    team: str
    description: str
    default_model: str

    # Optional personality
    display_name: str | None = None
    tagline: str | None = None
    avatar_emoji: str | None = None
    voice_signature: str | None = None
    named_by_self: bool = True

    # Org graph
    reports_to: str | None = None
    manages: list[Any] = Field(default_factory=list)

    # Runtime config
    escalation_model: str | None = None
    escalate_if: list[Any] = Field(default_factory=list)
    requires_tools: bool = False
    daily_cost_ceiling_usd: float | None = None
    owner_channel: str | None = None
    mode: str | None = None
    tone_prefix: str | None = None
    proactive_cadence: str | None = None
    max_output_tokens: int | None = None
    requests_per_minute: int | None = None

    # Cursor IDE config
    cursor_description: str | None = None
    cursor_globs: list[Any] = Field(default_factory=list)
    cursor_always_apply: bool = False

    # Ownership
    owned_rules: list[Any] = Field(default_factory=list)
    owned_runbooks: list[Any] = Field(default_factory=list)
    owned_workflows: list[Any] = Field(default_factory=list)
    owned_skills: list[Any] = Field(default_factory=list)

    body_markdown: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmployeeUpdate(BaseModel):
    """Partial update — all fields optional. Includes founder name override."""

    kind: str | None = None
    role_title: str | None = None
    team: str | None = None

    # Naming ceremony fields (founder can override)
    display_name: str | None = None
    tagline: str | None = None
    avatar_emoji: str | None = None
    voice_signature: str | None = None
    named_by_self: bool | None = None

    # Org graph
    reports_to: str | None = None
    manages: list[Any] | None = None

    # Runtime config
    description: str | None = None
    default_model: str | None = None
    escalation_model: str | None = None
    escalate_if: list[Any] | None = None
    requires_tools: bool | None = None
    daily_cost_ceiling_usd: float | None = None
    owner_channel: str | None = None
    mode: str | None = None
    tone_prefix: str | None = None
    proactive_cadence: str | None = None
    max_output_tokens: int | None = None
    requests_per_minute: int | None = None

    # Cursor IDE config
    cursor_description: str | None = None
    cursor_globs: list[Any] | None = None
    cursor_always_apply: bool | None = None

    # Ownership
    owned_rules: list[Any] | None = None
    owned_runbooks: list[Any] | None = None
    owned_workflows: list[Any] | None = None
    owned_skills: list[Any] | None = None

    body_markdown: str | None = None
    metadata: dict[str, Any] | None = None


class EmployeeResponse(BaseModel):
    """Full employee detail — all fields."""

    slug: str
    kind: str
    role_title: str
    team: str

    display_name: str | None
    tagline: str | None
    avatar_emoji: str | None
    voice_signature: str | None
    named_at: datetime | None
    named_by_self: bool

    reports_to: str | None
    manages: list[Any]

    description: str
    default_model: str
    escalation_model: str | None
    escalate_if: list[Any]
    requires_tools: bool
    daily_cost_ceiling_usd: float | None
    owner_channel: str | None
    mode: str | None
    tone_prefix: str | None
    proactive_cadence: str | None
    max_output_tokens: int | None
    requests_per_minute: int | None

    cursor_description: str | None
    cursor_globs: list[Any]
    cursor_always_apply: bool

    owned_rules: list[Any]
    owned_runbooks: list[Any]
    owned_workflows: list[Any]
    owned_skills: list[Any]

    body_markdown: str | None

    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_row(cls, row: Any) -> EmployeeResponse:
        data = {c.key: getattr(row, c.key) for c in row.__table__.columns}
        # metadata_ -> metadata alias
        data["metadata"] = data.pop("metadata", {}) or {}
        return cls(**data)


class EmployeeListItem(BaseModel):
    """Compact representation for list views."""

    slug: str
    kind: str
    role_title: str
    team: str
    display_name: str | None
    tagline: str | None
    avatar_emoji: str | None
    named_at: datetime | None
    named_by_self: bool
    reports_to: str | None

    model_config = {"from_attributes": True}


class NamingCeremonyResult(BaseModel):
    """Parsed from LLM response during naming ceremony: Name | tagline | emoji."""

    display_name: str
    tagline: str
    avatar_emoji: str
