"""Tests for WS-63 Brain self-prioritization."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from app.schemas.workstream_candidates import WorkstreamCandidate
from app.services import self_prioritization as sp

NOW = datetime(2026, 4, 29, 8, 0, tzinfo=UTC)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _candidate(
    cid: str,
    *,
    source_ref: str = "pillar:web_perf_ux",
    proposed_at: datetime = NOW,
) -> WorkstreamCandidate:
    return WorkstreamCandidate(
        candidate_id=cid,
        proposed_at=proposed_at,
        title=f"Candidate {cid}",
        why_now="Because the source signal is actionable.",
        source_signal="pos_pillar_below_70",
        source_ref=source_ref,
        estimated_effort_days=2,
        estimated_impact="medium",
        score=42,
        status="proposed",
        promoted_workstream_id=None,
    )


@pytest.fixture
def prioritization_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    paths = {
        "candidates": tmp_path / "apis/brain/data/workstream_candidates.json",
        "objectives": tmp_path / "docs/strategy/OBJECTIVES.yaml",
        "pos": tmp_path / "apis/brain/data/operating_score.json",
        "procedural": tmp_path / "apis/brain/data/procedural_memory.yaml",
        "audit": tmp_path / "docs/STACK_AUDIT_2026-Q2.md",
        "outcomes": tmp_path / "apis/brain/data/pr_outcomes.json",
        "workstreams": tmp_path / "apps/studio/src/data/workstreams.json",
    }
    monkeypatch.setenv("BRAIN_WORKSTREAM_CANDIDATES_JSON", str(paths["candidates"]))
    monkeypatch.setenv("BRAIN_OBJECTIVES_YAML", str(paths["objectives"]))
    monkeypatch.setenv("BRAIN_OPERATING_SCORE_JSON", str(paths["pos"]))
    monkeypatch.setenv("BRAIN_PROCEDURAL_MEMORY_YAML", str(paths["procedural"]))
    monkeypatch.setenv("BRAIN_STACK_AUDIT_MD", str(paths["audit"]))
    monkeypatch.setenv("BRAIN_PR_OUTCOMES_JSON", str(paths["outcomes"]))
    monkeypatch.setenv("BRAIN_WORKSTREAMS_JSON", str(paths["workstreams"]))
    return paths


def _seed_all_sources(paths: dict[str, Path]) -> None:
    paths["objectives"].parent.mkdir(parents=True, exist_ok=True)
    paths["objectives"].write_text(
        yaml.dump(
            {
                "schema": {
                    "description": "Founder-written strategic objectives.",
                    "entry": {
                        "id": "kebab-slug",
                        "objective": "statement",
                        "horizon": "30d",
                        "metric": "metric",
                        "target": "target",
                        "review_cadence_days": "int",
                        "written_at": "RFC3339Z",
                        "notes": "notes",
                    },
                },
                "version": 1,
                "last_reviewed_at": "2026-03-01T00:00:00Z",
                "objectives": [
                    {
                        "id": "ship-l5-autonomy",
                        "objective": "Reach L5 autonomy readiness.",
                        "horizon": "90d",
                        "metric": "pos",
                        "target": "90",
                        "review_cadence_days": 14,
                        "written_at": "2026-03-01T00:00:00Z",
                        "progress": 25,
                        "notes": "",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    _write_json(
        paths["pos"],
        {
            "schema": "operating_score/v1",
            "current": {
                "computed_at": "2026-04-20T00:00:00Z",
                "total": 75,
                "pillars": {
                    "web_perf_ux": {
                        "score": 63,
                        "weight": 10,
                        "weighted": 6.3,
                        "measured": True,
                    },
                    "autonomy": {
                        "score": 50,
                        "weight": 10,
                        "weighted": 5,
                        "measured": False,
                    },
                },
                "gates": {"l4_pass": False, "l5_pass": False, "lowest_pillar": "web_perf_ux"},
            },
            "history": [],
        },
    )
    paths["procedural"].parent.mkdir(parents=True, exist_ok=True)
    paths["procedural"].write_text(
        yaml.dump(
            {
                "version": 1,
                "rules": [
                    {
                        "id": "medallion_tag",
                        "when": "service file edited",
                        "do": "include medallion tag",
                        "source": "PR #377",
                        "learned_at": "2026-04-20T00:00:00Z",
                        "confidence": "high",
                        "applies_to": ["orchestrator"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    paths["audit"].parent.mkdir(parents=True, exist_ok=True)
    paths["audit"].write_text(
        "\n".join(
            [
                "# Stack Audit",
                "**Audit date:** 2026-04-29",
                "| Layer | Current | Latest stable | Verdict | Why | Cost | Replace with |",
                "|---|---|---|---|---|---|---|",
                "| Python package manager | pip | uv | REPLACE | Reproducibility | M | uv |",
            ]
        ),
        encoding="utf-8",
    )
    _write_json(
        paths["outcomes"],
        {
            "schema": "pr_outcomes/v1",
            "outcomes": [
                {
                    "pr_number": 401,
                    "merged_at": "2026-04-28T00:00:00Z",
                    "merged_by_agent": "cheap",
                    "agent_model": "composer",
                    "subagent_type": "brain",
                    "workstream_ids": ["WS-63"],
                    "outcomes": {"h24": {"regressed": True}},
                }
            ],
        },
    )


def test_gather_signals_returns_expected_signal_types(
    prioritization_paths: dict[str, Path],
) -> None:
    _seed_all_sources(prioritization_paths)
    signals = sp.gather_signals()
    assert {signal.source_signal for signal in signals} == {
        "objective_gap",
        "pos_pillar_below_70",
        "procedural_rule_demand",
        "stack_audit_replace",
        "pr_outcome_regression",
    }


def test_score_signal_weights_correctly() -> None:
    signal = sp.Signal(
        source_signal="objective_gap",
        source_ref="OBJ:ship",
        title="Close objective gap",
        why_now="Objective is stale.",
        estimated_effort_days=7,
        estimated_impact="critical",
        observed_at=NOW,
        stale_days=12,
        objective_aligned=True,
    )
    assert sp.score_signal(signal) == 52


def test_propose_candidates_deduplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = sp.Signal(
        source_signal="pos_pillar_below_70",
        source_ref="pillar:web_perf_ux",
        title="Raise web performance",
        why_now="Below 70.",
        estimated_effort_days=2,
        estimated_impact="medium",
        observed_at=NOW,
        stale_days=1,
    )
    s2 = s1.model_copy(update={"estimated_impact": "critical", "stale_days": 3})
    monkeypatch.setattr(sp, "gather_signals", lambda: [s1, s2])
    rows = sp.propose_candidates(top_n=5)
    assert len(rows) == 1
    assert rows[0].score == sp.score_signal(s2)


def test_propose_candidates_returns_top_n_only(monkeypatch: pytest.MonkeyPatch) -> None:
    signals = [
        sp.Signal(
            source_signal="stack_audit_replace",
            source_ref=f"audit:{idx}",
            title=f"Replace stack layer {idx}",
            why_now="Audit says replace.",
            estimated_effort_days=1,
            estimated_impact="low",
            observed_at=NOW,
            stale_days=idx,
        )
        for idx in range(10)
    ]
    monkeypatch.setattr(sp, "gather_signals", lambda: signals)
    rows = sp.propose_candidates(top_n=3)
    assert len(rows) == 3
    assert rows[0].source_ref == "audit:9"


def test_record_candidates_atomic_and_appends_history(
    prioritization_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = _candidate(
        "C-2026-04-01-001",
        source_ref="pillar:old",
        proposed_at=NOW - timedelta(days=20),
    )
    file = {
        "schema": "workstream_candidates/v1",
        "description": "x",
        "version": 1,
        "generated_at": NOW.isoformat(),
        "candidates": [old.model_dump(mode="json")],
        "history": [],
    }
    _write_json(prioritization_paths["candidates"], file)
    monkeypatch.setattr(sp, "_utcnow", lambda: NOW)
    sp.record_candidates([_candidate("C-2026-04-29-001")])
    parsed = json.loads(prioritization_paths["candidates"].read_text(encoding="utf-8"))
    assert [row["candidate_id"] for row in parsed["candidates"]] == ["C-2026-04-29-001"]
    assert [row["candidate_id"] for row in parsed["history"]] == ["C-2026-04-01-001"]


def test_malformed_candidate_file_raises(prioritization_paths: dict[str, Path]) -> None:
    prioritization_paths["candidates"].parent.mkdir(parents=True, exist_ok=True)
    prioritization_paths["candidates"].write_text("{not-json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        sp.latest_candidates()


def _seed_workstreams(path: Path) -> None:
    _write_json(
        path,
        {
            "version": 1,
            "updated": "2026-04-29T00:00:00Z",
            "workstreams": [
                {
                    "id": "WS-01-existing",
                    "title": "Existing workstream",
                    "track": "Z",
                    "priority": 0,
                    "status": "completed",
                    "percent_done": 100,
                    "owner": "brain",
                    "brief_tag": "track:existing",
                    "blockers": [],
                    "last_pr": 1,
                    "last_activity": "2026-04-29T00:00:00Z",
                    "last_dispatched_at": None,
                    "notes": "",
                    "estimated_pr_count": 1,
                    "github_actions_workflow": None,
                    "related_plan": None,
                }
            ],
        },
    )


def test_promotion_writes_valid_workstream_entry(
    prioritization_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sp, "_utcnow", lambda: NOW)
    sp.record_candidates([_candidate("C-2026-04-29-001")])
    _seed_workstreams(prioritization_paths["workstreams"])
    result = sp.promote_candidate("C-2026-04-29-001")
    assert result.workstream["status"] == "pending"
    assert result.workstream["proposed_by_brain"] is True
    assert result.workstream["priority"] == 1
    parsed = json.loads(prioritization_paths["workstreams"].read_text(encoding="utf-8"))
    assert parsed["workstreams"][1]["id"].startswith("WS-02-")
    assert sp.load_candidates_file().candidates[0].status == "approved_to_workstream"


def test_rejection_updates_status_and_founder_reason(
    prioritization_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sp, "_utcnow", lambda: NOW)
    sp.record_candidates([_candidate("C-2026-04-29-001")])
    rejected = sp.reject_candidate("C-2026-04-29-001", "Not now.")
    assert rejected.status == "rejected"
    assert rejected.founder_reason == "Not now."


def test_objectives_yaml_missing_no_objective_signals(
    prioritization_paths: dict[str, Path],
) -> None:
    assert sp._objective_gap_signals() == []


def test_pos_file_missing_no_pillar_signals(prioritization_paths: dict[str, Path]) -> None:
    assert sp._pos_pillar_signals() == []


def test_audit_doc_missing_no_replace_signals(prioritization_paths: dict[str, Path]) -> None:
    assert sp._stack_audit_replace_signals() == []


def test_file_lock_works_under_concurrent_writes(
    prioritization_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sp, "_utcnow", lambda: NOW)

    def _write(idx: int) -> None:
        sp.record_candidates([_candidate(f"C-2026-04-29-{idx:03d}", source_ref=f"pillar:{idx}")])

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_write, range(1, 25)))

    parsed = sp.load_candidates_file()
    assert len(parsed.candidates) == 24
    assert len({row.candidate_id for row in parsed.candidates}) == 24
