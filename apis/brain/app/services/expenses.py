"""Expense tracking service — file-locked JSON store (WS-69 PR N).

Data files:
- ``apis/brain/data/expenses.json``     — expense ledger
- ``apis/brain/data/expense_routing_rules.json`` — routing config
- ``apis/brain/data/expense_rule_audits.json``   — audit trail
- ``apis/brain/data/expense_events.json``         — side-channel events (PR O wires Conversations)
- ``apis/brain/data/expenses_attachments/<sha256>.<ext>`` — receipt blobs

medallion: ops
"""

from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import json
import logging
import os
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.schemas.expenses import (
    Expense,
    ExpenseAttachment,
    ExpenseCategory,
    ExpenseCreate,
    ExpenseRollup,
    ExpenseRollupCategory,
    ExpenseRoutingRules,
    ExpenseRuleAuditEntry,
    ExpensesFile,
    ExpenseStatus,
)

logger = logging.getLogger(__name__)

_TMP_SUFFIX = ".tmp"
_DEFAULT_RULES = ExpenseRoutingRules(
    auto_approve_threshold_cents=0,
    auto_approve_categories=[],
    flagged_threshold_cents=50000,
    flagged_categories=["legal", "tax"],
)


# ---------------------------------------------------------------------------
# Path helpers — brain_data_dir_traverses_three_levels
# ---------------------------------------------------------------------------


def _brain_data_dir() -> str:
    """services/ → app/ → brain/ ; data lives at brain/data."""
    here = os.path.dirname(os.path.abspath(__file__))
    brain_app = os.path.dirname(here)
    brain_root = os.path.dirname(brain_app)
    d = os.path.join(brain_root, "data")
    os.makedirs(d, exist_ok=True)
    return d


def _expenses_path() -> str:
    env = os.environ.get("BRAIN_EXPENSES_JSON", "").strip()
    return env or os.path.join(_brain_data_dir(), "expenses.json")


def _rules_path() -> str:
    env = os.environ.get("BRAIN_EXPENSE_RULES_JSON", "").strip()
    return env or os.path.join(_brain_data_dir(), "expense_routing_rules.json")


def _audits_path() -> str:
    env = os.environ.get("BRAIN_EXPENSE_AUDITS_JSON", "").strip()
    return env or os.path.join(_brain_data_dir(), "expense_rule_audits.json")


def _events_path() -> str:
    env = os.environ.get("BRAIN_EXPENSE_EVENTS_JSON", "").strip()
    return env or os.path.join(_brain_data_dir(), "expense_events.json")


