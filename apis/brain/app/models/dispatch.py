"""Pydantic models for autopilot dispatch entries and results.

medallion: ops
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

DispatchSource = Literal["probe", "goal", "manual"]
DispatchStatus = Literal[
    "pending",
    "dispatched",
    "completed",
    "failed",
]

CheapModel = Literal[
    "composer-1.5",
    "composer-2-fast",
    "gpt-5.5-medium",
    "claude-4.6-sonnet-medium-thinking",
]

TShirtSize = Literal["XS", "S", "M", "L", "XL"]

_MODEL_TO_SIZE: dict[str, TShirtSize] = {
    "composer-1.5": "XS",
    "composer-2-fast": "S",
    "gpt-5.5-medium": "M",
    "claude-4.6-sonnet-medium-thinking": "L",
}

_LEGACY_MODEL_MAP: dict[str, str] = {
    "cheap": "composer-2-fast",
    "expensive": "gpt-5.5-medium",
}


def derive_t_shirt_size(model: str) -> TShirtSize:
    """Return the T-Shirt size for a given model slug.

    Raises ValueError for unknown or Opus models (XL is not a valid
    subagent size — orchestrator-only).
    """
    if model in _MODEL_TO_SIZE:
        return _MODEL_TO_SIZE[model]
    if "opus" in model.lower():
        raise ValueError(
            f"Model '{model}' contains 'opus' and is FORBIDDEN as a subagent. "
            "Opus is orchestrator-only. See cheap-agent-fleet.mdc Rule #2."
        )
    raise ValueError(
        f"Model '{model}' is not in the T-Shirt Size allow-list. "
        f"Allowed: {', '.join(_MODEL_TO_SIZE)}. "
        "See docs/PR_TSHIRT_SIZING.md."
    )


def normalize_legacy_model(model: str) -> str:
    """Map legacy 'cheap'/'expensive' strings to canonical model slugs."""
    return _LEGACY_MODEL_MAP.get(model, model)


class DispatchEntry(BaseModel):
    """A single work item queued for autopilot dispatch."""

    task_id: str
    source: DispatchSource
    description: str = ""
    product: str = ""
    persona_id: str = ""
    agent_model: CheapModel
    t_shirt_size: TShirtSize = Field(default="M", description="Derived from agent_model")
    status: DispatchStatus = "pending"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    dispatched_at: datetime | None = None

    @model_validator(mode="after")
    def _derive_size(self) -> DispatchEntry:
        self.t_shirt_size = _MODEL_TO_SIZE[self.agent_model]
        return self


class DispatchResult(BaseModel):
    """Outcome record appended to agent_dispatch_log.jsonl."""

    task_id: str
    persona_id: str
    agent_model: str
    t_shirt_size: TShirtSize = "M"
    pr_number: int | None = None
    outcome: str = ""
    duration_ms: int = 0

    @model_validator(mode="after")
    def _derive_size(self) -> DispatchResult:
        normalized = normalize_legacy_model(self.agent_model)
        if normalized in _MODEL_TO_SIZE:
            self.t_shirt_size = _MODEL_TO_SIZE[normalized]
        return self


class LegacyDispatchEntry(BaseModel):
    """Reader for old-format JSONL entries that used 'cheap'/'expensive' strings.

    Maps legacy model names to canonical slugs for backfill / migration purposes.
    """

    task_id: str
    source: str = "probe"
    description: str = ""
    product: str = ""
    persona_id: str = ""
    agent_model: str = "composer-2-fast"
    status: str = "pending"
    created_at: Annotated[datetime, Field(default_factory=lambda: datetime.now(UTC))]
    dispatched_at: datetime | None = None

    @model_validator(mode="after")
    def _normalize_model(self) -> LegacyDispatchEntry:
        self.agent_model = normalize_legacy_model(self.agent_model)
        return self

    def to_dispatch_entry(self) -> DispatchEntry:
        model = self.agent_model
        if model not in _MODEL_TO_SIZE:
            model = "gpt-5.5-medium"
        norm_status = (
            self.status
            if self.status in ("pending", "dispatched", "completed", "failed")
            else "pending"
        )
        return DispatchEntry(
            task_id=self.task_id,
            source=self.source if self.source in ("probe", "goal", "manual") else "probe",  # type: ignore[arg-type]
            description=self.description,
            product=self.product,
            persona_id=self.persona_id,
            agent_model=model,  # type: ignore[arg-type]
            status=norm_status,  # type: ignore[arg-type]
            created_at=self.created_at,
            dispatched_at=self.dispatched_at,
        )
