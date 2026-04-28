from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ConfidenceLevel = Literal["low", "medium", "high"]
AgentScope = Literal["orchestrator", "brain-self-dispatch", "cheap-agents"]

_CONFIDENCE_ORDER: dict[ConfidenceLevel, int] = {"high": 0, "medium": 1, "low": 2}


def _default_applies_to() -> list[AgentScope]:
    return ["cheap-agents"]


class ProceduralRule(BaseModel):
    id: str = Field(..., description="Snake_case unique identifier")
    when: str = Field(..., description="Trigger condition -- free text")
    do: str = Field(..., description="Action / preference -- free text")
    source: str = Field(..., description="Origin: PR #, incident name, retro")
    learned_at: datetime = Field(..., description="When added (RFC3339Z UTC)")
    confidence: ConfidenceLevel
    applies_to: list[AgentScope] = Field(..., min_length=1)

    @property
    def confidence_rank(self) -> int:
        return _CONFIDENCE_ORDER[self.confidence]


class ProceduralRuleInput(BaseModel):
    """Input schema for add_rule() -- learned_at defaults to now if omitted."""

    id: str = Field(..., description="Snake_case unique identifier")
    when: str
    do: str
    source: str
    learned_at: datetime | None = Field(None, description="Defaults to UTC now when not provided")
    confidence: ConfidenceLevel = "low"
    applies_to: list[AgentScope] = Field(default_factory=_default_applies_to)


class ProceduralMemoryFile(BaseModel):
    version: int = 1
    rules: list[ProceduralRule] = Field(default_factory=list)
