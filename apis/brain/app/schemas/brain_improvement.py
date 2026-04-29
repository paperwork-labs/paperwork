"""Pydantic models for the Brain Improvement Index (WS-69 PR D).

Composite 0-100 score measuring Brain's learning and self-improvement
velocity over three sub-metrics in v1. PR P adds a 4th (audit_freshness).

medallion: ops
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — Pydantic resolves datetime at model validation time

from pydantic import BaseModel, Field


class BrainImprovementCurrent(BaseModel):
    """Point-in-time Brain Improvement Index snapshot."""

    score: int = Field(ge=0, le=100, description="Composite 0-100 Brain Improvement score.")
    acceptance_rate_pct: float = Field(
        ge=0.0,
        le=100.0,
        description="% of Brain-merged PRs not reverted at h24 (0=none measured yet).",
    )
    promotion_progress_pct: float = Field(
        ge=0.0,
        le=100.0,
        description="Progress toward next self-merge tier (0-100; 100=fully graduated).",
    )
    rules_count: int = Field(ge=0, description="Total procedural rules in procedural_memory.yaml.")
    retro_delta_pct: float = Field(
        description="Latest weekly retro POS total change (raw, e.g. +2.5 or -1.0).",
    )
    computed_at: datetime
    note: str = Field(
        default="",
        description="Non-empty when data is missing or insufficient; never fabricated.",
    )


class BrainImprovementHistoryEntry(BaseModel):
    """One historical Brain Improvement score data-point."""

    at: datetime
    score: int = Field(ge=0, le=100)


class BrainImprovementResponse(BaseModel):
    """Top-level response for GET /admin/brain-improvement-index."""

    current: BrainImprovementCurrent
    history_12w: list[BrainImprovementHistoryEntry] = Field(
        default_factory=list,
        description=(
            "Weekly scores for the last 12 weeks, oldest-first. Empty until history accumulates."
        ),
    )
