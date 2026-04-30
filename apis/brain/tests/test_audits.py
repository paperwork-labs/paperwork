"""Tests for Brain audit registry, run dispatch, cadence logic, and digest.

medallion: ops
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from app.schemas.audits import AuditFinding, AuditRun

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(
    audit_id: str,
    *,
    findings: list[AuditFinding] | None = None,
    ran_at: datetime | None = None,
    next_cadence: str = "weekly",
) -> AuditRun:
    return AuditRun(
        audit_id=audit_id,
        ran_at=ran_at or datetime.now(tz=UTC),
        findings=findings or [],
        summary="test run",
        next_cadence=next_cadence,  # type: ignore[arg-type]
    )


def _info_finding(audit_id: str = "stack") -> AuditFinding:
    return AuditFinding(audit_id=audit_id, severity="info", title="ok", detail="all good")


def _warn_finding(audit_id: str = "stack") -> AuditFinding:
    return AuditFinding(audit_id=audit_id, severity="warn", title="issue", detail="problem found")


def _error_finding(audit_id: str = "stack") -> AuditFinding:
    return AuditFinding(
        audit_id=audit_id, severity="error", title="critical", detail="critical issue"
    )


# ---------------------------------------------------------------------------
# Registry seed
# ---------------------------------------------------------------------------


def test_registry_seeds_12_audits(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        defs = audits.load_registry()

    assert len(defs) == 12
    ids = {d.id for d in defs}
    expected = {
        "stack",
        "runbook_completeness",
        "persona_coverage",
        "docs_freshness",
        "cost",
        "secrets_drift",
        "kg_self_validate",
        "a11y",
        "lighthouse",
        "vendor_renewal",
        "cross_app_ui_redundancy",
        "auto_distillation",
    }
    assert ids == expected


def test_registry_seed_is_idempotent(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        defs1 = audits.load_registry()
        defs2 = audits.load_registry()

    assert len(defs1) == len(defs2) == 12


def test_all_audits_default_weekly(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        defs = audits.load_registry()

    assert all(d.cadence == "weekly" for d in defs)


def test_all_audits_enabled_by_default(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        defs = audits.load_registry()

    assert all(d.enabled for d in defs)


# ---------------------------------------------------------------------------
# Run dispatch
# ---------------------------------------------------------------------------


def test_run_dispatch_calls_runner(tmp_path: Path) -> None:
    """run_audit should dynamically import runner and return AuditRun."""
    expected_run = _make_run("stack", findings=[_info_finding("stack")])

    def fake_run() -> AuditRun:
        return expected_run

    import types

    fake_mod = types.ModuleType("app.audits.stack")
    fake_mod.run = fake_run  # type: ignore[attr-defined]

    with (
        patch("app.services.audits._brain_data_dir", return_value=tmp_path),
        patch("importlib.import_module", return_value=fake_mod),
    ):
        from app.services import audits

        result = audits.run_audit("stack")

    assert result.audit_id == "stack"
    assert len(result.findings) == 1


def test_run_dispatch_missing_runner_module_raises(tmp_path: Path) -> None:
    """Missing runner_module → RuntimeError, not silent fallback."""
    with (
        patch("app.services.audits._brain_data_dir", return_value=tmp_path),
        patch("importlib.import_module", side_effect=ImportError("no module")),
    ):
        from app.services import audits

        with pytest.raises(RuntimeError, match="runner module not found"):
            audits.run_audit("stack")


def test_run_dispatch_unknown_audit_raises(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        with pytest.raises(ValueError, match="unknown audit"):
            audits.run_audit("nonexistent_audit_xyz")


def test_run_dispatch_persists_run(tmp_path: Path) -> None:
    import types

    run_obj = _make_run("stack")

    fake_mod = types.ModuleType("app.audits.stack")
    fake_mod.run = lambda: run_obj  # type: ignore[attr-defined]

    with (
        patch("app.services.audits._brain_data_dir", return_value=tmp_path),
        patch("importlib.import_module", return_value=fake_mod),
    ):
        from app.services import audits

        audits.run_audit("stack")
        runs = audits.load_runs_for("stack")

    assert len(runs) == 1
    assert runs[0].audit_id == "stack"


# ---------------------------------------------------------------------------
# Cadence relaxation / tightening
# ---------------------------------------------------------------------------


def test_cadence_relaxes_after_4_clean_weekly_runs(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        defs = audits.load_registry()
        defn = next(d for d in defs if d.id == "stack")
        assert defn.cadence == "weekly"

        # Seed 4 clean runs
        base_time = datetime.now(tz=UTC) - timedelta(days=28)
        runs = [
            _make_run("stack", findings=[_info_finding()], ran_at=base_time + timedelta(days=i * 7))
            for i in range(4)
        ]
        audits._save_runs(runs)

        adj = audits.evaluate_cadence_adjustment("stack")
        assert adj is not None
        assert adj.from_cadence == "weekly"
        assert adj.to_cadence == "monthly"
        assert adj.manual_override is False

        updated = audits.get_audit_def("stack")
        assert updated is not None
        assert updated.cadence == "monthly"


def test_cadence_relaxes_monthly_to_quarterly(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        # Set cadence to monthly
        audits.load_registry()
        audits.set_audit_cadence("stack", "monthly", manual=False)

        base_time = datetime.now(tz=UTC) - timedelta(days=120)
        runs = [
            _make_run(
                "stack", findings=[_info_finding()], ran_at=base_time + timedelta(days=i * 30)
            )
            for i in range(4)
        ]
        audits._save_runs(runs)

        adj = audits.evaluate_cadence_adjustment("stack")
        assert adj is not None
        assert adj.to_cadence == "quarterly"


def test_cadence_does_not_relax_before_4_runs(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        audits.load_registry()
        runs = [
            _make_run(
                "stack", findings=[_info_finding()], ran_at=datetime.now(tz=UTC) - timedelta(days=i)
            )
            for i in range(3)
        ]
        audits._save_runs(runs)

        adj = audits.evaluate_cadence_adjustment("stack")
        assert adj is None


def test_cadence_tightens_on_warn_finding(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        audits.load_registry()
        audits.set_audit_cadence("stack", "monthly", manual=False)

        run = _make_run("stack", findings=[_warn_finding()])
        audits._save_runs([run])

        adj = audits.evaluate_cadence_adjustment("stack")
        assert adj is not None
        assert adj.to_cadence == "weekly"


def test_cadence_tightens_on_error_finding(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        audits.load_registry()
        audits.set_audit_cadence("stack", "quarterly", manual=False)

        run = _make_run("stack", findings=[_error_finding()])
        audits._save_runs([run])

        adj = audits.evaluate_cadence_adjustment("stack")
        assert adj is not None
        assert adj.to_cadence == "weekly"


def test_manual_override_respected_no_auto_adjust(tmp_path: Path) -> None:
    """Manual override blocks subsequent auto-adjust."""
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        audits.load_registry()
        audits.set_audit_cadence("stack", "monthly", manual=True)

        # Even 4 clean runs should NOT auto-adjust since manual override is active
        runs = [
            _make_run(
                "stack", findings=[_info_finding()], ran_at=datetime.now(tz=UTC) - timedelta(days=i)
            )
            for i in range(4)
        ]
        audits._save_runs(runs)

        adj = audits.evaluate_cadence_adjustment("stack")
        assert adj is None


# ---------------------------------------------------------------------------
# Weekly digest bundling
# ---------------------------------------------------------------------------


def test_weekly_digest_bundles_info_findings(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        audits.load_registry()
        recent_run = _make_run(
            "stack",
            findings=[_info_finding(), _warn_finding()],
            ran_at=datetime.now(tz=UTC) - timedelta(days=1),
        )
        audits._save_runs([recent_run])

        digest = audits.weekly_audit_digest()

    assert digest["tag"] == "weekly-audit-digest"
    assert digest["finding_count"] == 1  # only info findings
    assert digest["findings"][0]["severity"] == "info"


def test_weekly_digest_excludes_old_runs(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        audits.load_registry()
        old_run = _make_run(
            "stack",
            findings=[_info_finding()],
            ran_at=datetime.now(tz=UTC) - timedelta(days=10),
        )
        audits._save_runs([old_run])

        digest = audits.weekly_audit_digest()

    assert digest["finding_count"] == 0


def test_high_severity_findings_queued_to_pending_conversations(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        audits.load_registry()
        run = _make_run("stack", findings=[_error_finding()])
        audits._save_runs([run])
        audits._handle_high_severity_findings(run)

        pending_path = tmp_path / "pending_audit_conversations.json"
        assert pending_path.is_file()
        data = json.loads(pending_path.read_text())
        assert len(data) == 1
        assert data[0]["urgency"] == "high"
        assert data[0]["severity"] == "error"


# ---------------------------------------------------------------------------
# audit_freshness POS pillar
# ---------------------------------------------------------------------------


def test_audit_freshness_all_fresh(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        audits.load_registry()
        # Give each audit a fresh run
        defs = audits.load_registry()
        runs = [
            _make_run(
                d.id,
                findings=[_info_finding(d.id)],
                ran_at=datetime.now(tz=UTC) - timedelta(hours=1),
            )
            for d in defs
            if d.enabled
        ]
        audits._save_runs(runs)

        score, measured, notes = audits.audit_freshness()

    assert measured is True
    assert score == 100.0
    assert "12/12" in notes


def test_audit_freshness_none_run(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        audits.load_registry()
        score, measured, notes = audits.audit_freshness()

    assert measured is True
    assert score == 0.0
    _ = notes  # suppress unused-variable


def test_audit_freshness_partial(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        audits.load_registry()
        # Run only "stack" within window
        run = _make_run("stack", findings=[], ran_at=datetime.now(tz=UTC) - timedelta(hours=1))
        audits._save_runs([run])

        score, measured, _notes2 = audits.audit_freshness()

    assert measured is True
    # 1 out of 12
    assert abs(score - (1 / 12 * 100)) < 0.1


# ---------------------------------------------------------------------------
# Runs capped at 100
# ---------------------------------------------------------------------------


def test_runs_capped_at_100(tmp_path: Path) -> None:
    with patch("app.services.audits._brain_data_dir", return_value=tmp_path):
        from app.services import audits

        audits.load_registry()
        runs = [
            _make_run("stack", ran_at=datetime.now(tz=UTC) - timedelta(hours=i)) for i in range(110)
        ]
        audits._save_runs(runs)
        loaded = audits.load_runs()

    assert len(loaded) == 100
