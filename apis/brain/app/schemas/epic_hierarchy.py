"""Pydantic schemas for the Goal → Epic → Sprint → Task hierarchy CRUD API.

medallion: ops
"""

from __future__ import annotations

from datetime import date, datetime  # noqa: TC003 — needed at runtime by Pydantic
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Task schemas
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    status: str
    sprint_id: str | None = None
    epic_id: str | None = None
    github_pr: int | None = Field(None, gt=0)
    github_pr_url: str | None = None
    owner_employee_slug: str | None = None
    assignee: str | None = None
    brief_tag: str | None = None
    ordinal: int | None = None
    estimated_minutes: int | None = Field(None, gt=0)
    merged_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    sprint_id: str | None = None
    epic_id: str | None = None
    github_pr: int | None = None
    github_pr_url: str | None = None
    owner_employee_slug: str | None = None
    assignee: str | None = None
    brief_tag: str | None = None
    ordinal: int | None = None
    estimated_minutes: int | None = None
    merged_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    title: str
    status: str
    sprint_id: str | None
    epic_id: str | None
    github_pr: int | None
    github_pr_url: str | None
    owner_employee_slug: str | None
    assignee: str | None
    brief_tag: str | None
    ordinal: int | None
    estimated_minutes: int | None
    created_at: datetime
    merged_at: datetime | None
    metadata: dict[str, Any] = Field(alias="metadata_")


# ---------------------------------------------------------------------------
# Sprint schemas
# ---------------------------------------------------------------------------


class SprintCreate(BaseModel):
    id: str = Field(..., min_length=1)
    epic_id: str
    title: str = Field(..., min_length=1)
    goal: str | None = None
    status: str
    start_date: date | None = None
    end_date: date | None = None
    lead_employee_slug: str | None = None
    ordinal: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class SprintUpdate(BaseModel):
    title: str | None = None
    goal: str | None = None
    status: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    lead_employee_slug: str | None = None
    ordinal: int | None = None
    metadata: dict[str, Any] | None = None


class SprintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    epic_id: str
    title: str
    goal: str | None
    status: str
    start_date: date | None
    end_date: date | None
    lead_employee_slug: str | None
    ordinal: int
    metadata: dict[str, Any] = Field(alias="metadata_")
    tasks: list[TaskResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Epic schemas
# ---------------------------------------------------------------------------


class EpicCreate(BaseModel):
    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    goal_id: str | None = None
    owner_employee_slug: str
    status: str
    priority: int = Field(..., ge=0)
    percent_done: int = Field(0, ge=0, le=100)
    brief_tag: str
    description: str | None = None
    related_plan: str | None = None
    blockers: list[Any] = Field(default_factory=list)
    last_activity: datetime | None = None
    last_dispatched_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EpicUpdate(BaseModel):
    title: str | None = None
    goal_id: str | None = None
    owner_employee_slug: str | None = None
    status: str | None = None
    priority: int | None = None
    percent_done: int | None = Field(None, ge=0, le=100)
    brief_tag: str | None = None
    description: str | None = None
    related_plan: str | None = None
    blockers: list[Any] | None = None
    last_activity: datetime | None = None
    last_dispatched_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class EpicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    title: str
    goal_id: str | None
    owner_employee_slug: str
    status: str
    priority: int
    percent_done: int
    brief_tag: str
    description: str | None
    related_plan: str | None
    blockers: list[Any]
    last_activity: datetime | None
    last_dispatched_at: datetime | None
    created_at: datetime
    metadata: dict[str, Any] = Field(alias="metadata_")
    sprints: list[SprintResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Goal schemas
# ---------------------------------------------------------------------------


class GoalCreate(BaseModel):
    id: str = Field(..., min_length=1)
    objective: str = Field(..., min_length=1)
    horizon: str
    metric: str
    target: str
    status: str = "active"
    owner_employee_slug: str | None = None
    written_at: datetime
    review_cadence_days: int | None = Field(None, gt=0)
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GoalUpdate(BaseModel):
    objective: str | None = None
    horizon: str | None = None
    metric: str | None = None
    target: str | None = None
    status: str | None = None
    owner_employee_slug: str | None = None
    written_at: datetime | None = None
    review_cadence_days: int | None = None
    notes: str | None = None
    metadata: dict[str, Any] | None = None


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    objective: str
    horizon: str
    metric: str
    target: str
    status: str
    owner_employee_slug: str | None
    written_at: datetime
    review_cadence_days: int | None
    notes: str | None
    created_at: datetime
    metadata: dict[str, Any] = Field(alias="metadata_")
    epics: list[EpicResponse] = Field(default_factory=list)
