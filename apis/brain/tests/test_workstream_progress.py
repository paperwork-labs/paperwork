"""Workstream progress math + hourly snapshot path."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from app.config import settings
from app.schemas.workstream import Workstream, WorkstreamsFile
from app.services import workstream_progress as wp


def test_compute_percent_done_uses_estimated_when_set() -> None:
    pct, denom = wp.compute_percent_done(merged_prs=1, open_prs=1, estimated_pr_count=4)
    assert denom == 4
    assert pct == 25


def test_compute_percent_done_falls_back_to_open_plus_merged() -> None:
    pct, denom = wp.compute_percent_done(merged_prs=2, open_prs=1, estimated_pr_count=None)
    assert denom == 3
    assert pct == min(100, round(2 / 3 * 100))


def test_compute_percent_done_denominator_at_least_one() -> None:
    pct, denom = wp.compute_percent_done(merged_prs=0, open_prs=0, estimated_pr_count=None)
    assert denom == 1
    assert pct == 0


def test_snapshot_status_completed_only_when_no_open() -> None:
    assert wp.compute_snapshot_status(100, 0, "in_progress") == "completed"
    assert wp.compute_snapshot_status(100, 1, "in_progress") == "in_progress"
    assert wp.compute_snapshot_status(80, 0, "pending") == "pending"


def _one_ws(**kwargs) -> WorkstreamsFile:  # type: ignore[no-untyped-def]
    defaults = {
        "id": "WS-01-prog",
        "title": "Progress test",
        "track": "Z",
        "priority": 0,
        "status": "pending",
        "percent_done": 0,
        "owner": "brain",
        "brief_tag": "track:prog-test",
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
    w = Workstream(**defaults)
    return WorkstreamsFile(version=1, updated="2026-04-27T12:00:00Z", workstreams=[w])


@pytest.mark.asyncio
async def test_run_workstream_progress_skipped_when_scheduler_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", False)
    res = await wp.run_workstream_progress()
    assert res.skipped is True
    assert res.snapshots_recorded == 0


class _FakeProgressDb:
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
async def test_run_workstream_progress_records_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_SCHEDULER_ENABLED", True)
    monkeypatch.setattr(
        "app.services.workstream_progress.load_workstreams_file",
        lambda **_: _one_ws(),
    )

    async def _fake_search(_tag: str) -> tuple[int, int]:
        return (2, 0)

    monkeypatch.setattr(
        "app.services.workstream_progress.wh.search_prs_with_brief_tag_in_body",
        _fake_search,
    )

    fake = _FakeProgressDb()

    @asynccontextmanager
    async def _sess():
        yield fake

    monkeypatch.setattr(
        "app.services.workstream_progress.async_session_factory",
        lambda: _sess(),
    )

    res = await wp.run_workstream_progress()
    assert res.skipped is False
    assert res.snapshots_recorded == 1
    assert res.by_workstream_id["WS-01-prog"] == 100
    assert wp.compute_snapshot_status(100, 0, "pending") == "completed"
