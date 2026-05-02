"""Workstream dispatcher selection + run path (parity with Studio ``schema.ts``)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import pytest

from app.config import settings
from app.schedulers import workstream_dispatcher as wd
from app.schemas.workstream import (
    DISPATCH_COOLDOWN_MS,
    Workstream,
    WorkstreamsFile,
    dispatchable_workstreams,
)


def _ws(
    *,
    wid: str,
    priority: int,
    owner: str = "brain",
    status: str = "pending",
    percent_done: int = 0,
    blockers: list[str] | None = None,
    last_dispatched_at: str | None = None,
    brief_tag: str = "track:test-ws",
) -> Workstream:
    return Workstream(
        id=wid,
        title="Test title here",
        track="Z",
        priority=priority,
        status=status,  # type: ignore[arg-type]
        percent_done=percent_done,
        owner=owner,  # type: ignore[arg-type]
        brief_tag=brief_tag,
        blockers=blockers or [],
        last_pr=None,
        last_activity="2026-04-27T12:00:00Z",
        last_dispatched_at=last_dispatched_at,
        notes="",
        estimated_pr_count=1,
        github_actions_workflow="agent-sprint-runner",
        related_plan=None,
    )


def _file(*streams: Workstream) -> WorkstreamsFile:
    return WorkstreamsFile(
        version=1,
        updated="2026-04-27T12:00:00Z",
        workstreams=list(streams),
    )


def test_dispatchable_rejects_non_brain_owner() -> None:
    f = _file(
        _ws(wid="WS-10-a", priority=0, owner="founder"),
        _ws(wid="WS-11-b", priority=1),
    )
    out = dispatchable_workstreams(f, n=5)
    assert [w.id for w in out] == ["WS-11-b"]


def test_dispatchable_rejects_blocked_and_non_dispatchable_status() -> None:
    f = _file(
        _ws(wid="WS-20-a", priority=0, status="blocked", blockers=["WS-99-needs-x"]),
        _ws(wid="WS-20-b", priority=1, status="completed", percent_done=100),
        _ws(wid="WS-20-c", priority=2),
    )
    out = dispatchable_workstreams(f, n=5)
    assert [w.id for w in out] == ["WS-20-c"]


def test_dispatchable_respects_blockers_empty() -> None:
    f = _file(
        _ws(wid="WS-30-a", priority=0, blockers=["wait for WS-01"]),
        _ws(wid="WS-30-b", priority=1),
    )
    out = dispatchable_workstreams(f, n=5)
    assert [w.id for w in out] == ["WS-30-b"]


def test_dispatchable_sorts_by_priority_and_caps_n() -> None:
    f = _file(
        _ws(wid="WS-40-a", priority=2),
        _ws(wid="WS-40-b", priority=0),
        _ws(wid="WS-40-c", priority=1),
        _ws(wid="WS-40-d", priority=3),
    )
    out = dispatchable_workstreams(f, n=3)
    assert [w.id for w in out] == ["WS-40-b", "WS-40-c", "WS-40-a"]


def test_dispatchable_cooldown_boundary_matches_ts_strict_gt() -> None:
    base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
    last_ms = int(base.timestamp() * 1000)
    last_iso = base.strftime("%Y-%m-%dT%H:%M:%SZ")
    f = _file(_ws(wid="WS-50-a", priority=0, last_dispatched_at=last_iso))
    # Exactly cooldown: not eligible in TS (strict >).
    assert dispatchable_workstreams(f, n=3, now_ms=last_ms + DISPATCH_COOLDOWN_MS) == []
    assert (
        dispatchable_workstreams(f, n=3, now_ms=last_ms + DISPATCH_COOLDOWN_MS + 1)[0].id
        == "WS-50-a"
    )


def test_dispatchable_null_last_dispatched_eligible() -> None:
    f = _file(_ws(wid="WS-60-a", priority=0, last_dispatched_at=None))
    assert len(dispatchable_workstreams(f, n=3)) == 1


def test_seed_workstreams_json_loads_from_monorepo() -> None:
    """Skipped: workstreams.json was removed in WS-82 — hierarchy lives in Brain DB now."""
    pytest.skip("workstreams.json deleted; hierarchy migrated to Brain DB (WS-82 PR-3a)")


def test_workstreams_file_rejects_duplicate_ids() -> None:
    a = _ws(wid="WS-70-a", priority=0, brief_tag="track:one")
    b = a.model_copy(update={"priority": 1, "brief_tag": "track:two"})
    with pytest.raises(ValueError, match="unique"):
        _file(a, b)


@pytest.mark.asyncio
async def test_run_dispatcher_skips_if_scheduler_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", False)
    res = await wd.run_workstream_dispatcher()
    assert res.skipped is True
    assert res.dispatched_workstream_ids == []


class _FakeDispatchDb:
    """Minimal async session stand-in for dispatch log persistence tests."""

    def __init__(self) -> None:
        self._next_id = 1

    def add(self, row: object) -> None:
        _ = row

    async def commit(self) -> None:
        return None

    async def refresh(self, row: object) -> None:
        r: Any = row
        r.id = self._next_id
        self._next_id += 1


@pytest.mark.asyncio
async def test_run_dispatcher_dispatches_and_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", True)
    f = _file(
        _ws(wid="WS-80-a", priority=0, brief_tag="track:dispatch-a"),
        _ws(wid="WS-80-b", priority=1, brief_tag="track:dispatch-b"),
    )
    monkeypatch.setattr(
        "app.schedulers.workstream_dispatcher.load_workstreams_file",
        lambda **_: f,
    )
    dispatched: list[str] = []

    async def _fake_dispatch(_workflow, **kwargs):  # type: ignore[no-untyped-def]
        dispatched.append(kwargs["brief_tag"])
        return True

    monkeypatch.setattr(
        "app.schedulers.workstream_dispatcher.wh.workflow_dispatch",
        _fake_dispatch,
    )

    fake = _FakeDispatchDb()

    @asynccontextmanager
    async def _sess():
        yield fake

    monkeypatch.setattr(
        "app.schedulers.workstream_dispatcher.async_session_factory",
        lambda: _sess(),
    )

    res = await wd.run_workstream_dispatcher(
        datetime(2030, 1, 1, tzinfo=UTC),
    )
    assert res.skipped is False
    assert res.dispatched_workstream_ids == ["WS-80-a", "WS-80-b"]
    assert len(res.dispatch_log_ids) == 2
    assert "track:dispatch-a" in dispatched


@pytest.mark.asyncio
async def test_run_dispatcher_skips_failed_github_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", True)
    f = _file(_ws(wid="WS-90-a", priority=0))
    monkeypatch.setattr(
        "app.schedulers.workstream_dispatcher.load_workstreams_file",
        lambda **_: f,
    )

    async def _fail_dispatch(*_a: object, **_k: object) -> bool:
        return False

    monkeypatch.setattr(
        "app.schedulers.workstream_dispatcher.wh.workflow_dispatch",
        _fail_dispatch,
    )

    fake = _FakeDispatchDb()

    @asynccontextmanager
    async def _sess():
        yield fake

    monkeypatch.setattr(
        "app.schedulers.workstream_dispatcher.async_session_factory",
        lambda: _sess(),
    )

    res = await wd.run_workstream_dispatcher()
    assert res.dispatched_workstream_ids == []
    assert res.dispatch_log_ids == []
