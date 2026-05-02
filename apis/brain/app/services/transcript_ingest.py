"""Ingest Cursor agent JSONL transcripts into `transcript_episodes`.

medallion: ops
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.models.transcript_episode import TranscriptEpisode as TranscriptEpisodeDB
from app.personas.registry import list_specs
from app.schemas.transcript_ingest import IngestResult

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_PR_NUMBER_RE = re.compile(r"(?:PR\s*#|pull/|#)\s*(\d+)", re.IGNORECASE)
_WS_RE = re.compile(r"\b(WS-\d+[a-z]?)\b", re.IGNORECASE)
_PATH_RE = re.compile(
    r"(?:^|\s)[`\"']((?:\.{0,2}/)?(?:[\w.-]+/)+[\w.-]+\.\w+)[`\"']",
)
_FILE_EXT_RE = re.compile(r"\b[\w./-]+\.(?:py|ts|tsx|js|md|mdc|yaml|yml|json)\b")
_DECISION_RE = re.compile(
    r"(?i)(?:decided|decision\b|we will|going with|chose to|resolved to)\s*[:\s]+"
    r"(.{8,400}?)(?:\n\n|\Z|\.)",
)


def resolve_transcript_path(*, root: Path, transcript_id: str) -> Path:
    """Build ``{root}/{uuid}/{uuid}.jsonl`` and ensure it stays under ``root``."""
    tid = transcript_id.strip()
    if not _UUID_RE.fullmatch(tid):
        msg = f"transcript_id must be a UUID string, got {tid!r}"
        raise ValueError(msg)
    root_r = root.expanduser().resolve()
    candidate = (root_r / tid / f"{tid}.jsonl").resolve()
    try:
        candidate.relative_to(root_r)
    except ValueError as exc:
        msg = "Resolved transcript path escapes configured root"
        raise ValueError(msg) from exc
    return candidate


def derive_transcript_id(file_path: str) -> str:
    """Prefer parent/stem UUID match; else use file stem."""
    p = Path(file_path).resolve()
    stem = p.stem
    parent = p.parent.name
    if _UUID_RE.fullmatch(stem) and stem.lower() == parent.lower():
        return stem
    if _UUID_RE.fullmatch(parent):
        return parent
    return stem


def _flatten_blocks(content: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
        elif btype == "tool_use":
            name = block.get("name")
            if isinstance(name, str):
                parts.append(f"[tool:{name}]")
    return "\n".join(parts).strip()


def _event_text(event: dict[str, Any]) -> str:
    msg = event.get("message")
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return _flatten_blocks(content)
    return ""


def _event_ts(event: dict[str, Any]) -> datetime | None:
    for key in ("timestamp", "created_at", "ts"):
        raw = event.get(key)
        if isinstance(raw, str) and raw.strip():
            s = raw.strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(s)
            except ValueError:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
    return None


def _pair_turns(events: list[dict[str, Any]]) -> list[tuple[str, str, datetime | None]]:
    turns: list[tuple[str, str, datetime | None]] = []
    pending_user: str | None = None
    pending_ts: datetime | None = None
    asst_buf: list[str] = []

    def flush_pair() -> None:
        nonlocal pending_user, pending_ts, asst_buf
        if pending_user and asst_buf:
            body = "\n\n".join(asst_buf).strip()
            if body:
                turns.append((pending_user, body, pending_ts))
        pending_user = None
        pending_ts = None
        asst_buf = []

    for ev in events:
        if not isinstance(ev, dict):
            continue
        role = ev.get("role")
        if role == "user":
            flush_pair()
            ut = _event_text(ev)
            if ut:
                pending_user = ut
                pending_ts = _event_ts(ev)
        elif role == "assistant" and pending_user is not None:
            at = _event_text(ev)
            if at:
                asst_buf.append(at)
    flush_pair()
    return turns


def _known_persona_slugs() -> set[str]:
    return {s.name.strip().lower() for s in list_specs() if getattr(s, "name", None)}


def _extract_entities_and_personas(
    blob: str,
    *,
    persona_slugs: set[str],
) -> tuple[list[str], list[str]]:
    found: set[str] = set()
    for m in _PR_NUMBER_RE.finditer(blob):
        found.add(f"PR #{m.group(1)}")
    for m in _WS_RE.finditer(blob):
        found.add(m.group(1).upper())
    for m in _PATH_RE.finditer(blob):
        found.add(m.group(1))
    for m in _FILE_EXT_RE.finditer(blob):
        g0 = m.group(0).strip()
        if "/" in g0 or g0.startswith("."):
            found.add(g0)

    personas_out: set[str] = set()
    lower = blob.lower()
    for slug in persona_slugs:
        if not slug:
            continue
        if re.search(rf"\b{re.escape(slug)}\b", lower):
            personas_out.add(slug)

    return sorted(found), sorted(personas_out)


def _extract_decision(user_text: str, asst_text: str) -> str | None:
    joined = f"{user_text}\n{asst_text}"
    m = _DECISION_RE.search(joined)
    if m:
        return m.group(1).strip()
    return None


def _brief_summary(user_text: str, asst_text: str) -> str:
    u = " ".join(user_text.split())[:180]
    a = " ".join(asst_text.split())[:180]
    if len(asst_text) > 180:
        a = f"{a}…"
    if len(user_text) > 180:
        u = f"{u}…"
    return f"User: {u} · Assistant: {a}"


async def transcript_already_ingested(db: AsyncSession, transcript_id: str) -> bool:
    stmt = (
        select(func.count())
        .select_from(TranscriptEpisodeDB)
        .where(
            TranscriptEpisodeDB.transcript_id == transcript_id,
        )
    )
    n = (await db.execute(stmt)).scalar_one()
    return int(n or 0) > 0


async def ingest_transcript(db: AsyncSession, file_path: str) -> IngestResult:
    """Parse ``file_path`` JSONL, chunk user→assistant turns, persist rows.

    Skips the file when any row already exists for the derived ``transcript_id``.
    """
    path = Path(file_path).expanduser()
    errors: list[str] = []
    transcript_id = derive_transcript_id(str(path))

    if not path.is_file():
        return IngestResult(
            transcript_id=transcript_id,
            episodes_created=0,
            entities_extracted=[],
            errors=[f"Not a file: {path}"],
        )

    if await transcript_already_ingested(db, transcript_id):
        return IngestResult(
            transcript_id=transcript_id,
            episodes_created=0,
            entities_extracted=[],
            errors=[],
            skipped=True,
        )

    events: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"line {line_no}: JSON decode: {exc}")
                    continue
                if isinstance(obj, dict) and obj.get("role") in ("user", "assistant"):
                    events.append(obj)
    except OSError as exc:
        return IngestResult(
            transcript_id=transcript_id,
            episodes_created=0,
            entities_extracted=[],
            errors=[f"Read error: {exc}"],
        )

    turns = _pair_turns(events)
    persona_known = _known_persona_slugs()
    all_entities: set[str] = set()

    for idx, (user_text, asst_text, ts) in enumerate(turns):
        ents, pers = _extract_entities_and_personas(
            f"{user_text}\n{asst_text}",
            persona_slugs=persona_known,
        )
        all_entities.update(ents)
        decision = _extract_decision(user_text, asst_text)
        meta: dict[str, Any] = {}
        if decision:
            meta["decision"] = decision
        if ts is not None:
            meta["turn_timestamp"] = ts.isoformat()
        row = TranscriptEpisodeDB(
            transcript_id=transcript_id,
            turn_index=idx,
            user_message=user_text,
            assistant_message=asst_text,
            summary=_brief_summary(user_text, asst_text),
            entities=list(ents),
            persona_slugs=list(pers),
            episode_metadata=meta,
        )
        db.add(row)

    await db.commit()

    return IngestResult(
        transcript_id=transcript_id,
        episodes_created=len(turns),
        entities_extracted=sorted(all_entities),
        errors=errors,
    )


def discover_jsonl_files(directory: str) -> list[Path]:
    """Return sorted ``.jsonl`` files under ``directory`` (recursive)."""
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in root.rglob("*.jsonl"):
        if p.is_file():
            out.append(p)
    return sorted(out)
