"""Tests for WS-64 Brain weekly self-improvement retros."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.schemas.weekly_retro import RetroSummary, WeeklyRetro
from app.services import self_improvement as si

WEEK_END = datetime(2026, 4, 29, tzinfo=UTC)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_empty_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    paths = {
        "retros": tmp_path / "weekly_retros.json",
        "pos": tmp_path / "operating_score.json",
        "prs": tmp_path / "pr_outcomes.json",
        "incidents": tmp_path / "incidents.json",
        "candidates": tmp_path / "workstream_candidates.json",
        "procedural": tmp_path / "procedural_memory.yaml",
        "objectives": tmp_path / "OBJECTIVES.yaml",
        "workstreams": tmp_path / "workstreams.json",
    }
    _write_json(
        paths["retros"],
        {
            "schema": "weekly_retros/v1",
            "description": "test",
            "version": 1,
            "retros": [],
        },
    )
    _write_json(
        paths["pos"],
        {
            "schema": "operating_score/v1",
            "description": "test",
            "current": None,
            "history": [],
        },
    )
    _write_json(paths["prs"], {"schema": "pr_outcomes/v1", "description": "test", "outcomes": []})
    _write_json(
        paths["incidents"], {"schema": "incidents/v1", "description": "test", "incidents": []}
    )
    _write_json(paths["candidates"], {"schema": "workstream_candidates/v1", "candidates": []})
    paths["procedural"].write_text("version: 1\nrules: []\n", encoding="utf-8")
    paths["objectives"].write_text(
        """\
schema:
  description: test
  entry:
    id: example
    objective: example
    horizon: 30d
    metric: example
    target: example
    review_cadence_days: example
    written_at: example
    notes: example
version: 1
objectives: []
last_reviewed_at: null
""",
        encoding="utf-8",
    )
    _write_json(paths["workstreams"], {"version": 1, "workstreams": []})

    monkeypatch.setenv("BRAIN_WEEKLY_RETROS_JSON", str(paths["retros"]))
    monkeypatch.setenv("BRAIN_OPERATING_SCORE_JSON", str(paths["pos"]))
    monkeypatch.setenv("BRAIN_PR_OUTCOMES_JSON", str(paths["prs"]))
    monkeypatch.setenv("BRAIN_INCIDENTS_JSON", str(paths["incidents"]))
    monkeypatch.setenv("BRAIN_WORKSTREAM_CANDIDATES_JSON", str(paths["candidates"]))
    monkeypatch.setenv("BRAIN_PROCEDURAL_MEMORY_YAML", str(paths["procedural"]))
    monkeypatch.setenv("BRAIN_OBJECTIVES_YAML", str(paths["objectives"]))
    monkeypatch.setenv("BRAIN_WORKSTREAMS_JSON", str(paths["workstreams"]))
    return paths


def _score_entry(total: float, alpha: float = 75.0) -> dict[str, object]:
    return {
        "computed_at": "2026-04-28T00:00:00Z",
        "total": total,
        "pillars": {
            "alpha": {
                "score": alpha,
                "weight": 100,
                "weighted": alpha,
                "measured": True,
                "notes": "test",
            }
        },
        "gates": {"l4_pass": False, "l5_pass": False, "lowest_pillar": "alpha"},
    }


def _retro(days_back: int) -> WeeklyRetro:
    week_ending = WEEK_END - timedelta(days=7 * days_back)
    return WeeklyRetro(
        week_ending=week_ending,
        computed_at=week_ending,
        summary=RetroSummary(
            pos_total_change=0.0,
            merges=days_back,
            reverts=0,
            incidents=0,
            candidates_proposed=0,
            candidates_promoted=0,
        ),
        highlights=[],
        rule_changes=[],
        objective_progress={},
        notes="test",
    )


def test_compute_weekly_retro_empty_data_all_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_empty_files(tmp_path, monkeypatch)
    retro = si.compute_weekly_retro(WEEK_END)
    assert retro.summary == RetroSummary(
        pos_total_change=0.0,
        merges=0,
        reverts=0,
        incidents=0,
        candidates_proposed=0,
        candidates_promoted=0,
    )
    assert retro.highlights == []
    assert retro.objective_progress == {}


def test_compute_weekly_retro_fixture_data_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _write_empty_files(tmp_path, monkeypatch)
    _write_json(
        paths["pos"],
        {
            "schema": "operating_score/v1",
            "description": "test",
            "current": _score_entry(76.0, 81.0),
            "history": [_score_entry(70.0, 79.0), _score_entry(76.0, 81.0)],
        },
    )
    _write_json(
        paths["prs"],
        {
            "schema": "pr_outcomes/v1",
            "description": "test",
            "outcomes": [
                {
                    "pr_number": 1,
                    "merged_at": "2026-04-24T12:00:00Z",
                    "merged_by_agent": "brain",
                    "agent_model": "cheap",
                    "subagent_type": "ops",
                    "workstream_ids": ["WS-1"],
                    "workstream_types": ["ops"],
                    "outcomes": {},
                },
                {
                    "pr_number": 2,
                    "merged_at": "2026-04-25T12:00:00Z",
                    "merged_by_agent": "brain",
                    "agent_model": "cheap",
                    "subagent_type": "ops",
                    "workstream_ids": ["WS-2"],
                    "workstream_types": ["ops"],
                    "outcomes": {},
                },
            ],
        },
    )
    _write_json(
        paths["incidents"],
        {
            "schema": "incidents/v1",
            "incidents": [
                {"id": "inc-1", "type": "auto-revert", "opened_at": "2026-04-26T00:00:00Z"},
                {"id": "inc-2", "type": "ci-redness", "opened_at": "2026-04-27T00:00:00Z"},
            ],
        },
    )
    _write_json(
        paths["candidates"],
        {
            "schema": "workstream_candidates/v1",
            "candidates": [
                {
                    "id": "cand-1",
                    "score": 9.0,
                    "status": "approved_to_workstream",
                    "proposed_at": "2026-04-23T00:00:00Z",
                    "approved_at": "2026-04-24T00:00:00Z",
                },
                {
                    "id": "cand-2",
                    "score": 7.0,
                    "status": "proposed",
                    "proposed_at": "2026-04-23T00:00:00Z",
                },
            ],
        },
    )
    retro = si.compute_weekly_retro(WEEK_END)
    assert retro.summary.pos_total_change == 6.0
    assert retro.summary.merges == 2
    assert retro.summary.reverts == 1
    assert retro.summary.incidents == 2
    assert retro.summary.candidates_proposed == 2
    assert retro.summary.candidates_promoted == 1


def test_record_retro_appends_and_caps_at_52(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_empty_files(tmp_path, monkeypatch)
    for idx in range(55):
        si.record_retro(_retro(idx))
    rows = si.latest_retros(100)
    assert len(rows) == 52
    assert rows[0].week_ending == WEEK_END


def test_pos_history_one_entry_has_zero_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _write_empty_files(tmp_path, monkeypatch)
    _write_json(
        paths["pos"],
        {
            "schema": "operating_score/v1",
            "description": "test",
            "current": _score_entry(80.0),
            "history": [_score_entry(80.0)],
        },
    )
    assert si.compute_weekly_retro(WEEK_END).summary.pos_total_change == 0.0


def test_highlights_include_top_three_candidates_by_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _write_empty_files(tmp_path, monkeypatch)
    _write_json(
        paths["candidates"],
        {
            "schema": "workstream_candidates/v1",
            "candidates": [
                {"id": "low", "score": 1, "proposed_at": "2026-04-23T00:00:00Z"},
                {"id": "top", "score": 10, "proposed_at": "2026-04-23T00:00:00Z"},
                {"id": "mid", "score": 5, "proposed_at": "2026-04-23T00:00:00Z"},
                {"id": "second", "score": 8, "proposed_at": "2026-04-23T00:00:00Z"},
            ],
        },
    )
    highlights = si.compute_weekly_retro(WEEK_END).highlights
    assert highlights[:3] == [
        "Top candidate: top (score=10.00)",
        "Top candidate: second (score=8.00)",
        "Top candidate: mid (score=5.00)",
    ]


def test_new_rules_detected_via_learned_at_in_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _write_empty_files(tmp_path, monkeypatch)
    paths["procedural"].write_text(
        """\
