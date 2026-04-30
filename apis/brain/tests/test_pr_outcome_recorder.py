"""Tests for the Brain PR outcome recorder scheduler."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.config import settings
from app.schedulers import pr_outcome_recorder as rec


@pytest.mark.asyncio
async def test_pr_outcome_recorder_records_new_merged_pr(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outcomes_path = tmp_path / "pr_outcomes.json"
    outcomes_path.write_text('{"schema":"pr_outcomes/v1","outcomes":[]}\n', encoding="utf-8")
    state_path = tmp_path / "pr_outcome_recorder_state.json"
    dispatch_path = tmp_path / "agent_dispatch_log.json"
    dispatch_path.write_text(
        json.dumps(
            {
                "dispatches": [
                    {
                        "dispatch_id": "dispatch-1",
                        "agent_model": "composer-2-fast",
                        "subagent_type": "generalPurpose",
                        "workstream_id": "WS-82",
                        "workstream_type": "ops",
                        "pr_number": 123,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    now = datetime(2026, 4, 30, 12, 0, tzinfo=UTC)
    calls: list[dict[str, Any]] = []

    async def fake_fetch(_client: object, since: datetime, *, limit: int = 100):
        calls.append({"since": since, "limit": limit})
        return [
            rec.MergedPullRequest(
                number=123,
                merged_at="2026-04-30T11:00:00Z",
                branch="ws82/wave0/pr-a3-pr-outcomes-wiring",
                head_sha="abc123",
                author="paperwork-agent",
            )
        ]

    async def fake_ci(_client: object, sha: str) -> str:
        assert sha == "abc123"
        return "success"

    monkeypatch.setenv("BRAIN_PR_OUTCOMES_JSON", str(outcomes_path))
    monkeypatch.setenv("BRAIN_PR_OUTCOME_RECORDER_STATE_JSON", str(state_path))
    monkeypatch.setenv("BRAIN_AGENT_DISPATCH_LOG_JSON", str(dispatch_path))
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "gh-test-token")
    monkeypatch.setattr(settings, "GITHUB_REPO", "paperwork-labs/paperwork")
    monkeypatch.setattr(rec, "_now_utc", lambda: now)
    monkeypatch.setattr(rec, "_fetch_merged_prs_since", fake_fetch)
    monkeypatch.setattr(rec, "_ci_status_for_sha", fake_ci)

    report = await rec.run_once()

    assert report == {"ok": True, "recorded": 1, "h24_updated": 0}
    assert calls[0]["since"] == now - timedelta(hours=2)
    data = json.loads(outcomes_path.read_text(encoding="utf-8"))
    row = data["outcomes"][0]
    assert row["pr_number"] == 123
    assert row["merged_by_agent"] == "brain-dispatch-1"
    assert row["agent_model"] == "composer-2-fast"
    assert row["subagent_type"] == "generalPurpose"
    assert row["branch"] == "ws82/wave0/pr-a3-pr-outcomes-wiring"
    assert row["ci_status_at_merge"] == "success"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["last_checked_at"] == "2026-04-30T12:00:00Z"


@pytest.mark.asyncio
async def test_pr_outcome_recorder_missing_token_logs_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    state_path = tmp_path / "pr_outcome_recorder_state.json"
    monkeypatch.setenv("BRAIN_PR_OUTCOME_RECORDER_STATE_JSON", str(state_path))
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "")

    report = await rec.run_once()

    assert report["ok"] is False
    assert "GITHUB_TOKEN not configured" in str(report["error"])
    assert "GITHUB_TOKEN not configured" in caplog.text
    assert not state_path.exists()


@pytest.mark.asyncio
async def test_pr_outcome_recorder_updates_due_h24(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outcomes_path = tmp_path / "pr_outcomes.json"
    outcomes_path.write_text(
        json.dumps(
            {
                "schema": "pr_outcomes/v1",
                "outcomes": [
                    {
                        "pr_number": 321,
                        "merged_at": "2026-04-29T11:00:00Z",
                        "merged_by_agent": "brain-dispatch",
                        "agent_model": "composer-2-fast",
                        "subagent_type": "generalPurpose",
                        "branch": "ws82/example",
                        "ci_status_at_merge": "success",
                        "workstream_ids": ["WS-82"],
                        "workstream_types": ["ops"],
                        "outcomes": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    now = datetime(2026, 4, 30, 12, 0, tzinfo=UTC)

    async def fake_fetch(_client: object, _since: datetime, *, limit: int = 100):
        return []

    async def fake_get_json(_client: object, path: str, *, params: dict[str, Any] | None = None):
        assert path == "/repos/paperwork-labs/paperwork/pulls/321"
        _ = params
        return {
            "number": 321,
            "merged_at": "2026-04-29T11:00:00Z",
            "head": {"ref": "ws82/example", "sha": "def456"},
            "user": {"login": "paperwork-agent"},
        }

    async def fake_ci(_client: object, sha: str) -> str:
        assert sha == "def456"
        return "success"

    async def fake_deploy(_client: object, sha: str) -> bool:
        assert sha == "def456"
        return True

    async def fake_reverted(_client: object, pr_number: int) -> bool:
        assert pr_number == 321
        return False

    monkeypatch.setenv("BRAIN_PR_OUTCOMES_JSON", str(outcomes_path))
    monkeypatch.setenv("BRAIN_PR_OUTCOME_RECORDER_STATE_JSON", str(tmp_path / "state.json"))
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "gh-test-token")
    monkeypatch.setattr(settings, "GITHUB_REPO", "paperwork-labs/paperwork")
    monkeypatch.setattr(rec, "_now_utc", lambda: now)
    monkeypatch.setattr(rec, "_fetch_merged_prs_since", fake_fetch)
    monkeypatch.setattr(rec, "_get_json", fake_get_json)
    monkeypatch.setattr(rec, "_ci_status_for_sha", fake_ci)
    monkeypatch.setattr(rec, "_deploy_success_for_sha", fake_deploy)
    monkeypatch.setattr(rec, "_was_reverted", fake_reverted)

    report = await rec.run_once()

    assert report == {"ok": True, "recorded": 0, "h24_updated": 1}
    data = json.loads(outcomes_path.read_text(encoding="utf-8"))
    h24 = data["outcomes"][0]["outcomes"]["h24"]
    assert h24 == {"ci_pass": True, "deploy_success": True, "reverted": False}
