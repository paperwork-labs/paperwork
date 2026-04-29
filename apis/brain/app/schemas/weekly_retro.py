"""Pydantic schemas for `apis/brain/data/weekly_retros.json`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RuleChangeAction = Literal["added", "revised", "deprecated"]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        msg = "datetime must be timezone-aware"
        raise ValueError(msg)
    return value.astimezone(UTC)


class RetroSummary(BaseModel):
    pos_total_change: float = Field(ge=-100, le=100)
    merges: int = Field(ge=0)
    reverts: int = Field(ge=0)
    incidents: int = Field(ge=0)
    candidates_proposed: int = Field(ge=0)
    candidates_promoted: int = Field(ge=0)


class RuleChange(BaseModel):
    action: RuleChangeAction
    rule_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class WeeklyRetro(BaseModel):
    week_ending: datetime
    computed_at: datetime
    summary: RetroSummary
    highlights: list[str] = Field(default_factory=list)
    rule_changes: list[RuleChange] = Field(default_factory=list)
    objective_progress: dict[str, float] = Field(default_factory=dict)
    notes: str = ""

    @field_validator("week_ending", "computed_at")
    @classmethod
    def _validate_datetime(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @field_validator("objective_progress")
    @classmethod
    def _validate_objective_progress(cls, value: dict[str, float]) -> dict[str, float]:
        for objective_id, progress in value.items():
            if not 0.0 <= progress <= 1.0:
                msg = f"objective progress for {objective_id!r} must be between 0.0 and 1.0"
                raise ValueError(msg)
        return value


class WeeklyRetrosFile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    retro_schema: str = Field(
        default="weekly_retros/v1",
        alias="schema",
        serialization_alias="schema",
    )
    description: str = (
        "Brain weekly retrospective — Phase G2 self-improvement loop. "
        "Each entry summarizes a 7-day window."
    )
    version: int = 1
    retros: list[WeeklyRetro] = Field(default_factory=list)
