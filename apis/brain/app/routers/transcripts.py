"""Admin routes for Cursor transcript JSONL ingestion.

medallion: ops
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002 — FastAPI DI

from app.config import settings
from app.database import get_db
from app.routers.admin import _require_admin
from app.schemas.base import success_response
from app.schemas.transcript_ingest import (
    IngestResult,
    TranscriptIngestBatchRequest,
    TranscriptIngestBatchResult,
    TranscriptIngestRequest,
)
from app.services import transcript_ingest as transcript_ingest_svc

router = APIRouter(prefix="/admin/transcripts", tags=["admin", "transcripts"])


def _resolved_path_for_request(body: TranscriptIngestRequest) -> Path:
    if body.file_path and body.file_path.strip():
        return Path(body.file_path.strip()).expanduser()
    tid = (body.transcript_id or "").strip()
    root = (settings.BRAIN_CURSOR_AGENT_TRANSCRIPTS_DIR or "").strip()
    if not root:
        raise HTTPException(
            status_code=400,
            detail=(
                "transcript_id requires BRAIN_CURSOR_AGENT_TRANSCRIPTS_DIR "
                "(parent of agent-transcripts uuid folders)"
            ),
        )
    try:
        return transcript_ingest_svc.resolve_transcript_path(
            root=Path(root),
            transcript_id=tid,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ingest")
async def ingest_one_transcript(
    body: TranscriptIngestRequest,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> dict[str, object]:
    """Ingest one Cursor JSONL transcript by path or uuid under configured root."""
    path = _resolved_path_for_request(body)
    result = await transcript_ingest_svc.ingest_transcript(db, str(path))
    return success_response(result.model_dump(mode="json"))


@router.post("/ingest-batch")
async def ingest_transcripts_batch(
    body: TranscriptIngestBatchRequest,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> dict[str, object]:
    """Scan a directory recursively for ``*.jsonl`` and ingest each transcript once."""
    directory = body.directory.strip()
    root = Path(directory).expanduser()
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {root}")

    files = transcript_ingest_svc.discover_jsonl_files(str(root))
    file_results: list[IngestResult] = []
    batch_errors: list[str] = []
    ingested = 0
    skipped = 0
    total_episodes = 0

    for fp in files:
        try:
            one = await transcript_ingest_svc.ingest_transcript(db, str(fp))
        except Exception as exc:
            batch_errors.append(f"{fp}: {exc}")
            continue
        file_results.append(one)
        if one.skipped:
            skipped += 1
        elif one.episodes_created > 0:
            ingested += 1
        total_episodes += one.episodes_created
        batch_errors.extend(f"{fp}: {e}" for e in one.errors)

    agg = TranscriptIngestBatchResult(
        scanned_files=len(files),
        ingested_files=ingested,
        skipped_files=skipped,
        total_episodes_created=total_episodes,
        errors=batch_errors,
        file_results=file_results,
    )
    return success_response(agg.model_dump(mode="json"))
