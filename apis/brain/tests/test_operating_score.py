"""Tests for Paperwork Operating Score (WS-66)."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest
import yaml

from app.schemas.operating_score import (
    OperatingScoreEntry,
    OperatingScoreSpec,
    PillarScore,
    ScoreGates,
)
from app.services import operating_score as pos
from app.services.operating_score_collectors import (
    a11y_design_system,
    autonomy,
    code_quality,
    data_architecture,
    knowledge_capital,
    reliability_security,
    stack_modernity,
    web_perf_ux,
)
from app.services.operating_score_collectors import (
    persona_coverage as persona_cov,
)

# tests/ lives under apis/brain/tests/
_SPEC_MINIMUM = Path(__file__).resolve().parents[1] / "data" / "operating_score_spec.yaml"

_TWO_PILLAR_SPEC = """\
schema:
  description: Paperwork Operating Score POS test fixture
version: 1
target_total: 90
graduation_gates:
  l4: { min_total: 80, min_pillar: 70 }
  l5: { min_total: 90, sustained_weeks: 4 }
pillars:
  - id: autonomy
    weight: 49
    industry_reference: x
    target: 80
    measurement_source: x
    description: x
  - id: persona_coverage
    weight: 51
    industry_reference: x
    target: 80
    measurement_source: x
    description: x
