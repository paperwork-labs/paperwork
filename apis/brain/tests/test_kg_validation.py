"""Tests for Knowledge-Graph self-validation service (WS-52)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

from app.schemas.kg_validation import KGValidationFile, KGValidationRun, ViolationSeverity
from app.services import kg_validation as svc

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _minimal_workstreams(ws_ids: list[str], owners: list[str] | None = None) -> dict:
    """Return a minimal workstreams.json dict with given IDs."""
    _owners = owners or ["brain"] * len(ws_ids)
    return {
        "version": 1,
        "workstreams": [
            {"id": ws_id, "owner": owner, "status": "pending"}
            for ws_id, owner in zip(ws_ids, _owners, strict=False)
        ],
    }


def _minimal_dispatch_log(entries: list[dict]) -> dict:
    return {
        "schema": {"description": "test"},
        "version": 1,
        "dispatches": entries,
        "updated_at": "2026-04-28T00:00:00Z",
    }


def _minimal_spec(pillar_ids: list[str]) -> dict:
    n = len(pillar_ids)
    base = 100 // n
    remainder = 100 - base * n
    weights = [base] * n
    weights[0] += remainder
    return {
        "schema": {"description": "test spec"},
        "version": 1,
        "target_total": 90,
        "graduation_gates": {
            "l4": {"min_total": 80, "min_pillar": 70},
            "l5": {"min_total": 90, "sustained_weeks": 4},
        },
        "pillars": [
            {
                "id": pid,
                "weight": w,
                "industry_reference": "x",
                "target": 80,
                "measurement_source": "x",
                "description": "x",
            }
            for pid, w in zip(pillar_ids, weights, strict=False)
        ],
    }


def _minimal_score(pillar_ids: list[str]) -> dict:
    pillars = {
        pid: {"score": 75.0, "weight": 10, "weighted": 7.5, "measured": True, "notes": ""}
        for pid in pillar_ids
    }
    return {
        "schema": "operating_score/v1",
        "description": "test",
        "current": {
            "computed_at": "2026-04-29T06:00:00Z",
            "total": 75.0,
            "pillars": pillars,
            "gates": {"l4_pass": False, "l5_pass": False, "lowest_pillar": pillar_ids[0]},
        },
        "history": [],
    }


# ---------------------------------------------------------------------------
# Rule 1: schema_validation — positive (valid data → no violation)
# ---------------------------------------------------------------------------


def test_schema_validation_valid_no_violations(tmp_path: Path) -> None:
    """Valid kg_validation.json parses without violations."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    valid_kg = {"schema": "kg_validation/v1", "current": None, "history": []}
    (data_dir / "kg_validation.json").write_text(json.dumps(valid_kg), encoding="utf-8")

    files_checked: list[str] = []
    violations = svc._rule_schema_validation(data_dir, files_checked)
    assert violations == []
    assert any("kg_validation.json" in f for f in files_checked)


# ---------------------------------------------------------------------------
# Rule 1: schema_validation — negative (corrupt JSON → high violation)
# ---------------------------------------------------------------------------


def test_schema_validation_invalid_json_high_violation(tmp_path: Path) -> None:
    """Corrupt JSON in a data file is flagged as a high violation."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Write an invalid kg_validation.json (bad schema value)
    bad = {"schema": "kg_validation/v1", "current": {"bad": "struct"}, "history": "not-a-list"}
    (data_dir / "kg_validation.json").write_text(json.dumps(bad), encoding="utf-8")

    files_checked: list[str] = []
    violations = svc._rule_schema_validation(data_dir, files_checked)
    assert any(v.severity == ViolationSeverity.high for v in violations)
    assert any(v.rule == "schema_validation" for v in violations)


# ---------------------------------------------------------------------------
# Rule 2: workstream_id_references — positive
# ---------------------------------------------------------------------------


def test_workstream_id_refs_valid_no_violations(tmp_path: Path) -> None:
    """Data files referencing only existing WS IDs produce no violations."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    ws_ids: frozenset[str] = frozenset({"WS-42-iac-drift-detector", "WS-52-kg-self-validation"})
    # A file that references only existing IDs
    content = {"note": "see WS-42-iac-drift-detector for context", "other": 123}
    (data_dir / "some_data.json").write_text(json.dumps(content), encoding="utf-8")

    files_checked: list[str] = []
    violations = svc._rule_workstream_id_references(data_dir, ws_ids, files_checked)
    assert violations == []


