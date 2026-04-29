from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.schedulers import auto_revert as auto_revert_scheduler
from app.services import auto_revert


def _write_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcomes: list[dict]) -> None:
    outcomes_path = tmp_path / "pr_outcomes.json"
    incidents_path = tmp_path / "incidents.json"
    outcomes_path.write_text(
        json.dumps(
            {
                "schema": "pr_outcomes/v1",
                "description": "test outcomes",
                "outcomes": outcomes,
            }
        ),
        encoding="utf-8",
    )
    incidents_path.write_text(
        json.dumps(
            {
                "schema": "incidents/v1",
                "description": "test incidents",
                "incidents": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_PR_OUTCOMES_JSON", str(outcomes_path))
    monkeypatch.setenv("BRAIN_INCIDENTS_JSON", str(incidents_path))


def _outcome(
    pr_number: int,
    merged_at: datetime,
    merged_by_agent: str = "brain-code",
) -> dict:
    return {
        "pr_number": pr_number,
        "merged_at": merged_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "merged_by_agent": merged_by_agent,
        "agent_model": "composer-2-fast",
        "subagent_type": "cheap-agent",
        "workstream_ids": ["WS-46"],
        "workstream_types": ["ops"],
        "outcomes": {},
    }


def _completed(stdout: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["gh"], returncode=0, stdout=json.dumps(stdout), stderr=""
    )


def test_recent_brain_merges_no_recent_merges_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = datetime.now(UTC) - timedelta(hours=2)
    _write_state(tmp_path, monkeypatch, [_outcome(1, old)])
    mock_run = Mock()
    monkeypatch.setattr(auto_revert.subprocess, "run", mock_run)

    assert auto_revert.recent_brain_merges(window_minutes=30) == []
    assert auto_revert.run_auto_revert_check() == []
    mock_run.assert_not_called()


def test_recent_brain_merges_filters_to_brain_agents_within_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recent = datetime.now(UTC) - timedelta(minutes=5)
    _write_state(
        tmp_path,
        monkeypatch,
        [
            _outcome(1, recent, "brain-code"),
            _outcome(2, recent, "human-operator"),
        ],
    )
    monkeypatch.setattr(auto_revert.subprocess, "run", Mock())

    rows = auto_revert.recent_brain_merges(window_minutes=30)
    assert [r["pr_number"] for r in rows] == [1]


def test_malformed_pr_outcomes_json_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outcomes_path = tmp_path / "pr_outcomes.json"
    incidents_path = tmp_path / "incidents.json"
    outcomes_path.write_text("{not json", encoding="utf-8")
    incidents_path.write_text('{"schema":"incidents/v1","incidents":[]}', encoding="utf-8")
    monkeypatch.setenv("BRAIN_PR_OUTCOMES_JSON", str(outcomes_path))
    monkeypatch.setenv("BRAIN_INCIDENTS_JSON", str(incidents_path))
    monkeypatch.setattr(auto_revert.subprocess, "run", Mock())

    with pytest.raises(json.JSONDecodeError):
        auto_revert.recent_brain_merges()


def test_is_main_ci_failed_after_green_ci_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    merged_at = datetime.now(UTC) - timedelta(minutes=10)
    run_started = datetime.now(UTC) - timedelta(minutes=5)
    _write_state(tmp_path, monkeypatch, [])
    mock_run = Mock(
        return_value=_completed(
            [
                {
                    "status": "completed",
                    "conclusion": "success",
                    "headSha": "abc",
                    "startedAt": run_started.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "url": "https://github.com/org/repo/actions/runs/1",
                }
            ]
        )
    )
    monkeypatch.setattr(auto_revert.subprocess, "run", mock_run)

    assert auto_revert.is_main_ci_failed_after(merged_at) == (False, None)


def test_is_main_ci_failed_after_red_ci_returns_run_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    merged_at = datetime.now(UTC) - timedelta(minutes=10)
    run_started = datetime.now(UTC) - timedelta(minutes=5)
    _write_state(tmp_path, monkeypatch, [])
    url = "https://github.com/org/repo/actions/runs/2"
    mock_run = Mock(
        return_value=_completed(
            [
                {
                    "status": "completed",
                    "conclusion": "failure",
                    "headSha": "abc",
                    "startedAt": run_started.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "url": url,
                }
            ]
        )
    )
    monkeypatch.setattr(auto_revert.subprocess, "run", mock_run)

    assert auto_revert.is_main_ci_failed_after(merged_at) == (True, url)


def test_run_auto_revert_check_recent_merge_green_ci_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    merged_at = datetime.now(UTC) - timedelta(minutes=10)
    _write_state(tmp_path, monkeypatch, [_outcome(44, merged_at)])
    mock_run = Mock(return_value=_completed([]))
    monkeypatch.setattr(auto_revert.subprocess, "run", mock_run)

    assert auto_revert.run_auto_revert_check() == []
    assert mock_run.call_count == 1
    assert json.loads((tmp_path / "incidents.json").read_text(encoding="utf-8"))["incidents"] == []


def test_run_auto_revert_check_red_ci_opens_revert_and_records_incident(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    merged_at = datetime.now(UTC) - timedelta(minutes=10)
    run_started = datetime.now(UTC) - timedelta(minutes=5)
    run_url = "https://github.com/org/repo/actions/runs/3"
    _write_state(tmp_path, monkeypatch, [_outcome(46, merged_at)])
    monkeypatch.setattr(
        auto_revert,
        "is_main_ci_failed_after",
        Mock(return_value=(True, run_url)),
    )
    open_revert = Mock(return_value=146)
    auto_merge = Mock()
    monkeypatch.setattr(auto_revert, "open_revert_pr", open_revert)
    monkeypatch.setattr(auto_revert, "auto_merge_revert", auto_merge)
    monkeypatch.setattr(auto_revert.subprocess, "run", Mock())

    incidents = auto_revert.run_auto_revert_check()

    assert len(incidents) == 1
    open_revert.assert_called_once_with(46, run_url)
    auto_merge.assert_called_once_with(146)
    data = json.loads((tmp_path / "incidents.json").read_text(encoding="utf-8"))
    assert data["incidents"][0]["kind"] == "brain-merge-revert"
    assert data["incidents"][0]["pr_number_reverted"] == 46
    assert data["incidents"][0]["revert_pr_number"] == 146
    assert data["incidents"][0]["ci_failure_run_url"] == run_url
    assert data["incidents"][0]["closed_at"] is not None
    assert run_started > merged_at


def test_open_revert_pr_uses_gh_pr_revert_when_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_state(tmp_path, monkeypatch, [])
    mock_run = Mock(
        side_effect=[
            subprocess.CompletedProcess(
                args=["gh", "pr", "revert", "--help"], returncode=0, stdout="", stderr=""
            ),
            subprocess.CompletedProcess(
                args=["gh", "pr", "revert", "46"],
                returncode=0,
                stdout="https://github.com/paperwork-labs/paperwork/pull/147\n",
                stderr="",
            ),
        ]
    )
    monkeypatch.setattr(auto_revert.subprocess, "run", mock_run)

    assert auto_revert.open_revert_pr(46, "https://example.test/run") == 147
    assert mock_run.call_args_list[1].args[0][0:4] == ["gh", "pr", "revert", "46"]


def test_open_revert_pr_falls_back_to_git_revert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_state(tmp_path, monkeypatch, [])

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if command == ["gh", "pr", "revert", "--help"]:
            raise subprocess.CalledProcessError(1, command)
        if command[:4] == ["gh", "pr", "view", "46"]:
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout=json.dumps({"mergeCommit": {"oid": "abc123"}}),
                stderr="",
            )
        if command[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout="https://github.com/paperwork-labs/paperwork/pull/148\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    mock_run = Mock(side_effect=fake_run)
    monkeypatch.setattr(auto_revert.subprocess, "run", mock_run)

    assert auto_revert.open_revert_pr(46, "https://example.test/run") == 148
    commands = [call.args[0] for call in mock_run.call_args_list]
    assert any(cmd[:3] == ["git", "revert", "--no-edit"] for cmd in commands)
    assert any(cmd[:3] == ["git", "push", "-u"] for cmd in commands)


@pytest.mark.asyncio
async def test_scheduler_skips_when_brain_paused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_state(tmp_path, monkeypatch, [])
    pause_flag = tmp_path / "brain-paused.flag"
    pause_flag.write_text("paused for test\n", encoding="utf-8")
    monkeypatch.setenv("BRAIN_PAUSED_FLAG_PATH", str(pause_flag))
    run_check = Mock(side_effect=AssertionError("should not run while paused"))
    monkeypatch.setattr(auto_revert_scheduler, "run_auto_revert_check", run_check)
    monkeypatch.setattr(auto_revert.subprocess, "run", Mock())

    assert await auto_revert_scheduler.run_auto_revert_job() is None
    run_check.assert_not_called()
