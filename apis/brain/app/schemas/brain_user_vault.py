"""Schemas for per-user Brain vault (D61)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class VaultEntry(BaseModel):
    """Metadata for one vault secret — never includes the ciphertext or plaintext value."""

    key: str = Field(description="Secret name (maps to DB ``name`` column)")
    created_at: datetime = Field(description="UTC creation time")
    updated_at: datetime = Field(
        description=(
            "UTC last-update time; mirrors ``created_at`` until schema gains ``updated_at``"
        ),
    )


class AdminBrainVaultSetBody(BaseModel):
    """Admin upsert body."""

    value: str = Field(min_length=1)
    organization_id: str = Field(default="paperwork-labs", min_length=1)