# ---------------------------------------------------------------------------
# Rule 2: workstream_id_references — negative
# ---------------------------------------------------------------------------


def test_workstream_id_refs_dangling_ref_medium_violation(tmp_path: Path) -> None:
    """Data files referencing a non-existent WS ID produce a medium violation."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    ws_ids: frozenset[str] = frozenset({"WS-42-iac-drift-detector"})
    content = {"dispatch_ids": "WS-99-nonexistent-workstream"}
    (data_dir / "some_data.json").write_text(json.dumps(content), encoding="utf-8")

    files_checked: list[str] = []
    violations = svc._rule_workstream_id_references(data_dir, ws_ids, files_checked)
    assert len(violations) >= 1
    assert any(v.severity == ViolationSeverity.medium for v in violations)
    assert any("WS-99" in v.detail for v in violations)


# ---------------------------------------------------------------------------
# Rule 3: persona_owner_references — positive
# ---------------------------------------------------------------------------


def test_persona_owner_valid_system_actor(tmp_path: Path) -> None:
    """System actors (brain, founder, opus) are always valid owners."""
    ws_path = tmp_path / "workstreams.json"
    ws_path.write_text(
        json.dumps(_minimal_workstreams(["WS-52-kg-self-validation"], owners=["brain"])),
        encoding="utf-8",
    )
    known_personas = svc._SYSTEM_ACTORS | frozenset({"cfo", "growth"})

    files_checked: list[str] = []
    violations = svc._rule_persona_owner_references(ws_path, known_personas, files_checked)
    assert violations == []


# ---------------------------------------------------------------------------
# Rule 3: persona_owner_references — negative
# ---------------------------------------------------------------------------


def test_persona_owner_unknown_medium_violation(tmp_path: Path) -> None:
    """An owner that is not a known persona or system actor produces a medium violation."""
    ws_path = tmp_path / "workstreams.json"
    ws_path.write_text(
        json.dumps(
            _minimal_workstreams(["WS-52-kg-self-validation"], owners=["totally-unknown-bot"])
        ),
        encoding="utf-8",
    )
    known_personas: frozenset[str] = svc._SYSTEM_ACTORS | frozenset({"cfo"})

    files_checked: list[str] = []
    violations = svc._rule_persona_owner_references(ws_path, known_personas, files_checked)
    assert len(violations) == 1
    assert violations[0].severity == ViolationSeverity.medium
    assert "totally-unknown-bot" in violations[0].detail


# ---------------------------------------------------------------------------
# Rule 4: procedural_memory_freshness — positive (recent low-confidence rule)
# ---------------------------------------------------------------------------


def test_procedural_freshness_recent_low_no_violation(tmp_path: Path) -> None:
    """A low-confidence rule added recently is NOT flagged."""
    memory_path = tmp_path / "procedural_memory.yaml"
    data = {
        "version": 1,
        "rules": [
            {
                "id": "recent_rule",
                "when": "x",
                "do": "y",
                "source": "test",
                "learned_at": "2026-04-01T00:00:00Z",  # ~28 days ago; well under 180
                "confidence": "low",
                "applies_to": ["cheap-agents"],
            }
        ],
    }
    memory_path.write_text(yaml.dump(data), encoding="utf-8")

    files_checked: list[str] = []
    violations = svc._rule_procedural_memory_freshness(memory_path, files_checked)
    assert violations == []


# ---------------------------------------------------------------------------
# Rule 4: procedural_memory_freshness — negative (old low-confidence rule)
# ---------------------------------------------------------------------------


def test_procedural_freshness_stale_low_confidence_violation(tmp_path: Path) -> None:
    """A low-confidence rule older than 180 days is flagged as low severity."""
    memory_path = tmp_path / "procedural_memory.yaml"
    data = {
        "version": 1,
        "rules": [
            {
                "id": "stale_rule",
                "when": "x",
                "do": "y",
                "source": "test",
                "learned_at": "2025-01-01T00:00:00Z",  # >180 days ago
                "confidence": "low",
                "applies_to": ["cheap-agents"],
            },
            {
                "id": "high_conf_old",
                "when": "x",
                "do": "y",
                "source": "test",
                "learned_at": "2025-01-01T00:00:00Z",
                "confidence": "high",  # should NOT be flagged
                "applies_to": ["orchestrator"],
            },
        ],
    }
    memory_path.write_text(yaml.dump(data), encoding="utf-8")

    files_checked: list[str] = []
    violations = svc._rule_procedural_memory_freshness(memory_path, files_checked)
    assert len(violations) == 1
    assert violations[0].severity == ViolationSeverity.low
    assert "stale_rule" in violations[0].detail


# ---------------------------------------------------------------------------
# Rule 5: dangling_dispatch_log — positive
# ---------------------------------------------------------------------------


def test_dangling_dispatch_log_valid(tmp_path: Path) -> None:
    """Dispatch entries referencing valid workstream IDs produce no violations."""
    dispatch_path = tmp_path / "agent_dispatch_log.json"
    dispatch_path.write_text(
        json.dumps(
            _minimal_dispatch_log(
                [
                    {
                        "dispatch_id": "abc-123",
                        "workstream_id": "WS-52-kg-self-validation",
                        "agent_model": "composer-1.5",
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    ws_ids: frozenset[str] = frozenset({"WS-52-kg-self-validation"})

    files_checked: list[str] = []
    violations = svc._rule_dangling_dispatch_log(dispatch_path, ws_ids, files_checked)
    assert violations == []


# ---------------------------------------------------------------------------
# Rule 5: dangling_dispatch_log — negative
# ---------------------------------------------------------------------------


def test_dangling_dispatch_log_missing_ws_medium_violation(tmp_path: Path) -> None:
    """Dispatch entries referencing a missing workstream ID are flagged."""
    dispatch_path = tmp_path / "agent_dispatch_log.json"
    dispatch_path.write_text(
        json.dumps(
            _minimal_dispatch_log(
                [
                    {
                        "dispatch_id": "xyz-999",
                        "workstream_id": "WS-999-does-not-exist",
                        "agent_model": "composer-1.5",
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    ws_ids: frozenset[str] = frozenset({"WS-52-kg-self-validation"})

    files_checked: list[str] = []
    violations = svc._rule_dangling_dispatch_log(dispatch_path, ws_ids, files_checked)
    assert len(violations) == 1
    assert violations[0].severity == ViolationSeverity.medium
    assert "WS-999" in violations[0].detail


# ---------------------------------------------------------------------------
# Rule 6: operating_score_pillar_consistency — positive
# ---------------------------------------------------------------------------


def test_pillar_consistency_matching_pillars_no_violation(tmp_path: Path) -> None:
    """Operating score pillars match spec → no violations."""
    spec_path = tmp_path / "operating_score_spec.yaml"
    score_path = tmp_path / "operating_score.json"

    pillar_ids = ["autonomy", "dora_elite"]
    spec_path.write_text(yaml.dump(_minimal_spec(pillar_ids)), encoding="utf-8")
    score_path.write_text(json.dumps(_minimal_score(pillar_ids)), encoding="utf-8")

    files_checked: list[str] = []
    violations = svc._rule_operating_score_pillar_consistency(spec_path, score_path, files_checked)
    assert violations == []


# ---------------------------------------------------------------------------
# Rule 6: operating_score_pillar_consistency — negative (missing pillar)
# ---------------------------------------------------------------------------


def test_pillar_consistency_missing_pillar_high_violation(tmp_path: Path) -> None:
    """A pillar in spec that is absent from operating_score.json → high violation."""
    spec_path = tmp_path / "operating_score_spec.yaml"
    score_path = tmp_path / "operating_score.json"

    spec_pillar_ids = ["autonomy", "dora_elite", "stack_modernity"]
    score_pillar_ids = ["autonomy", "dora_elite"]  # missing stack_modernity

    spec_path.write_text(yaml.dump(_minimal_spec(spec_pillar_ids)), encoding="utf-8")
    score_path.write_text(json.dumps(_minimal_score(score_pillar_ids)), encoding="utf-8")

    files_checked: list[str] = []
    violations = svc._rule_operating_score_pillar_consistency(spec_path, score_path, files_checked)
    assert any(v.severity == ViolationSeverity.high for v in violations)
    assert any("stack_modernity" in v.detail for v in violations)


# ---------------------------------------------------------------------------
# History bounding to 30 entries
# ---------------------------------------------------------------------------


def test_record_validation_run_history_bounded_to_30(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """History is capped at 30 entries after many consecutive runs."""
    kg_path = tmp_path / "kg_validation.json"
    monkeypatch.setenv("BRAIN_KG_VALIDATION_JSON", str(kg_path))

    for i in range(35):
        run = KGValidationRun(
            validated_at=f"2026-04-{i + 1:02d}T06:00:00Z" if i < 30 else "2026-05-05T06:00:00Z",
            files_checked=5,
            violations=[],
            passed=True,
            summary=f"run {i}",
        )
        svc.record_validation_run(run)

    file = svc.load_validation_file()
    assert len(file.history) <= 30


# ---------------------------------------------------------------------------
# Empty / missing files handled gracefully
# ---------------------------------------------------------------------------


def test_validate_empty_data_dir_returns_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """validate() against an empty directory does not raise and returns a run."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ws_path = tmp_path / "workstreams.json"
    ws_path.write_text(json.dumps({"version": 1, "workstreams": []}), encoding="utf-8")

    monkeypatch.setenv("BRAIN_WORKSTREAMS_JSON", str(ws_path))

    run = svc.validate(repo_root=tmp_path, data_dir=data_dir)
    assert isinstance(run, KGValidationRun)
    assert isinstance(run.passed, bool)
    assert isinstance(run.summary, str)


def test_load_validation_file_missing_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """load_validation_file() returns an empty KGValidationFile when the file does not exist."""
    monkeypatch.setenv("BRAIN_KG_VALIDATION_JSON", str(tmp_path / "nonexistent.json"))
    file = svc.load_validation_file()
    assert isinstance(file, KGValidationFile)
    assert file.current is None
    assert file.history == []


# ---------------------------------------------------------------------------
# Full validate() integration smoke test against the real repo
# ---------------------------------------------------------------------------


def test_validate_runs_against_real_repo() -> None:
    """validate() runs end-to-end against the live repo data and returns a valid run."""
    repo_root_env = os.environ.get("REPO_ROOT", "")
    if not repo_root_env:
        # Infer from the test file location (apis/brain/tests → 3 levels up → apis/brain,
        # then 2 more up to repo root)
        repo_root_env = str(Path(__file__).resolve().parents[3])
    repo_root = Path(repo_root_env)
    if not (repo_root / "apis" / "brain").is_dir():
        pytest.skip("Real repo data not available")

    run = svc.validate(repo_root=repo_root)
    assert isinstance(run, KGValidationRun)
    assert run.files_checked >= 0
    assert run.summary
    assert isinstance(run.violations, list)
