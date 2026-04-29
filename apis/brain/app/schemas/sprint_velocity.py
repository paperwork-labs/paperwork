"""Pydantic models for `apis/brain/data/sprint_velocity.json` (WS-51)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

_HISTORY_MAX_WEEKS = 26
_SCHEMA_KEY = "schema"


class ByAuthor(BaseModel):
    founder: int = Field(default=0, ge=0)
    brain_self_dispatch: int = Field(default=0, ge=0, alias="brain-self-dispatch")
    cheap_agent: int = Field(default=0, ge=0, alias="cheap-agent")

    model_config = ConfigDict(populate_by_name=True)


class SprintVelocityEntry(BaseModel):
    week_start: str
    week_end: str
    prs_merged: int = Field(default=0, ge=0)
    by_author: ByAuthor = Field(default_factory=ByAuthor)
    workstreams_completed: int = Field(default=0, ge=0)
    workstreams_completed_estimated_pr_count: int = Field(default=0, ge=0)
    story_points_burned: int = Field(default=0, ge=0)
    throughput_per_day: float = Field(default=0.0, ge=0.0)
    measured: bool = True
    notes: str = ""
    computed_at: str


class SprintVelocityFile(BaseModel):
    """Root JSON at ``sprint_velocity.json``."""

    model_config = ConfigDict(populate_by_name=True)

    sv_schema: str = Field(
        default="sprint_velocity/v1",
        alias=_SCHEMA_KEY,
        description="Schema id (JSON key: schema).",
    )
    description: str = (
        "Weekly sprint velocity computed from PR merge cadence + workstream completions (WS-51)."
    )
    current: SprintVelocityEntry | None = None
    history: list[SprintVelocityEntry] = Field(default_factory=list)

    @field_validator("history", mode="before")
    @classmethod
    def _history_list(cls, v: object) -> object:
        if v is None:
            return []
        return v

    def bounded_history(self) -> list[SprintVelocityEntry]:
        """Return history bounded to ``_HISTORY_MAX_WEEKS`` entries (oldest dropped)."""
        return list(self.history[-_HISTORY_MAX_WEEKS:])
