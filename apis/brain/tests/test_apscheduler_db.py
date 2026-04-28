"""APScheduler Postgres URL helpers."""

from __future__ import annotations

from psycopg2.extensions import parse_dsn

from app.schedulers.apscheduler_db import apscheduler_sync_database_url


def test_apscheduler_sync_database_url_rewrites_ssl_to_sslmode_for_psycopg2() -> None:
    """Neon-style async URL uses ssl= after Settings normalization; libpq needs sslmode."""
    async_url = (
        "postgresql+asyncpg://user:pass@ep.example.aws.neon.tech/db?ssl=require"
    )
    sync_url = apscheduler_sync_database_url(async_url)
    assert "+asyncpg" not in sync_url
    assert "ssl=require" not in sync_url
    assert "sslmode=require" in sync_url
    parse_dsn(sync_url)  # raises if libpq rejects query params


def test_apscheduler_sync_database_url_preserves_explicit_sslmode() -> None:
    url = "postgresql+asyncpg://u:p@localhost/db?sslmode=disable"
    assert "sslmode=disable" in apscheduler_sync_database_url(url)
