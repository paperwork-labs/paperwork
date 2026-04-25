"""n8n cron shadow mirrors + SQLAlchemy job store URL (T2.2)."""
from __future__ import annotations

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.schedulers import apscheduler_db
from app.schedulers.n8n_mirror import N8N_MIRROR_SPECS, install


def test_apscheduler_sync_database_url_strips_asyncpg() -> None:
    url = "postgresql+asyncpg://brain:sec@db.example:5432/brain_prod?ssl=true"
    assert apscheduler_db.apscheduler_sync_database_url(url) == (
        "postgresql://brain:sec@db.example:5432/brain_prod?ssl=true"
    )


def test_build_sqlalchemy_jobstore_uses_sync_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """SQLAlchemyJobStore is sync; URL must be ``postgresql://`` (no +asyncpg)."""
    async_url = "postgresql+asyncpg://u:p@localhost:5432/db"
    monkeypatch.setattr(settings, "DATABASE_URL", async_url)
    stores = apscheduler_db.build_sqlalchemy_jobstores()
    assert "default" in stores
    jstore = stores["default"]
    # Engine URL is sync postgres (driver may be default psycopg2).
    s = str(jstore.engine.url)
    assert "+asyncpg" not in s
    assert s.startswith("postgresql:")


def test_mirror_disabled_no_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SCHEDULER_N8N_MIRROR_ENABLED", False)
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    assert len(sched.get_jobs()) == 0


def test_mirror_enabled_registers_all_specs_with_expected_triggers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SCHEDULER_N8N_MIRROR_ENABLED", True)
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == len(N8N_MIRROR_SPECS)
    by_id = {j.id: j for j in jobs}
    for spec in N8N_MIRROR_SPECS:
        assert spec.job_id in by_id
        t = by_id[spec.job_id].trigger
        if spec.kind == "cron":
            assert isinstance(t, CronTrigger)
            ref = CronTrigger.from_crontab(spec.schedule, timezone="UTC")
            assert t.fields == ref.fields
        else:
            assert isinstance(t, IntervalTrigger)
            assert t.interval_length == 30 * 60
