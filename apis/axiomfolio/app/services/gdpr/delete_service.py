"""GDPR account-delete service (two-phase).

Flow:

1. ``start_delete(user_id)`` — creates a PENDING job + plaintext token
   (returned once to the caller; only its SHA-256 hash is stored).
2. ``confirm(user_id, plaintext_token)`` — verifies the token, marks
   the job CONFIRMED, dispatches the Celery cascade-delete task.
3. ``run_delete(job_id)`` — worker-side cascade delete. Removes every
   row from every table whose ``user_id`` matches, then nulls the user
   record itself. Failure writes an ``IncidentRow``.

Iron law: shared / market-wide rows are NOT deleted (we'd damage
other tenants). Those tables are listed in ``_SHARED_TABLES``.

medallion: ops
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Base
from app.models.multitenant import (
    GDPRDeleteJob,
    GDPRJobStatus,
    IncidentRow,
    IncidentSeverity,
)
from app.models.user import User

logger = logging.getLogger(__name__)

# User-scoped tables that must always be included in GDPR delete cascades.
GDPR_DELETE_CASCADE_TABLES: tuple[str, ...] = ("historical_import_runs",)


# Tables whose ``user_id`` column is a metadata pointer rather than
# personal data ownership; deleting them would break other tenants.
_SHARED_TABLES: frozenset[str] = frozenset(
    {
        "market_snapshots",
        "market_snapshot_history",
        # Audit trails. We keep these by design (regulatory) but null
        # the user_id so the rows survive without identifying data.
        "rate_limit_violations",
        "incidents",
    }
)

# Explicit registry for newly added user-scoped tables. These are still
# discovered dynamically through Base.metadata, but the set acts as a
# fail-loud checklist for GDPR coverage regressions.
_EXPLICIT_USER_SCOPED_TABLES: frozenset[str] = frozenset(GDPR_DELETE_CASCADE_TABLES)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _user_scoped_tables() -> list:
    out = []
    seen: set[str] = set()
    for table in Base.metadata.sorted_tables:
        if "user_id" not in table.c:
            continue
        if table.name in _SHARED_TABLES:
            continue
        # Don't delete the bookkeeping job rows themselves until the
        # very end; we'll handle them in run_delete explicitly.
        if table.name in {"gdpr_export_jobs", "gdpr_delete_jobs"}:
            continue
        if table.name == "users":
            continue
        out.append(table)
        seen.add(table.name)
    missing = sorted(_EXPLICIT_USER_SCOPED_TABLES - seen)
    if missing:
        raise RuntimeError(f"GDPR delete table registry mismatch; missing metadata for: {missing}")
    # Reverse so we delete leaves before parents (sorted_tables is
    # parent-first for FK ordering on insert).
    return list(reversed(out))


class GDPRDeleteService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- request --------------------------------------------------------

    def start_delete(self, user_id: int) -> tuple[GDPRDeleteJob, str]:
        """Create a PENDING delete job + return ``(job, plaintext_token)``.

        The plaintext token is returned exactly once and never stored.
        Caller is responsible for delivering it (e.g. emailing a
        confirmation link).
        """
        user = self.db.get(User, user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")

        token = secrets.token_urlsafe(32)
        job = GDPRDeleteJob(
            user_id=user_id,
            status=GDPRJobStatus.PENDING.value,
            confirmation_token_hash=_hash_token(token),
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job, token

    def confirm(self, user_id: int, job_id: int, plaintext_token: str) -> GDPRDeleteJob:
        job = self.db.get(GDPRDeleteJob, job_id)
        if job is None or job.user_id != user_id:
            # Same response for "missing" and "not yours" to avoid
            # leaking job-id existence cross-tenant.
            raise PermissionError("Delete job not found for this tenant")

        if job.status != GDPRJobStatus.PENDING.value:
            raise ValueError(f"Cannot confirm job in status={job.status}")

        ttl = timedelta(hours=max(1, settings.GDPR_DELETE_CONFIRM_TTL_HOURS))
        if datetime.now(UTC) - job.requested_at > ttl:
            job.status = GDPRJobStatus.EXPIRED.value
            self.db.commit()
            raise ValueError("Delete confirmation token expired")

        if not job.confirmation_token_hash or not secrets.compare_digest(
            job.confirmation_token_hash, _hash_token(plaintext_token)
        ):
            raise PermissionError("Invalid confirmation token")

        job.status = GDPRJobStatus.CONFIRMED.value
        job.confirmed_at = datetime.now(UTC)
        # Token is single-use.
        job.confirmation_token_hash = None
        self.db.commit()

        from app.tasks.multitenant.gdpr import run_delete as run_delete_task

        run_delete_task.delay(job.id)
        return job

    # -- worker entrypoint ---------------------------------------------

    def run_delete(self, job_id: int) -> None:
        job = self.db.get(GDPRDeleteJob, job_id)
        if job is None:
            logger.error("gdpr_delete: job %s not found", job_id)
            return
        if job.status != GDPRJobStatus.CONFIRMED.value:
            logger.error(
                "gdpr_delete: job %s in unexpected status=%s; refusing to run",
                job_id,
                job.status,
            )
            return

        user_id = job.user_id
        job.status = GDPRJobStatus.RUNNING.value
        self.db.commit()

        try:
            self._cascade_delete(user_id)
            # Null user_id on retained audit tables (regulatory).
            for tname in ("rate_limit_violations", "incidents"):
                tbl = Base.metadata.tables.get(tname)
                if tbl is not None and "user_id" in tbl.c:
                    self.db.execute(
                        tbl.update().where(tbl.c.user_id == user_id).values(user_id=None)
                    )

            # Mark the user record itself anonymised but preserved
            # for FK integrity in the bookkeeping rows above. We do
            # NOT physically delete the user row; we scrub PII fields.
            user = self.db.get(User, user_id)
            if user is not None:
                user.email = f"deleted+{user_id}@axiomfolio.invalid"
                user.username = f"deleted_user_{user_id}_{secrets.token_hex(4)}"
                user.is_active = False
                user.password_hash = "!"  # disable login

            job.status = GDPRJobStatus.COMPLETED.value
            job.completed_at = datetime.now(UTC)
            self.db.commit()
            logger.info("gdpr_delete: job=%s user=%s OK", job_id, user_id)
        except Exception as exc:
            self.db.rollback()
            logger.exception("gdpr_delete: job=%s failed", job_id)
            # Re-fetch job after rollback.
            job = self.db.get(GDPRDeleteJob, job_id)
            if job is not None:
                job.status = GDPRJobStatus.FAILED.value
                job.error_message = str(exc)[:1000]
                self.db.commit()
            self._record_incident(user_id, job_id, exc)
            raise

    # -- internals ------------------------------------------------------

    def _cascade_delete(self, user_id: int) -> None:
        for table in _user_scoped_tables():
            self.db.execute(delete(table).where(table.c.user_id == user_id))

    def _record_incident(self, user_id: int, job_id: int, exc: Exception) -> None:
        try:
            self.db.add(
                IncidentRow(
                    user_id=user_id,
                    category="gdpr.delete_failed",
                    severity=IncidentSeverity.CRITICAL.value,
                    summary=f"GDPR delete job {job_id} failed: {exc}"[:500],
                    context={
                        "job_id": job_id,
                        "exc_type": type(exc).__name__,
                    },
                )
            )
            self.db.commit()
        except Exception:  # pragma: no cover
            logger.exception("gdpr_delete: failed to write incident row")
            self.db.rollback()
