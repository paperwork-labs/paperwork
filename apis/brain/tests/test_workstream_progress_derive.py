"""Linked-PR derived percent for workstreams (GitHub merge state)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.schemas.workstream import Workstream
from app.services import workstream_progress_derive as d


def _ws(**kwargs: Any) -> Workstream:
    base: dict[str, Any] = {
        "id": "WS-99-derive-test",
        "title": "Derive test workstream title here",
        "track": "Z",
        "priority": 0,
        "status": "in_progress",
        "percent_done": 50,
        "owner": "brain",
        "brief_tag": "track:derive-test",
        "blockers": [],
        "last_pr": None,
        "last_activity": "2026-04-27T12:00:00Z",
        "last_dispatched_at": None,
        "notes": "",
        "estimated_pr_count": 2,
        "github_actions_workflow": None,
        "related_plan": None,
    }
    base.update(kwargs)
    return Workstream(**base)


@pytest.mark.asyncio
async def test_derived_percent_half_merged(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(n: int) -> dict[str, Any] | None:
        if n == 10:
            return {"merged_at": "2026-04-01T00:00:00Z"}
        if n == 11:
            return {"merged_at": None, "state": "open"}
        return None

    monkeypatch.setattr(d.gh, "get_github_pull_dict", fake_get)
    ws = _ws(prs=[10, 11])
    pct = await d.derive_percent_for_workstream(ws)
    assert pct == 50


@pytest.mark.asyncio
async def test_derived_percent_none_when_fetch_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(d.gh, "get_github_pull_dict", AsyncMock(return_value=None))
    ws = _ws(last_pr=55)
    pct = await d.derive_percent_for_workstream(ws)
    assert pct is None


@pytest.mark.asyncio
async def test_collect_linked_pr_numbers_union(monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(
        last_pr=1,
        prs=[2],
        pr_numbers=[3],
        pr_url="https://github.com/paperwork-labs/paperwork/pull/4",
    )
    assert d.collect_linked_pr_numbers(ws) == [1, 2, 3, 4]

    async def merged(_n: int) -> dict[str, Any]:
        return {"merged_at": "2026-04-02T00:00:00Z"}

    monkeypatch.setattr(d.gh, "get_github_pull_dict", merged)
    m = await d.compute_derived_percents_for_workstreams([ws])
    assert m[ws.id] == 100
