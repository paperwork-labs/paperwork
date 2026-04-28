"""Workstream JSON writeback — Postgres snapshots → ``workstreams.json`` PR."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.models.workstream_board import WorkstreamDispatchLog, WorkstreamProgressSnapshot
from app.schemas.workstream import Workstream, WorkstreamsFile
from app.services import workstream_progress_writeback as wb

_SnapDisp = tuple[dict[str, WorkstreamProgressSnapshot], dict[str, WorkstreamDispatchLog]]


def _ws(
    *,
    wid: str = "WS-01-prog",
    status: str = "in_progress",
    percent_done: int = 50,
    last_pr: int | None = None,
) -> Workstream:
    return Workstream(
        id=wid,
        title="Progress writeback test title",
        track="Z",
        priority=0,
        status=status,  # type: ignore[arg-type]
        percent_done=percent_done,
        owner="brain",
        brief_tag="track:writeback-test",
        blockers=[],
        last_pr=last_pr,
        last_activity="2026-04-27T12:00:00Z",
        last_dispatched_at=None,
        notes="",
        estimated_pr_count=2,
        github_actions_workflow=None,
        related_plan=None,
        updated_at="2026-04-27T12:00:00Z",
    )


def _file(*streams: Workstream) -> WorkstreamsFile:
    return WorkstreamsFile(
        version=1,
        updated="2026-04-27T12:00:00Z",
        workstreams=list(streams),
    )


def _snap(
    wid: str,
    *,
    pct: int,
    status: str,
    recorded: datetime | None = None,
) -> WorkstreamProgressSnapshot:
    return WorkstreamProgressSnapshot(
        workstream_id=wid,
        recorded_at=recorded or datetime(2026, 4, 27, 14, 0, 0, tzinfo=UTC),
        percent_done=pct,
        computed_status=status,
        merged_pr_count=1,
        open_pr_count=0,
        denominator=2,
        extra_json={"brief_tag": "track:writeback-test"},
    )


@pytest.mark.asyncio
async def test_skipped_when_scheduler_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", False)
    calls: list[str] = []

    async def _no(*_a: Any, **_k: Any) -> None:
        calls.append("maps")

    monkeypatch.setattr(wb, "_load_snapshot_dispatch_maps", _no)
    res = await wb.run_workstream_progress_writeback()
    assert res.skipped is True
    assert calls == []


@pytest.mark.asyncio
async def test_no_pr_when_no_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", True)
    w = _ws(percent_done=50, status="in_progress")
    monkeypatch.setattr(
        wb,
        "load_workstreams_file",
        lambda **_: _file(w),
    )

    async def _maps() -> _SnapDisp:
        return {"WS-01-prog": _snap("WS-01-prog", pct=50, status="in_progress")}, {}

    monkeypatch.setattr(wb, "_load_snapshot_dispatch_maps", _maps)

    async def _boom(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("should not call GitHub")

    monkeypatch.setattr(wb.gh, "list_repo_pull_requests", _boom)
    monkeypatch.setattr(wb.gh, "create_github_pull", _boom)

    res = await wb.run_workstream_progress_writeback()
    assert res.no_drift is True
    assert res.pr_number is None


@pytest.mark.asyncio
async def test_pr_opened_when_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "tok")
    monkeypatch.setattr(settings, "GITHUB_REPO", "paperwork-labs/paperwork")

    w = _ws(percent_done=50, status="in_progress")
    monkeypatch.setattr(
        wb,
        "load_workstreams_file",
        lambda **_: _file(w),
    )

    async def _maps() -> _SnapDisp:
        return {"WS-01-prog": _snap("WS-01-prog", pct=90, status="in_progress")}, {}

    monkeypatch.setattr(wb, "_load_snapshot_dispatch_maps", _maps)

    monkeypatch.setattr(wb.gh, "list_repo_pull_requests", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        wb.gh,
        "get_git_ref_sha",
        AsyncMock(return_value="a" * 40),
    )
    monkeypatch.setattr(wb.gh, "create_git_ref", AsyncMock(return_value=True))
    monkeypatch.setattr(
        wb.gh,
        "commit_files_to_branch",
        AsyncMock(return_value="b" * 40),
    )
    create_pr = AsyncMock(
        return_value={
            "number": 9001,
            "html_url": "https://github.com/paperwork-labs/paperwork/pull/9001",
        }
    )
    monkeypatch.setattr(wb.gh, "create_github_pull", create_pr)

    res = await wb.run_workstream_progress_writeback()
    assert res.no_drift is False
    assert res.pr_number == 9001
    assert res.amended_existing_pr is False
    create_pr.assert_awaited_once()
    call_kw = create_pr.await_args.kwargs
    assert call_kw["title"] == wb._PR_TITLE
    assert call_kw["head"].startswith(wb._HEAD_PREFIX)
    assert "percent_done" in call_kw["body"] or "WS-01-prog" in call_kw["body"]


@pytest.mark.asyncio
async def test_invariants_enforced_completed_coerces_percent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DB snapshot inconsistent (completed + 80%) must not yield invalid JSON."""
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "tok")
    monkeypatch.setattr(settings, "GITHUB_REPO", "paperwork-labs/paperwork")

    w = _ws(percent_done=50, status="in_progress")
    monkeypatch.setattr(
        wb,
        "load_workstreams_file",
        lambda **_: _file(w),
    )

    async def _maps() -> _SnapDisp:
        snap = _snap("WS-01-prog", pct=80, status="completed")
        return {"WS-01-prog": snap}, {}

    monkeypatch.setattr(wb, "_load_snapshot_dispatch_maps", _maps)

    monkeypatch.setattr(wb.gh, "list_repo_pull_requests", AsyncMock(return_value=[]))
    monkeypatch.setattr(wb.gh, "get_git_ref_sha", AsyncMock(return_value="a" * 40))
    monkeypatch.setattr(wb.gh, "create_git_ref", AsyncMock(return_value=True))
    monkeypatch.setattr(wb.gh, "commit_files_to_branch", AsyncMock(return_value="c" * 40))
    create_pr = AsyncMock(
        return_value={
            "number": 9002,
            "html_url": "https://github.com/paperwork-labs/paperwork/pull/9002",
        }
    )
    monkeypatch.setattr(wb.gh, "create_github_pull", create_pr)

    await wb.run_workstream_progress_writeback()
    assert create_pr.await_args is not None
    _branch, _msg, files_map = wb.gh.commit_files_to_branch.await_args.args
    raw = files_map[wb._JSON_PATH]
    data = json.loads(raw)
    row = data["workstreams"][0]
    assert row["status"] == "completed"
    assert row["percent_done"] == 100


