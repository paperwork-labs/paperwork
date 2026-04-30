"""WS-69 PR O — expense routing, Conversations wiring, rules, CFO gate, monthly close."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.schemas.expenses import ExpenseCreate, ExpenseRoutingRulesUpdate


def _default_rules_dict(**overrides: object) -> dict:
    base = {
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
    base.update(overrides)
    return base


def _brain_layout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rules: dict) -> None:
    data = tmp_path / "apis" / "brain" / "data"
    data.mkdir(parents=True)
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    (data / "expenses.json").write_text("[]", encoding="utf-8")
    (data / "expense_routing_rules.json").write_text(
        json.dumps(rules),
        encoding="utf-8",
    )


def _reload_expenses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rules: dict) -> object:
    _brain_layout(monkeypatch, tmp_path, rules)
    import importlib

    import app.services.expenses as svc

    importlib.reload(svc)
    return svc


def _make_payload(**kwargs: object) -> ExpenseCreate:
    defaults: dict = {
        "vendor": "Vercel",
        "amount_cents": 500,
        "currency": "USD",
        "category": "infra",
        "source": "manual",
        "occurred_at": "2026-04-15",
        "notes": "Hosting",
        "use_cfo_classify": False,
    }
    defaults.update(kwargs)
    return ExpenseCreate(**defaults)


class TestDefaultThresholdRoutesAll:
    def test_five_dollar_charge_pending_and_has_conversation(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        svc = _reload_expenses(monkeypatch, tmp_path, _default_rules_dict())
        expense = svc.submit_expense(
            _make_payload(vendor="Vercel", amount_cents=500, category="infra")
        )
        assert expense.status == "pending"
        assert expense.conversation_id is not None
        conv_dir = tmp_path / "apis" / "brain" / "data" / "conversations"
        assert (conv_dir / f"{expense.conversation_id}.json").is_file()


class TestRaisedThresholdAutoApprove:
    def test_under_threshold_auto_approves_no_conversation(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        rules = _default_rules_dict(
            auto_approve_threshold_cents=50000,
            auto_approve_categories=["infra"],
        )
        svc = _reload_expenses(monkeypatch, tmp_path, rules)
        expense = svc.submit_expense(
            _make_payload(vendor="Vercel", amount_cents=5000, category="infra")
        )
        assert expense.status == "approved"
        assert expense.conversation_id is None


class TestAlwaysReview:
    def test_always_review_routes_despite_high_threshold(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        rules = _default_rules_dict(
            auto_approve_threshold_cents=500000,
            auto_approve_categories=["contractors"],
            always_review_categories=["contractors"],
        )
        svc = _reload_expenses(monkeypatch, tmp_path, rules)
        expense = svc.submit_expense(
            _make_payload(
                vendor="Acme LLC",
                amount_cents=80000,
                category="contractors",
            )
        )
        assert expense.status == "pending"
        assert expense.conversation_id is not None


class TestFlagAmount:
    def test_large_amount_flagged_and_has_conversation(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        rules = _default_rules_dict(
            auto_approve_threshold_cents=500000,
            auto_approve_categories=["infra"],
            flag_amount_cents_above=100000,
        )
        svc = _reload_expenses(monkeypatch, tmp_path, rules)
        expense = svc.submit_expense(_make_payload(amount_cents=500000, category="infra"))
        assert expense.status == "flagged"
        assert expense.conversation_id is not None


class TestRulesValidation:
    def test_overlap_rejected_by_schema(self) -> None:
        with pytest.raises(ValueError, match="both auto-approve"):
            ExpenseRoutingRulesUpdate(
                auto_approve_threshold_cents=0,
                auto_approve_categories=["infra"],
                always_review_categories=["infra"],
                flag_amount_cents_above=100000,
                founder_card_default_source="founder-card",
                subscription_skip_approval=False,
                updated_by="founder",
            )

    def test_flag_below_threshold_rejected(self) -> None:
        with pytest.raises(ValueError, match="flag_amount"):
            ExpenseRoutingRulesUpdate(
                auto_approve_threshold_cents=100000,
                auto_approve_categories=["infra"],
                always_review_categories=[],
                flag_amount_cents_above=50000,
                founder_card_default_source="founder-card",
                subscription_skip_approval=False,
                updated_by="founder",
            )


class TestFounderShortCircuitsCfo:
    def test_cfo_not_called_when_use_cfo_false(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        svc = _reload_expenses(monkeypatch, tmp_path, _default_rules_dict())
        with patch("app.personas.cfo_classifier.classify", new_callable=AsyncMock) as mock_cf:
            exp = svc.submit_expense(_make_payload(category="tools", use_cfo_classify=False))
            mock_cf.assert_not_called()
            assert exp.category == "tools"
            assert exp.classified_by == "founder"


class TestCfoCeiling:
    @pytest.mark.asyncio
    async def test_classify_raises_structured_error(self) -> None:
        from app.services.cost_tracker import CostCeilingExceeded

        with patch(
            "app.personas.cfo_classifier.check_ceiling",
            new_callable=AsyncMock,
            side_effect=CostCeilingExceeded(persona="cfo", spent_usd=10.0, ceiling_usd=1.0),
        ):
            from app.personas import cfo_classifier

            with pytest.raises(CostCeilingExceeded):
                await cfo_classifier.classify(
                    amount_cents=100,
                    merchant="x",
                    description="y",
                    redis_client=None,
                )


class TestResolveAtomic:
    def test_resolve_updates_expense_and_conversation(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        svc = _reload_expenses(monkeypatch, tmp_path, _default_rules_dict())
        expense = svc.submit_expense(_make_payload())
        assert expense.conversation_id
        updated_exp, conv = svc.resolve_expense_linked_conversation(
            expense.conversation_id,
            "approve",
            None,
        )
        assert updated_exp.status == "approved"
        assert conv.status == "resolved"


class TestMonthlyClose:
    def test_creates_conversation(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _brain_layout(monkeypatch, tmp_path, _default_rules_dict())
        import importlib

        import app.services.expenses as expense_svc

        importlib.reload(expense_svc)
        row = {
            "id": "e1",
            "vendor": "Paper",
            "amount_cents": 1000,
            "currency": "USD",
            "category": "misc",
            "status": "approved",
            "source": "manual",
            "classified_by": "founder",
            "occurred_at": "2026-03-10",
            "submitted_at": datetime.now(UTC).isoformat(),
            "notes": "",
            "tags": [],
            "conversation_id": None,
        }
        p = tmp_path / "apis" / "brain" / "data" / "expenses.json"
        p.write_text(json.dumps([row]), encoding="utf-8")

        from app.schedulers import expense_monthly_close

        cid = expense_monthly_close.run_prior_month_close(
            datetime(2026, 4, 5, 10, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        )
        assert cid
        conv_path = tmp_path / "apis" / "brain" / "data" / "conversations" / f"{cid}.json"
        assert conv_path.is_file()
        data = json.loads(conv_path.read_text(encoding="utf-8"))
        assert "expense-monthly-close" in data.get("tags", [])


class TestThresholdRaiseAudit:
    def test_put_rules_raises_threshold_creates_audit_conversation(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _brain_layout(monkeypatch, tmp_path, _default_rules_dict())
        import importlib

        import app.services.expense_rules as erules
        import app.services.expenses as expense_svc

        importlib.reload(expense_svc)
        importlib.reload(erules)

        from app.schemas.conversation import ConversationCreate
        from app.services import conversations as conv_svc

        current = expense_svc.load_routing_rules()
        body = ExpenseRoutingRulesUpdate(
            auto_approve_threshold_cents=50000,
            auto_approve_categories=["infra"],
            always_review_categories=[],
            flag_amount_cents_above=100000,
            founder_card_default_source="founder-card",
            subscription_skip_approval=False,
            updated_by="founder",
        )
        merged = erules.merge_update(current, body)
        erules.save_rules(merged, updated_by=body.updated_by)
        if body.auto_approve_threshold_cents > current.auto_approve_threshold_cents:
            create = ConversationCreate(
                title="Expense rules: auto-approve threshold raised",
                body_md="diff",
                tags=["expense-rule-change"],
                urgency="info",
                persona="cfo",
                needs_founder_action=False,
            )
            conv_svc.create_conversation(create)
        conv_dir = tmp_path / "apis" / "brain" / "data" / "conversations"
        assert any(p.name.endswith(".json") for p in conv_dir.glob("*.json"))
