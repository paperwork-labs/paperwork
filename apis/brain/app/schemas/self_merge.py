"""Pydantic models for Brain self-merge graduation state (WS-44)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MergeTier = Literal["data-only", "brain-code", "app-code"]


class SelfMergeSchemaDoc(BaseModel):
    description: str = "Brain self-merge graduation log. cheap-agent-fleet.mdc rule + WS-44."
    tier_definitions: dict[str, str] = Field(
        default_factory=lambda: {
            "data-only": (
                "merges only paths matching apis/brain/data/**, docs/**, .cursor/rules/**"
            ),
            "brain-code": (
                "merges paths under apis/brain/** (graduation requires N=50 clean data-only merges)"
            ),
            "app-code": (
                "merges paths under apis/<other>/, apps/, packages/ "
                "(graduation requires N=50 clean brain-code merges)"
            ),
        }
    )


class SelfMergeRecord(BaseModel):
    pr_number: int
    merged_at: datetime
    tier: MergeTier
    paths_touched: list[str] = Field(default_factory=list)
    graduation_eligible: bool


class RevertRecord(BaseModel):
    pr_number: int
    original_pr: int
    reverted_at: datetime
    reason: str


class PromotionRecord(BaseModel):
    from_tier: MergeTier
    to_tier: MergeTier
    promoted_at: datetime
    clean_merge_count_at_promotion: int
    notes: str


class SelfMergePromotionsFile(BaseModel):
    """Root document stored at ``self_merge_promotions.json``."""

    model_config = ConfigDict(populate_by_name=True)

    self_merge_schema: SelfMergeSchemaDoc = Field(
        default_factory=SelfMergeSchemaDoc,
        alias="schema",
    )
    version: int = 1
    current_tier: MergeTier = "data-only"
    promotions: list[PromotionRecord] = Field(default_factory=list)
    merges: list[SelfMergeRecord] = Field(default_factory=list)
    reverts: list[RevertRecord] = Field(default_factory=list)
