"""Tests for WS-62 `pr_outcomes` JSON + admin list API."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import app.services.pr_outcomes as pr_out
from app.config import settings
from app.database import get_db
from app.main import app

_ENV = "BRAIN_PR_OUTCOMES_JSON"


@pytest_asyncio.fixture
async def client_mock_db() -> AsyncClient:
    """ASGI client with mock DB (same pattern as ``test_admin_learning``)."""

    async def mock_get_db():
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=AsyncMock(
                scalars=lambda: AsyncMock(all=list),
                all=list,
                one=lambda: (0, 0),
            )
        )
        db.add = lambda _x: None
        yield db

    app.dependency_overrides[get_db] = mock_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def outcomes_path(tmp_path: Path) -> Path:
    p = tmp_path / "pr_outcomes.json"
    p.write_text(
        json.dumps(
            {
                "schema": "pr_outcomes/v1",
                "description": "test",
                "outcomes": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    prev = os.environ.get(_ENV)
    os.environ[_ENV] = str(p)
    yield p
    if prev is None:
        os.environ.pop(_ENV, None)
    else:
        os.environ[_ENV] = prev


def test_record_merged_pr_then_get_round_trip(outcomes_path: Path) -> None:
    pr_out.record_merged_pr(
        501,
        "2026-04-28T12:00:00Z",
        "orchestrator",
        "composer-2-fast",
        "implementation",
        ["WS-41", "WS-10"],
        ["autonomy", "ops"],
        branch="ws-41/example",
        ci_status_at_merge="success",
    )
    row = pr_out.get_pr_outcome(501)
    assert row is not None
    assert row.pr_number == 501
    assert row.merged_at == "2026-04-28T12:00:00Z"
    assert row.branch == "ws-41/example"
    assert row.ci_status_at_merge == "success"
    assert row.workstream_ids == ["WS-41", "WS-10"]
    assert row.outcomes.h1 is None
    data = json.loads(outcomes_path.read_text(encoding="utf-8"))
    assert len(data["outcomes"]) == 1
    assert data["outcomes"][0]["pr_number"] == 501


def test_update_outcome_h1_persists(outcomes_path: Path) -> None:
    pr_out.record_merged_pr(
        88,
        "2026-04-28T13:00:00Z",
        "a",
        "m",
        "t",
        [],
        [],
    )
    pr_out.update_outcome_h1(88, True, True, False)
    row = pr_out.get_pr_outcome(88)
    assert row is not None
    assert row.outcomes.h1 is not None
    assert row.outcomes.h1.ci_pass is True
    assert row.outcomes.h1.deploy_success is True
    assert row.outcomes.h1.reverted is False

    reloaded = json.loads(outcomes_path.read_text(encoding="utf-8"))
    assert reloaded["outcomes"][0]["outcomes"]["h1"]["ci_pass"] is True


def test_list_outcomes_for_workstream_finds_ws41(outcomes_path: Path) -> None:
    pr_out.record_merged_pr(
        1,
        "2026-04-27T00:00:00Z",
        "a",
        "m",
        "t",
        ["WS-40"],
        [],
    )
    pr_out.record_merged_pr(
        2,
        "2026-04-28T00:00:00Z",
        "a",
        "m",
        "t",
        ["WS-41"],
        ["x"],
    )
    rows = pr_out.list_outcomes_for_workstream("WS-41")
    assert len(rows) == 1
    assert rows[0].pr_number == 2


def test_get_pr_outcome_missing_returns_none(outcomes_path: Path) -> None:
    assert pr_out.get_pr_outcome(99999) is None


def test_record_merged_pr_overwrite_preserves_horizons(outcomes_path: Path) -> None:
    pr_out.record_merged_pr(77, "2026-04-28T13:00:00Z", "a", "m", "t", [], [])
    pr_out.update_outcome_h24(77, True, True, False)

    pr_out.record_merged_pr(
        77,
        "2026-04-28T13:00:01Z",
        "brain-dispatch",
        "composer-2-fast",
        "generalPurpose",
        ["WS-82"],
        ["ops"],
        branch="ws82/wave0/pr-a3-pr-outcomes-wiring",
        ci_status_at_merge="success",
        overwrite_existing=True,
    )

    row = pr_out.get_pr_outcome(77)
    assert row is not None
    assert row.merged_by_agent == "brain-dispatch"
    assert row.branch == "ws82/wave0/pr-a3-pr-outcomes-wiring"
    assert row.outcomes.h24 is not None
    assert row.outcomes.h24.ci_pass is True


@pytest.mark.asyncio
async def test_admin_pr_outcomes_list(
    client_mock_db: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = tmp_path / "pr_outcomes.json"
    monkeypatch.setenv(_ENV, str(p))
    p.write_text('{"schema":"pr_outcomes/v1","outcomes":[]}\n', encoding="utf-8")
    pr_out.record_merged_pr(
        9000,
        "2026-04-28T15:00:00Z",
        "a",
        "m",
        "t",
        ["WS-41"],
        [],
    )
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "s")
    res = await client_mock_db.get(
        "/api/v1/admin/pr-outcomes",
        params={"workstream_id": "WS-41", "limit": 10},
        headers={"X-Brain-Secret": "s"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    d = body["data"]
    assert d["count"] == 1
    assert d["outcomes"][0]["pr_number"] == 9000
    assert d["workstream_id"] == "WS-41"
