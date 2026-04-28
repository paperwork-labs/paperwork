"""Tests for the procedural memory service layer (WS-65)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from app.schemas.procedural_memory import ProceduralRule, ProceduralRuleInput
from app.services import procedural_memory as pm


def _make_yaml(tmp_path: Path) -> Path:
    """Copy the real seed YAML into *tmp_path* so tests are isolated."""
    real = Path(__file__).parent.parent / "data" / "procedural_memory.yaml"
    dest = tmp_path / "procedural_memory.yaml"
    dest.write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def test_load_rules_returns_four_seed_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    yaml_path = _make_yaml(tmp_path)
    monkeypatch.setattr(pm, "_memory_path", lambda: yaml_path)

    rules = pm.load_rules()
    assert len(rules) == 4
    ids = {r.id for r in rules}
    assert "ruff_format_pre_push_guard" in ids
    assert "workstream_priority_unique" in ids
    assert "cancelled_status_estimated_pr_count_null" in ids
    assert "vercel_design_storybook_known_failure" in ids


def test_load_rules_missing_file_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pm, "_memory_path", lambda: tmp_path / "nonexistent.yaml")
    with pytest.raises(FileNotFoundError):
        pm.load_rules()


def test_find_rules_for_context_ruff_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    yaml_path = _make_yaml(tmp_path)
    monkeypatch.setattr(pm, "_memory_path", lambda: yaml_path)

    results = pm.find_rules_for_context(["ruff", "format"])
    assert len(results) >= 1
    assert results[0].id == "ruff_format_pre_push_guard"


def test_find_rules_for_context_sorted_by_confidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    yaml_path = _make_yaml(tmp_path)
    monkeypatch.setattr(pm, "_memory_path", lambda: yaml_path)

    results = pm.find_rules_for_context(["agent"])
    confidences = [r.confidence for r in results]
    order = {"high": 0, "medium": 1, "low": 2}
    ranks = [order[c] for c in confidences]
    assert ranks == sorted(ranks), "Results should be sorted high -> medium -> low"


def test_find_rules_for_context_empty_keywords(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    yaml_path = _make_yaml(tmp_path)
    monkeypatch.setattr(pm, "_memory_path", lambda: yaml_path)

    results = pm.find_rules_for_context([])
    assert results == []


def test_find_rules_for_context_no_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_path = _make_yaml(tmp_path)
    monkeypatch.setattr(pm, "_memory_path", lambda: yaml_path)

    results = pm.find_rules_for_context(["zzznomatch9876"])
    assert results == []


def test_add_rule_appends_new_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_path = _make_yaml(tmp_path)
    monkeypatch.setattr(pm, "_memory_path", lambda: yaml_path)

    new_rule = ProceduralRuleInput(
        id="test_new_rule",
        when="agent creates a new endpoint",
        do="always add an auth dependency",
        source="test",
        confidence="medium",
        applies_to=["cheap-agents"],
    )
    pm.add_rule(new_rule)

    rules = pm.load_rules()
    assert len(rules) == 5
    ids = {r.id for r in rules}
    assert "test_new_rule" in ids


def test_add_rule_duplicate_id_noop_with_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    yaml_path = _make_yaml(tmp_path)
    monkeypatch.setattr(pm, "_memory_path", lambda: yaml_path)

    duplicate = ProceduralRuleInput(
        id="ruff_format_pre_push_guard",
        when="some new when",
        do="some new do",
        source="test",
        confidence="low",
        applies_to=["cheap-agents"],
    )

    with caplog.at_level(logging.WARNING, logger="app.services.procedural_memory"):
        pm.add_rule(duplicate)

    rules = pm.load_rules()
    assert len(rules) == 4, "Duplicate should not be added"
    assert any("already exists" in msg for msg in caplog.messages)


def test_add_rule_atomic_write_survives_reload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    yaml_path = _make_yaml(tmp_path)
    monkeypatch.setattr(pm, "_memory_path", lambda: yaml_path)

    new_rule = ProceduralRuleInput(
        id="atomicity_check",
        when="anything",
        do="verify",
        source="test",
        confidence="low",
        applies_to=["orchestrator"],
    )
    pm.add_rule(new_rule)

    rules = pm.load_rules()
    assert any(r.id == "atomicity_check" for r in rules)


def test_consolidate_from_incidents_missing_file_returns_empty(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "incidents.json"
    result = pm.consolidate_from_incidents(incidents_path=missing)
    assert result == []


def test_consolidate_from_incidents_empty_list(tmp_path: Path) -> None:
    incidents_file = tmp_path / "incidents.json"
    incidents_file.write_text("[]", encoding="utf-8")

    result = pm.consolidate_from_incidents(incidents_path=incidents_file)
    assert result == []


def test_consolidate_from_incidents_returns_candidates(tmp_path: Path) -> None:
    incidents = [
        {
            "id": "inc-001",
            "title": "DB connection pool exhaustion during peak traffic",
            "resolution": "Increase pool size and add circuit breaker",
            "occurred_at": "2026-04-01T10:00:00Z",
        },
        {
            "id": "inc-002",
            "title": "Missing ruff format guard on CI push",
            "summary": "Add ruff format check as pre-push hook",
            "created_at": "2026-04-02T08:00:00Z",
        },
    ]
    incidents_file = tmp_path / "incidents.json"
    incidents_file.write_text(json.dumps(incidents), encoding="utf-8")

    result = pm.consolidate_from_incidents(incidents_path=incidents_file)
    assert len(result) == 2
    assert all(isinstance(r, ProceduralRule) for r in result)
    assert all(r.confidence == "low" for r in result)


def test_consolidate_from_incidents_skips_entries_without_title_or_resolution(
    tmp_path: Path,
) -> None:
    incidents = [
        {"id": "inc-bad1"},
        {"id": "inc-bad2", "title": ""},
        {"id": "inc-bad3", "title": "Valid title", "resolution": ""},
        {
            "id": "inc-good",
            "title": "Valid title",
            "resolution": "Valid resolution",
        },
    ]
    incidents_file = tmp_path / "incidents.json"
    incidents_file.write_text(json.dumps(incidents), encoding="utf-8")

    result = pm.consolidate_from_incidents(incidents_path=incidents_file)
    assert len(result) == 1
    assert result[0].when == "Valid title"
