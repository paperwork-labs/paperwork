"""Social post ledger row schema (JSONL under ``apis/brain/data/``).

medallion: ops
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SocialPostRecord(BaseModel):
    """One line in ``social_posts.jsonl``."""

    id: str
    persona_slug: str
    created_at: str = Field(description="ISO-8601 timestamp")
    body: str = ""
    platform: str | None = None
    status: Literal["draft", "queued", "published", "rejected"] = "draft"
    metadata: dict[str, Any] = Field(default_factory=dict)
