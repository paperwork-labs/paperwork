"""Brain-canonical Expense store — JSON-file backed, file-locked, idempotent.

Covers WS-69 PR N:
  - submit_expense / list_expenses / get_expense / update_expense_status / edit_expense
  - compute_monthly_rollup / compute_quarterly_rollup
  - export_csv
  - load_routing_rules / save_routing_rules (stub; PR O adds writer)

Storage: apis/brain/data/expenses.json
Rules:   apis/brain/data/expense_routing_rules.json

medallion: ops
"""

from __future__ import annotations

import csv
import fcntl
import io
import json
import logging
import os
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas.expenses import (
    CategoryTotal,
    Expense,
    ExpenseCategory,
    ExpenseCreate,
    ExpenseEdit,
    ExpenseRoutingRules,
    ExpenseSource,
    ExpenseStatus,
    ExpenseStatusUpdate,
    ExpensesListPage,
    MonthlyRollup,
    QuarterlyRollup,
)

logger = logging.getLogger(__name__)

_ENV_EXPENSES_JSON = "BRAIN_EXPENSES_JSON"
_ENV_RULES_JSON = "BRAIN_EXPENSE_RULES_JSON"
_ENV_REPO_ROOT = "REPO_ROOT"

# Status transition graph — terminal states cannot change.
_ALLOWED_TRANSITIONS: dict[ExpenseStatus, set[ExpenseStatus]] = {
    "pending": {"approved", "flagged", "rejected"},
    "flagged": {"approved", "rejected", "pending"},
    "approved": {"reimbursed", "rejected"},
    "reimbursed": set(),  # terminal
    "rejected": set(),  # terminal
}


# ---------------------------------------------------------------------------
# Path helpers (three levels: services/ → app/ → brain/)
# ---------------------------------------------------------------------------


def _brain_root() -> Path:
    here = Path(__file__).resolve()
    # services/ -> app/ -> brain/
    brain_root = here.parent.parent.parent
    return brain_root


def _data_dir() -> Path:
    env = os.environ.get(_ENV_REPO_ROOT, "").strip()
    if env:
        # REPO_ROOT/apis/brain/data
        return Path(env) / "apis" / "brain" / "data"
    return _brain_root() / "data"


def _expenses_json_path() -> Path:
    env = os.environ.get(_ENV_EXPENSES_JSON, "").strip()
    if env:
        return Path(env)
    return _data_dir() / "expenses.json"


def _rules_json_path() -> Path:
    env = os.environ.get(_ENV_RULES_JSON, "").strip()
    if env:
        return Path(env)
    return _data_dir() / "expense_routing_rules.json"


# ---------------------------------------------------------------------------
# JSON store helpers
# ---------------------------------------------------------------------------


def _read_expenses_raw() -> list[dict[str, Any]]:
    path = _expenses_json_path()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        # Tolerate {"expenses": [...]} envelope
        if isinstance(data, dict) and "expenses" in data:
            envelope = data["expenses"]
            if isinstance(envelope, list):
                return envelope
        return []
    except (json.JSONDecodeError, OSError):
        logger.warning("expenses.json unreadable — treating as empty")
        return []


def _write_expenses_raw(rows: list[dict[str, Any]]) -> None:
    path = _expenses_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def _locked_read_write(
    fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
) -> None:
    """Acquire a file lock around expenses.json, run fn(rows) -> rows, persist."""
    lock_path = _expenses_json_path().with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            rows = _read_expenses_raw()
            rows = fn(rows)
            _write_expenses_raw(rows)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Routing rules
# ---------------------------------------------------------------------------


def load_routing_rules() -> ExpenseRoutingRules:
    path = _rules_json_path()
    if not path.exists():
        logger.info("expense_routing_rules.json not found — returning safe defaults")
        return ExpenseRoutingRules()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ExpenseRoutingRules.model_validate(raw)
    except Exception:
        logger.warning("expense_routing_rules.json parse error — returning safe defaults")
        return ExpenseRoutingRules()


def save_routing_rules(rules: ExpenseRoutingRules) -> ExpenseRoutingRules:
    """Persist updated routing rules. PR O adds audit Conversation; PR N just writes the file."""
    path = _rules_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rules.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return rules


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------


def _apply_routing(expense: Expense, rules: ExpenseRoutingRules) -> Expense:
    """Apply routing rules to determine initial status."""
    # Flag overrides everything
    if expense.amount_cents > rules.flag_amount_cents_above:
        return expense.model_copy(update={"status": "flagged"})
    # Always-review categories are never auto-approved
    if expense.category in rules.always_review_categories:
        return expense.model_copy(update={"status": "pending"})
    # Auto-approve when threshold > 0 and category eligible
    if (
        rules.auto_approve_threshold_cents > 0
        and expense.amount_cents <= rules.auto_approve_threshold_cents
        and expense.category in rules.auto_approve_categories
    ):
        return expense.model_copy(
            update={"status": "approved", "approved_at": datetime.now(UTC).isoformat()}
        )
    return expense


