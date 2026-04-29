"""Tests for compute_brain_improvement_index (WS-69 PR D).

Fixtures cover empty / mid-tier / fully-graduated states.
Score bands: 0 / 30 / 70 / 95 ranges, plus divide-by-zero safety.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from app.services.self_improvement import compute_brain_improvement_index

# ---------------------------------------------------------------------------
# Helpers to write fixture files
# ---------------------------------------------------------------------------


def _write_pr_outcomes(tmp_path: Path, outcomes: list[dict]) -> Path:
    p = tmp_path / "pr_outcomes.json"
    p.write_text(
        json.dumps(
            {
                "schema": "pr_outcomes/v1",
                "description": "test",
                "outcomes": outcomes,
            }
        ),
        encoding="utf-8",
    )
    return p


def _write_promotions(tmp_path: Path, *, tier: str, merges: list[dict]) -> Path:
    p = tmp_path / "self_merge_promotions.json"
    p.write_text(
        json.dumps(
            {
                "schema": {
                    "description": "test",
                    "tier_definitions": {
                        "data-only": "test",
                        "brain-code": "test",
                        "app-code": "test",
                    },
                },
                "version": 1,
                "current_tier": tier,
                "promotions": [],
                "merges": merges,
                "reverts": [],
            }
        ),
        encoding="utf-8",
    )
    return p


def _write_procedural_memory(tmp_path: Path, num_rules: int) -> Path:
    p = tmp_path / "procedural_memory.yaml"
    rules = [
        {
            "id": f"rule_{i}",
            "when": "test trigger",
            "do": "test action",
            "source": "test",
            "learned_at": "2026-04-01T00:00:00Z",
            "confidence": "high",
            "applies_to": ["cheap-agents"],
        }
        for i in range(num_rules)
    ]
    p.write_text(yaml.dump({"version": 1, "rules": rules}), encoding="utf-8")
    return p


def _write_weekly_retros(tmp_path: Path, pos_changes: list[float]) -> Path:
    p = tmp_path / "weekly_retros.json"
    retros = [
        {
            "week_ending": f"2026-04-{14 + i:02d}T00:00:00+00:00",
            "computed_at": f"2026-04-{14 + i:02d}T01:00:00+00:00",
            "summary": {
                "pos_total_change": change,
                "merges": 5,
                "reverts": 0,
                "incidents": 0,
                "candidates_proposed": 1,
                "candidates_promoted": 0,
            },
            "highlights": [],
            "rule_changes": [],
            "objective_progress": {},
            "notes": "test",
        }
        for i, change in enumerate(pos_changes)
    ]
    p.write_text(
        json.dumps(
            {"schema": "weekly_retros/v1", "description": "test", "version": 1, "retros": retros}
        ),
        encoding="utf-8",
    )
    return p


def _setup_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pr_outcomes_path: Path,
    promotions_path: Path,
    procedural_memory_path: Path,
    weekly_retros_path: Path,
) -> None:
    monkeypatch.setenv("BRAIN_PR_OUTCOMES_JSON", str(pr_outcomes_path))
    monkeypatch.setenv("BRAIN_SELF_MERGE_PROMOTIONS_JSON", str(promotions_path))
    monkeypatch.setenv("BRAIN_PROCEDURAL_MEMORY_YAML", str(procedural_memory_path))
    monkeypatch.setenv("BRAIN_WEEKLY_RETROS_JSON", str(weekly_retros_path))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def empty_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Empty state: no outcomes, no merges, few rules, no retros."""
    pr_path = _write_pr_outcomes(tmp_path, [])
    promo_path = _write_promotions(tmp_path, tier="data-only", merges=[])
    mem_path = _write_procedural_memory(tmp_path, num_rules=0)
    retros_path = _write_weekly_retros(tmp_path, [])
    _setup_env(
        monkeypatch,
        pr_outcomes_path=pr_path,
        promotions_path=promo_path,
        procedural_memory_path=mem_path,
        weekly_retros_path=retros_path,
    )
    return tmp_path


