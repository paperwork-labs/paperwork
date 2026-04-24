"""GDPR data-export service.

Walks every SQLAlchemy table that holds a ``user_id`` column, dumps
each user-scoped slice to a CSV, zips them, and either uploads to S3
(presigned URL) or stores the ZIP locally. The download URL + expiry
are written back to ``GDPRExportJob``.

Failures write an ``IncidentRow`` so we have a forensic trail even
after the user-facing job row is marked FAILED. This is the
no-silent-fallback iron law in practice.

medallion: ops
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import shutil
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Base
from app.models.multitenant import (
    GDPRExportJob,
    GDPRJobStatus,
    IncidentRow,
    IncidentSeverity,
)
from app.models.user import User

logger = logging.getLogger(__name__)


# Tables that look user-scoped via FK but are actually shared
# infrastructure or contain only generated metadata. Excluded from
# export to keep the artefact focused on the user's own data.
_SKIP_TABLES: frozenset[str] = frozenset(
    {
        "alembic_version",
        # Per-tenant rate limit *overrides* may exist with user_id, but the
        # global default rows would not. The user's overrides are not
        # personally identifying data — keep them out.
        "tenant_rate_limits",
        "rate_limit_violations",
        "incidents",
        # Shared market-data caches may carry a user_id when populated by
        # a per-user request, but their content is market-wide. Skip.
        "market_snapshots",
        "market_snapshot_history",
    }
)


def _user_scoped_tables() -> List[Any]:
    """Return SA Table objects that have a ``user_id`` column.

    Uses the metadata that's already loaded by the time this runs (the
    full app boots before Celery does, importing every model).
    """
    out: list = []
    for table in Base.metadata.sorted_tables:
        if table.name in _SKIP_TABLES:
            continue
        if "user_id" in table.c:
            out.append(table)
    return out


def _row_to_dict(row: Any, columns: List[str]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for col in columns:
        val = getattr(row, col, None)
        if isinstance(val, datetime):
            record[col] = val.isoformat()
        elif isinstance(val, (dict, list)):
            record[col] = json.dumps(val, default=str)
        elif val is None:
            record[col] = ""
        else:
            record[col] = str(val)
    return record


class GDPRExportService:
    """Per-user GDPR data export. One job row, one ZIP."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # -- request --------------------------------------------------------

    def start_export(self, user_id: int) -> GDPRExportJob:
        """Create a PENDING export job and dispatch a Celery task.

        The task runs out of band so the request returns immediately.
        """
        user = self.db.get(User, user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")

        job = GDPRExportJob(
            user_id=user_id,
            status=GDPRJobStatus.PENDING.value,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        # Local import to avoid Celery import at module load.
        from app.tasks.multitenant.gdpr import run_export as run_export_task

        run_export_task.delay(job.id)
        return job

    # -- worker entrypoint ---------------------------------------------

    def run_export(self, job_id: int) -> None:
        """Worker-side: collect every user-scoped row, zip, persist URL."""
        job = self.db.get(GDPRExportJob, job_id)
        if job is None:
            logger.error("gdpr_export: job %s not found", job_id)
            return

        user_id = job.user_id
        job.status = GDPRJobStatus.RUNNING.value
        self.db.commit()

        os.makedirs(settings.GDPR_EXPORT_LOCAL_DIR, exist_ok=True)
        zip_filename = f"axiomfolio-export-user{user_id}-job{job_id}.zip"
        local_path = os.path.join(settings.GDPR_EXPORT_LOCAL_DIR, zip_filename)

        try:
            bytes_written = self._write_zip(local_path, user_id)
            url, expires_at = self._publish(local_path, zip_filename)

            job.status = GDPRJobStatus.COMPLETED.value
            job.completed_at = datetime.now(timezone.utc)
            job.download_url = url
            job.expires_at = expires_at
            job.bytes_written = bytes_written
            self.db.commit()
            logger.info(
                "gdpr_export: job=%s user=%s bytes=%s url=%s",
                job_id,
                user_id,
                bytes_written,
                url,
            )
        except Exception as exc:
            logger.exception("gdpr_export: job=%s failed", job_id)
            job.status = GDPRJobStatus.FAILED.value
            job.error_message = str(exc)[:1000]
            self.db.commit()
            self._record_incident(user_id, job_id, exc)
            # Re-raise so Celery marks the task failed too.
            raise

    # -- internals ------------------------------------------------------

    def _write_zip(self, path: str, user_id: int) -> int:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            manifest = {
                "user_id": user_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "tables": [],
            }

            for table in _user_scoped_tables():
                rows = self.db.execute(
                    select(table).where(table.c.user_id == user_id)
                ).fetchall()
                columns = [c.name for c in table.c]
                buf = io.StringIO()
                writer = csv.DictWriter(buf, fieldnames=columns)
                writer.writeheader()
                for row in rows:
                    writer.writerow(_row_to_dict(row, columns))
                zf.writestr(f"{table.name}.csv", buf.getvalue())
                manifest["tables"].append(
                    {"name": table.name, "row_count": len(rows)}
                )

            zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2))

        return os.path.getsize(path)

    def _publish(
        self, local_path: str, zip_filename: str
    ) -> tuple[str, datetime]:
        """Return ``(download_url, expires_at)``.

        Uploads to S3 if configured, else copies to a public local dir
        served via the API and returns a relative URL. Expiry is
        capped by ``GDPR_EXPORT_TTL_DAYS``.
        """
        ttl = timedelta(days=max(1, settings.GDPR_EXPORT_TTL_DAYS))
        expires_at = datetime.now(timezone.utc) + ttl

        if settings.S3_GDPR_BUCKET and settings.S3_GDPR_ACCESS_KEY_ID:
            try:
                import boto3  # type: ignore[import-not-found]
            except ImportError as exc:
                raise RuntimeError(
                    "boto3 is required when S3_GDPR_BUCKET is set"
                ) from exc

            s3 = boto3.client(
                "s3",
                region_name=settings.S3_GDPR_REGION,
                endpoint_url=settings.S3_GDPR_ENDPOINT_URL,
                aws_access_key_id=settings.S3_GDPR_ACCESS_KEY_ID,
                aws_secret_access_key=settings.S3_GDPR_SECRET_ACCESS_KEY,
            )
            key = f"gdpr-exports/{zip_filename}"
            s3.upload_file(local_path, settings.S3_GDPR_BUCKET, key)
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_GDPR_BUCKET, "Key": key},
                ExpiresIn=int(ttl.total_seconds()),
            )
            # Best-effort: remove local copy after upload.
            try:
                os.remove(local_path)
            except OSError:
                pass
            return url, expires_at

        # Local fallback: keep the ZIP on disk; the API serves it via
        # /api/v1/me/data-export/{job_id}/download (added in routes).
        return f"local://{zip_filename}", expires_at

    def _record_incident(
        self, user_id: int, job_id: int, exc: Exception
    ) -> None:
        try:
            self.db.add(
                IncidentRow(
                    user_id=user_id,
                    category="gdpr.export_failed",
                    severity=IncidentSeverity.HIGH.value,
                    summary=f"GDPR export job {job_id} failed: {exc}"[:500],
                    context={
                        "job_id": job_id,
                        "exc_type": type(exc).__name__,
                    },
                )
            )
            self.db.commit()
        except Exception:  # pragma: no cover - best-effort audit
            logger.exception("gdpr_export: failed to write incident row")
            self.db.rollback()
