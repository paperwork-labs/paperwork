"""Tests for WS-67.E auto-distillation (failure clustering → staged rules).

medallion: ops
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import yaml

from app.schemas.procedural_memory import ProceduralMemoryFile, ProceduralRule
from app.services.auto_distillation import (
    ProposedRule,
    cluster_failures,
    propose_rules,
    run_distillation,
    write_proposed_rules,
)


def _dispatch(
    i: int,
    *,
    model: str = "composer-1.5",
    ws: str = "platform-cli",
    summary: str = "ruff check failed on apis/brain",
    ci_initial_pass: bool | None = False,
    review_pass: bool | None = None,
    merge_conflict: bool = False,
    ci_failure_type: str | None = None,
) -> dict:
    out: dict = {
        "ci_initial_pass": ci_initial_pass,
        "review_pass": review_pass,
        "review_iterations": 0,
        "merged_at": None,
        "reverted": None,
        "wall_clock_seconds": None,
    }
    if merge_conflict:
        out["merge_conflict"] = True
    if ci_failure_type:
        out["ci_failure_type"] = ci_failure_type
    return {
        "dispatch_id": f"d{i:04d}",
        "dispatched_at": "2026-04-30T10:00:00Z",
        "agent_model": model,
        "subagent_type": "shell",
        "workstream_id": f"WS-{i}",
        "workstream_type": ws,
        "blast_radius": "brain-code",
        "task_summary": summary,
        "preflight_consulted": False,
        "branch": None,
        "pr_number": 9000 + i,
        "outcome": out,
    }


def test_clustering_ci_failures_same_pattern() -> None:
    dispatches = [_dispatch(i) for i in range(3)]
    clusters = cluster_failures([], dispatches)
    assert len(clusters) == 1
    c0 = clusters[0]
    assert c0.error_category == "ci_failure"
    assert c0.count == 3
    assert c0.agent_model == "composer-1.5"
    assert c0.workstream_type == "platform-cli"


def test_clustering_does_not_merge_different_patterns() -> None:
    dispatches = [
        _dispatch(0, summary="ruff failed"),
        _dispatch(1, summary="ruff failed"),
        _dispatch(2, summary="ruff failed"),
        _dispatch(3, summary="mypy failed"),
        _dispatch(4, summary="mypy failed"),
        _dispatch(5, summary="mypy failed"),
    ]
    clusters = cluster_failures([], dispatches)
    assert len(clusters) == 2


def test_clustering_merge_conflict_category() -> None:
    dispatches = [
        _dispatch(0, summary="merge conflict in shared path", merge_conflict=True),
        _dispatch(1, summary="merge conflict in shared path", merge_conflict=True),
        _dispatch(2, summary="merge conflict in shared path", merge_conflict=True),
    ]
    for d in dispatches:
        d["outcome"]["ci_initial_pass"] = None
    clusters = cluster_failures([], dispatches)
    assert len(clusters) == 1
    assert clusters[0].error_category == "merge_conflict"


def test_clustering_review_rejection() -> None:
    dispatches = []
    for i in range(3):
        d = _dispatch(i, ci_initial_pass=True, review_pass=False)
        dispatches.append(d)
    clusters = cluster_failures([], dispatches)
    assert len(clusters) == 1
    assert clusters[0].error_category == "review_rejection"


def test_propose_rules_validates_against_schema() -> None:
    dispatches = [_dispatch(i) for i in range(3)]
    clusters = cluster_failures([], dispatches)
    with patch(
        "app.services.auto_distillation.procedural_memory_svc.load_rules",
        return_value=[],
    ):
        proposals = propose_rules(clusters)

    assert len(proposals) == 1
    raw = {
        "version": 1,
        "rules": [proposals[0].rule.model_dump(mode="python")],
    }
    parsed = ProceduralMemoryFile.model_validate(raw)
    assert len(parsed.rules) == 1
    r0 = parsed.rules[0]
    assert r0.confidence == "medium"
    assert "cheap-agents" in r0.applies_to


def test_dedup_skips_existing_procedural_memory_rule() -> None:
    dispatches = [_dispatch(i) for i in range(3)]
    clusters = cluster_failures([], dispatches)
    with patch(
        "app.services.auto_distillation.procedural_memory_svc.load_rules",
        return_value=[],
    ):
        first = propose_rules(clusters)
    assert len(first) == 1
    rid = first[0].rule.id

    memory = ProceduralRule(
        id=rid,
        when=first[0].rule.when,
        do=first[0].rule.do,
        source="fixture",
        learned_at=first[0].rule.learned_at,
        confidence="high",
        applies_to=["cheap-agents"],
    )
    with patch(
        "app.services.auto_distillation.procedural_memory_svc.load_rules",
        return_value=[memory],
    ):
        second = propose_rules(clusters)
    assert second == []


def test_run_distillation_writes_and_dedupes_staged_file(tmp_path: Path) -> None:
    po = tmp_path / "pr_outcomes.json"
    po.write_text(
        '{"schema":"pr_outcomes/v1","description":"t","outcomes":[]}',
        encoding="utf-8",
    )
    dl = tmp_path / "agent_dispatch_log.json"
    dl.write_text(
        json.dumps(
            {
                "version": 1,
                "dispatches": [_dispatch(i) for i in range(3)],
                "updated_at": "2026-04-30T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    props = tmp_path / "proposed_rules.yaml"

    with patch(
        "app.services.auto_distillation.procedural_memory_svc.load_rules",
        return_value=[],
    ):
        w1, p1 = run_distillation(
            outcomes_path=po,
            dispatch_path=dl,
            proposed_path=props,
        )
    assert w1 == 1
    assert len(p1) == 1

    with patch(
        "app.services.auto_distillation.procedural_memory_svc.load_rules",
        return_value=[],
    ):
        w2, p2 = run_distillation(
            outcomes_path=po,
            dispatch_path=dl,
            proposed_path=props,
        )
    assert w2 == 0
    assert p2 == []


def test_write_proposed_rules_merge_by_id(tmp_path: Path) -> None:
    path = tmp_path / "proposed_rules.yaml"
    ts = datetime(2026, 4, 30, tzinfo=UTC)
    r_a = ProceduralRule(
        id="a",
        when="when a",
        do="do a",
        source="s",
        learned_at=ts,
        confidence="low",
        applies_to=["cheap-agents"],
    )
    write_proposed_rules([ProposedRule(rule=r_a, cluster_size=3)], path=path)
    r_b = ProceduralRule(
        id="b",
        when="when b",
        do="do b",
        source="s",
        learned_at=ts,
        confidence="low",
        applies_to=["cheap-agents"],
    )
    n = write_proposed_rules([ProposedRule(rule=r_b, cluster_size=3)], path=path)
    assert n == 1
    loaded = ProceduralMemoryFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    assert {r.id for r in loaded.rules} == {"a", "b"}
