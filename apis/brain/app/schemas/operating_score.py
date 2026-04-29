"""Pydantic models for `operating_score_spec.yaml` and `operating_score.json` (WS-66)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SCHEMA_KEY = "schema"


class SpecSchemaBlock(BaseModel):
    """Top-level ``schema:`` block in ``operating_score_spec.yaml``."""

    description: str


class GateL4(BaseModel):
    min_total: float | int
    min_pillar: float | int


class GateL5(BaseModel):
    min_total: float | int
    sustained_weeks: int = Field(ge=1)


class GraduationGates(BaseModel):
    l4: GateL4
    l5: GateL5


class Pillar(BaseModel):
    id: str = Field(min_length=1)
    weight: int = Field(ge=0, le=100)
    industry_reference: str = ""
    target: int | float = 80
    measurement_source: str = ""
    description: str = ""


class OperatingScoreSpec(BaseModel):
    """Loaded from ``apis/brain/data/operating_score_spec.yaml``."""

    model_config = ConfigDict(populate_by_name=True)

    spec_schema: SpecSchemaBlock = Field(alias=_SCHEMA_KEY)
    version: int = 1
    target_total: int | float = 90
    graduation_gates: GraduationGates
    pillars: list[Pillar]

    @model_validator(mode="after")
    def _pillar_weights_sum_one_hundred(self) -> OperatingScoreSpec:
        s = sum(p.weight for p in self.pillars)
        if s != 100:
            msg = f"Pillar weights must sum to 100 (got {s})"
            raise ValueError(msg)
        return self


class PillarScore(BaseModel):
    score: float = Field(ge=0, le=100)
    weight: int = Field(ge=0, le=100)
    weighted: float = Field(ge=0, le=100)
    measured: bool
    notes: str = ""


class ScoreGates(BaseModel):
    l4_pass: bool
    l5_pass: bool
    lowest_pillar: str


class OperatingScoreEntry(BaseModel):
    computed_at: str
    total: float
    pillars: dict[str, PillarScore]
    gates: ScoreGates


class OperatingScoreFile(BaseModel):
    """Root JSON at ``operating_score.json``."""

    model_config = ConfigDict(populate_by_name=True)

    os_schema: str = Field(
        default="operating_score/v1",
        alias=_SCHEMA_KEY,
        description="Schema id (JSON key: schema).",
    )
    description: str = (
        "Paperwork Operating Score weekly composite "
        "(spec: apis/brain/data/operating_score_spec.yaml)."
    )
    current: OperatingScoreEntry | None = None
    history: list[OperatingScoreEntry] = Field(default_factory=list)

    @field_validator("history", mode="before")
    @classmethod
    def _history_list(cls, v: object) -> object:
        if v is None:
            return []
        return v
