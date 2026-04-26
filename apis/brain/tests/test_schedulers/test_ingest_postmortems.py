"""Postmortem ingestion idempotency."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.schedulers.ingest_postmortems_cadence import install
from app.services.continuous_learning import ingest_postmortems


def test_install_registers_one_cron_job() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "ingest_postmortems_daily"


@pytest.mark.asyncio
async def test_ingest_postmortems_idempotent_and_pin_shape(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(
        "app.services.continuous_learning._data_dir",
        lambda: str(data_dir),
    )

    repo = tmp_path / "repo"
    sp = repo / "docs" / "sprints"
    sp.mkdir(parents=True)
    (sp / "DEAD_2026Q1.md").write_text(
        """---
status: abandoned
---
# Dead sprint

## Postmortem

We stopped because reasons on 2026-01-15.
""",
        encoding="utf-8",
    )

    r1 = await ingest_postmortems(db_session, str(repo), skip_embedding=True)
    assert r1["created"] == 1
    assert r1["skipped"] == 0

    r2 = await ingest_postmortems(db_session, str(repo), skip_embedding=True)
    assert r2["created"] == 0
    assert r2["skipped"] == 1

    pin = data_dir / "ingested_postmortems.json"
    assert pin.is_file()
    raw = json.loads(pin.read_text())
    assert len(raw) == 1
    h, v = next(iter(raw.items()))
    assert len(h) == 64
    assert v.startswith("pm:")
