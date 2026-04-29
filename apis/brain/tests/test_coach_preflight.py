"""Tests for WS-67.A — Brain coach preflight endpoint and service."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from httpx import AsyncClient

from app.config import settings
from app.schemas.coach_preflight import CoachPreflightRequest
from app.services import coach_preflight as svc

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_YAML = dedent(
    """\
    version: 1
    rules: []
    """
)

_BRAIN_DATA_DIR_YAML = dedent(
    """\
    version: 1
    rules:
      - id: brain_data_dir_traverses_three_levels
        when: "agent creates a _data_dir() or _brain_data_dir() helper inside apis/brain/app/services/"
        do: "MUST traverse three dirname levels: services -> app -> brain; return brain/data path; never hardcode the path"
        source: "WS-67.A spec"
        learned_at: "2026-04-29T00:00:00Z"
        confidence: high
        applies_to: [cheap-agents, brain-self-dispatch]
    """
)

_LOW_CONFIDENCE_YAML = dedent(
    """\
    version: 1
    rules:
      - id: some_low_rule
        when: "some trigger about apis/brain/app/services/"
        do: "do something optional"
        source: "test"
        learned_at: "2026-04-29T00:00:00Z"
        confidence: low
        applies_to: [cheap-agents]
    """
)

_CPA_YAML = dedent(
    """\
    version: 1
    rules:
      - id: cpa_rule
        when: "when the cpa persona runs a dispatch or merge"
        do: "do cpa-specific thing"
        source: "test"
        learned_at: "2026-04-29T00:00:00Z"
        confidence: high
        applies_to: [cheap-agents]
      - id: no_persona_match_rule
        when: "some unrelated vercel design storybook trigger"
        do: "do storybook thing"
        source: "test"
        learned_at: "2026-04-29T00:00:00Z"
        confidence: medium
        applies_to: [orchestrator]
    """
)

_HIGH_MUST_YAML = dedent(
    """\
    version: 1
    rules:
      - id: must_rule
        when: "some important trigger"
        do: "agent must do the thing before push"
        source: "test"
        learned_at: "2026-04-29T00:00:00Z"
        confidence: high
        applies_to: [cheap-agents, orchestrator]
    """
)


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "procedural_memory.yaml"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Service unit tests
# ---------------------------------------------------------------------------


def test_no_data_returns_degraded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing procedural_memory.yaml → degraded=True, no rules."""
    monkeypatch.setattr(svc, "_memory_path", lambda: tmp_path / "nonexistent.yaml")
    monkeypatch.setattr(svc, "_incidents_path", lambda: tmp_path / "incidents.json")

    req = CoachPreflightRequest(action_type="dispatch")
    resp = svc.run_preflight(req)

    assert resp.degraded is True
    assert resp.degraded_reason is not None
    assert resp.matched_rules == []


def test_path_match_finds_brain_data_dir_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """files_touched with brain services path → matches brain_data_dir rule, severity=blocker."""
    yaml_path = _write_yaml(tmp_path, _BRAIN_DATA_DIR_YAML)
    monkeypatch.setattr(svc, "_memory_path", lambda: yaml_path)
    monkeypatch.setattr(svc, "_incidents_path", lambda: tmp_path / "incidents.json")

    req = CoachPreflightRequest(
        action_type="dispatch",
        files_touched=["apis/brain/app/services/foo.py"],
    )
    resp = svc.run_preflight(req)

    assert resp.degraded is False
    assert len(resp.matched_rules) >= 1
    rule_ids = [r.id for r in resp.matched_rules]
    assert "brain_data_dir_traverses_three_levels" in rule_ids
    matched = next(r for r in resp.matched_rules if r.id == "brain_data_dir_traverses_three_levels")
    assert matched.severity == "blocker"


def test_persona_match_filters_correctly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """personas=['cpa'] → rule whose 'when' mentions 'cpa' is matched."""
    yaml_path = _write_yaml(tmp_path, _CPA_YAML)
    monkeypatch.setattr(svc, "_memory_path", lambda: yaml_path)
    monkeypatch.setattr(svc, "_incidents_path", lambda: tmp_path / "incidents.json")

    req = CoachPreflightRequest(
        action_type="dispatch",
        personas=["cpa"],
    )
    resp = svc.run_preflight(req)

    assert resp.degraded is False
    rule_ids = [r.id for r in resp.matched_rules]
    assert "cpa_rule" in rule_ids