version: 1
rules:
  - id: new_rule
    when: x
    do: y
    source: retro
    learned_at: "2026-04-24T00:00:00Z"
    confidence: high
    applies_to: [cheap-agents]
""",
        encoding="utf-8",
    )
    changes = si.compute_weekly_retro(WEEK_END).rule_changes
    assert [change.rule_id for change in changes] == ["new_rule"]
    assert changes[0].action == "added"


def test_low_confidence_old_rules_flagged_deprecated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _write_empty_files(tmp_path, monkeypatch)
    paths["procedural"].write_text(
        """\
version: 1
rules:
  - id: stale_low_rule
    when: x
    do: y
    source: retro
    learned_at: "2026-03-01T00:00:00Z"
    confidence: low
    applies_to: [cheap-agents]
""",
        encoding="utf-8",
    )
    changes = si.compute_weekly_retro(WEEK_END).rule_changes
    assert changes[0].action == "deprecated"
    assert changes[0].rule_id == "stale_low_rule"


def test_propose_rule_revisions_stub_returns_empty() -> None:
    assert si.propose_rule_revisions() == []


def test_file_lock_concurrent_reads_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_empty_files(tmp_path, monkeypatch)
    errors: list[BaseException] = []

    def writer(idx: int) -> None:
        try:
            si.record_retro(_retro(idx))
        except BaseException as exc:
            errors.append(exc)

    def reader() -> None:
        try:
            si.latest_retros(4)
        except BaseException as exc:
            errors.append(exc)

    threads = [
        *[threading.Thread(target=writer, args=(idx,)) for idx in range(12)],
        *[threading.Thread(target=reader) for _ in range(12)],
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []


def test_atomic_write_file_always_parseable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _write_empty_files(tmp_path, monkeypatch)
    for idx in range(20):
        si.record_retro(_retro(idx))
        parsed = json.loads(paths["retros"].read_text(encoding="utf-8"))
        assert isinstance(parsed["retros"], list)


def test_malformed_file_raises_no_silent_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _write_empty_files(tmp_path, monkeypatch)
    paths["prs"].write_text("{broken-json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        si.compute_weekly_retro(WEEK_END)


@pytest.mark.asyncio
async def test_recompute_endpoint_replaces_existing_week(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _write_empty_files(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "s")
    monkeypatch.setattr(si, "_normalise_week_ending", lambda _value: WEEK_END)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(2):
            res = await client.post(
                "/api/v1/admin/weekly-retros/recompute",
                headers={"X-Brain-Secret": "s"},
            )
            assert res.status_code == 200

    data = json.loads(paths["retros"].read_text(encoding="utf-8"))
    assert len(data["retros"]) == 1
