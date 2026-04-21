"""Celery tasks for GDPR data export + delete (heavy queue)."""

from __future__ import annotations

import logging

from celery import shared_task

from backend.database import SessionLocal
from backend.services.gdpr.delete_service import (
    GDPR_DELETE_CASCADE_TABLES as _GDPR_DELETE_CASCADE_TABLES,
    GDPRDeleteService,
)
from backend.services.gdpr.export_service import GDPRExportService

logger = logging.getLogger(__name__)
# Re-export the canonical registry so worker-side callers/tests can reference one source.
GDPR_DELETE_CASCADE_TABLES = _GDPR_DELETE_CASCADE_TABLES
__all__ = ("run_export", "run_delete", "GDPR_DELETE_CASCADE_TABLES")


# Both tasks set explicit time limits per the iron law in
# ``job_catalog.py``. They run on the ``heavy`` queue (routed in
# ``celery_app.py``).


@shared_task(
    name="backend.tasks.multitenant.gdpr.run_export",
    bind=True,
    queue="heavy",
    soft_time_limit=600,
    time_limit=900,
    autoretry_for=(),  # explicit: do NOT auto-retry data exports
    max_retries=0,
)
def run_export(self, job_id: int) -> None:  # noqa: D401
    """Worker entry: build + publish a user's data export ZIP."""
    db = SessionLocal()
    try:
        GDPRExportService(db).run_export(job_id)
    finally:
        db.close()


@shared_task(
    name="backend.tasks.multitenant.gdpr.run_delete",
    bind=True,
    queue="heavy",
    soft_time_limit=900,
    time_limit=1200,
    autoretry_for=(),  # never retry destructive operations
    max_retries=0,
)
def run_delete(self, job_id: int) -> None:  # noqa: D401
    """Worker entry: cascade-delete a user's data."""
    db = SessionLocal()
    try:
        GDPRDeleteService(db).run_delete(job_id)
    finally:
        db.close()
