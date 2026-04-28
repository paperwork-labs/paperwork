"""Resilience tests — branch collision races + Redis scheduler lock."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.models.workstream_board import WorkstreamProgressSnapshot
from app.schemas.workstream import Workstream, WorkstreamsFile
from app.services import workstream_progress_writeback as wb


def _ws(**kwargs: Any) -> Workstream:
    defaults: dict[str, Any] = {
        "id": "WS-01-prog",
        "title": "Progress writeback test title",
        "track": "Z",
        "priority": 0,
        "status": "in_progress",
        "percent_done": 50,
        "owner": "brain",
        "brief_tag": "track:writeback-test",
        "blockers": [],
        "last_pr": None,
        "last_activity": "2026-04-27T12:00:00Z",
        "last_dispatched_at": None,
        "notes": "",
        "estimated_pr_count": 2,
        "github_actions_workflow": None,
        "related_plan": None,
    }
    defaults.update(kwargs)
    return Workstream(**defaults)


def _file(*streams: Workstream) -> WorkstreamsFile:
    return WorkstreamsFile(
        version=1,
        updated="2026-04-27T12:00:00Z",
        workstreams=list(streams),
    )


def _snap(wid: str, *, pct: int, status: str) -> WorkstreamProgressSnapshot:
    from datetime import UTC, datetime

    return WorkstreamProgressSnapshot(
        workstream_id=wid,
        recorded_at=datetime(2026, 4, 27, 14, 0, 0, tzinfo=UTC),
        percent_done=pct,
        computed_status=status,
        merged_pr_count=1,
        open_pr_count=0,
        denominator=2,
        extra_json={"brief_tag": "track:writeback-test"},
    )


@pytest.mark.asyncio
async def test_skipped_when_redis_lock_held(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", True)
    monkeypatch.setattr(wb, "try_acquire_scheduler_lock", AsyncMock(return_value=False))
    release = AsyncMock()
    monkeypatch.setattr(wb, "release_scheduler_lock", release)

    async def _boom(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("should not load maps when lock not acquired")

    monkeypatch.setattr(wb, "_load_snapshot_dispatch_maps", _boom)

    res = await wb.run_workstream_progress_writeback()
    assert res.skipped is True
    assert res.skip_reason == "scheduler_lock_held"
    release.assert_not_called()


@pytest.mark.asyncio
async def test_recovers_when_create_git_ref_fails_but_branch_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """422 duplicate ref: adopt existing branch SHA and open PR."""
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "tok")
    monkeypatch.setattr(settings, "GITHUB_REPO", "paperwork-labs/paperwork")
    monkeypatch.setattr(wb, "try_acquire_scheduler_lock", AsyncMock(return_value=True))
    monkeypatch.setattr(wb, "release_scheduler_lock", AsyncMock())

    w = _ws(percent_done=50, status="in_progress")
    monkeypatch.setattr(wb, "load_workstreams_file", lambda **_: _file(w))

    async def _maps() -> tuple[dict[str, Any], dict[str, Any]]:
        return {"WS-01-prog": _snap("WS-01-prog", pct=90, status="in_progress")}, {}

    monkeypatch.setattr(wb, "_load_snapshot_dispatch_maps", _maps)

    monkeypatch.setattr(wb.gh, "list_repo_pull_requests", AsyncMock(return_value=[]))
    monkeypatch.setattr(wb.gh, "get_git_ref_sha", AsyncMock(return_value="a" * 40))
    monkeypatch.setattr(wb.gh, "create_git_ref", AsyncMock(return_value=False))
    monkeypatch.setattr(wb.gh, "get_branch_sha", AsyncMock(return_value="b" * 40))
    monkeypatch.setattr(wb.gh, "commit_files_to_branch", AsyncMock(return_value="c" * 40))
    create_pr = AsyncMock(
        return_value={
            "number": 9003,
            "html_url": "https://github.com/paperwork-labs/paperwork/pull/9003",
        }
    )
    monkeypatch.setattr(wb.gh, "create_github_pull", create_pr)

    res = await wb.run_workstream_progress_writeback()
    assert res.pr_number == 9003
    assert res.amended_existing_pr is False
    wb.gh.create_git_ref.assert_awaited_once()
    wb.gh.get_branch_sha.assert_awaited_once()
    create_pr.assert_awaited_once()


@pytest.mark.asyncio
async def test_recovers_when_create_git_ref_fails_open_pr_appears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Race: other worker opened PR between create_git_ref failure and amend lookup."""
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "tok")
    monkeypatch.setattr(settings, "GITHUB_REPO", "paperwork-labs/paperwork")
    monkeypatch.setattr(wb, "try_acquire_scheduler_lock", AsyncMock(return_value=True))
    monkeypatch.setattr(wb, "release_scheduler_lock", AsyncMock())

    w = _ws(percent_done=10, status="in_progress")
    monkeypatch.setattr(wb, "load_workstreams_file", lambda **_: _file(w))

    async def _maps() -> tuple[dict[str, Any], dict[str, Any]]:
        return {"WS-01-prog": _snap("WS-01-prog", pct=20, status="in_progress")}, {}

    monkeypatch.setattr(wb, "_load_snapshot_dispatch_maps", _maps)

    open_pr = {"number": 801, "head": {"ref": "bot/workstream-progress-raced"}}
    pull_batches: list[list[dict[str, Any]]] = [[], [open_pr]]

    async def list_pulls(**_: Any) -> list[dict[str, Any]]:
        return pull_batches.pop(0)

    monkeypatch.setattr(wb.gh, "list_repo_pull_requests", list_pulls)
    monkeypatch.setattr(wb.gh, "get_git_ref_sha", AsyncMock(return_value="a" * 40))
    monkeypatch.setattr(wb.gh, "create_git_ref", AsyncMock(return_value=False))
    monkeypatch.setattr(wb.gh, "get_branch_sha", AsyncMock(return_value=None))
    monkeypatch.setattr(wb.gh, "commit_files_to_branch", AsyncMock(return_value="d" * 40))
    monkeypatch.setattr(wb.gh, "create_github_pull", AsyncMock())

    res = await wb.run_workstream_progress_writeback()
    assert res.amended_existing_pr is True
    assert res.pr_number == 801


@pytest.mark.asyncio
async def test_raises_after_two_attempts_without_adoption(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "tok")
    monkeypatch.setattr(settings, "GITHUB_REPO", "paperwork-labs/paperwork")
    monkeypatch.setattr(wb, "try_acquire_scheduler_lock", AsyncMock(return_value=True))
    monkeypatch.setattr(wb, "release_scheduler_lock", AsyncMock())

    w = _ws(percent_done=50, status="in_progress")
    monkeypatch.setattr(wb, "load_workstreams_file", lambda **_: _file(w))

    async def _maps() -> tuple[dict[str, Any], dict[str, Any]]:
        return {"WS-01-prog": _snap("WS-01-prog", pct=90, status="in_progress")}, {}

    monkeypatch.setattr(wb, "_load_snapshot_dispatch_maps", _maps)

    monkeypatch.setattr(wb.gh, "list_repo_pull_requests", AsyncMock(return_value=[]))
    monkeypatch.setattr(wb.gh, "get_git_ref_sha", AsyncMock(return_value="a" * 40))
    monkeypatch.setattr(wb.gh, "create_git_ref", AsyncMock(return_value=False))
    monkeypatch.setattr(wb.gh, "get_branch_sha", AsyncMock(return_value=None))

    with pytest.raises(RuntimeError, match="could not create branch"):
        await wb.run_workstream_progress_writeback()

    assert wb.gh.create_git_ref.await_count == 2