def _attachments_dir() -> str:
    env = os.environ.get("BRAIN_EXPENSE_ATTACHMENTS_DIR", "").strip()
    if env:
        os.makedirs(env, exist_ok=True)
        return env
    d = os.path.join(_brain_data_dir(), "expenses_attachments")
    os.makedirs(d, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Atomic file I/O with fcntl locking
# ---------------------------------------------------------------------------


def _atomic_write(path: str, data: dict[str, Any]) -> None:
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    tmp = f"{path}{_TMP_SUFFIX}"
    raw = json.dumps(data, indent=2, default=str) + "\n"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(raw)
    os.replace(tmp, path)


def _locked_read_write(path: str, mutate_fn) -> Any:  # type: ignore[type-arg]
    """Read JSON at *path*, call *mutate_fn(data) -> (data, result)*, write back atomically."""
    lock_path = f"{path}.lock"
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    with open(lock_path, "a", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f, fcntl.LOCK_EX)
        try:
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {}
            data, result = mutate_fn(data)
            _atomic_write(path, data)
            return result
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Routing rules
# ---------------------------------------------------------------------------


def load_routing_rules() -> ExpenseRoutingRules:
    path = _rules_path()
    if not os.path.isfile(path):
        _atomic_write(path, _DEFAULT_RULES.model_dump())
        return _DEFAULT_RULES
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return ExpenseRoutingRules.model_validate(raw)
    except Exception as e:
        logger.warning("expense rules load failed (%s); using defaults", e)
        return _DEFAULT_RULES


def update_routing_rules(
    updated: ExpenseRoutingRules,
    *,
    changed_by: str,
    note: str = "",
) -> ExpenseRoutingRules:
    previous = load_routing_rules()
    _atomic_write(_rules_path(), updated.model_dump())

    audit = ExpenseRuleAuditEntry(
        id=f"era_{uuid.uuid4().hex[:12]}",
        changed_at=datetime.now(UTC),
        changed_by=changed_by,
        previous=previous.model_dump(),
        updated=updated.model_dump(),
        note=note,
    )
    _append_audit(audit)
    _append_event(
        {
            "kind": "routing_rules_updated",
            "audit_id": audit.id,
            "changed_by": changed_by,
            "note": note,
            "ts": audit.changed_at.isoformat(),
        }
    )
    return updated


def _append_audit(audit: ExpenseRuleAuditEntry) -> None:
    def mutate(data: dict) -> tuple[dict, None]:
        audits = data.get("audits", [])
        audits.append(audit.model_dump(mode="json"))
        data["audits"] = audits
        data.setdefault("schema", "expense_rule_audits/v1")
        return data, None

    _locked_read_write(_audits_path(), mutate)


def _append_event(event: dict) -> None:
    def mutate(data: dict) -> tuple[dict, None]:
        events = data.get("events", [])
        events.append(event)
        data["events"] = events
        data.setdefault("schema", "expense_events/v1")
        return data, None

    _locked_read_write(_events_path(), mutate)


# ---------------------------------------------------------------------------
# Expenses CRUD
# ---------------------------------------------------------------------------


def _determine_initial_status(
    amount_cents: int,
    category: ExpenseCategory,
    rules: ExpenseRoutingRules,
) -> ExpenseStatus:
    if category in rules.flagged_categories:
        return "flagged"
    if amount_cents >= rules.flagged_threshold_cents:
        return "flagged"
    if (
        rules.auto_approve_threshold_cents > 0
        and amount_cents < rules.auto_approve_threshold_cents
        and category in rules.auto_approve_categories
    ):
        return "approved"
    return "pending"


def _load_expenses() -> list[Expense]:
    path = _expenses_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return ExpensesFile.model_validate(raw).expenses
    except Exception as e:
        logger.warning("expenses load failed (%s); returning empty", e)
        return []


def list_expenses(
    *,
    filter_status: str = "pending",
    cursor: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    expenses = _load_expenses()

    if filter_status != "all":
        expenses = [e for e in expenses if e.status == filter_status]

    expenses = sorted(expenses, key=lambda e: e.submitted_at, reverse=True)

    start = 0
    if cursor:
        ids = [e.id for e in expenses]
        if cursor in ids:
            start = ids.index(cursor) + 1

    page = expenses[start : start + limit]
    next_cursor = page[-1].id if len(page) == limit else None

    return {
        "items": [e.model_dump(mode="json") for e in page],
        "next_cursor": next_cursor,
        "total": len(expenses),
    }


def get_expense(expense_id: str) -> Expense | None:
    for e in _load_expenses():
        if e.id == expense_id:
            return e
    return None


def create_expense(
    data: ExpenseCreate,
    *,
    attachments: list[ExpenseAttachment] | None = None,
) -> Expense:
    rules = load_routing_rules()
    status = _determine_initial_status(data.amount_cents, data.category, rules)

    expense = Expense(
        id=f"exp_{uuid.uuid4().hex[:16]}",
        amount_cents=data.amount_cents,
        currency=data.currency,
        vendor=data.vendor,
        category=data.category,
        tags=data.tags,
        status=status,
        submitted_at=datetime.now(UTC),
        approved_at=None,
        reimbursed_at=None,
        attachments=attachments or [],
        notes=data.notes,
        submitted_by=data.submitted_by,
        tax_deductible_pct=data.tax_deductible_pct,
        tax_category_note=data.tax_category_note,
    )

    def mutate(raw: dict) -> tuple[dict, Expense]:
        raw.setdefault("schema", "expenses/v1")
        items = raw.get("expenses", [])
        items.append(expense.model_dump(mode="json"))
        raw["expenses"] = items
        return raw, expense

    result = _locked_read_write(_expenses_path(), mutate)
    _append_event(
        {
            "kind": "expense_created",
            "expense_id": expense.id,
            "status": status,
            "ts": expense.submitted_at.isoformat(),
        }
    )
    return result


def _update_expense_field(
    expense_id: str,
    updates: dict[str, Any],
) -> Expense | None:
    result_holder: list[Expense | None] = [None]

    def mutate(raw: dict) -> tuple[dict, None]:
        items = raw.get("expenses", [])
        for item in items:
            if item.get("id") == expense_id:
                item.update(updates)
                result_holder[0] = Expense.model_validate(item)
                break
        raw["expenses"] = items
        return raw, None

    _locked_read_write(_expenses_path(), mutate)
    return result_holder[0]


def approve_expense(expense_id: str, *, approved_by: str) -> Expense | None:
    now = datetime.now(UTC)
    expense = _update_expense_field(
        expense_id,
        {"status": "approved", "approved_at": now.isoformat()},
    )
    if expense:
        _append_event(
            {
                "kind": "expense_approved",
                "expense_id": expense_id,
                "approved_by": approved_by,
                "ts": now.isoformat(),
            }
        )
    return expense


def reject_expense(expense_id: str, *, rejected_by: str, reason: str = "") -> Expense | None:
    now = datetime.now(UTC)
    expense = _update_expense_field(expense_id, {"status": "rejected"})
    if expense:
        _append_event(
            {
                "kind": "expense_rejected",
                "expense_id": expense_id,
                "rejected_by": rejected_by,
                "reason": reason,
                "ts": now.isoformat(),
            }
        )
    return expense


def mark_reimbursed(expense_id: str, *, reimbursed_by: str) -> Expense | None:
    now = datetime.now(UTC)
    expense = _update_expense_field(
        expense_id,
        {"status": "reimbursed", "reimbursed_at": now.isoformat()},
    )
    if expense:
        _append_event(
            {
                "kind": "expense_reimbursed",
                "expense_id": expense_id,
                "reimbursed_by": reimbursed_by,
                "ts": now.isoformat(),
            }
        )
    return expense


# ---------------------------------------------------------------------------
# Rollups
# ---------------------------------------------------------------------------


def compute_rollup(*, period: str, year: int, month: int | None = None) -> ExpenseRollup:
    """Compute totals for a month (period='month') or quarter (period='quarter')."""
    expenses = _load_expenses()

    def _in_period(e: Expense) -> bool:
        dt = e.submitted_at
        if period == "month":
            return dt.year == year and dt.month == month
        if period == "quarter":
            if month is None:
                return False
            q = (month - 1) // 3 + 1
            expense_q = (dt.month - 1) // 3 + 1
            return dt.year == year and expense_q == q
        return False

    filtered = [e for e in expenses if _in_period(e)]

    by_cat: dict[str, int] = defaultdict(int)
    by_cat_count: dict[str, int] = defaultdict(int)
    for e in filtered:
        by_cat[e.category] += e.amount_cents
        by_cat_count[e.category] += 1

    period_label: str
    if period == "month" and month:
        period_label = f"{year}-{month:02d}"
    elif period == "quarter" and month:
        q = (month - 1) // 3 + 1
        period_label = f"{year}-Q{q}"
    else:
        period_label = str(year)

    return ExpenseRollup(
        period=period_label,
        total_cents=sum(e.amount_cents for e in filtered),
        count=len(filtered),
        by_category=[
            ExpenseRollupCategory(
                category=cat,  # type: ignore[arg-type]
                total_cents=total,
                count=by_cat_count[cat],
            )
            for cat, total in sorted(by_cat.items(), key=lambda kv: -kv[1])
        ],
    )


def export_csv(*, period: str, year: int, month: int | None = None) -> str:
    """Return CSV string of expenses for the given period."""
    rollup = compute_rollup(period=period, year=year, month=month)
    expenses = _load_expenses()

    def _in_period(e: Expense) -> bool:
        dt = e.submitted_at
        if period == "month":
            return dt.year == year and dt.month == month
        if period == "quarter" and month is not None:
            q = (month - 1) // 3 + 1
            expense_q = (dt.month - 1) // 3 + 1
            return dt.year == year and expense_q == q
        return False

    filtered = [e for e in expenses if _in_period(e)]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "submitted_at",
            "vendor",
            "category",
            "amount_cents",
            "amount_usd",
            "currency",
            "status",
            "submitted_by",
            "tags",
            "notes",
            "tax_deductible_pct",
        ]
    )
    for e in sorted(filtered, key=lambda x: x.submitted_at):
        writer.writerow(
            [
                e.id,
                e.submitted_at.isoformat(),
                e.vendor,
                e.category,
                e.amount_cents,
                f"{e.amount_cents / 100:.2f}",
                e.currency,
                e.status,
                e.submitted_by,
                ";".join(e.tags),
                e.notes,
                e.tax_deductible_pct if e.tax_deductible_pct is not None else "",
            ]
        )

    _ = rollup  # available for future summary row
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Receipt attachment storage
# ---------------------------------------------------------------------------


