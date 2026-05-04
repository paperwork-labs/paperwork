"""Read-side aggregation for `transcript_episodes` (grouped by transcript_id).

medallion: ops
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transcript_episode import TranscriptEpisode

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _AggRow:
    transcript_id: str
    message_count: int
    started_at: datetime
    ended_at: datetime
    title_summary: str | None
    title_user_hint: str


def transcript_title_from_turn(*, summary: str | None, user_message: str) -> str:
    s = (summary or "").strip()
    if s:
        return s
    text = user_message.strip().replace("\n", " ")
    if not text:
        return "(no title)"
    suf = "…" if len(text) > 120 else ""
    return text[:120] + suf


def encode_list_cursor(*, ended_at: datetime, transcript_id: str) -> str:
    payload = {"ended_at": ended_at.isoformat(), "tid": transcript_id}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_list_cursor(cursor: str) -> tuple[datetime, str]:
    pad = "=" * (-len(cursor) % 4)
    try:
        decoded = base64.urlsafe_b64decode(cursor + pad).decode()
        obj = json.loads(decoded)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        msg = "Invalid cursor"
        raise ValueError(msg) from exc
    if not isinstance(obj, dict):
        msg = "Invalid cursor"
        raise ValueError(msg)
    tid = obj.get("tid")
    ended_raw = obj.get("ended_at")
    if not isinstance(tid, str) or not isinstance(ended_raw, str):
        msg = "Invalid cursor"
        raise ValueError(msg)
    tid_stripped = tid.strip()
    s = ended_raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        ended_dt = datetime.fromisoformat(s)
    except ValueError as exc:
        msg = "Invalid cursor"
        raise ValueError(msg) from exc
    if ended_dt.tzinfo is None:
        msg = "Invalid cursor"
        raise ValueError(msg)
    return ended_dt, tid_stripped


def is_transcript_uuid(value: str) -> bool:
    return bool(_UUID_RE.fullmatch(value.strip()))


async def load_tags_for_transcripts(
    db: AsyncSession,
    transcript_ids: list[str],
) -> dict[str, list[str]]:
    if not transcript_ids:
        return {}
    tag_stmt = select(TranscriptEpisode.transcript_id, TranscriptEpisode.persona_slugs).where(
        TranscriptEpisode.transcript_id.in_(transcript_ids)
    )
    rows = (await db.execute(tag_stmt)).all()
    acc: dict[str, set[str]] = {tid: set() for tid in transcript_ids}
    for tid, slugs in rows:
        if not isinstance(slugs, list):
            continue
        bucket = acc.setdefault(str(tid), set())
        for item in slugs:
            if isinstance(item, str) and item.strip():
                bucket.add(item.strip())
    return {k: sorted(v) for k, v in acc.items()}


async def list_transcript_sessions(
    db: AsyncSession,
    *,
    limit: int,
    cursor: str | None,
) -> tuple[list[_AggRow], str | None]:
    ranked_inner = (
        select(
            TranscriptEpisode.transcript_id.label("tid"),
            TranscriptEpisode.summary,
            TranscriptEpisode.user_message,
            func.row_number()
            .over(
                partition_by=TranscriptEpisode.transcript_id,
                order_by=TranscriptEpisode.turn_index.asc(),
            )
            .label("rn"),
        )
    ).subquery()

    first_turn = (
        select(
            ranked_inner.c.tid,
            ranked_inner.c.summary,
            ranked_inner.c.user_message,
        ).where(ranked_inner.c.rn == 1)
    ).subquery()

    agg = (
        select(
            TranscriptEpisode.transcript_id.label("tid"),
            func.count().label("message_count"),
            func.min(TranscriptEpisode.ingested_at).label("started_at"),
            func.max(TranscriptEpisode.ingested_at).label("ended_at"),
        ).group_by(TranscriptEpisode.transcript_id)
    ).subquery()

    stmt = (
        select(
            agg.c.tid,
            agg.c.message_count,
            agg.c.started_at,
            agg.c.ended_at,
            first_turn.c.summary.label("title_summary"),
            first_turn.c.user_message.label("title_user_hint"),
        )
        .select_from(
            agg.join(first_turn, first_turn.c.tid == agg.c.tid),
        )
        .order_by(agg.c.ended_at.desc(), agg.c.tid.desc())
    )

    if cursor:
        cursor_ended, cursor_tid = decode_list_cursor(cursor)
        stmt = stmt.where(
            (agg.c.ended_at < cursor_ended)
            | ((agg.c.ended_at == cursor_ended) & (agg.c.tid < cursor_tid))
        )

    stmt = stmt.limit(limit + 1)
    result_rows = (await db.execute(stmt)).all()

    has_more = len(result_rows) > limit
    page_rows = result_rows[:limit]

    out: list[_AggRow] = []
    for tid, mc, started_at, ended_at, summ, uhint in page_rows:
        out.append(
            _AggRow(
                transcript_id=str(tid),
                message_count=int(mc or 0),
                started_at=started_at,
                ended_at=ended_at,
                title_summary=summ if isinstance(summ, str) else None,
                title_user_hint=str(uhint or ""),
            )
        )

    next_cursor: str | None = None
    if has_more and out:
        last = out[-1]
        next_cursor = encode_list_cursor(ended_at=last.ended_at, transcript_id=last.transcript_id)

    return out, next_cursor


async def transcript_session_header(db: AsyncSession, transcript_id: str) -> _AggRow | None:
    agg_stmt = select(
        func.count().label("message_count"),
        func.min(TranscriptEpisode.ingested_at).label("started_at"),
        func.max(TranscriptEpisode.ingested_at).label("ended_at"),
    ).where(TranscriptEpisode.transcript_id == transcript_id)
    agg_row = (await db.execute(agg_stmt)).one()

    message_count = int(agg_row.message_count or 0)
    if message_count == 0:
        return None

    started_at = agg_row.started_at
    ended_at = agg_row.ended_at
    if started_at is None or ended_at is None:
        return None

    first_stmt = (
        select(TranscriptEpisode.summary, TranscriptEpisode.user_message)
        .where(TranscriptEpisode.transcript_id == transcript_id)
        .order_by(TranscriptEpisode.turn_index.asc())
        .limit(1)
    )
    first = (await db.execute(first_stmt)).one()
    summ, uhint = first

    return _AggRow(
        transcript_id=transcript_id,
        message_count=message_count,
        started_at=started_at,
        ended_at=ended_at,
        title_summary=summ if isinstance(summ, str) else None,
        title_user_hint=str(uhint or ""),
    )


async def load_transcript_messages(db: AsyncSession, transcript_id: str) -> list[dict[str, Any]]:
    stmt = (
        select(
            TranscriptEpisode.turn_index,
            TranscriptEpisode.user_message,
            TranscriptEpisode.assistant_message,
            TranscriptEpisode.summary,
            TranscriptEpisode.ingested_at,
        )
        .where(TranscriptEpisode.transcript_id == transcript_id)
        .order_by(TranscriptEpisode.turn_index.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "turn_index": int(r.turn_index),
            "user_message": str(r.user_message),
            "assistant_message": str(r.assistant_message),
            "summary": r.summary,
            "ingested_at": r.ingested_at,
        }
        for r in rows
    ]
