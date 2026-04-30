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
from collections.abc import Callable  # noqa: TC003
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas.conversation import Conversation, ConversationCreate, ConversationLinks
from app.schemas.expenses import (
    CategoryTotal,
    Expense,
    ExpenseCategory,
    ExpenseCreate,
    ExpenseEdit,
    ExpenseRoutingRules,
    ExpensesListPage,
    ExpenseSource,
    ExpenseStatus,
    ExpenseStatusUpdate,
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


def load_routing_rules() -> ExpenseRoutingRules:
    """Load routing rules via ``expense_rules`` (raises on corrupt JSON — no silent fallback)."""
    from app.services import expense_rules as erules

    return erules.load_rules()


def save_routing_rules(rules: ExpenseRoutingRules) -> ExpenseRoutingRules:
    """Persist routing rules with append-only history."""
    from app.services import expense_rules as erules

    return erules.save_rules(rules, updated_by=rules.updated_by)


def derived_repo_root_from_expense_store() -> str | None:
    """Resolve monorepo root for Conversations + audit posts.

    Prefer deriving from ``BRAIN_EXPENSES_JSON`` when it lives under
    ``.../apis/brain/data/``. Otherwise fall back to ``REPO_ROOT`` so
    expense flows and rules PUT still create Conversations in dev/prod
    without a custom expenses path env.
    """
    ex = os.environ.get(_ENV_EXPENSES_JSON, "").strip()
    if ex:
        p = Path(ex).resolve()
        parts = p.parts
        if "apis" in parts and "brain" in parts and "data" in parts:
            i = parts.index("apis")
            return str(Path(*parts[:i]))
    root = os.environ.get(_ENV_REPO_ROOT, "").strip()
    return root or None


def _with_repo_root_for_conversations(fn: Callable[[], str]) -> str:
    derived = derived_repo_root_from_expense_store()
    if derived is None:
        return fn()
    old = os.environ.get(_ENV_REPO_ROOT)
    os.environ[_ENV_REPO_ROOT] = derived
    try:
        return fn()
    finally:
        if old is None:
            os.environ.pop(_ENV_REPO_ROOT, None)
        else:
            os.environ[_ENV_REPO_ROOT] = old


def _format_money_cents(cents: int, currency: str = "USD") -> str:
    return f"{cents / 100:.2f} {currency}"


def _render_expense_card_md(expense: Expense) -> str:
    lines = [
        "### Expense approval",
        f"- **Vendor:** {expense.vendor}",
        f"- **Amount:** {_format_money_cents(expense.amount_cents, expense.currency)}",
        f"- **Category:** {expense.category}",
        f"- **Classified by:** {expense.classified_by}",
        f"- **Occurred:** {expense.occurred_at}",
    ]
    if expense.notes.strip():
        lines.append(f"- **Notes:** {expense.notes.strip()}")
    if expense.receipt:
        lines.append(f"- **Receipt:** `{expense.receipt.filename}`")
    lines.append("")
    lines.append("Use the action buttons below to approve, change category, flag, or reject.")
    return "\n".join(lines)


def _routing_decision(expense: Expense, rules: ExpenseRoutingRules) -> tuple[ExpenseStatus, bool]:
    """Return (status, needs_approval_conversation)."""
    if expense.amount_cents > rules.flag_amount_cents_above:
        return "flagged", True
    if expense.category in rules.always_review_categories:
        return "pending", True
    if (
        rules.auto_approve_threshold_cents > 0
        and expense.amount_cents < rules.auto_approve_threshold_cents
        and expense.category in rules.auto_approve_categories
    ):
        return "approved", False
    return "pending", True


def _apply_expense_action(
    expense: Expense,
    expense_action: str,
    new_category: ExpenseCategory | None,
) -> Expense:
    now = datetime.now(UTC).isoformat()
    if expense_action == "approve":
        target: ExpenseStatus = "approved"
        patch: dict[str, Any] = {"status": target, "approved_at": now}
    elif expense_action == "approve-change-category":
        if new_category is None:
            raise ValueError("new_category is required for approve-change-category")
        patch = {"status": "approved", "category": new_category, "approved_at": now}
    elif expense_action == "flag":
        patch = {"status": "flagged"}
    elif expense_action == "reject":
        patch = {"status": "rejected"}
    else:
        raise ValueError(f"Unknown expense_action: {expense_action!r}")

    allowed = _ALLOWED_TRANSITIONS.get(expense.status, set())
    new_status = patch["status"]
    if new_status not in allowed:
        raise ValueError(f"Cannot transition {expense.status} → {new_status}")
    return expense.model_copy(update=patch)


def resolve_expense_linked_conversation(
    conversation_id: str,
    expense_action: str,
    new_category: ExpenseCategory | None,
) -> tuple[Expense, Conversation]:
    """Atomically resolve the Conversation and update the linked Expense (expense lock held)."""
    from app.services import conversations as conv_svc

    out: dict[str, Any] = {}

    def mutate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        try:
            conv_inner = conv_svc.get_conversation(conversation_id)
        except KeyError as exc:
            raise ValueError(f"Conversation {conversation_id!r} not found") from exc
        if conv_inner.links is None or not conv_inner.links.expense_id:
            raise ValueError("Conversation has no expense_id link")
        eid = conv_inner.links.expense_id
        for i, raw in enumerate(rows):
            if raw.get("id") != eid:
                continue
            expense = _parse_expense(raw)
            if expense is None:
                raise ValueError("Linked expense row is invalid")
            if expense.conversation_id != conversation_id:
                raise ValueError("Expense is not linked to this conversation")
            updated = _apply_expense_action(expense, expense_action, new_category)
            rows[i] = updated.model_dump(mode="json")
            conv_done = conv_inner.model_copy(
                update={
                    "status": "resolved",
                    "updated_at": datetime.now(UTC),
                    "needs_founder_action": False,
                }
            )
            conv_svc._save_conversation(conv_done)
            out["expense"] = updated
            out["conversation"] = conv_done
            return rows
        raise ValueError("Linked expense not found in store")

    _locked_read_write(mutate)
    return out["expense"], out["conversation"]


async def classify_and_route(payload: ExpenseCreate, *, expense_id: str) -> Expense:
    """CFO classify when requested, apply routing rules, optionally create approval Conversation.

    Called from expense creation before the row is appended to ``expenses.json``.
    """
    from app.personas import cfo_classifier
    from app.services import conversations as conv_svc

    rules = load_routing_rules()
    now = datetime.now(UTC).isoformat()

    category: ExpenseCategory = payload.category
    classified_by = "founder"
    if payload.use_cfo_classify:
        try:
            from app.redis import get_redis

            redis_client = get_redis()
        except RuntimeError:
            redis_client = None
        cat, _flag_reason = await cfo_classifier.classify(
            amount_cents=payload.amount_cents,
            merchant=payload.vendor,
            description=payload.notes or "",
            redis_client=redis_client,
        )
        category = cat
        classified_by = "cfo-persona"

    expense = Expense(
        id=expense_id,
        vendor=payload.vendor,
        amount_cents=payload.amount_cents,
        currency=payload.currency,
        category=category,
        status="pending",
        source=payload.source,
        classified_by=classified_by,
        occurred_at=payload.occurred_at,
        submitted_at=now,
        notes=payload.notes,
        tags=payload.tags,
        conversation_id=None,
    )

    status, needs_conv = _routing_decision(expense, rules)
    patch: dict[str, Any] = {"status": status}
    if status == "approved":
        patch["approved_at"] = datetime.now(UTC).isoformat()
    expense = expense.model_copy(update=patch)

    conv_id: str | None = None
    if needs_conv:

        def _mk() -> str:
            amt = _format_money_cents(expense.amount_cents, expense.currency)
            create = ConversationCreate(
                title=f"Expense: {expense.vendor} ({amt})",
                body_md=_render_expense_card_md(expense),
                tags=["expense-approval"],
                urgency="normal",
                persona="cfo",
                needs_founder_action=True,
                links=ConversationLinks(expense_id=expense.id),
            )
            conv = conv_svc.create_conversation(create)
            return conv.id

        derived = derived_repo_root_from_expense_store()
        if derived is not None:
            conv_id = _with_repo_root_for_conversations(_mk)
            expense = expense.model_copy(update={"conversation_id": conv_id})
        else:
            logger.warning(
                "expense %s: skipping approval Conversation "
                "(no REPO_ROOT / monorepo path for Conversations)",
                expense.id,
            )

    return expense


async def _submit_expense_impl(payload: ExpenseCreate) -> Expense:
    """Create expense row: classify, route, persist."""
    expense_id = str(uuid.uuid4())
    expense = await classify_and_route(payload, expense_id=expense_id)
    row = expense.model_dump(mode="json")

    def mutate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows.append(row)
        return rows

    _locked_read_write(mutate)
    return expense


def submit_expense(payload: ExpenseCreate) -> Expense:
    """Sync entrypoint for tests and tooling. Async callers must use ``asyncio.to_thread``."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_submit_expense_impl(payload))
    raise RuntimeError(
        "submit_expense() cannot run inside an active event loop; "
        "await asyncio.to_thread(expenses.submit_expense, payload) instead"
    )


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
