"""GDPR data-subject-rights API.

All routes are scoped to the authenticated user (no admin override). A
job's ``user_id`` is always taken from ``current_user`` so a
compromised job-id can't be used cross-tenant.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.config import settings
from app.database import get_db
from app.models.multitenant import (
    GDPRDeleteJob,
    GDPRExportJob,
    GDPRJobStatus,
)
from app.models.user import User
from app.services.gdpr.delete_service import GDPRDeleteService
from app.services.gdpr.export_service import GDPRExportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/me", tags=["DataPrivacy"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ExportJobResponse(BaseModel):
    id: int
    status: str
    requested_at: datetime
    completed_at: datetime | None = None
    download_url: str | None = None
    expires_at: datetime | None = None
    bytes_written: int | None = None
    error_message: str | None = None


class DeleteJobResponse(BaseModel):
    id: int
    status: str
    requested_at: datetime
    confirmed_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class StartDeleteResponse(BaseModel):
    job: DeleteJobResponse
    confirmation_token: str


class ConfirmDeleteRequest(BaseModel):
    confirmation_token: str


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


@router.post("/data-export", response_model=ExportJobResponse)
def start_data_export(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportJobResponse:
    """Kick off a per-user data export. Returns the job row."""
    service = GDPRExportService(db)
    job = service.start_export(current_user.id)
    return ExportJobResponse(
        id=job.id,
        status=job.status,
        requested_at=job.requested_at,
        completed_at=job.completed_at,
        download_url=job.download_url,
        expires_at=job.expires_at,
        bytes_written=job.bytes_written,
        error_message=job.error_message,
    )


@router.get("/data-export/{job_id}", response_model=ExportJobResponse)
def get_export_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportJobResponse:
    job = db.get(GDPRExportJob, job_id)
    if job is None or job.user_id != current_user.id:
        # Same response for "not found" and "wrong tenant" so we don't
        # leak job-id existence cross-tenant.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found")
    return ExportJobResponse(
        id=job.id,
        status=job.status,
        requested_at=job.requested_at,
        completed_at=job.completed_at,
        download_url=job.download_url,
        expires_at=job.expires_at,
        bytes_written=job.bytes_written,
        error_message=job.error_message,
    )


@router.get("/data-export/{job_id}/download")
def download_export(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream the export ZIP for jobs published to local storage.

    S3-backed jobs return the presigned URL via ``download_url`` and
    do not hit this endpoint.
    """
    job = db.get(GDPRExportJob, job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found")
    if job.status != GDPRJobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Export job not ready (status={job.status})",
        )
    if not job.download_url or not job.download_url.startswith("local://"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Export was published to remote storage; use download_url instead",
        )
    if job.expires_at and job.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Export has expired")
    fname = job.download_url.removeprefix("local://")
    path = os.path.join(settings.GDPR_EXPORT_LOCAL_DIR, fname)
    if not os.path.exists(path):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Export artefact missing")
    return FileResponse(path, media_type="application/zip", filename=fname)


# ---------------------------------------------------------------------------
# Delete (two-phase)
# ---------------------------------------------------------------------------


@router.post("/account-delete", response_model=StartDeleteResponse)
def start_account_delete(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StartDeleteResponse:
    """Begin two-phase account deletion. Returns the confirmation token once.

    The plaintext token is shown to the user a single time. We store
    only its SHA-256 hash. The caller MUST hit
    ``/account-delete/{job_id}/confirm`` with the same token within
    ``GDPR_DELETE_CONFIRM_TTL_HOURS``.
    """
    service = GDPRDeleteService(db)
    job, token = service.start_delete(current_user.id)
    return StartDeleteResponse(
        job=DeleteJobResponse(
            id=job.id,
            status=job.status,
            requested_at=job.requested_at,
            confirmed_at=job.confirmed_at,
            completed_at=job.completed_at,
            error_message=job.error_message,
        ),
        confirmation_token=token,
    )


@router.post("/account-delete/{job_id}/confirm", response_model=DeleteJobResponse)
def confirm_account_delete(
    job_id: int,
    body: ConfirmDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeleteJobResponse:
    service = GDPRDeleteService(db)
    try:
        job = service.confirm(current_user.id, job_id, body.confirmation_token)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return DeleteJobResponse(
        id=job.id,
        status=job.status,
        requested_at=job.requested_at,
        confirmed_at=job.confirmed_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
    )


@router.get("/account-delete/{job_id}", response_model=DeleteJobResponse)
def get_delete_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeleteJobResponse:
    job = db.get(GDPRDeleteJob, job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delete job not found")
    return DeleteJobResponse(
        id=job.id,
        status=job.status,
        requested_at=job.requested_at,
        confirmed_at=job.confirmed_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
    )