def store_attachment(content: bytes, mime: str) -> ExpenseAttachment:
    sha = hashlib.sha256(content).hexdigest()
    ext = mime.split("/")[-1].split(";")[0].strip() or "bin"
    filename = f"{sha}.{ext}"
    dest = os.path.join(_attachments_dir(), filename)
    if not os.path.exists(dest):
        with open(dest, "wb") as f:
            f.write(content)
    return ExpenseAttachment(
        kind="receipt",
        url=f"/admin/expenses/attachments/{sha}",
        mime=mime,
        sha256=sha,
        size_bytes=len(content),
    )


def get_attachment_path(sha256: str) -> str | None:
    d = _attachments_dir()
    for fname in os.listdir(d):
        if fname.startswith(sha256):
            return os.path.join(d, fname)
    return None


# ---------------------------------------------------------------------------
# Backfill from docs/FINANCIALS.md
# ---------------------------------------------------------------------------

_BACKFILL_ROWS = [
    (
        "Dynadot / filefree.ai domain",
        22000,
        "domains",
        "2026-03-15T00:00:00Z",
        "USD",
        "2yr registration",
    ),
    (
        "Dynadot / launchfree.ai domain",
        22000,
        "domains",
        "2026-03-15T00:00:00Z",
        "USD",
        "2yr registration",
    ),
    ("Namecheap / paperworklabs.com", 1200, "domains", "2026-03-15T00:00:00Z", "USD", "Annual"),
    ("Namecheap / distill.tax domain", 800, "domains", "2026-03-15T00:00:00Z", "USD", "Annual"),
    ("Hetzner VPS CX33", 600, "infra", "2026-03-01T00:00:00Z", "USD", "Monthly — n8n/Redis/PG"),
    ("Render FileFree API", 700, "infra", "2026-03-01T00:00:00Z", "USD", "Starter 512MB"),
    ("Google Workspace (1 seat)", 600, "ops", "2026-03-01T00:00:00Z", "USD", "Monthly"),
    ("OpenAI API", 1000, "ai", "2026-03-01T00:00:00Z", "USD", "Monthly dev usage"),
    ("ElevenLabs Starter", 500, "ai", "2026-03-01T00:00:00Z", "USD", "Voice clone plan"),
]


