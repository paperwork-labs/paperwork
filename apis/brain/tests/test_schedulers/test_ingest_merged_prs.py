"""Scheduler + idempotency for merged-PR continuous learning."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.schedulers.merged_prs_ingest import install
from app.services.continuous_learning import MergedPRRecord, ingest_merged_prs


def test_install_registers_job() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "merged_prs_ingest"


@pytest.mark.asyncio
async def test_ingest_merged_prs_idempotent_and_pin_shape(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "brain_data"
    data_dir.mkdir()

    def _fake_data_dir() -> str:
        return str(data_dir)

    async def fake_fetch(days: int = 7, limit: int = 50) -> list[MergedPRRecord]:
        return [
            MergedPRRecord(
                number=999001,
                title="Test PR",
                body="Hello <!-- x --> \n## Summary\nignored",
                merged_at="2026-04-01T12:00:00Z",
                labels=["area:brain"],
                author="tester",
                base_ref="main",
                file_paths=["apis/brain/app/x.py", "docs/README.md"],
            )
        ]

    monkeypatch.setattr(
        "app.services.continuous_learning._data_dir",
        _fake_data_dir,
    )
    monkeypatch.setattr(
        "app.services.continuous_learning._http_fetch_merged_prs",
        fake_fetch,
    )

    r1 = await ingest_merged_prs(db_session, str(tmp_path), skip_embedding=True)
    assert r1.get("created") == 1
    assert r1.get("skipped") == 0

    r2 = await ingest_merged_prs(db_session, str(tmp_path), skip_embedding=True)
    assert r2.get("created") == 0
    assert r2.get("skipped") == 1

    pin = data_dir / "ingested_prs.json"
    assert pin.is_file()
    raw = json.loads(pin.read_text())
    assert raw.get("999001") == "2026-04-01T12:00:00Z"
