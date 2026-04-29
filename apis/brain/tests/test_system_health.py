"""Tests for system_health_snapshot (WS-43)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import system_health


def _minimal_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    flag = tmp_path / "brain.flag"
    flag.write_text("", encoding="utf-8")
    monkeypatch.setenv("BRAIN_PAUSED_FLAG_PATH", str(flag))


def test_missing_optional_files_return_null_and_ints_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _minimal_repo(tmp_path, monkeypatch)
    (tmp_path / "apis" / "brain" / "data").mkdir(parents=True)
    snap = system_health.system_health_snapshot()
    assert snap["writeback_last_run"] is None
    assert snap["last_pr_opened"] is None
    assert snap["last_drift_check"] is None
    assert snap["scheduler_skew_seconds"] is None
    assert snap["merge_queue_depth"] == 0
    assert snap["pending_workstreams"] == 0
    assert snap["procedural_rules_count"] == 0
    assert snap["brain_paused"] is False
    assert snap["brain_paused_reason"] is None


def test_writeback_last_run_from_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_repo(tmp_path, monkeypatch)
    d = tmp_path / "apis" / "brain" / "data"
    d.mkdir(parents=True)
    (d / "writeback_runs.json").write_text(
        json.dumps(
            {
                "runs": [
                    {"finished_at": "2026-04-28T10:00:00Z"},
                    {"finished_at": "2026-04-28T12:00:00Z"},
                ]
            }
        ),
        encoding="utf-8",
    )
    snap = system_health.system_health_snapshot()
    assert snap["writeback_last_run"] == "2026-04-28T12:00:00Z"


def test_last_pr_opened_from_last_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_repo(tmp_path, monkeypatch)
    d = tmp_path / "apis" / "brain" / "data"
    d.mkdir(parents=True)
    (d / "pr_opens.json").write_text(
        json.dumps(
            {
                "last": {
                    "pr_number": 99,
                    "branch": "feat/ws-43",
                    "opened_at": "2026-04-28T15:30:00+00:00",
                }
            }
        ),
        encoding="utf-8",
    )
    snap = system_health.system_health_snapshot()
    assert snap["last_pr_opened"] == {
        "pr_number": 99,
        "branch": "feat/ws-43",
        "opened_at": "2026-04-28T15:30:00Z",
    }


def test_last_drift_check_top_level(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_repo(tmp_path, monkeypatch)
    d = tmp_path / "apis" / "brain" / "data"
    d.mkdir(parents=True)
    (d / "drift_check_runs.json").write_text(
        json.dumps({"last_drift_check": "2026-04-27T08:00:00Z"}),
        encoding="utf-8",
    )
    snap = system_health.system_health_snapshot()
    assert snap["last_drift_check"] == "2026-04-27T08:00:00Z"


def test_merge_queue_depth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_repo(tmp_path, monkeypatch)
    d = tmp_path / "apis" / "brain" / "data"
    d.mkdir(parents=True)
    (d / "merge_queue.json").write_text(
        json.dumps({"queue": [{"pr": 1}, {"pr": 2}, {}]}),
        encoding="utf-8",
    )
    snap = system_health.system_health_snapshot()
    assert snap["merge_queue_depth"] == 3


def test_pending_workstreams_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_repo(tmp_path, monkeypatch)
    (tmp_path / "apis" / "brain" / "data").mkdir(parents=True)
    ws_dir = tmp_path / "apps" / "studio" / "src" / "data"
    ws_dir.mkdir(parents=True)
    (ws_dir / "workstreams.json").write_text(
        json.dumps(
            {
                "workstreams": [
                    {"id": "a", "status": "pending"},
                    {"id": "b", "status": "in_progress"},
                    {"id": "c", "status": "pending"},
                ]
            }
        ),
        encoding="utf-8",
    )
    snap = system_health.system_health_snapshot()
    assert snap["pending_workstreams"] == 2


def test_malformed_json_does_not_raise(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_repo(tmp_path, monkeypatch)
    d = tmp_path / "apis" / "brain" / "data"
    d.mkdir(parents=True)
    (d / "writeback_runs.json").write_text("not-json", encoding="utf-8")
    (d / "merge_queue.json").write_text("{", encoding="utf-8")
    snap = system_health.system_health_snapshot()
    assert snap["writeback_last_run"] is None
    assert snap["merge_queue_depth"] == 0


def test_procedural_rules_count_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_repo(tmp_path, monkeypatch)
    d = tmp_path / "apis" / "brain" / "data"
    d.mkdir(parents=True)
    (d / "procedural_memory.yaml").write_text(
        "version: 1\nrules:\n  - id: a\n  - id: b\n",
        encoding="utf-8",
    )
    snap = system_health.system_health_snapshot()
    assert snap["procedural_rules_count"] == 2


def test_snapshot_is_json_serializable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_repo(tmp_path, monkeypatch)
    d = tmp_path / "apis" / "brain" / "data"
    d.mkdir(parents=True)
    (d / "pr_opens.json").write_text(
        json.dumps(
            {
                "last": {
                    "pr_number": 1,
                    "branch": "main",
                    "opened_at": "2026-04-28T00:00:00Z",
                }
            }
        ),
        encoding="utf-8",
    )
    snap = system_health.system_health_snapshot()
    json.dumps(snap)
