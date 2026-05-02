"""Workstream dispatcher selection + run path (parity with Studio ``schema.ts``)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.epic_hierarchy import Epic
from app.schedulers import workstream_dispatcher as wd
from app.schemas.workstream import (
    DISPATCH_COOLDOWN_MS,
    Workstream,
    WorkstreamsFile,
    dispatchable_workstreams,
)
from app.services.workstreams_loader import load_epics_from_db


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


def test_workstreams_file_rejects_duplicate_ids() -> None:
    a = _ws(wid="WS-70-a", priority=0, brief_tag="track:one")
    b = a.model_copy(update={"priority": 1, "brief_tag": "track:two"})
    with pytest.raises(ValueError, match="unique"):
        _file(a, b)


@pytest.mark.asyncio
async def test_load_epics_from_db_maps_active_and_in_progress(
    db_session: AsyncSession,
) -> None:
    db_session.add_all(
        [
            Epic(
                id="WS-91-a",
                title="First epic title",
                owner_employee_slug="brain",
                status="active",
                priority=10,
                percent_done=0,
                brief_tag="track:epic-a",
            ),
            Epic(
                id="WS-91-b",
                title="Second epic title",
                owner_employee_slug="brain",
                status="in_progress",
                priority=5,
                percent_done=20,
                brief_tag="track:epic-b",
            ),
            Epic(
                id="WS-91-done",
                title="Done epic",
                owner_employee_slug="brain",
                status="completed",
                priority=0,
                percent_done=100,
                brief_tag="track:epic-done",
            ),
        ]
    )
    await db_session.flush()

    file = await load_epics_from_db(db_session)
    ids = [w.id for w in file.workstreams]
    assert "WS-91-done" not in ids
    assert ids == ["WS-91-b", "WS-91-a"]
    by_id = {w.id: w for w in file.workstreams}
    assert by_id["WS-91-a"].status == "pending"
    assert by_id["WS-91-b"].status == "in_progress"
    prios = [w.priority for w in file.workstreams]
    assert len(set(prios)) == len(prios)


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

    async def get(self, *_a: object, **_kw: object) -> None:
        return None


@pytest.mark.asyncio
async def test_run_dispatcher_dispatches_and_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", True)
    f = _file(
        _ws(wid="WS-80-a", priority=0, brief_tag="track:dispatch-a"),
        _ws(wid="WS-80-b", priority=1, brief_tag="track:dispatch-b"),
    )

    async def _fake_load(_session: AsyncSession) -> WorkstreamsFile:
        return f

    monkeypatch.setattr(wd, "load_epics_from_db", _fake_load)
    dispatched: list[str] = []

    async def _fake_dispatch(_workflow, **kwargs):  # type: ignore[no-untyped-def]
        dispatched.append(kwargs["brief_tag"])
        return True

    monkeypatch.setattr(
        "app.schedulers.workstream_dispatcher.wh.workflow_dispatch",
        _fake_dispatch,
    )

    fake = _FakeDispatchDb()

    res = await wd.run_workstream_dispatcher(
        datetime(2030, 1, 1, tzinfo=UTC),
        db=fake,
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

    async def _fake_load(_session: AsyncSession) -> WorkstreamsFile:
        return f

    monkeypatch.setattr(wd, "load_epics_from_db", _fake_load)

    async def _fail_dispatch(*_a: object, **_k: object) -> bool:
        return False

    monkeypatch.setattr(
        "app.schedulers.workstream_dispatcher.wh.workflow_dispatch",
        _fail_dispatch,
    )

    fake = _FakeDispatchDb()

    res = await wd.run_workstream_dispatcher(db=fake)
    assert res.dispatched_workstream_ids == []
    assert res.dispatch_log_ids == []


@pytest.mark.asyncio
async def test_run_dispatcher_writes_last_dispatched_at_to_epic(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", True)
    epic = Epic(
        id="WS-92-cooldown",
        title="Cooldown writeback epic",
        owner_employee_slug="brain",
        status="active",
        priority=0,
        percent_done=0,
        brief_tag="track:cooldown-wb",
    )
    db_session.add(epic)
    await db_session.flush()

    async def _ok_dispatch(*_a: object, **_k: object) -> bool:
        return True

    monkeypatch.setattr(
        "app.schedulers.workstream_dispatcher.wh.workflow_dispatch",
        _ok_dispatch,
    )

    fixed = datetime(2030, 6, 1, 12, 0, 0, tzinfo=UTC)
    res = await wd.run_workstream_dispatcher(now=fixed, db=db_session)
    assert res.skipped is False
    assert res.dispatched_workstream_ids == ["WS-92-cooldown"]
    await db_session.refresh(epic)
    assert epic.last_dispatched_at is not None
    assert epic.last_dispatched_at.tzinfo is not None


@pytest.mark.asyncio
async def test_run_dispatcher_empty_when_db_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backward compat: no working DB session factory yields empty result + warning path."""
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", True)

    def _boom() -> None:
        raise RuntimeError("no db")

    monkeypatch.setattr(
        "app.schedulers.workstream_dispatcher.async_session_factory",
        _boom,
    )
    res = await wd.run_workstream_dispatcher()
    assert res.skipped is False
    assert res.dispatched_workstream_ids == []