def backfill_from_financials() -> int:
    """Parse known expenses from FINANCIALS.md and create as status=reimbursed. Idempotent."""
    existing = _load_expenses()
    existing_notes = {e.notes for e in existing if e.status == "reimbursed"}

    created = 0
    for vendor, amount_cents, category, submitted_at_iso, currency, notes in _BACKFILL_ROWS:
        if notes in existing_notes:
            continue
        expense = Expense(
            id=f"exp_backfill_{uuid.uuid4().hex[:12]}",
            amount_cents=amount_cents,
            currency=currency,
            vendor=vendor,
            category=category,  # type: ignore[arg-type]
            tags=["backfill"],
            status="reimbursed",
            submitted_at=datetime.fromisoformat(submitted_at_iso.replace("Z", "+00:00")),
            approved_at=datetime.fromisoformat(submitted_at_iso.replace("Z", "+00:00")),
            reimbursed_at=datetime.fromisoformat(submitted_at_iso.replace("Z", "+00:00")),
            attachments=[],
            notes=notes,
            submitted_by="system_backfill",
        )

        def mutate(raw: dict, _exp: Expense = expense) -> tuple[dict, None]:
            raw.setdefault("schema", "expenses/v1")
            raw.setdefault("expenses", [])
            raw["expenses"].append(_exp.model_dump(mode="json"))
            return raw, None

        _locked_read_write(_expenses_path(), mutate)
        existing_notes.add(notes)
        created += 1

    logger.info("expense backfill: created %d rows", created)
    return created


# ---------------------------------------------------------------------------
# Pending count helper (for sidebar badge)
# ---------------------------------------------------------------------------


def pending_count() -> int:
    return sum(1 for e in _load_expenses() if e.status in ("pending", "flagged"))