def submit_expense(payload: ExpenseCreate) -> Expense:
    rules = load_routing_rules()
    now = datetime.now(UTC).isoformat()
    expense = Expense(
        id=str(uuid.uuid4()),
        vendor=payload.vendor,
        amount_cents=payload.amount_cents,
        currency=payload.currency,
        category=payload.category,
        status="pending",
        source=payload.source,
        classified_by="founder",
        occurred_at=payload.occurred_at,
        submitted_at=now,
        notes=payload.notes,
        tags=payload.tags,
    )
    expense = _apply_routing(expense, rules)

    row = expense.model_dump(mode="json")

    def mutate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows.append(row)
        return rows

    _locked_read_write(mutate)
    return expense


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def _parse_expense(raw: dict[str, Any]) -> Expense | None:
    try:
        return Expense.model_validate(raw)
    except Exception:
        logger.warning("Skipping unparseable expense row: %s", raw.get("id"))
        return None


def list_expenses(
    *,
    status: ExpenseStatus | None = None,
    category: ExpenseCategory | None = None,
    source: ExpenseSource | None = None,
    search: str | None = None,
    year: int | None = None,
    month: int | None = None,
    count_only: bool = False,
    cursor: str | None = None,
    limit: int = 50,
) -> ExpensesListPage:
    rows = _read_expenses_raw()
    items: list[Expense] = []
    for raw in rows:
        expense = _parse_expense(raw)
        if expense is None:
            continue
        if status and expense.status != status:
            continue
        if category and expense.category != category:
            continue
        if source and expense.source != source:
            continue
        if year and not expense.occurred_at.startswith(str(year)):
            continue
        if month:
            mo_str = f"{year or ''}-{month:02d}" if year else f"-{month:02d}"
            if mo_str not in expense.occurred_at:
                continue
        if search:
            needle = search.lower()
            if needle not in expense.vendor.lower() and needle not in expense.notes.lower():
                continue
        items.append(expense)

    # Newest first
    items.sort(key=lambda e: e.submitted_at, reverse=True)

    total = len(items)
    if count_only:
        return ExpensesListPage(items=[], total=total, has_more=False)

    # Cursor pagination by index
    start = 0
    if cursor:
        try:
            start = int(cursor)
        except ValueError:
            start = 0
    page = items[start : start + limit]
    next_cursor = str(start + limit) if start + limit < total else None
    return ExpensesListPage(
        items=page, total=total, next_cursor=next_cursor, has_more=next_cursor is not None
    )


def get_expense(expense_id: str) -> Expense | None:
    rows = _read_expenses_raw()
    for raw in rows:
        if raw.get("id") == expense_id:
            return _parse_expense(raw)
    return None


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


def update_expense_status(expense_id: str, update: ExpenseStatusUpdate) -> Expense | None:
    result: list[Expense] = []

    def mutate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for i, raw in enumerate(rows):
            if raw.get("id") == expense_id:
                expense = _parse_expense(raw)
                if expense is None:
                    continue
                allowed = _ALLOWED_TRANSITIONS.get(expense.status, set())
                if update.status not in allowed:
                    raise ValueError(f"Cannot transition {expense.status} → {update.status}")
                now = datetime.now(UTC).isoformat()
                patch: dict[str, Any] = {
                    "status": update.status,
                    "notes": update.notes or expense.notes,
                }
                if update.status == "approved":
                    patch["approved_at"] = now
                elif update.status == "reimbursed":
                    patch["reimbursed_at"] = now
                updated = expense.model_copy(update=patch)
                rows[i] = updated.model_dump(mode="json")
                result.append(updated)
                return rows
        return rows

    _locked_read_write(mutate)
    return result[0] if result else None


def edit_expense(expense_id: str, edit: ExpenseEdit) -> Expense | None:
    result: list[Expense] = []

    def mutate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for i, raw in enumerate(rows):
            if raw.get("id") == expense_id:
                expense = _parse_expense(raw)
                if expense is None:
                    continue
                patch = dict(edit.model_dump(exclude_none=True))
                updated = expense.model_copy(update=patch)
                rows[i] = updated.model_dump(mode="json")
                result.append(updated)
                return rows
        return rows

    _locked_read_write(mutate)
    return result[0] if result else None


def attach_receipt(expense_id: str, receipt_data: dict[str, Any]) -> Expense | None:
    result: list[Expense] = []

    def mutate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for i, raw in enumerate(rows):
            if raw.get("id") == expense_id:
                expense = _parse_expense(raw)
                if expense is None:
                    continue
                updated = expense.model_copy(update={"receipt": receipt_data})
                rows[i] = updated.model_dump(mode="json")
                result.append(updated)
                return rows
        return rows

    _locked_read_write(mutate)
    return result[0] if result else None


# ---------------------------------------------------------------------------
# Rollup
# ---------------------------------------------------------------------------


def _filter_by_month(items: list[Expense], year: int, month: int) -> list[Expense]:
    prefix = f"{year}-{month:02d}"
    return [e for e in items if e.occurred_at.startswith(prefix)]


