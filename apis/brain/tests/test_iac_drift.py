from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml

from app.schedulers import iac_drift as iac_drift_scheduler
from app.services import iac_drift


def _write_vercel_state(path: Path, projects: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "schema": {"description": "test"},
                "version": 1,
                "projects": projects,
                "last_reconciled_at": None,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _surface(tmp_path: Path, projects: list[dict]) -> iac_drift.VercelEnvSurface:
    state_path = tmp_path / "infra" / "state" / "vercel.yaml"
    _write_vercel_state(state_path, projects)
    return iac_drift.VercelEnvSurface(state_path=state_path)


def test_missing_canonical_file_raises(tmp_path: Path) -> None:
    surface = iac_drift.VercelEnvSurface(state_path=tmp_path / "missing.yaml")
    with pytest.raises(FileNotFoundError, match="Missing canonical Vercel state"):
        surface.load_canonical()


def test_no_drift_returns_empty_list(tmp_path: Path) -> None:
    projects = [{"name": "studio", "envs": [{"key": "FOO", "target": "production"}]}]
    surface = _surface(tmp_path, projects)
    canonical = surface.load_canonical()
    assert surface.compute_drift(canonical, {"projects": projects}) == []


def test_live_added_env_is_semantic(tmp_path: Path) -> None:
    surface = _surface(tmp_path, [{"name": "studio", "envs": []}])
    drift = surface.compute_drift(
        surface.load_canonical(),
        {"projects": [{"name": "studio", "envs": [{"key": "NEW", "target": "production"}]}]},
    )
    assert len(drift) == 1
    assert drift[0].kind == "added"
    assert surface.classify(drift[0]) == "semantic"


def test_live_removed_env_is_semantic(tmp_path: Path) -> None:
    surface = _surface(
        tmp_path,
        [{"name": "studio", "envs": [{"key": "OLD", "target": "production"}]}],
    )
    drift = surface.compute_drift(
        surface.load_canonical(), {"projects": [{"name": "studio", "envs": []}]}
    )
    assert len(drift) == 1
    assert drift[0].kind == "removed"
    assert surface.classify(drift[0]) == "semantic"


def test_non_cosmetic_value_change_is_semantic(tmp_path: Path) -> None:
    surface = _surface(
        tmp_path,
        [{"name": "studio", "envs": [{"key": "TOKEN", "target": "production", "value": "abc"}]}],
    )
    drift = surface.compute_drift(
        surface.load_canonical(),
        {
            "projects": [
                {
                    "name": "studio",
                    "envs": [{"key": "TOKEN", "target": "production", "value": "xyz"}],
                }
            ]
        },
    )
    assert len(drift) == 1
    assert drift[0].kind == "changed"
    assert surface.classify(drift[0]) == "semantic"


def test_cosmetic_value_change_is_ui_only(tmp_path: Path) -> None:
    surface = _surface(
        tmp_path,
        [
            {
                "name": "studio",
                "envs": [{"key": "NOTES", "target": "production", "value": "alpha\n# old"}],
            }
        ],
    )
    drift = surface.compute_drift(
        surface.load_canonical(),
        {
            "projects": [
                {
                    "name": "studio",
                    "envs": [{"key": "NOTES", "target": "production", "value": "alpha\n# new"}],
                }
            ]
        },
    )
    assert len(drift) == 1
    assert surface.classify(drift[0]) == "ui-only"


def test_run_drift_check_writes_run_and_alerts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = tmp_path / "data" / "drift_check_runs.json"
    alerts = tmp_path / "data" / "drift_alerts.json"
    monkeypatch.setenv("BRAIN_IAC_DRIFT_RUNS_JSON", str(runs))
    monkeypatch.setenv("BRAIN_IAC_DRIFT_ALERTS_JSON", str(alerts))
    surface = _surface(tmp_path, [{"name": "studio", "envs": []}])
    monkeypatch.setattr(
        surface,
        "fetch_live",
        lambda: {
            "projects": [{"name": "studio", "envs": [{"key": "NEW", "target": "production"}]}]
        },
    )

    summary = iac_drift.run_drift_check([surface])

    assert summary["vercel"]["drift_count"] == 1
    assert summary["vercel"]["semantic_drift_count"] == 1
    assert json.loads(runs.read_text(encoding="utf-8"))[0]["summary"]["vercel"]["drift_count"] == 1
    alert_rows = json.loads(alerts.read_text(encoding="utf-8"))
    assert alert_rows[0]["status"] == "open"
    assert alert_rows[0]["channel"] == "#brain-status"


def test_fetch_live_uses_vercel_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class Result:
        stdout = json.dumps([{"key": "A", "target": "production"}])

    def fake_run(args: list[str], **kwargs):
        calls.append(args)
        assert kwargs["check"] is True
        assert kwargs["timeout"] == 30
        return Result()

    monkeypatch.setattr(iac_drift.subprocess, "run", fake_run)
    live = iac_drift.VercelEnvSurface().fetch_live()
    assert calls == [["vercel", "env", "ls", "--json"]]
    assert live["projects"][0]["envs"][0]["key"] == "A"


@pytest.mark.asyncio
async def test_scheduler_skips_when_brain_paused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flag = tmp_path / "brain_paused.flag"
    flag.write_text("maintenance\n", encoding="utf-8")
    monkeypatch.setenv("BRAIN_PAUSED_FLAG_PATH", str(flag))
    runner = AsyncMock()
    monkeypatch.setattr(iac_drift_scheduler, "run_with_scheduler_record", runner)

    await iac_drift_scheduler.run_iac_drift_job()

    runner.assert_not_awaited()


def test_follow_up_surfaces_are_explicit_stubs() -> None:
    with pytest.raises(NotImplementedError, match="WS-42 follow-up"):
        iac_drift.CloudflareDNSSurface().fetch_live()