@pytest.mark.asyncio
async def test_amends_existing_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "tok")
    monkeypatch.setattr(settings, "GITHUB_REPO", "paperwork-labs/paperwork")

    w = _ws(percent_done=10, status="in_progress")
    monkeypatch.setattr(
        wb,
        "load_workstreams_file",
        lambda **_: _file(w),
    )

    async def _maps() -> _SnapDisp:
        return {"WS-01-prog": _snap("WS-01-prog", pct=20, status="in_progress")}, {}

    monkeypatch.setattr(wb, "_load_snapshot_dispatch_maps", _maps)

    open_pr = {
        "number": 777,
        "head": {"ref": f"{wb._HEAD_PREFIX}1700000000"},
    }
    monkeypatch.setattr(wb.gh, "list_repo_pull_requests", AsyncMock(return_value=[open_pr]))
    monkeypatch.setattr(
        wb.gh,
        "commit_files_to_branch",
        AsyncMock(return_value="d" * 40),
    )
    create_pr = AsyncMock()
    monkeypatch.setattr(wb.gh, "create_github_pull", create_pr)
    create_ref = AsyncMock()
    monkeypatch.setattr(wb.gh, "create_git_ref", create_ref)

    res = await wb.run_workstream_progress_writeback()
    assert res.amended_existing_pr is True
    assert res.pr_number == 777
    create_ref.assert_not_called()
    create_pr.assert_not_called()
    wb.gh.commit_files_to_branch.assert_awaited_once()
    assert wb.gh.commit_files_to_branch.await_args.args[0] == open_pr["head"]["ref"]