@pytest.fixture()
def mid_tier_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Mid-tier state: some outcomes, 20 clean merges, 10 rules, small pos gain."""
    outcomes = [
        {
            "pr_number": i,
            "merged_at": "2026-04-20T10:00:00Z",
            "merged_by_agent": "composer-1.5",
            "agent_model": "composer-1.5",
            "subagent_type": "code",
            "workstream_ids": [],
            "workstream_types": [],
            "outcomes": {
                "h1": None,
                "h24": {"ci_pass": True, "deploy_success": True, "reverted": False},
                "d7": None,
                "d14": None,
                "d30": None,
            },
        }
        for i in range(1, 11)
    ]
    pr_path = _write_pr_outcomes(tmp_path, outcomes)
    merges = [
        {
            "pr_number": i,
            "merged_at": "2026-04-20T10:00:00Z",
            "tier": "data-only",
            "paths_touched": ["apis/brain/data/test.json"],
            "graduation_eligible": True,
        }
        for i in range(101, 121)  # 20 clean merges
    ]
    promo_path = _write_promotions(tmp_path, tier="data-only", merges=merges)
    mem_path = _write_procedural_memory(tmp_path, num_rules=10)
    retros_path = _write_weekly_retros(tmp_path, [1.0])
    _setup_env(
        monkeypatch,
        pr_outcomes_path=pr_path,
        promotions_path=promo_path,
        procedural_memory_path=mem_path,
        weekly_retros_path=retros_path,
    )
    return tmp_path


@pytest.fixture()
def graduated_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Fully-graduated state: 100% acceptance, app-code tier, 50 rules, strong retro."""
    outcomes = [
        {
            "pr_number": i,
            "merged_at": "2026-04-20T10:00:00Z",
            "merged_by_agent": "composer-1.5",
            "agent_model": "composer-1.5",
            "subagent_type": "code",
            "workstream_ids": [],
            "workstream_types": [],
            "outcomes": {
                "h1": None,
                "h24": {"ci_pass": True, "deploy_success": True, "reverted": False},
                "d7": None,
                "d14": None,
                "d30": None,
            },
        }
        for i in range(1, 21)
    ]
    pr_path = _write_pr_outcomes(tmp_path, outcomes)
    promo_path = _write_promotions(tmp_path, tier="app-code", merges=[])
    mem_path = _write_procedural_memory(tmp_path, num_rules=50)
    retros_path = _write_weekly_retros(tmp_path, [15.0])
    _setup_env(
        monkeypatch,
        pr_outcomes_path=pr_path,
        promotions_path=promo_path,
        procedural_memory_path=mem_path,
        weekly_retros_path=retros_path,
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Tests: empty state
# ---------------------------------------------------------------------------


def test_empty_state_score_zero(empty_fixture):
    result = compute_brain_improvement_index()
    assert result.score == 0
    assert result.acceptance_rate_pct == 0.0
    assert result.promotion_progress_pct == 0.0
    assert result.rules_count == 0
    assert "insufficient data" in result.note


def test_empty_state_no_divide_by_zero(empty_fixture):
    """Calling with empty corpus must not raise ZeroDivisionError."""
    result = compute_brain_improvement_index()
    assert isinstance(result.score, int)


def test_empty_state_score_in_range(empty_fixture):
    result = compute_brain_improvement_index()
    assert 0 <= result.score <= 100


# ---------------------------------------------------------------------------
# Tests: mid-tier state (expect score ~30-55)
# ---------------------------------------------------------------------------


def test_mid_tier_acceptance_rate(mid_tier_fixture):
    result = compute_brain_improvement_index()
    assert result.acceptance_rate_pct == pytest.approx(100.0)


def test_mid_tier_promotion_progress(mid_tier_fixture):
    result = compute_brain_improvement_index()
    assert result.promotion_progress_pct == pytest.approx(40.0)  # 20/50 * 100


def test_mid_tier_rules_count(mid_tier_fixture):
    result = compute_brain_improvement_index()
    assert result.rules_count == 10


def test_mid_tier_score_band(mid_tier_fixture):
    """Expected math: 0.40*100 + 0.30*40 + 0.20*20 + 0.10*(50+1*2.5) = 61.25 -> round 61."""
    result = compute_brain_improvement_index()
    assert 30 <= result.score <= 75


def test_mid_tier_no_note_on_non_empty(mid_tier_fixture):
    result = compute_brain_improvement_index()
    assert result.note == ""


# ---------------------------------------------------------------------------
# Tests: fully-graduated state (expect score ~90-100)
# ---------------------------------------------------------------------------


def test_graduated_acceptance_rate_full(graduated_fixture):
    result = compute_brain_improvement_index()
    assert result.acceptance_rate_pct == pytest.approx(100.0)


def test_graduated_promotion_full(graduated_fixture):
    result = compute_brain_improvement_index()
    assert result.promotion_progress_pct == pytest.approx(100.0)


def test_graduated_rules_saturated(graduated_fixture):
    result = compute_brain_improvement_index()
    assert result.rules_count == 50


def test_graduated_score_band(graduated_fixture):
    """Expected math: 0.40*100 + 0.30*100 + 0.20*100 + 0.10*87.5 = 98.75 -> round 99."""
    result = compute_brain_improvement_index()
    assert 70 <= result.score <= 100


# ---------------------------------------------------------------------------
# Tests: missing files (hard 0)
# ---------------------------------------------------------------------------


def test_missing_pr_outcomes_returns_zero(tmp_path, monkeypatch):
    promo_path = _write_promotions(tmp_path, tier="data-only", merges=[])
    mem_path = _write_procedural_memory(tmp_path, num_rules=5)
    retros_path = _write_weekly_retros(tmp_path, [])
    monkeypatch.setenv("BRAIN_PR_OUTCOMES_JSON", str(tmp_path / "nonexistent.json"))
    monkeypatch.setenv("BRAIN_SELF_MERGE_PROMOTIONS_JSON", str(promo_path))
    monkeypatch.setenv("BRAIN_PROCEDURAL_MEMORY_YAML", str(mem_path))
    monkeypatch.setenv("BRAIN_WEEKLY_RETROS_JSON", str(retros_path))
    result = compute_brain_improvement_index()
    assert result.score == 0
    assert "insufficient data" in result.note


def test_missing_promotions_returns_zero(tmp_path, monkeypatch):
    pr_path = _write_pr_outcomes(tmp_path, [])
    mem_path = _write_procedural_memory(tmp_path, num_rules=5)
    retros_path = _write_weekly_retros(tmp_path, [])
    monkeypatch.setenv("BRAIN_PR_OUTCOMES_JSON", str(pr_path))
    monkeypatch.setenv("BRAIN_SELF_MERGE_PROMOTIONS_JSON", str(tmp_path / "nonexistent.json"))
    monkeypatch.setenv("BRAIN_PROCEDURAL_MEMORY_YAML", str(mem_path))
    monkeypatch.setenv("BRAIN_WEEKLY_RETROS_JSON", str(retros_path))
    result = compute_brain_improvement_index()
    assert result.score == 0
    assert "insufficient data" in result.note


def test_missing_procedural_memory_returns_zero(tmp_path, monkeypatch):
    pr_path = _write_pr_outcomes(tmp_path, [])
    promo_path = _write_promotions(tmp_path, tier="data-only", merges=[])
    retros_path = _write_weekly_retros(tmp_path, [])
    monkeypatch.setenv("BRAIN_PR_OUTCOMES_JSON", str(pr_path))
    monkeypatch.setenv("BRAIN_SELF_MERGE_PROMOTIONS_JSON", str(promo_path))
    monkeypatch.setenv("BRAIN_PROCEDURAL_MEMORY_YAML", str(tmp_path / "nonexistent.yaml"))
    monkeypatch.setenv("BRAIN_WEEKLY_RETROS_JSON", str(retros_path))
    result = compute_brain_improvement_index()
    assert result.score == 0
    assert "insufficient data" in result.note


# ---------------------------------------------------------------------------
# Tests: all PRs reverted (acceptance_rate = 0)
# ---------------------------------------------------------------------------


def test_all_reverted_acceptance_zero(tmp_path, monkeypatch):
    outcomes = [
        {
            "pr_number": 1,
            "merged_at": "2026-04-20T10:00:00Z",
            "merged_by_agent": "composer-1.5",
            "agent_model": "composer-1.5",
            "subagent_type": "code",
            "workstream_ids": [],
            "workstream_types": [],
            "outcomes": {
                "h1": None,
                "h24": {"ci_pass": False, "deploy_success": False, "reverted": True},
                "d7": None,
                "d14": None,
                "d30": None,
            },
        }
    ]
    pr_path = _write_pr_outcomes(tmp_path, outcomes)
    promo_path = _write_promotions(tmp_path, tier="data-only", merges=[])
    mem_path = _write_procedural_memory(tmp_path, num_rules=5)
    retros_path = _write_weekly_retros(tmp_path, [])
    _setup_env(
        monkeypatch,
        pr_outcomes_path=pr_path,
        promotions_path=promo_path,
        procedural_memory_path=mem_path,
        weekly_retros_path=retros_path,
    )
    result = compute_brain_improvement_index()
    assert result.acceptance_rate_pct == pytest.approx(0.0)
    assert 0 <= result.score <= 30


# ---------------------------------------------------------------------------
# Tests: computed_at metadata
# ---------------------------------------------------------------------------


def test_computed_at_is_utc(empty_fixture):
    result = compute_brain_improvement_index()
    assert result.computed_at.tzinfo is not None


def test_custom_at_param(empty_fixture):
    custom_at = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)
    result = compute_brain_improvement_index(at=custom_at)
    assert result.computed_at == custom_at
