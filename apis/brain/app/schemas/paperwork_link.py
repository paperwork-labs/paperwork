"""Ledger row linking a Clerk user to Brain tenancy (WS-76 PR-13).

medallion: ops
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, Field


class PaperworkLink(BaseModel):
    id: str
    clerk_user_id: str
    organization_id: str | None = None
    display_name: str
    role: str = Field(default="member", description="member | admin | owner")
    created_at: datetime
