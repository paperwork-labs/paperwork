"""JSONL ledger rows for drafted / queued social posts (voice pipeline).

medallion: ops
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SocialPostStatus = Literal["draft", "queued", "published", "rejected"]


class SocialPostLedgerEntry(BaseModel):
    """One line in ``data/social_posts.jsonl``."""

    id: str = Field(..., min_length=1, max_length=200)
    persona_slug: str = Field(..., min_length=1, max_length=200)
    route: str = Field(..., description="conversation | queue | archived (from voice stub)")
    body: str = ""
    voice_mode: Literal["shadow", "active", "archived"] = "shadow"
    platform: str | None = None
    created_at: str = Field(..., description="ISO-8601 timestamp")
    status: SocialPostStatus = "draft"
    metadata: dict[str, str] = Field(default_factory=dict)
