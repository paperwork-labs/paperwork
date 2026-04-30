"""Pydantic models for Brain-canonical Bills (invoices) — WS-76 PR-26.

medallion: ops
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BillStatus = Literal["pending", "approved", "paid", "rejected"]


class Bill(BaseModel):
    id: str
    vendor_id: str = Field(..., min_length=1, max_length=200)
    status: BillStatus = "pending"
    due_date: str  # ISO date YYYY-MM-DD
    amount_usd: float = Field(..., ge=0)
    description: str = ""
    attachments: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class BillCreate(BaseModel):
    vendor_id: str = Field(..., min_length=1, max_length=200)
    due_date: str
    amount_usd: float = Field(..., ge=0)
    description: str = ""
    attachments: list[str] = Field(default_factory=list)


class BillUpdate(BaseModel):
    vendor_id: str | None = Field(default=None, min_length=1, max_length=200)
    due_date: str | None = None
    amount_usd: float | None = Field(default=None, ge=0)
    description: str | None = None
    attachments: list[str] | None = None


class BillsListPage(BaseModel):
    items: list[Bill]
    total: int
