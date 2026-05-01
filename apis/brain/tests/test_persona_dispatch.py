"""Tests for persona dispatch domains and autonomy tiers."""

from __future__ import annotations

from app.services.persona_dispatch import (
    AUTONOMY_TIER_AUTO_MERGE,
    AUTONOMY_TIER_AUTO_MERGE_WITH_REVIEW,
    AUTONOMY_TIER_FOUNDER_ONLY,
    AUTONOMY_TIER_NEEDS_APPROVAL,
    DISPATCH_REGISTRY,
    get_autonomy_tier,
    get_escalation_target,
    select_persona_for_path,
    select_persona_for_task,
)


class TestDispatchRegistry:
    def test_registry_has_required_fields(self) -> None:
        for name, domain in DISPATCH_REGISTRY.items():
            assert domain["persona_id"] == name
            assert len(domain["domain_patterns"]) > 0
            assert domain["autonomy_tier"] in (1, 2, 3, 4)
            assert isinstance(domain["escalation_to"], str)

    def test_all_tiers_represented(self) -> None:
        tiers = {d["autonomy_tier"] for d in DISPATCH_REGISTRY.values()}
        assert tiers == {1, 2, 3, 4}


class TestSelectPersonaForPath:
    def test_empty_files_returns_default(self) -> None:
        assert select_persona_for_path([]) == "engineer"

    def test_brain_service_file(self) -> None:
        result = select_persona_for_path(["apis/brain/app/services/foo.py"])
        assert result == "agent-ops"

    def test_brain_data_file(self) -> None:
        result = select_persona_for_path(["apis/brain/data/personas/engineer.yaml"])
        assert result == "data-ops"

    def test_tax_engine_file(self) -> None:
        result = select_persona_for_path(["packages/tax-engine/calc.py"])
        assert result == "tax-domain"

    def test_formation_data(self) -> None:
        result = select_persona_for_path(["packages/data/formation/california.json"])
        assert result == "legal"

    def test_ui_package(self) -> None:
        result = select_persona_for_path(["packages/ui/components/button.tsx"])
        assert result == "ux-lead"

    def test_infra_file(self) -> None:
        result = select_persona_for_path(["infra/compose.dev.yaml"])
        assert result == "ops-engineer"

    def test_github_actions(self) -> None:
        result = select_persona_for_path([".github/workflows/ci.yml"])
        assert result == "ops-engineer"

    def test_test_file_in_brain(self) -> None:
        result = select_persona_for_path(["apis/brain/tests/test_foo.py"])
        assert result == "qa"

    def test_cursor_rules_file(self) -> None:
        result = select_persona_for_path([".cursor/rules/engineering.mdc"])
        assert result == "data-ops"

    def test_cost_service(self) -> None:
        result = select_persona_for_path(["apis/brain/app/services/cost_monitor.py"])
        assert result == "cfo"

    def test_multiple_files_highest_priority_wins(self) -> None:
        result = select_persona_for_path(
            [
                "packages/ui/button.tsx",
                "packages/tax-engine/calc.py",
            ]
        )
        assert result == "tax-domain"

    def test_unmatched_file_returns_default(self) -> None:
        result = select_persona_for_path(["random/unknown/file.txt"])
        assert result == "engineer"

    def test_docs_file(self) -> None:
        result = select_persona_for_path(["docs/strategy/plan.md"])
        assert result == "data-ops"

    def test_filefree_app(self) -> None:
        result = select_persona_for_path(["apps/filefree/src/app/page.tsx"])
        assert result == "ux-lead"


class TestSelectPersonaForTask:
    def test_known_task_type(self) -> None:
        assert select_persona_for_task("cost-analysis") == "cfo"

    def test_unknown_task_type_returns_default(self) -> None:
        assert select_persona_for_task("unknown-task") == "engineer"

    def test_product_override_higher_tier(self) -> None:
        result = select_persona_for_task("pr-review", product="filefree")
        assert result == "tax-domain"

    def test_product_override_brain(self) -> None:
        result = select_persona_for_task("data-update", product="brain")
        assert result == "agent-ops"

    def test_no_product(self) -> None:
        result = select_persona_for_task("deploy", product=None)
        assert result == "ops-engineer"

    def test_task_with_unknown_product(self) -> None:
        result = select_persona_for_task("test-coverage", product="nonexistent")
        assert result == "qa"


class TestAutonomyTierHelpers:
    def test_get_tier_known_persona(self) -> None:
        assert get_autonomy_tier("data-ops") == AUTONOMY_TIER_AUTO_MERGE
        assert get_autonomy_tier("agent-ops") == AUTONOMY_TIER_AUTO_MERGE_WITH_REVIEW
        assert get_autonomy_tier("engineer") == AUTONOMY_TIER_NEEDS_APPROVAL
        assert get_autonomy_tier("tax-domain") == AUTONOMY_TIER_FOUNDER_ONLY

    def test_get_tier_unknown_persona(self) -> None:
        assert get_autonomy_tier("nonexistent") == AUTONOMY_TIER_FOUNDER_ONLY

    def test_get_escalation_known(self) -> None:
        assert get_escalation_target("data-ops") == "agent-ops"
        assert get_escalation_target("agent-ops") == "engineer"
        assert get_escalation_target("engineer") == "founder"

    def test_get_escalation_unknown(self) -> None:
        assert get_escalation_target("nonexistent") == "founder"
