"""Helpers for APScheduler persistence (sync SQLAlchemy job store on Postgres)."""

from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from app.config import settings


def apscheduler_sync_database_url(database_url: str) -> str:
    """APScheduler's SQLAlchemy job store is sync-only. Strip the asyncpg driver.

    After ``Settings`` normalization, ``DATABASE_URL`` uses ``postgresql+asyncpg://``.
    Neon URLs use ``sslmode=require``; :class:`~app.config.Settings` rewrites that to
    ``ssl=`` for asyncpg. psycopg2/libpq **reject** the ``ssl`` query key (see
    ``psycopg2.extensions.parse_dsn``) — restore ``sslmode`` for the sync job store URL
    so ``SQLAlchemyJobStore`` can connect on startup.
    """
    sync_url = database_url.replace("+asyncpg", "", 1)
    parsed = urlparse(sync_url)
    params = parse_qs(parsed.query)
    if "ssl" in params and "sslmode" not in params:
        params["sslmode"] = params.pop("ssl")
    clean_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=clean_query))


def build_sqlalchemy_jobstores() -> dict[str, SQLAlchemyJobStore]:
    """Postgres-backed job persistence so process restarts do not drop schedules."""
    sync_url = apscheduler_sync_database_url(settings.DATABASE_URL)
    return {
        "default": SQLAlchemyJobStore(url=sync_url, tablename="apscheduler_jobs"),
    }