def _category_breakdown(items: list[Expense]) -> list[CategoryTotal]:
    totals: dict[str, dict[str, Any]] = {}
    for e in items:
        cat = e.category
        if cat not in totals:
            totals[cat] = {"category": cat, "amount_cents": 0, "count": 0}
        totals[cat]["amount_cents"] += e.amount_cents
        totals[cat]["count"] += 1
    return [CategoryTotal(**v) for v in sorted(totals.values(), key=lambda x: -x["amount_cents"])]


def compute_monthly_rollup(year: int, month: int) -> MonthlyRollup:
    rows = _read_expenses_raw()
    all_expenses = [e for raw in rows if (e := _parse_expense(raw)) is not None]
    month_items = _filter_by_month(all_expenses, year, month)

    total_cents = sum(e.amount_cents for e in month_items)
    approved_cents = sum(e.amount_cents for e in month_items if e.status == "approved")
    pending_cents = sum(e.amount_cents for e in month_items if e.status == "pending")
    flagged_cents = sum(e.amount_cents for e in month_items if e.status == "flagged")

    # Prior 3 months avg (denom safety: use actual count of non-empty months)
    prior_months: list[int] = []
    y, m = year, month
    for _ in range(3):
        m -= 1
        if m == 0:
            m = 12
            y -= 1
        mo_items = _filter_by_month(all_expenses, y, m)
        if mo_items:
            prior_months.append(sum(e.amount_cents for e in mo_items))

    prior_3mo_avg = sum(prior_months) // len(prior_months) if prior_months else 0
    pct_vs_prior_avg = (
        round((total_cents - prior_3mo_avg) / prior_3mo_avg * 100, 1) if prior_3mo_avg > 0 else None
    )

    vendor_set = {e.vendor for e in month_items}
    return MonthlyRollup(
        year=year,
        month=month,
        total_cents=total_cents,
        approved_cents=approved_cents,
        pending_cents=pending_cents,
        flagged_cents=flagged_cents,
        category_breakdown=_category_breakdown(month_items),
        vendor_count=len(vendor_set),
        expense_count=len(month_items),
        prior_3mo_avg_cents=prior_3mo_avg,
        pct_vs_prior_avg=pct_vs_prior_avg,
    )


def compute_quarterly_rollup(year: int, quarter: int) -> QuarterlyRollup:
    if not 1 <= quarter <= 4:
        raise ValueError(f"Quarter must be 1-4, got {quarter}")
    first_month = (quarter - 1) * 3 + 1
    months = [compute_monthly_rollup(year, first_month + i) for i in range(3)]
    all_items = []
    rows = _read_expenses_raw()
    all_expenses = [e for raw in rows if (e := _parse_expense(raw)) is not None]
    for i in range(3):
        all_items.extend(_filter_by_month(all_expenses, year, first_month + i))

    total_cents = sum(e.amount_cents for e in all_items)
    approved_cents = sum(e.amount_cents for e in all_items if e.status == "approved")
    return QuarterlyRollup(
        year=year,
        quarter=quarter,
        total_cents=total_cents,
        approved_cents=approved_cents,
        category_breakdown=_category_breakdown(all_items),
        expense_count=len(all_items),
        months=months,
    )


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

_CSV_COLUMNS = [
    "id",
    "occurred_at",
    "vendor",
    "amount_cents",
    "amount_dollars",
    "currency",
    "category",
    "source",
    "status",
    "classified_by",
    "notes",
    "receipt_filename",
    "conversation_id",
    "tags",
    "submitted_at",
    "approved_at",
    "reimbursed_at",
]


def export_csv(
    *,
    status: ExpenseStatus | None = None,
    category: ExpenseCategory | None = None,
    year: int | None = None,
    month: int | None = None,
) -> str:
    page = list_expenses(status=status, category=category, year=year, month=month, limit=10000)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for e in page.items:
        writer.writerow(
            {
                "id": e.id,
                "occurred_at": e.occurred_at,
                "vendor": e.vendor,
                "amount_cents": e.amount_cents,
                "amount_dollars": f"{e.amount_cents / 100:.2f}",
                "currency": e.currency,
                "category": e.category,
                "source": e.source,
                "status": e.status,
                "classified_by": e.classified_by,
                "notes": e.notes,
                "receipt_filename": e.receipt.filename if e.receipt else "",
                "conversation_id": e.conversation_id or "",
                "tags": ",".join(e.tags),
                "submitted_at": e.submitted_at,
                "approved_at": e.approved_at or "",
                "reimbursed_at": e.reimbursed_at or "",
            }
        )
    return output.getvalue()


# ---------------------------------------------------------------------------
# Upsert for seed/backfill (used by migration script)
# ---------------------------------------------------------------------------


def upsert_expense_raw(expense: Expense) -> bool:
    """Insert expense if id not already present. Returns True if inserted."""
    inserted: list[bool] = [False]

    def mutate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        existing_ids = {r.get("id") for r in rows}
        if expense.id not in existing_ids:
            rows.append(expense.model_dump(mode="json"))
            inserted[0] = True
        return rows

    _locked_read_write(mutate)
    return inserted[0]