"""


def test_operating_score_spec_yaml_weights_total_one_hundred() -> None:
    loaded = yaml.safe_load(_SPEC_MINIMUM.read_text(encoding="utf-8"))
    spec = OperatingScoreSpec.model_validate(loaded)
    assert sum(p.weight for p in spec.pillars) == 100


def test_spec_bad_weight_sum_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bad_yaml = yaml.safe_load(_TWO_PILLAR_SPEC)
    rows = bad_yaml["pillars"]
    rows[0]["weight"] = 40
    rows[1]["weight"] = 40  # totals 80
    pth = tmp_path / "bad.yaml"
    pth.write_text(yaml.dump(bad_yaml), encoding="utf-8")
    monkeypatch.setenv("BRAIN_OPERATING_SCORE_SPEC_YAML", str(pth))
    with pytest.raises(ValueError, match="sum to 100"):
        pos.load_spec()


def test_compute_score_has_all_spec_pillars(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _tiny_spec(monkeypatch, tmp_path)
    entry = pos.compute_score()
    assert entry.pillars.keys() == {"autonomy", "persona_coverage"}


def test_record_score_appends_updates_current(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _tiny_spec(monkeypatch, tmp_path)
    jq = tmp_path / "scores.json"
    jq.write_text(
        '{"schema": "operating_score/v1", "description": "t", "current": null, "history": []}\n'
    )
    monkeypatch.setenv("BRAIN_OPERATING_SCORE_JSON", str(jq))
    e1 = mk_entry(61.55)
    pos.record_score(e1)
    blob = pos.read_operating_file()
    assert blob.current is not None and pytest.approx(blob.current.total, rel=1e-4) == 61.55
    assert len(blob.history) == 1


@pytest.mark.parametrize(
    ("collector", "want", "measured"),
    [
        (web_perf_ux.collect, 55.0, False),
        (a11y_design_system.collect, 50.0, False),
        (data_architecture.collect, 55.0, False),
    ],
)
def test_bootstrap_collectors_stub(
    collector,
    want: float,
    measured: bool,
) -> None:
    score, mf, _notes = collector()
    assert pytest.approx(score) == want
    assert mf is measured


def test_autonomy_under_ten_is_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _tiny_spec(monkeypatch, tmp_path)
    po = tmp_path / "po.json"
    po.write_text('{"schema":"pr_outcomes/v1","description":"x","outcomes":[]}')
    monkeypatch.setenv("BRAIN_PR_OUTCOMES_JSON", str(po))
    monkeypatch.setenv("BRAIN_APP_REGISTRY_JSON", str(tmp_path / "no-registry.json"))
    s, ok, notes = autonomy.collect()
    assert s == 20.0 and ok is False
    assert "corpus building" in notes.lower()


def test_knowledge_capital_reads_rules(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ym = tmp_path / "proc.yaml"
    ym.write_text("version: 1\nrules:\n  - id: alpha\n")
    monkeypatch.setenv("BRAIN_PROCEDURAL_MEMORY_YAML", str(ym))
    pr = tmp_path / "po.json"
    pr.write_text('{"schema":"pr_outcomes/v1","description":"x","outcomes":[]}')
    monkeypatch.setenv("BRAIN_PR_OUTCOMES_JSON", str(pr))
    score, mf, notes = knowledge_capital.collect()
    assert mf is True and pytest.approx(score) == 5.0
    assert "rules=" in notes


def test_persona_coverage_reports_counts() -> None:
    _s, mf, notes = persona_cov.collect()
    assert mf is True
    assert "personas/specs/*.yaml" in notes
    assert ".cursor/rules" in notes


def test_gates_l4_fails_below_total(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    full_spec(monkeypatch, tmp_path)
    spec = pos.load_spec()
    pillars_even = pillar_scores_uniform(spec, 95.0)
    g_false = pos._gates_for_entry(spec, 70.5, pillars_even, [])  # type: ignore[attr-defined]
    assert g_false.l4_pass is False


def test_gates_l4_fails_below_min_pillar(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    full_spec(monkeypatch, tmp_path)
    spec = pos.load_spec()
    pillars_bad = pillar_scores_override(spec, "a11y_design_system", 65.0)
    total_here = round(sum(pv.weighted for pv in pillars_bad.values()), 4)
    g_false = pos._gates_for_entry(spec, total_here, pillars_bad, [])  # type: ignore[attr-defined]
    assert g_false.l4_pass is False


def test_gates_l5_requires_four_consecutive_above_min(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    full_spec(monkeypatch, tmp_path)
    spec = pos.load_spec()
    pillars = pillar_scores_uniform(spec, 93.7)
    total_ok = round(sum(pv.weighted for pv in pillars.values()), 4)

    early = pos._gates_for_entry(spec, total_ok, pillars, [])  # type: ignore[attr-defined]
    assert early.l5_pass is False

    three = pos._gates_for_entry(spec, 91.5, pillars, [91.0, 91.5])  # type: ignore[attr-defined]
    assert three.l5_pass is False

    four = pos._gates_for_entry(spec, 91.0, pillars, [91.0, 91.0, 92.0, 92.5])  # type: ignore[attr-defined]
    assert four.l5_pass is True


def test_concurrent_writes_no_exceptions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _tiny_spec(monkeypatch, tmp_path)
    jq = tmp_path / "c.json"
    jq.write_text(
        '{"schema": "operating_score/v1", "description": "t", "current": null, "history": []}\n'
    )
    monkeypatch.setenv("BRAIN_OPERATING_SCORE_JSON", str(jq))

    errs: list[BaseException] = []

    def run(score: float) -> None:
        try:
            pos.record_score(mk_entry(score))
        except BaseException as ex:
            errs.append(ex)

    threads = [threading.Thread(target=run, args=(float(i),)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errs
    data = json.loads(jq.read_text(encoding="utf-8"))
    assert isinstance(data.get("history"), list)


def test_web_perf_ux_collector_reads_lighthouse_runs_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lj = tmp_path / "lh.json"
    lj.write_text(
        json.dumps(
            {
                "schema": "lighthouse_ci_runs/v1",
                "runs": [
                    {
                        "run_at": "2026-04-29T02:05:06Z",
                        "url": "https://example.test/",
                        "scores": {
                            "performance": 0.8,
                            "accessibility": 0.7,
                            "best_practices": 0.9,
                            "seo": 0.85,
                        },
                        "metrics": {
                            "lcp_ms": 100.0,
                            "cls": 0.0,
                            "tbt_ms": 0.0,
                            "fcp_ms": 90.0,
                        },
                        "commit_sha": "abc123",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_LIGHTHOUSE_CI_RUNS_JSON", str(lj))
    s, ok, notes = web_perf_ux.collect()
    want = ((0.8 + 0.7 + 0.9 + 0.85) / 4.0) * 100.0
    assert ok is True and pytest.approx(s) == want
    assert "lighthouse_ci_runs.json @ 2026-04-29T02:05:06Z" in notes


def test_web_perf_ux_collector_empty_file_returns_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lj = tmp_path / "lh_empty.json"
    lj.write_text(
        '{"schema":"lighthouse_ci_runs/v1","runs":[]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_LIGHTHOUSE_CI_RUNS_JSON", str(lj))
    score, mf, notes = web_perf_ux.collect()
    assert score == pytest.approx(55.0) and mf is False
    assert "no Lighthouse-CI runs yet" in notes


def test_atomic_write_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _tiny_spec(monkeypatch, tmp_path)
    jq = tmp_path / "r.json"
    jq.write_text('{"schema":"operating_score/v1","description":"t","current":null,"history":[]}')
    monkeypatch.setenv("BRAIN_OPERATING_SCORE_JSON", str(jq))
    pos.record_score(mk_entry(44.44))
    raw = json.loads(jq.read_text(encoding="utf-8"))
    assert pytest.approx(float(raw["current"]["total"])) == 44.44


def test_dora_collector_with_gh_available_returns_measured(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import app.services.operating_score_collectors.dora_elite as de

    monkeypatch.setattr(de, "_brain_data_dir", lambda: tmp_path)

    hits = {"i": 0}

    def fake_search_ordered(q: str) -> int:
        if "Revert in:title" in q:
            return 2
        hits["i"] += 1
        if hits["i"] == 1:
            return 10
        return 20

    monkeypatch.setattr(de, "_repo_slug", lambda: "paperworklabs/paperwork")
    monkeypatch.setattr(de, "_search_issues_total", fake_search_ordered)
    monkeypatch.setattr(
        de, "_lead_time_median_recent", lambda _s, _b: (10.0, [{} for _ in range(30)])
    )
    monkeypatch.setattr(de, "_workflow_mttr_hours", lambda _s, _w, _b: 2.0)

    score, measured, _notes = de.collect()
    assert measured is True
    assert pytest.approx(score) == 77.5
    dumped = json.loads((tmp_path / "dora_metrics.json").read_text(encoding="utf-8"))
    assert dumped["schema"] == "dora_metrics/v1"


def test_dora_collector_gh_unavailable_returns_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.operating_score_collectors.dora_elite as de

    monkeypatch.setattr(de, "_repo_slug", lambda: "paperworklabs/paperwork")

    def boom(_q: str) -> int:
        raise subprocess.CalledProcessError(1, ["gh", "api"])

    monkeypatch.setattr(de, "_search_issues_total", boom)
    score, measured, notes = de.collect()
    assert measured is False and pytest.approx(score) == 75.0
    assert "gh CLI unavailable" in notes


def test_stack_modernity_reads_audit_doc(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    p = tmp_path / "STACK_AUDIT.md"
    p.write_text(
        "## Executive Summary\n\n"
        "- KEEP: 10\n"
        "- UPGRADE: 10\n"
        "- REPLACE: 10\n"
        "**Audit date:** 2026-04-29\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_STACK_AUDIT_MD", str(p))
    monkeypatch.setenv("BRAIN_REPO_ROOT", str(tmp_path))

    score, measured, notes = stack_modernity.collect()
    assert measured is True and pytest.approx(score) == 50.0
    assert "KEEP / 10 UPGRADE / 10 REPLACE" in notes


def test_stack_modernity_audit_stale_penalty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    p = tmp_path / "STACK_AUDIT.md"
    p.write_text(
        "## Executive Summary\n\n"
        "- KEEP: 10\n"
        "- UPGRADE: 10\n"
        "- REPLACE: 10\n"
        "**Audit date:** 2026-04-29\n",
        encoding="utf-8",
    )
    old = time.time() - 86400 * 91
    os.utime(p, (old, old))

    monkeypatch.setenv("BRAIN_STACK_AUDIT_MD", str(p))
    monkeypatch.setenv("BRAIN_REPO_ROOT", str(tmp_path))

    score, measured, notes = stack_modernity.collect()
    assert measured is True and pytest.approx(score) == 35.0
    assert "audit stale: " in notes


def test_stack_modernity_no_audit_returns_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("BRAIN_STACK_AUDIT_MD", str(tmp_path / "nope.md"))
    monkeypatch.setenv("BRAIN_REPO_ROOT", str(tmp_path))

    score, measured, notes = stack_modernity.collect()
    assert measured is False and pytest.approx(score) == 65.0
    assert "WS-49" in notes


def test_collector_exception_yields_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.services.operating_score_collectors import autonomy as aut_mod

    _tiny_spec(monkeypatch, tmp_path)

    def boom() -> tuple[float, bool, str]:
        raise RuntimeError("simulated")

    monkeypatch.setattr(aut_mod, "collect", boom)
    entry = pos.compute_score()
    ap = entry.pillars["autonomy"]
    assert ap.score == pytest.approx(50.0) and ap.measured is False


def test_code_quality_collector_with_coverage_xml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    brain = tmp_path / "apis" / "brain"
    (brain / "app").mkdir(parents=True)
    (brain / "app" / "sample.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (brain / "coverage.xml").write_text(
        '<?xml version="1.0" ?><coverage line-rate="0.9" branch-rate="0"><packages/></coverage>\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_PACKAGE_ROOT", str(brain))

    def fake_run(
        cmd: list[str],
        cwd: Path,
        *,
        timeout: float = 600,
    ) -> subprocess.CompletedProcess[str]:
        _ = cwd, timeout
        if "mypy" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "Success: no issues found\n", "")
        if "ruff" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        raise AssertionError(cmd)

    monkeypatch.setattr(code_quality, "_run", fake_run)

    score, measured, _notes = code_quality.collect()
    assert measured is True
    want = (90.0 + 100.0 + 100.0 + 100.0) / 4.0
    assert pytest.approx(score) == want
    dumped = json.loads((brain / "data" / "code_quality_metrics.json").read_text(encoding="utf-8"))
    assert dumped["schema"] == "code_quality_metrics/v1"
    assert pytest.approx(float(dumped["sub_scores"]["test_coverage"])) == 90.0


def test_code_quality_collector_no_tools_returns_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    brain = tmp_path / "apis" / "brain"
    (brain / "app").mkdir(parents=True)
    monkeypatch.setenv("BRAIN_PACKAGE_ROOT", str(brain))

    def boom(
        cmd: list[str],
        cwd: Path,
        *,
        timeout: float = 600,
    ) -> subprocess.CompletedProcess[str]:
        _ = cmd, cwd, timeout
        raise FileNotFoundError("uv")

    monkeypatch.setattr(code_quality, "_run", boom)
    score, measured, notes = code_quality.collect()
    assert measured is False and pytest.approx(score) == 75.0
    assert "tooling unavailable" in notes


def test_reliability_security_collector_with_iac_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "iac_state_vercel.yaml").write_text(
        "schema:\n  description: t\nversion: 1\n",
        encoding="utf-8",
    )
    tmp_path.joinpath("render_quota_probe.json").write_text(
        json.dumps({"recorded_at": "2026-04-28T15:00:00Z"}),
        encoding="utf-8",
    )
    (tmp_path / "incidents.json").write_text(
        '{"schema":"incidents/v1","incidents":[]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_RELIABILITY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("BRAIN_REPO_ROOT", str(tmp_path))

    monkeypatch.setattr(
        reliability_security,
        "_gitleaks_workflow_subscore",
        lambda _repo, _now: (100.0, "mock_ok"),
    )

    score, measured, _notes = reliability_security.collect()
    assert measured is True
    want = (50.0 + 100.0 + 100.0 + 100.0) / 4.0
    assert pytest.approx(score) == want
    payload = json.loads((tmp_path / "reliability_metrics.json").read_text(encoding="utf-8"))
    assert payload["schema"] == "reliability_metrics/v1"


def test_reliability_security_collector_empty_returns_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("BRAIN_RELIABILITY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("BRAIN_REPO_ROOT", str(tmp_path))
    score, measured, notes = reliability_security.collect()
    assert measured is False and pytest.approx(score) == 60.0
    assert "canonical" in notes.lower()


def test_a11y_collector_reads_axe_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """1 critical violation => 100 - 20 = 80 (POS axe formula in CI script)."""
    ax = tmp_path / "axe.json"
    ax.write_text(
        json.dumps(
            {
                "schema": "axe_runs/v1",
                "runs": [
                    {
                        "run_at": "2026-04-29T12:00:00Z",
                        "url": "https://studio.paperworklabs.com/",
                        "violations": {"critical": 1, "serious": 0, "moderate": 0, "minor": 0},
                        "passes": 12,
                        "incomplete": 1,
                        "score": 80.0,
                        "commit_sha": "abc",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_AXE_RUNS_JSON", str(ax))
    monkeypatch.setenv("BRAIN_REPO_ROOT", str(tmp_path))
    s, ok, notes = a11y_design_system.collect()
    assert ok is True and pytest.approx(s) == 80.0
    assert "from axe_runs.json @ 2026-04-29T12:00:00Z" in notes


def test_a11y_collector_empty_returns_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ax = tmp_path / "axe_empty.json"
    ax.write_text(
        '{"schema":"axe_runs/v1","runs":[]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_AXE_RUNS_JSON", str(ax))
    score, mf, notes = a11y_design_system.collect()
    assert score == pytest.approx(50.0) and mf is False
    assert "no axe-core runs yet" in notes


# --- helpers -----------------------------------------------------------


def _tiny_spec(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fp = tmp_path / "two.yaml"
    fp.write_text(_TWO_PILLAR_SPEC, encoding="utf-8")
    monkeypatch.setenv("BRAIN_OPERATING_SCORE_SPEC_YAML", str(fp))


def full_spec(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fp = tmp_path / "full.yaml"
    fp.write_text(_SPEC_MINIMUM.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("BRAIN_OPERATING_SCORE_SPEC_YAML", str(fp))


def pillar_scores_uniform(spec: OperatingScoreSpec, score: float) -> dict[str, PillarScore]:
    out: dict[str, PillarScore] = {}
    for p in spec.pillars:
        wght = round(score * p.weight / 100.0, 6)
        out[p.id] = PillarScore(
            score=score,
            weight=p.weight,
            weighted=wght,
            measured=False,
            notes="x",
        )
    return out


def pillar_scores_override(
    spec: OperatingScoreSpec,
    pid: str,
    score: float,
) -> dict[str, PillarScore]:
    out: dict[str, PillarScore] = {}
    for p in spec.pillars:
        s_val = score if p.id == pid else 95.0
        wght = round(s_val * p.weight / 100.0, 6)
        out[p.id] = PillarScore(
            score=s_val,
            weight=p.weight,
            weighted=wght,
            measured=False,
            notes="x",
        )
    return out


def mk_entry(per_pillar: float) -> OperatingScoreEntry:
    spec = OperatingScoreSpec.model_validate(yaml.safe_load(_TWO_PILLAR_SPEC))
    pillars: dict[str, PillarScore] = {}
    for p in spec.pillars:
        w = round(per_pillar * p.weight / 100.0, 6)
        pillars[p.id] = PillarScore(
            score=per_pillar,
            weight=p.weight,
            weighted=w,
            measured=False,
            notes="t",
        )
    total = round(sum(x.weighted for x in pillars.values()), 4)
    gate = ScoreGates(l4_pass=False, l5_pass=False, lowest_pillar="autonomy")
    return OperatingScoreEntry(
        computed_at="2026-01-01T00:00:00Z",
        total=total,
        pillars=pillars,
        gates=gate,
    )
