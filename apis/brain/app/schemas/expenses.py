"""Pydantic models for the Brain-canonical Expense store.

Covers WS-69 PR N (v1 — manual submission, list, rollup, CSV, routing rules).
PR O extends with auto-classify, Conversations wiring, and rules editing.

medallion: ops
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Domain literals
# ---------------------------------------------------------------------------

ExpenseCategory = Literal[
    "infra", "ai", "contractors", "tools", "legal", "tax", "misc", "domains", "ops"
]

ExpenseStatus = Literal["pending", "approved", "reimbursed", "flagged", "rejected"]

ExpenseSource = Literal["manual", "gmail", "stripe", "plaid", "subscription", "imported"]

# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


class ReceiptAttachment(BaseModel):
    filename: str
    mime_type: str
    size_bytes: int
    stored_path: str


class Expense(BaseModel):
    id: str
    vendor: str = Field(..., min_length=1, max_length=200)
    amount_cents: int = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=3)
    category: ExpenseCategory
    status: ExpenseStatus = "pending"
    source: ExpenseSource = "manual"
    classified_by: str = "founder"  # "founder" | "cfo-persona" | "imported"
    occurred_at: str  # ISO date string YYYY-MM-DD
    submitted_at: str  # ISO datetime string
    approved_at: str | None = None
    reimbursed_at: str | None = None
    notes: str = ""
    receipt: ReceiptAttachment | None = None
    tags: list[str] = Field(default_factory=list)
    conversation_id: str | None = None  # PR O wires this
    organization_id: str | None = None  # WS-76 explicit tenancy on inserts


class ExpenseCreate(BaseModel):
    vendor: str = Field(..., min_length=1, max_length=200)
    amount_cents: int = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=3)
    category: ExpenseCategory
    source: ExpenseSource = "manual"
    occurred_at: str  # YYYY-MM-DD
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    use_cfo_classify: bool = Field(
        default=False,
        description="When True, CFO persona sets category (overrides submitted category).",
    )


class ExpenseStatusUpdate(BaseModel):
    status: ExpenseStatus
    notes: str = ""


ExpenseConversationAction = Literal[
    "approve",
    "approve-change-category",
    "flag",
    "reject",
]


class ExpenseConversationResolveBody(BaseModel):
    """POST /admin/expenses/{id}/status — resolve via linked Conversation (atomic)."""

    expense_action: ExpenseConversationAction
    new_category: ExpenseCategory | None = None

    @model_validator(mode="after")
    def _require_category_for_change(self) -> ExpenseConversationResolveBody:
        if self.expense_action == "approve-change-category" and self.new_category is None:
            raise ValueError(
                "new_category is required when expense_action is approve-change-category"
            )
        return self


class ExpenseEdit(BaseModel):
    vendor: str | None = Field(default=None, min_length=1, max_length=200)
    amount_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=3)
    category: ExpenseCategory | None = None
    occurred_at: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class ExpensesListPage(BaseModel):
    items: list[Expense]
    total: int
    next_cursor: str | None = None
    has_more: bool = False


# ---------------------------------------------------------------------------
# Rollup models
# ---------------------------------------------------------------------------


class CategoryTotal(BaseModel):
    category: ExpenseCategory
    amount_cents: int
    count: int


class MonthlyRollup(BaseModel):
    year: int
    month: int  # 1-12
    total_cents: int
    approved_cents: int
    pending_cents: int
    flagged_cents: int
    category_breakdown: list[CategoryTotal]
    vendor_count: int
    expense_count: int
    prior_3mo_avg_cents: int  # 0 if fewer than 3 prior months of data
    pct_vs_prior_avg: float | None  # None when prior avg is 0 (avoid div/0)


class QuarterlyRollup(BaseModel):
    year: int
    quarter: int  # 1-4
    total_cents: int
    approved_cents: int
    category_breakdown: list[CategoryTotal]
    expense_count: int
    months: list[MonthlyRollup]


# ---------------------------------------------------------------------------
# Routing rules
# ---------------------------------------------------------------------------


class ExpenseRoutingRules(BaseModel):
    auto_approve_threshold_cents: int = Field(default=0, ge=0)
    auto_approve_categories: list[ExpenseCategory] = Field(default_factory=list)
    always_review_categories: list[ExpenseCategory] = Field(default_factory=list)
    flag_amount_cents_above: int = Field(default=100000, ge=0)
    founder_card_default_source: str = "founder-card"
    subscription_skip_approval: bool = False
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_by: str = "founder"
    history: list[dict[str, Any]] = Field(default_factory=list)


class ExpenseRoutingRulesUpdate(BaseModel):
    """Body for PUT /admin/expenses/rules — replaces tunable routing fields."""

    auto_approve_threshold_cents: int = Field(..., ge=0)
    auto_approve_categories: list[ExpenseCategory]
    always_review_categories: list[ExpenseCategory]
    flag_amount_cents_above: int = Field(..., ge=0)
    founder_card_default_source: str = "founder-card"
    subscription_skip_approval: bool = False
    updated_by: str = "founder"

    @model_validator(mode="after")
    def _validate_sets_and_flag(self) -> ExpenseRoutingRulesUpdate:
        auto_s = set(self.auto_approve_categories)
        always_s = set(self.always_review_categories)
        overlap = auto_s & always_s
        if overlap:
            raise ValueError(
                "Categories cannot appear in both auto-approve and always-review: "
                f"{sorted(overlap)}"
            )
        if self.flag_amount_cents_above < self.auto_approve_threshold_cents:
            raise ValueError("flag_amount_cents_above must be >= auto_approve_threshold_cents")
        return self
