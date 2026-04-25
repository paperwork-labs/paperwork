"""Helpers for APScheduler persistence (sync SQLAlchemy job store on Postgres)."""

from __future__ import annotations

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from app.config import settings


def apscheduler_sync_database_url(database_url: str) -> str:
    """APScheduler's SQLAlchemy job store is sync-only. Strip the asyncpg driver.

    After ``Settings`` normalization, ``DATABASE_URL`` uses ``postgresql+asyncpg://``.
    """
    return database_url.replace("+asyncpg", "", 1)


def build_sqlalchemy_jobstores() -> dict[str, SQLAlchemyJobStore]:
    """Postgres-backed job persistence so process restarts do not drop schedules."""
    sync_url = apscheduler_sync_database_url(settings.DATABASE_URL)
    return {
        "default": SQLAlchemyJobStore(url=sync_url, tablename="apscheduler_jobs"),
    }
