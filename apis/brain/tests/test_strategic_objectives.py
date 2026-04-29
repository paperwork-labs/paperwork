"""Tests for WS-61 strategic objectives manifest and Brain reader."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
import yaml
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.config import settings
from app.main import app
from app.services import strategic_objectives as so


def _schema_block() -> dict:
    return {
        "description": "Founder-written strategic objectives. Brain decomposes into candidate workstreams.",
        "entry": {
            "id": "kebab-slug",
            "objective": "statement",
            "horizon": "30d | 60d",
            "metric": "metric",
            "target": "target",
            "review_cadence_days": "int",
            "written_at": "RFC3339Z",
            "notes": "notes",
        },
    }


def _write_file(
    path: Path,
    objectives: list[dict],
    *,
    last_reviewed_at: datetime | None = None,
) -> None:
    payload = {
        "schema": _schema_block(),
        "version": 1,
        "objectives": objectives,
        "last_reviewed_at": last_reviewed_at,
    }
    path.write_text(
        yaml.dump(
            payload,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _patch_path(monkeypatch: pytest.MonkeyPatch, p: Path) -> None:
    monkeypatch.setattr(so, "objectives_file_path", lambda: p)


def test_load_empty_objectives(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "OBJECTIVES.yaml"
    _write_file(p, [])
    _patch_path(monkeypatch, p)
    rows = so.load_objectives()
    assert rows == []


def test_load_valid_objectives(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "OBJECTIVES.yaml"
    objectives = [
        {
            "id": "launch-readiness",
            "objective": "Ship the launch checklist.",
            "horizon": "30d",
            "metric": "tasks_done",
            "target": "100%",
            "review_cadence_days": 14,
            "written_at": "2026-04-01T10:00:00Z",
            "notes": "Keep tight.",
        }
    ]
    _write_file(p, objectives)
    _patch_path(monkeypatch, p)
    rows = so.load_objectives()
    assert len(rows) == 1
    assert rows[0].id == "launch-readiness"
    assert rows[0].horizon == "30d"


def test_schema_validation_invalid_horizon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "OBJECTIVES.yaml"
    objectives = [
        {
            "id": "bad-horizon",
            "objective": "x",
            "horizon": "7d",
            "metric": "m",
            "target": "t",
            "review_cadence_days": 1,
            "written_at": "2026-04-01T10:00:00Z",
            "notes": "",
        }
    ]
    _write_file(p, objectives)
    _patch_path(monkeypatch, p)
    with pytest.raises(ValidationError):
        so.load_objectives()


def test_invalid_id_pattern_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "OBJECTIVES.yaml"
    objectives = [
        {
            "id": "Bad_ID",
            "objective": "x",
            "horizon": "30d",
            "metric": "m",
            "target": "t",
            "review_cadence_days": 1,
            "written_at": "2026-04-01T10:00:00Z",
            "notes": "",
        }
    ]
    _write_file(p, objectives)
    _patch_path(monkeypatch, p)
    with pytest.raises(ValidationError):
        so.load_objectives()


def test_needs_review_respects_cadence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    overdue_written = (now - timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_written = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    objectives = [
        {
            "id": "stale-goal",
            "objective": "o1",
            "horizon": "90d",
            "metric": "m",
            "target": "t",
            "review_cadence_days": 30,
            "written_at": overdue_written,
            "notes": "",
        },
        {
            "id": "fresh-goal",
            "objective": "o2",
            "horizon": "60d",
            "metric": "m",
            "target": "t",
            "review_cadence_days": 30,
            "written_at": fresh_written,
            "notes": "",
        },
    ]
    p = tmp_path / "OBJECTIVES.yaml"
    _write_file(p, objectives)
    _patch_path(monkeypatch, p)
    due = so.needs_review()
    assert [o.id for o in due] == ["stale-goal"]


def test_mark_reviewed_now_updates_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "OBJECTIVES.yaml"
    _write_file(p, [])
    _patch_path(monkeypatch, p)
    assert so.load_strategic_objectives_file().last_reviewed_at is None
    so.mark_reviewed_now()
    loaded = so.load_strategic_objectives_file()
    assert loaded.last_reviewed_at is not None
    assert loaded.last_reviewed_at.tzinfo is not None


def test_objectives_summary_correctness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    objectives = [
        {
            "id": "a-goal",
            "objective": "o",
            "horizon": "180d",
            "metric": "m",
            "target": "t",
            "review_cadence_days": 7,
            "written_at": "2026-04-10T12:00:00Z",
            "notes": "",
        },
        {
            "id": "b-goal",
            "objective": "o2",
            "horizon": "30d",
            "metric": "m2",
            "target": "t2",
            "review_cadence_days": 7,
            "written_at": "2026-04-11T12:00:00Z",
            "notes": "",
        },
    ]
    p = tmp_path / "OBJECTIVES.yaml"
    lr = datetime(2026, 4, 20, 8, 0, tzinfo=UTC)
    _write_file(p, objectives, last_reviewed_at=lr)
    _patch_path(monkeypatch, p)
    s = so.objectives_summary()
    assert s["count"] == 2
    assert s["horizons"] == ["180d", "30d"]
    assert s["ids"] == ["a-goal", "b-goal"]
    assert s["oldest_review"] == lr


def test_file_not_found_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "missing.yaml"
    _patch_path(monkeypatch, p)
    with pytest.raises(FileNotFoundError):
        so.load_objectives()


def test_invalid_yaml_document_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    p = tmp_path / "OBJECTIVES.yaml"
    p.write_text("---\nnot-a-mapping\n", encoding="utf-8")
    _patch_path(monkeypatch, p)
    with pytest.raises(ValidationError):
        so.load_objectives()


@pytest_asyncio.fixture
async def admin_client(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "sec")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_admin_strategic_objectives_endpoint(
    admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    p = tmp_path / "OBJECTIVES.yaml"
    _write_file(p, [])
    _patch_path(monkeypatch, p)
    r = await admin_client.get(
        "/api/v1/admin/strategic-objectives",
        headers={"X-Brain-Secret": "sec"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["count"] == 0
    assert body["data"]["horizons"] == []
    assert body["data"]["ids"] == []
    assert body["data"]["oldest_review"] is None
