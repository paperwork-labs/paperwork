"""Pydantic models for ``kg_validation.json`` (WS-52)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ViolationSeverity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class KGViolation(BaseModel):
    rule: str = Field(..., description="Rule class identifier, e.g. 'workstream_id_references'")
    severity: ViolationSeverity
    where: str = Field(..., description="File:key path where the violation was found")
    detail: str = Field(..., description="Human-readable description of what went wrong")


class KGValidationRun(BaseModel):
    validated_at: str = Field(..., description="RFC3339Z UTC timestamp")
    files_checked: int = Field(ge=0)
    violations: list[KGViolation] = Field(default_factory=list)
    passed: bool
    summary: str = Field(..., description="One-line summary for Brain to read/post")


class KGValidationFile(BaseModel):
    """Root JSON at ``apis/brain/data/kg_validation.json``."""

    schema_id: Literal["kg_validation/v1"] = Field(
        "kg_validation/v1",
        alias="schema",
        description="Schema id (JSON key: schema).",
    )
    current: KGValidationRun | None = None
    history: list[KGValidationRun] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
