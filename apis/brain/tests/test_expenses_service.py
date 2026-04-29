"""Tests for WS-69 PR N — Expense service, receipts, rollup, CSV, and routing rules.

Uses tmp_path fixtures for isolated JSON stores; no DB required.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.schemas.expenses import (
    ExpenseCreate,
    ExpenseStatusUpdate,
)

# ---------------------------------------------------------------------------
# Helpers to point service at tmp files
# ---------------------------------------------------------------------------


def _seed_store(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows), encoding="utf-8")


def _use_tmp_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    expenses_path = tmp_path / "expenses.json"
    expenses_path.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("BRAIN_EXPENSES_JSON", str(expenses_path))
    return expenses_path


def _use_tmp_rules(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rules: dict | None = None
) -> Path:
    rules_path = tmp_path / "rules.json"
    default_rules = {
        "auto_approve_threshold_cents": 0,
        "auto_approve_categories": [],
        "always_review_categories": [],
        "flag_amount_cents_above": 100000,
        "founder_card_default_source": "founder-card",
        "subscription_skip_approval": False,
        "updated_at": "2026-04-29T19:00:00Z",
        "updated_by": "founder",
        "history": [],
    }
    if rules:
        default_rules.update(rules)
    rules_path.write_text(json.dumps(default_rules), encoding="utf-8")
    monkeypatch.setenv("BRAIN_EXPENSE_RULES_JSON", str(rules_path))
    return rules_path


def _make_payload(**kwargs) -> ExpenseCreate:
    defaults = {
        "vendor": "Hetzner",
        "amount_cents": 600,
        "currency": "USD",
        "category": "infra",
        "source": "manual",
        "occurred_at": "2026-04-15",
        "notes": "Monthly VPS",
    }
    defaults.update(kwargs)
    return ExpenseCreate(**defaults)


# ---------------------------------------------------------------------------
# import after env var setup — reimport each test for isolation
# ---------------------------------------------------------------------------


def _svc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _use_tmp_store(monkeypatch, tmp_path)
    _use_tmp_rules(monkeypatch, tmp_path)
    import importlib

    import app.services.expenses as svc

    importlib.reload(svc)
    return svc


# ---------------------------------------------------------------------------
# Submit — routing paths
# ---------------------------------------------------------------------------


class TestSubmit:
    def test_submit_goes_to_pending_with_zero_threshold(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        svc = _svc(monkeypatch, tmp_path)
        expense = svc.submit_expense(_make_payload())
        assert expense.status == "pending"

    def test_auto_approve_when_threshold_raised(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _use_tmp_store(monkeypatch, tmp_path)
        _use_tmp_rules(
            monkeypatch,
            tmp_path,
            {
                "auto_approve_threshold_cents": 1000,
                "auto_approve_categories": ["infra"],
                "always_review_categories": [],
            },
        )
        import importlib

        import app.services.expenses as svc

        importlib.reload(svc)
        expense = svc.submit_expense(_make_payload(amount_cents=500, category="infra"))
        assert expense.status == "approved"
        assert expense.approved_at is not None

    def test_always_review_prevents_auto_approve(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _use_tmp_store(monkeypatch, tmp_path)
        _use_tmp_rules(
            monkeypatch,
            tmp_path,
            {
                "auto_approve_threshold_cents": 10000,
                "auto_approve_categories": ["legal"],
                "always_review_categories": ["legal"],
            },
        )
        import importlib

        import app.services.expenses as svc

        importlib.reload(svc)
        expense = svc.submit_expense(_make_payload(amount_cents=500, category="legal"))
        assert expense.status == "pending"

    def test_flag_when_above_threshold(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        svc = _svc(monkeypatch, tmp_path)
        expense = svc.submit_expense(_make_payload(amount_cents=150000))
        assert expense.status == "flagged"

    def test_above_threshold_flags_even_if_auto_approve_category(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _use_tmp_store(monkeypatch, tmp_path)
        _use_tmp_rules(
            monkeypatch,
            tmp_path,
            {
                "auto_approve_threshold_cents": 200000,
                "auto_approve_categories": ["infra"],
                "always_review_categories": [],
                "flag_amount_cents_above": 100000,
            },
        )
        import importlib

        import app.services.expenses as svc

        importlib.reload(svc)
        expense = svc.submit_expense(_make_payload(amount_cents=150000, category="infra"))
        assert expense.status == "flagged"

    def test_submit_creates_record_with_id(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        svc = _svc(monkeypatch, tmp_path)
        expense = svc.submit_expense(_make_payload())
        assert expense.id
        assert expense.vendor == "Hetzner"
        assert expense.amount_cents == 600


# ---------------------------------------------------------------------------
# List + filters
# ---------------------------------------------------------------------------


class TestList:
    def test_list_returns_all(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        svc.submit_expense(_make_payload(vendor="A"))
        svc.submit_expense(_make_payload(vendor="B"))
        page = svc.list_expenses()
        assert page.total == 2
        assert len(page.items) == 2

    def test_filter_by_status(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        svc.submit_expense(_make_payload(amount_cents=200000))  # → flagged
        svc.submit_expense(_make_payload(amount_cents=500))  # → pending
        pending = svc.list_expenses(status="pending")
        flagged = svc.list_expenses(status="flagged")
        assert pending.total == 1
        assert flagged.total == 1

    def test_filter_by_category(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        svc.submit_expense(_make_payload(category="infra"))
        svc.submit_expense(_make_payload(category="tools"))
        page = svc.list_expenses(category="infra")
        assert page.total == 1

    def test_search_by_vendor(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        svc.submit_expense(_make_payload(vendor="Hetzner"))
        svc.submit_expense(_make_payload(vendor="OpenAI"))
        page = svc.list_expenses(search="openai")
        assert page.total == 1
        assert page.items[0].vendor == "OpenAI"

    def test_pagination(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        for i in range(5):
            svc.submit_expense(_make_payload(vendor=f"Vendor{i}"))
        page1 = svc.list_expenses(limit=3)
        assert len(page1.items) == 3
        assert page1.has_more
        page2 = svc.list_expenses(limit=3, cursor=page1.next_cursor)
        assert len(page2.items) == 2
        assert not page2.has_more

    def test_count_only(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        svc.submit_expense(_make_payload())
        page = svc.list_expenses(count_only=True)
        assert page.total == 1
        assert page.items == []


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


class TestStatusTransitions:
    def test_pending_to_approved(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        expense = svc.submit_expense(_make_payload())
        assert expense.status == "pending"
        updated = svc.update_expense_status(expense.id, ExpenseStatusUpdate(status="approved"))
        assert updated is not None
        assert updated.status == "approved"
        assert updated.approved_at is not None

    def test_approved_to_reimbursed(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        expense = svc.submit_expense(_make_payload())
        svc.update_expense_status(expense.id, ExpenseStatusUpdate(status="approved"))
        updated = svc.update_expense_status(expense.id, ExpenseStatusUpdate(status="reimbursed"))
        assert updated is not None
        assert updated.status == "reimbursed"
        assert updated.reimbursed_at is not None

    def test_reimbursed_is_terminal(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        expense = svc.submit_expense(_make_payload())
        svc.update_expense_status(expense.id, ExpenseStatusUpdate(status="approved"))
        svc.update_expense_status(expense.id, ExpenseStatusUpdate(status="reimbursed"))
        with pytest.raises(ValueError, match="Cannot transition reimbursed"):
            svc.update_expense_status(expense.id, ExpenseStatusUpdate(status="pending"))

    def test_rejected_is_terminal(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        expense = svc.submit_expense(_make_payload())
        svc.update_expense_status(expense.id, ExpenseStatusUpdate(status="rejected"))
        with pytest.raises(ValueError, match="Cannot transition rejected"):
            svc.update_expense_status(expense.id, ExpenseStatusUpdate(status="approved"))

    def test_invalid_expense_id_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        svc = _svc(monkeypatch, tmp_path)
        result = svc.update_expense_status("nonexistent-id", ExpenseStatusUpdate(status="approved"))
        assert result is None


# ---------------------------------------------------------------------------
# Rollup math
# ---------------------------------------------------------------------------


class TestRollup:
    def _make_expense_dict(
        self,
        occurred_at: str,
        amount_cents: int,
        category: str = "infra",
        status: str = "approved",
    ) -> dict:
        return {
            "id": f"test-{occurred_at}-{amount_cents}",
            "vendor": "TestVendor",
            "amount_cents": amount_cents,
            "currency": "USD",
            "category": category,
            "status": status,
            "source": "manual",
            "classified_by": "founder",
            "occurred_at": occurred_at,
            "submitted_at": datetime.now(UTC).isoformat(),
            "notes": "",
            "tags": [],
        }

    def test_empty_month_returns_zeros(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _use_tmp_store(monkeypatch, tmp_path)
        import importlib

        import app.services.expenses as svc

        importlib.reload(svc)
        rollup = svc.compute_monthly_rollup(2026, 1)
        assert rollup.total_cents == 0
        assert rollup.expense_count == 0
        assert rollup.prior_3mo_avg_cents == 0
        assert rollup.pct_vs_prior_avg is None

    def test_single_expense_rollup(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        expenses_path = tmp_path / "expenses.json"
        expenses_path.write_text(
            json.dumps([self._make_expense_dict("2026-04-01", 5000)]), encoding="utf-8"
        )
        monkeypatch.setenv("BRAIN_EXPENSES_JSON", str(expenses_path))
        import importlib

        import app.services.expenses as svc

        importlib.reload(svc)
        rollup = svc.compute_monthly_rollup(2026, 4)
        assert rollup.total_cents == 5000
        assert rollup.expense_count == 1
        assert rollup.approved_cents == 5000

    def test_multi_expense_category_breakdown(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        expenses_path = tmp_path / "expenses.json"
        expenses_path.write_text(
            json.dumps(
                [
                    self._make_expense_dict("2026-04-01", 1000, "infra"),
                    self._make_expense_dict("2026-04-15", 2000, "ai"),
                    self._make_expense_dict("2026-04-20", 500, "infra"),
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("BRAIN_EXPENSES_JSON", str(expenses_path))
        import importlib

        import app.services.expenses as svc

        importlib.reload(svc)
        rollup = svc.compute_monthly_rollup(2026, 4)
        assert rollup.total_cents == 3500
        cats = {c.category: c.amount_cents for c in rollup.category_breakdown}
        assert cats["infra"] == 1500
        assert cats["ai"] == 2000

    def test_prior_3mo_avg_denom_safety(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When no prior months exist, avg must be 0 and pct_vs_prior_avg None."""
        expenses_path = tmp_path / "expenses.json"
        expenses_path.write_text(
            json.dumps([self._make_expense_dict("2026-01-01", 1000)]), encoding="utf-8"
        )
        monkeypatch.setenv("BRAIN_EXPENSES_JSON", str(expenses_path))
        import importlib

        import app.services.expenses as svc

        importlib.reload(svc)
        rollup = svc.compute_monthly_rollup(2026, 1)
        # No prior months before Jan 2026 in our store
        assert rollup.prior_3mo_avg_cents == 0
        assert rollup.pct_vs_prior_avg is None

    def test_quarterly_rollup_sums_months(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        expenses_path = tmp_path / "expenses.json"
        expenses_path.write_text(
            json.dumps(
                [
                    self._make_expense_dict("2026-01-10", 1000),
                    self._make_expense_dict("2026-02-10", 2000),
                    self._make_expense_dict("2026-03-10", 3000),
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("BRAIN_EXPENSES_JSON", str(expenses_path))
        import importlib

        import app.services.expenses as svc

        importlib.reload(svc)
        rollup = svc.compute_quarterly_rollup(2026, 1)
        assert rollup.total_cents == 6000
        assert rollup.expense_count == 3
        assert len(rollup.months) == 3


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


class TestCsvExport:
    def test_csv_has_correct_columns(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        svc.submit_expense(_make_payload())
        csv_str = svc.export_csv()
        header = csv_str.splitlines()[0]
        for col in ["id", "vendor", "amount_cents", "amount_dollars", "category", "status"]:
            assert col in header

    def test_csv_row_values(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        svc.submit_expense(_make_payload(vendor="Render", amount_cents=700, category="infra"))
        csv_str = svc.export_csv()
        assert "Render" in csv_str
        assert "7.00" in csv_str
        assert "infra" in csv_str

    def test_empty_store_csv_header_only(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        svc = _svc(monkeypatch, tmp_path)
        csv_str = svc.export_csv()
        lines = [row for row in csv_str.splitlines() if row.strip()]
        assert len(lines) == 1  # header only


# ---------------------------------------------------------------------------
# Routing rules
# ---------------------------------------------------------------------------


class TestRoutingRules:
    def test_load_defaults_when_file_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("BRAIN_EXPENSE_RULES_JSON", str(tmp_path / "nonexistent.json"))
        import importlib

        import app.services.expenses as svc

        importlib.reload(svc)
        rules = svc.load_routing_rules()
        assert rules.auto_approve_threshold_cents == 0
        assert rules.flag_amount_cents_above == 100000

    def test_save_and_reload_rules(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _use_tmp_rules(monkeypatch, tmp_path)
        import importlib

        import app.services.expenses as svc

        importlib.reload(svc)
        rules = svc.load_routing_rules()
        rules.auto_approve_threshold_cents = 5000
        svc.save_routing_rules(rules)
        reloaded = svc.load_routing_rules()
        assert reloaded.auto_approve_threshold_cents == 5000

    def test_corrupted_rules_file_returns_defaults(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        rules_path = tmp_path / "bad_rules.json"
        rules_path.write_text("this is not json", encoding="utf-8")
        monkeypatch.setenv("BRAIN_EXPENSE_RULES_JSON", str(rules_path))
        import importlib

        import app.services.expenses as svc

        importlib.reload(svc)
        rules = svc.load_routing_rules()
        # Should not raise; returns defaults
        assert rules.auto_approve_threshold_cents == 0


# ---------------------------------------------------------------------------
# Receipt validation
# ---------------------------------------------------------------------------


class TestReceiptValidation:
    def test_valid_jpeg_passes(self) -> None:
        from app.services.expense_receipts import validate_receipt

        validate_receipt("photo.jpg", "image/jpeg", 1024)  # No raise

    def test_disallowed_mime_raises(self) -> None:
        from app.services.expense_receipts import validate_receipt

        with pytest.raises(ValueError, match="not allowed"):
            validate_receipt("file.exe", "application/octet-stream", 1024)

    def test_too_large_raises(self) -> None:
        from app.services.expense_receipts import validate_receipt

        with pytest.raises(ValueError, match="too large"):
            validate_receipt("big.pdf", "application/pdf", 11 * 1024 * 1024)

    def test_path_traversal_raises(self) -> None:
        from app.services.expense_receipts import validate_receipt

        with pytest.raises(ValueError, match="Invalid filename"):
            validate_receipt("../../etc/passwd", "image/jpeg", 100)


# ---------------------------------------------------------------------------
# FINANCIALS.md seed parser
# ---------------------------------------------------------------------------


class TestFinancialsSeedParser:
    def test_parse_date_mar_2026(self) -> None:
        from scripts.seed_expenses_from_financials_md import _parse_date

        assert _parse_date("Mar 2026") == "2026-03-01"

    def test_parse_date_tbd(self) -> None:
        from scripts.seed_expenses_from_financials_md import _parse_date

        assert _parse_date("TBD") == "2026-01-01"

    def test_parse_amount_dollars(self) -> None:
        from scripts.seed_expenses_from_financials_md import _parse_amount_cents

        assert _parse_amount_cents("$220") == 22000

    def test_parse_amount_approx(self) -> None:
        from scripts.seed_expenses_from_financials_md import _parse_amount_cents

        assert _parse_amount_cents("~$10/mo") == 1000

    def test_parse_amount_range_takes_lower(self) -> None:
        from scripts.seed_expenses_from_financials_md import _parse_amount_cents

        result = _parse_amount_cents("~$500-1,000")
        assert result == 50000

    def test_parse_amount_none_for_garbage(self) -> None:
        from scripts.seed_expenses_from_financials_md import _parse_amount_cents

        assert _parse_amount_cents("Varies") is None

    def test_category_map_domain(self) -> None:
        from scripts.seed_expenses_from_financials_md import _map_category

        assert _map_category("Domain") == "domains"

    def test_category_map_fallback_misc(self) -> None:
        from scripts.seed_expenses_from_financials_md import _map_category

        assert _map_category("Unknown Category XYZ") == "misc"

    def test_content_uuid_deterministic(self) -> None:
        from scripts.seed_expenses_from_financials_md import _content_uuid

        uid1 = _content_uuid("test-content")
        uid2 = _content_uuid("test-content")
        assert uid1 == uid2

    def test_content_uuid_different_for_different_content(self) -> None:
        from scripts.seed_expenses_from_financials_md import _content_uuid

        uid1 = _content_uuid("content-a")
        uid2 = _content_uuid("content-b")
        assert uid1 != uid2
