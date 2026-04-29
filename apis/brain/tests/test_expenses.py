"""Tests for expense service, router, and backfill (WS-69 PR N)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BRAIN_EXPENSES_JSON", str(tmp_path / "expenses.json"))
    monkeypatch.setenv("BRAIN_EXPENSE_RULES_JSON", str(tmp_path / "rules.json"))
    monkeypatch.setenv("BRAIN_EXPENSE_AUDITS_JSON", str(tmp_path / "audits.json"))
    monkeypatch.setenv("BRAIN_EXPENSE_EVENTS_JSON", str(tmp_path / "events.json"))
    monkeypatch.setenv("BRAIN_EXPENSE_ATTACHMENTS_DIR", str(tmp_path / "attachments"))


def _default_create_kwargs() -> dict:
    return {
        "amount_cents": 2500,
        "currency": "USD",
        "vendor": "Acme Corp",
        "category": "ops",
        "tags": ["test"],
        "notes": "test expense",
        "submitted_by": "user_test123",
    }


# ---------------------------------------------------------------------------
# Schema smoke
# ---------------------------------------------------------------------------


def test_expense_schema_roundtrip() -> None:
    from app.schemas.expenses import Expense, ExpenseRoutingRules

    rules = ExpenseRoutingRules()
    assert rules.auto_approve_threshold_cents == 0
    assert "legal" in rules.flagged_categories

    from datetime import UTC, datetime

    expense = Expense(
        id="exp_abc",
        amount_cents=5000,
        currency="USD",
        vendor="Test",
        category="ops",
        status="pending",
        submitted_at=datetime.now(UTC),
        submitted_by="user_test",
    )
    dumped = expense.model_dump(mode="json")
    assert dumped["id"] == "exp_abc"
    assert dumped["conversation_id"] is None


# ---------------------------------------------------------------------------
# Service: empty state
# ---------------------------------------------------------------------------


def test_list_expenses_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.services import expenses as svc

    result = svc.list_expenses(filter_status="pending")
    assert result["items"] == []
    assert result["total"] == 0
    assert result["next_cursor"] is None


def test_pending_count_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.services import expenses as svc

    assert svc.pending_count() == 0


# ---------------------------------------------------------------------------
# Service: create with $0 threshold → all pending
# ---------------------------------------------------------------------------


def test_create_expense_zero_threshold_all_pending(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.schemas.expenses import ExpenseCreate
    from app.services import expenses as svc

    # Ensure rules default to $0 threshold
    rules = svc.load_routing_rules()
    assert rules.auto_approve_threshold_cents == 0

    expense = svc.create_expense(ExpenseCreate(**_default_create_kwargs()))
    assert expense.status == "pending"

    result = svc.list_expenses(filter_status="pending")
    assert result["total"] == 1
    assert result["items"][0]["id"] == expense.id


def test_create_multiple_all_pending_at_zero_threshold(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.schemas.expenses import ExpenseCreate
    from app.services import expenses as svc

    for i in range(3):
        kwargs = _default_create_kwargs()
        kwargs["amount_cents"] = (i + 1) * 1000
        svc.create_expense(ExpenseCreate(**kwargs))

    result = svc.list_expenses(filter_status="pending")
    assert result["total"] == 3


# ---------------------------------------------------------------------------
# Service: flagged categories
# ---------------------------------------------------------------------------


def test_legal_expense_auto_flagged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.schemas.expenses import ExpenseCreate
    from app.services import expenses as svc

    kwargs = _default_create_kwargs()
    kwargs["category"] = "legal"
    kwargs["amount_cents"] = 100  # tiny amount — but legal is flagged_category

    expense = svc.create_expense(ExpenseCreate(**kwargs))
    assert expense.status == "flagged"


def test_large_amount_auto_flagged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.schemas.expenses import ExpenseCreate
    from app.services import expenses as svc

    kwargs = _default_create_kwargs()
    kwargs["amount_cents"] = 60000  # >= flagged_threshold_cents (50000)

    expense = svc.create_expense(ExpenseCreate(**kwargs))
    assert expense.status == "flagged"


# ---------------------------------------------------------------------------
# Service: routing rules update → audit logged
# ---------------------------------------------------------------------------


def test_update_routing_rules_audit_logged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.schemas.expenses import ExpenseRoutingRules
    from app.services import expenses as svc

    new_rules = ExpenseRoutingRules(
        auto_approve_threshold_cents=5000,
        auto_approve_categories=["ops", "tools"],
        flagged_threshold_cents=100000,
        flagged_categories=["legal"],
    )
    svc.update_routing_rules(new_rules, changed_by="user_founder", note="Raising threshold")

    audits_path = str(tmp_path / "audits.json")
    with open(audits_path) as f:
        data = json.load(f)
    audits = data["audits"]
    assert len(audits) == 1
    assert audits[0]["changed_by"] == "user_founder"
    assert audits[0]["note"] == "Raising threshold"
    assert audits[0]["previous"]["auto_approve_threshold_cents"] == 0
    assert audits[0]["updated"]["auto_approve_threshold_cents"] == 5000


def test_raised_threshold_auto_approves(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.schemas.expenses import ExpenseCreate, ExpenseRoutingRules
    from app.services import expenses as svc

    new_rules = ExpenseRoutingRules(
        auto_approve_threshold_cents=10000,
        auto_approve_categories=["ops"],
        flagged_threshold_cents=100000,
        flagged_categories=["legal", "tax"],
    )
    svc.update_routing_rules(new_rules, changed_by="user_founder")

    # Below threshold + in auto_approve_categories → approved
    kwargs = _default_create_kwargs()
    kwargs["amount_cents"] = 500
    kwargs["category"] = "ops"
    expense = svc.create_expense(ExpenseCreate(**kwargs))
    assert expense.status == "approved"

    # Above threshold → pending
    kwargs2 = _default_create_kwargs()
    kwargs2["amount_cents"] = 15000
    kwargs2["category"] = "ops"
    expense2 = svc.create_expense(ExpenseCreate(**kwargs2))
    assert expense2.status == "pending"


# ---------------------------------------------------------------------------
# Service: approve / reject / reimburse transitions
# ---------------------------------------------------------------------------


def test_approve_expense(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.schemas.expenses import ExpenseCreate
    from app.services import expenses as svc

    expense = svc.create_expense(ExpenseCreate(**_default_create_kwargs()))
    assert expense.status == "pending"

    approved = svc.approve_expense(expense.id, approved_by="user_founder")
    assert approved is not None
    assert approved.status == "approved"
    assert approved.approved_at is not None


def test_reject_expense(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.schemas.expenses import ExpenseCreate
    from app.services import expenses as svc

    expense = svc.create_expense(ExpenseCreate(**_default_create_kwargs()))
    rejected = svc.reject_expense(expense.id, rejected_by="user_founder", reason="Duplicate")
    assert rejected is not None
    assert rejected.status == "rejected"


def test_mark_reimbursed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.schemas.expenses import ExpenseCreate
    from app.services import expenses as svc

    expense = svc.create_expense(ExpenseCreate(**_default_create_kwargs()))
    svc.approve_expense(expense.id, approved_by="user_founder")
    reimbursed = svc.mark_reimbursed(expense.id, reimbursed_by="user_founder")
    assert reimbursed is not None
    assert reimbursed.status == "reimbursed"
    assert reimbursed.reimbursed_at is not None


def test_get_expense_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.services import expenses as svc

    assert svc.get_expense("exp_nonexistent") is None


# ---------------------------------------------------------------------------
# Service: attachment round-trip
# ---------------------------------------------------------------------------


def test_attachment_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.schemas.expenses import ExpenseCreate
    from app.services import expenses as svc

    content = b"fake receipt content PDF"
    attachment = svc.store_attachment(content, "application/pdf")
    assert attachment.mime == "application/pdf"
    assert len(attachment.sha256) == 64

    recovered = svc.get_attachment_path(attachment.sha256)
    assert recovered is not None
    assert os.path.isfile(recovered)
    with open(recovered, "rb") as f:
        assert f.read() == content

    # Create expense with attachment
    expense = svc.create_expense(
        ExpenseCreate(**_default_create_kwargs()), attachments=[attachment]
    )
    assert len(expense.attachments) == 1
    assert expense.attachments[0].sha256 == attachment.sha256


# ---------------------------------------------------------------------------
# Service: rollup math
# ---------------------------------------------------------------------------


def test_rollup_math(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.schemas.expenses import ExpenseCreate
    from app.services import expenses as svc

    # Create some expenses
    for cat, cents in [("ops", 1000), ("ai", 2000), ("ops", 500)]:
        kwargs = _default_create_kwargs()
        kwargs["category"] = cat
        kwargs["amount_cents"] = cents
        svc.create_expense(ExpenseCreate(**kwargs))

    from datetime import UTC, datetime

    now = datetime.now(UTC)
    rollup = svc.compute_rollup(period="month", year=now.year, month=now.month)
    assert rollup.total_cents == 3500
    assert rollup.count == 3

    by_cat = {r.category: r.total_cents for r in rollup.by_category}
    assert by_cat["ops"] == 1500
    assert by_cat["ai"] == 2000


def test_rollup_empty_period(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.services import expenses as svc

    rollup = svc.compute_rollup(period="month", year=2020, month=1)
    assert rollup.total_cents == 0
    assert rollup.count == 0
    assert rollup.by_category == []


# ---------------------------------------------------------------------------
# Service: CSV export
# ---------------------------------------------------------------------------


def test_csv_export(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.schemas.expenses import ExpenseCreate
    from app.services import expenses as svc

    kwargs = _default_create_kwargs()
    svc.create_expense(ExpenseCreate(**kwargs))

    from datetime import UTC, datetime

    now = datetime.now(UTC)
    csv_data = svc.export_csv(period="month", year=now.year, month=now.month)
    lines = csv_data.strip().split("\n")
    assert lines[0].startswith("id,submitted_at")
    assert len(lines) == 2  # header + 1 row
    assert "Acme Corp" in lines[1]


# ---------------------------------------------------------------------------
# Service: backfill idempotency
# ---------------------------------------------------------------------------


def test_backfill_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.services import expenses as svc

    n1 = svc.backfill_from_financials()
    assert n1 > 0

    n2 = svc.backfill_from_financials()
    assert n2 == 0  # idempotent — nothing new to add

    all_exp = svc.list_expenses(filter_status="reimbursed", limit=100)
    assert all_exp["total"] == n1


# ---------------------------------------------------------------------------
# Service: pending_count includes flagged
# ---------------------------------------------------------------------------


def test_pending_count_includes_flagged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env(monkeypatch, tmp_path)
    from app.schemas.expenses import ExpenseCreate
    from app.services import expenses as svc

    # Create pending (ops)
    svc.create_expense(ExpenseCreate(**_default_create_kwargs()))
    # Create flagged (legal)
    kwargs_legal = _default_create_kwargs()
    kwargs_legal["category"] = "legal"
    svc.create_expense(ExpenseCreate(**kwargs_legal))

    count = svc.pending_count()
    assert count == 2
