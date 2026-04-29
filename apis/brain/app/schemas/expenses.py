"""Expense tracking schemas — Brain canonical data model (WS-69 PR N).

medallion: ops
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — pydantic requires runtime availability
from typing import Literal

from pydantic import BaseModel, Field

ExpenseStatus = Literal["pending", "approved", "rejected", "reimbursed", "flagged"]
ExpenseCategory = Literal[
    "infra", "ai", "contractors", "tools", "legal", "tax", "domains", "ops", "misc"
]


class ExpenseAttachment(BaseModel):
    kind: Literal["receipt"]
    url: str  # /admin/expenses/attachments/<sha256>
    mime: str
    sha256: str
    size_bytes: int


class Expense(BaseModel):
    id: str
    amount_cents: int
    currency: str = "USD"  # ISO-4217
    vendor: str
    category: ExpenseCategory
    tags: list[str] = Field(default_factory=list)
    status: ExpenseStatus
    submitted_at: datetime
    approved_at: datetime | None = None
    reimbursed_at: datetime | None = None
    attachments: list[ExpenseAttachment] = Field(default_factory=list)
    notes: str = ""
    submitted_by: str  # Clerk user_id
    # Tax domain: deductibility surface for WS-74
    tax_deductible_pct: float | None = None  # 0-100; None = not yet determined
    tax_category_note: str | None = None  # free-text note for CPA review
    # Forward-compat placeholders for WS-74+
    vendor_id: str | None = None  # placeholder for vendor registry
    invoice_id: str | None = None  # placeholder for invoice linking
    gmail_message_id: str | None = None  # placeholder for ingested-from-gmail
    conversation_id: str | None = None  # link back to approval Conversation (PR O wires)


class ExpenseCreate(BaseModel):
    amount_cents: int
    currency: str = "USD"
    vendor: str
    category: ExpenseCategory
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    submitted_by: str
    tax_deductible_pct: float | None = None
    tax_category_note: str | None = None


class ExpenseRoutingRules(BaseModel):
    auto_approve_threshold_cents: int = 0  # default 0 = no auto-approval
    auto_approve_categories: list[ExpenseCategory] = Field(default_factory=list)
    flagged_threshold_cents: int = 50000  # auto-flag if amount >= this
    flagged_categories: list[ExpenseCategory] = Field(default_factory=lambda: ["legal", "tax"])


class ExpensesFile(BaseModel):
    schema_: str = Field("expenses/v1", alias="schema")
    expenses: list[Expense] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class ExpenseRollupCategory(BaseModel):
    category: ExpenseCategory
    total_cents: int
    count: int


class ExpenseRollup(BaseModel):
    period: str  # e.g. "2026-04" or "2026-Q2"
    total_cents: int
    count: int
    by_category: list[ExpenseRollupCategory]


class ExpenseRuleAuditEntry(BaseModel):
    id: str
    changed_at: datetime
    changed_by: str
    previous: dict
    updated: dict
    note: str = ""
