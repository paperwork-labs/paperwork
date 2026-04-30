"""Resolved caller identity for Brain HTTP handlers (WS-76 PR-13).

medallion: ops
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BrainUserContext(BaseModel):
    """Unified tenant + user binding after Clerk JWT or env fallback."""

    auth_source: Literal["clerk_jwt", "env_fallback"]
    paperwork_link_id: str | None = None
    clerk_user_id: str | None = None
    organization_id: str | None = None
    display_name: str | None = None
    role: str = "member"
    brain_user_id: str = Field(
        ...,
        description="Stable Brain user key for episodes, push routing, and audit.",
    )