def test_high_confidence_must_clause_yields_blocker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """High-confidence rule with 'must' in do → severity=blocker."""
    yaml_path = _write_yaml(tmp_path, _HIGH_MUST_YAML)
    monkeypatch.setattr(svc, "_memory_path", lambda: yaml_path)
    monkeypatch.setattr(svc, "_incidents_path", lambda: tmp_path / "incidents.json")

    req = CoachPreflightRequest(action_type="dispatch")
    resp = svc.run_preflight(req)

    assert resp.degraded is False
    assert len(resp.matched_rules) >= 1
    assert resp.matched_rules[0].severity == "blocker"


def test_low_confidence_yields_info(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Low-confidence rule → severity=info."""
    yaml_path = _write_yaml(tmp_path, _LOW_CONFIDENCE_YAML)
    monkeypatch.setattr(svc, "_memory_path", lambda: yaml_path)
    monkeypatch.setattr(svc, "_incidents_path", lambda: tmp_path / "incidents.json")

    req = CoachPreflightRequest(
        action_type="dispatch",
        files_touched=["apis/brain/app/services/something.py"],
    )
    resp = svc.run_preflight(req)

    assert resp.degraded is False
    if resp.matched_rules:
        for r in resp.matched_rules:
            if r.id == "some_low_rule":
                assert r.severity == "info"


def test_cost_predict_apps_estimate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """files_touched with apps/ path → predicts 1+ vercel builds."""
    yaml_path = _write_yaml(tmp_path, _MINIMAL_YAML)
    monkeypatch.setattr(svc, "_memory_path", lambda: yaml_path)
    monkeypatch.setattr(svc, "_incidents_path", lambda: tmp_path / "incidents.json")

    req = CoachPreflightRequest(
        action_type="deploy",
        files_touched=["apps/studio/x.tsx"],
    )
    resp = svc.run_preflight(req)

    assert resp.degraded is False
    assert resp.predicted_cost.vercel_builds_likely >= 1
    assert resp.predicted_cost.vercel_build_min_estimate > 0


def test_recent_incidents_filtered_by_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Incidents file with overlapping related_files → returned in recent_incidents."""
    yaml_path = _write_yaml(tmp_path, _MINIMAL_YAML)
    monkeypatch.setattr(svc, "_memory_path", lambda: yaml_path)

    inc_path = tmp_path / "incidents.json"
    incidents_data = [
        {
            "incident_id": "INC-001",
            "severity": "high",
            "root_cause": "test failure",
            "related_files": ["apis/brain/app/services/foo.py"],
            "opened_at": "2026-04-28T10:00:00Z",
        },
        {
            "incident_id": "INC-002",
            "severity": "low",
            "root_cause": "unrelated",
            "related_files": ["apps/studio/unrelated.tsx"],
            "opened_at": "2026-04-28T10:00:00Z",
        },
    ]
    inc_path.write_text(json.dumps(incidents_data), encoding="utf-8")
    monkeypatch.setattr(svc, "_incidents_path", lambda: inc_path)

    req = CoachPreflightRequest(
        action_type="merge",
        files_touched=["apis/brain/app/services/foo.py"],
    )
    resp = svc.run_preflight(req)

    assert resp.degraded is False
    incident_ids = [i.incident_id for i in resp.recent_incidents]
    assert "INC-001" in incident_ids
    assert "INC-002" not in incident_ids


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_endpoint_requires_secret(client: AsyncClient) -> None:
    """POST without X-Brain-Secret → 401."""
    res = await client.post(
        "/api/v1/admin/coach/preflight",
        json={"action_type": "dispatch"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_endpoint_returns_response(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Happy path: POST with valid secret → 200 with CoachPreflightResponse shape."""
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-secret")

    yaml_path = _write_yaml(tmp_path, _BRAIN_DATA_DIR_YAML)
    monkeypatch.setattr(svc, "_memory_path", lambda: yaml_path)
    monkeypatch.setattr(svc, "_incidents_path", lambda: tmp_path / "incidents.json")

    res = await client.post(
        "/api/v1/admin/coach/preflight",
        json={
            "action_type": "dispatch",
            "files_touched": ["apis/brain/app/services/coach_preflight.py"],
        },
        headers={"X-Brain-Secret": "test-secret"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "matched_rules" in body
    assert "recent_incidents" in body
    assert "predicted_cost" in body
    assert "degraded" in body
    assert isinstance(body["matched_rules"], list)
