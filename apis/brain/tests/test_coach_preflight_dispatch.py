"""Tests for get_coach_preflight_for_task() — Autopilot dispatch helper.

Exercises the new function added to coach_preflight.py service (Wave AUTO PR-AU1).
The underlying run_preflight() is already covered in test_coach_preflight.py;
these tests focus on the task-oriented wrapper.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest

from app.services import coach_preflight as svc


_MINIMAL_YAML = dedent("""\
    version: 1
    rules: []
""")

_DISPATCH_YAML = dedent("""\
    version: 1
    rules:
      - id: cheap_agent_model_rule
        when: "dispatching cheap-agents for typescript refactor tasks"
        do: "MUST use composer-1.5 or composer-2-fast; never dispatch Opus as a subagent"
        source: "cheap-agent-fleet.mdc"
        learned_at: "2026-04-29T00:00:00Z"
        confidence: high
        applies_to: [cheap-agents, orchestrator]
      - id: cpa_tax_rule
        when: "cpa persona processes a tax filing or W-2 workflow"
        do: "Always verify PII scrub before storing. Confidence floor: 0.85."
        source: "cpa.mdc"
        learned_at: "2026-04-29T00:00:00Z"
        confidence: medium
        applies_to: [orchestrator]
""")


def test_returns_response_with_empty_rules(tmp_path):
    mem_file = tmp_path / "procedural_memory.yaml"
    mem_file.write_text(_MINIMAL_YAML, encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(svc, "_memory_path", lambda: mem_file)
        mp.setattr(svc, "_incidents_path", lambda: tmp_path / "incidents.json")

        result = svc.get_coach_preflight_for_task(
            task_description="Refactor TypeScript imports across packages",
            persona_id="ea",
        )

    assert result.degraded is False
    assert isinstance(result.matched_rules, list)
    assert isinstance(result.recent_incidents, list)
    assert result.predicted_cost is not None


def test_matches_rules_by_persona(tmp_path):
    """Rules whose 'when' field mentions the persona slug are matched via keyword lookup."""
    mem_file = tmp_path / "procedural_memory.yaml"
    mem_file.write_text(_DISPATCH_YAML, encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(svc, "_memory_path", lambda: mem_file)
        mp.setattr(svc, "_incidents_path", lambda: tmp_path / "incidents.json")

        # "cpa" appears in cpa_tax_rule's 'when' field, so task keyword matching picks it up
        result = svc.get_coach_preflight_for_task(
            task_description="cpa processes W-2 and tax filing workflow",
            persona_id="orchestrator",
        )

    rule_ids = [r.id for r in result.matched_rules]
    assert "cpa_tax_rule" in rule_ids


def test_matches_rules_by_task_keywords(tmp_path):
    mem_file = tmp_path / "procedural_memory.yaml"
    mem_file.write_text(_DISPATCH_YAML, encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(svc, "_memory_path", lambda: mem_file)
        mp.setattr(svc, "_incidents_path", lambda: tmp_path / "incidents.json")

        result = svc.get_coach_preflight_for_task(
            task_description="Refactor typescript imports for cheap-agents dispatch pipeline",
            persona_id="ea",
        )

    rule_ids = [r.id for r in result.matched_rules]
    assert "cheap_agent_model_rule" in rule_ids


def test_degraded_when_yaml_missing(tmp_path):
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(svc, "_memory_path", lambda: tmp_path / "nonexistent.yaml")
        mp.setattr(svc, "_incidents_path", lambda: tmp_path / "incidents.json")

        result = svc.get_coach_preflight_for_task(
            task_description="Any task",
            persona_id="ea",
        )

    assert result.degraded is True
    assert result.matched_rules == []


def test_no_duplicate_rules_when_both_paths_match(tmp_path):
    """A rule that matches both persona and task keywords should appear once."""
    yaml_text = dedent("""\
        version: 1
        rules:
          - id: shared_rule
            when: "orchestrator dispatching cheap-agents for typescript tasks"
            do: "Use composer-1.5"
            source: "test"
            learned_at: "2026-04-29T00:00:00Z"
            confidence: high
            applies_to: [cheap-agents, orchestrator]
    """)
    mem_file = tmp_path / "procedural_memory.yaml"
    mem_file.write_text(yaml_text, encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(svc, "_memory_path", lambda: mem_file)
        mp.setattr(svc, "_incidents_path", lambda: tmp_path / "incidents.json")

        result = svc.get_coach_preflight_for_task(
            task_description="typescript cheap-agents dispatch",
            persona_id="orchestrator",
        )

    matching = [r for r in result.matched_rules if r.id == "shared_rule"]
    assert len(matching) == 1, "Rule must not appear twice even if both keyword paths match"


def test_blockers_have_correct_severity(tmp_path):
    yaml_text = dedent("""\
        version: 1
        rules:
          - id: must_rule
            when: "merging any PR that touches brain memory"
            do: "MUST run full test suite before merging"
            source: "test"
            learned_at: "2026-04-29T00:00:00Z"
            confidence: high
            applies_to: [orchestrator]
    """)
    mem_file = tmp_path / "procedural_memory.yaml"
    mem_file.write_text(yaml_text, encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(svc, "_memory_path", lambda: mem_file)
        mp.setattr(svc, "_incidents_path", lambda: tmp_path / "incidents.json")

        result = svc.get_coach_preflight_for_task(
            task_description="merging PR that touches brain memory",
            persona_id="orchestrator",
        )

    blocker_rules = [r for r in result.matched_rules if r.severity == "blocker"]
    assert len(blocker_rules) >= 1
