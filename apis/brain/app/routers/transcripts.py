"""Admin routes for Cursor transcript JSONL ingestion and read-back.

medallion: ops
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse  # noqa: TC002 — return type
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002 — FastAPI DI

from app.config import settings
from app.database import get_db
from app.routers.admin import _require_admin
from app.schemas.base import error_response, success_response
from app.schemas.transcript_ingest import (
    IngestResult,
    TranscriptIngestBatchRequest,
    TranscriptIngestBatchResult,
    TranscriptIngestRequest,
)
from app.schemas.transcripts_admin import (
    TranscriptDetailPayload,
    TranscriptListItem,
    TranscriptListPayload,
    TranscriptMessageItem,
)
from app.services import transcript_ingest as transcript_ingest_svc
from app.services import transcripts_admin as transcripts_admin_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/transcripts", tags=["admin", "transcripts"])


@router.get("")
async def list_transcripts(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
    limit: int = Query(50, ge=1, le=200, description="Page size (max 200)"),
    cursor: str | None = Query(None, description="Opaque pagination cursor"),
) -> JSONResponse:
    """Cursor-paginated transcript sessions (grouped ``transcript_id`` rows)."""
    try:
        rows, next_cursor = await transcripts_admin_svc.list_transcript_sessions(
            db,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as exc:
        return error_response(str(exc), status_code=400)

    tids = [r.transcript_id for r in rows]
    tag_map = await transcripts_admin_svc.load_tags_for_transcripts(db, tids)

    items: list[TranscriptListItem] = []
    for row in rows:
        tid = row.transcript_id
        title = transcripts_admin_svc.transcript_title_from_turn(
            summary=row.title_summary,
            user_message=row.title_user_hint,
        )
        items.append(
            TranscriptListItem(
                id=tid,
                session_id=tid,
                started_at=row.started_at.isoformat(),
                ended_at=row.ended_at.isoformat(),
                title=title,
                tags=tag_map.get(tid, []),
                message_count=row.message_count,
            )
        )

    payload = TranscriptListPayload(items=items, next_cursor=next_cursor)
    return success_response(payload.model_dump(mode="json"))


@router.get("/{transcript_id}")
async def get_transcript(
    transcript_id: str,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
    """Full transcript for one ``transcript_id`` (all turns)."""
    tid = transcript_id.strip()
    if not transcripts_admin_svc.is_transcript_uuid(tid):
        return error_response("Transcript not found", status_code=404)

    header = await transcripts_admin_svc.transcript_session_header(db, tid)
    if header is None:
        logger.info("transcript detail miss transcript_id=%s", tid)
        return error_response("Transcript not found", status_code=404)

    tag_map = await transcripts_admin_svc.load_tags_for_transcripts(db, [tid])
    raw_messages = await transcripts_admin_svc.load_transcript_messages(db, tid)

    title = transcripts_admin_svc.transcript_title_from_turn(
        summary=header.title_summary,
        user_message=header.title_user_hint,
    )

    messages: list[TranscriptMessageItem] = []
    for m in raw_messages:
        ing = m["ingested_at"]
        messages.append(
            TranscriptMessageItem(
                turn_index=m["turn_index"],
                user_message=m["user_message"],
                assistant_message=m["assistant_message"],
                summary=m["summary"] if isinstance(m["summary"], str) else None,
                ingested_at=ing.isoformat(),
            )
        )

    detail = TranscriptDetailPayload(
        id=tid,
        session_id=tid,
        started_at=header.started_at.isoformat(),
        ended_at=header.ended_at.isoformat(),
        title=title,
        tags=tag_map.get(tid, []),
        message_count=header.message_count,
        messages=messages,
    )
    return success_response(detail.model_dump(mode="json"))


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
) -> JSONResponse:
    """Ingest one Cursor JSONL transcript by path or uuid under configured root."""
    path = _resolved_path_for_request(body)
    result = await transcript_ingest_svc.ingest_transcript(db, str(path))
    return success_response(result.model_dump(mode="json"))


@router.post("/ingest-batch")
async def ingest_transcripts_batch(
    body: TranscriptIngestBatchRequest,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> JSONResponse:
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
