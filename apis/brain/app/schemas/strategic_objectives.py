from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Horizon = Literal["30d", "60d", "90d", "180d", "365d"]

_OBJECTIVE_ID_RE = re.compile(r"^[a-z0-9-]{3,80}$")


class StrategicObjectiveSchemaEntryDoc(BaseModel):
    """Inline schema documentation for OBJECTIVES.yaml (human / Brain)."""

    id: str
    objective: str
    horizon: str
    metric: str
    target: str
    review_cadence_days: str
    written_at: str
    notes: str


class StrategicObjectivesSchemaDoc(BaseModel):
    description: str
    entry: StrategicObjectiveSchemaEntryDoc


class StrategicObjective(BaseModel):
    id: str = Field(..., description="Kebab-case slug, 3-80 chars (a-z, 0-9, hyphen)")
    objective: str
    horizon: Horizon
    metric: str
    target: str
    review_cadence_days: int = Field(..., ge=1)
    written_at: datetime
    notes: str = ""

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        if not _OBJECTIVE_ID_RE.match(v):
            raise ValueError("id must match ^[a-z0-9-]{3,80}$")
        return v


class StrategicObjectivesFile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_docs: StrategicObjectivesSchemaDoc = Field(
        ...,
        alias="schema",
        serialization_alias="schema",
    )
    version: int = 1
    objectives: list[StrategicObjective] = Field(default_factory=list)
    last_reviewed_at: datetime | None = None
