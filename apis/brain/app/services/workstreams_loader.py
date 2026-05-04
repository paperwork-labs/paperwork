"""Load workstreams from Brain DB (epics) or legacy ``workstreams.json``.

medallion: ops
"""

from __future__ import annotations

import json
import os
import re
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.models.epic_hierarchy import Epic
from app.schemas.workstream import Workstream, WorkstreamsFile

_TRACK_RE = re.compile(r"^[A-Z][0-9A-Z]{0,2}$")
_WORKSTREAMS_REL = Path("apps/studio/src/data/workstreams.json")

# Loose slug shape used to coerce non-conforming brief_tag values into the
# Workstream schema's permitted shape. Schema allows bare slugs and prefixed
# slugs; this helper just makes sure we never write whitespace/punctuation
# garbage.
_SLUG_SCRUB_RE = re.compile(r"[^a-z0-9-]+")

_cache_file: WorkstreamsFile | None = None
_cache_at: float = 0.0
_CACHE_TTL_SEC = 60.0


def _repo_root() -> Path:
    """Best-effort root of the monorepo checkout where Brain's ``app/`` lives.

    Kept for legacy ``load_workstreams_file`` and path helpers elsewhere.
    """
    env = os.environ.get("REPO_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / _WORKSTREAMS_REL).exists():
            return parent
    return Path("/app")


def workstreams_json_path() -> Path:
    return _repo_root() / _WORKSTREAMS_REL


def _dt_activity_iso(dt: datetime | None) -> str:
    """RFC3339 Zulu for ``Workstream.last_activity`` — schema requires a string."""
    d = dt or datetime(1970, 1, 1, tzinfo=UTC)
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def _dt_dispatch_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    d = dt
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def _blockers_as_str_list(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        out: list[str] = []
        for x in raw:
            s = str(x).strip()
            if len(s) >= 3:
                out.append(s)
        return out
    if isinstance(raw, dict):
        out2: list[str] = []
        for k, v in raw.items():
            s = f"{k}: {v}" if v not in (None, "") else str(k)
            if len(s) >= 3:
                out2.append(s)
        return out2
    return []


def _epic_status_to_workstream(status: str) -> str:
    """Map DB epic status to ``Workstream`` status (dispatch layer expects pending/in_progress)."""
    s = (status or "").strip().lower()
    if s == "active":
        return "pending"
    return "in_progress"


def _owner_slug_to_workstream_owner(slug: str) -> str:
    s = (slug or "").strip().lower()
    if s == "brain":
        return "brain"
    if s == "opus":
        return "opus"
    return "founder"


def _safe_title(raw: str, epic_id: str) -> str:
    t = (raw or "").strip() or epic_id
    if len(t) < 3:
        t = f"{t} ({epic_id})"
    return t[:100]


_WORKSTREAM_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,99}$")


def _safe_workstream_id(epic_id: str) -> str:
    """Return the epic id verbatim if it satisfies the schema, else a scrubbed slug.

    The Workstream schema accepts both legacy ``WS-NN-...`` ids and DB-sourced
    epic ids (``epic-ws-82-studio-hq``). This helper just guards against
    pathological inputs (whitespace, leading digits, empty strings) so we
    never raise ``ValidationError`` from the loader.
    """
    raw = (epic_id or "").strip()
    if _WORKSTREAM_ID_RE.match(raw):
        return raw
    slug = _SLUG_SCRUB_RE.sub("-", raw.lower()).strip("-") or "epic"
    return f"epic-{slug}" if not slug[:1].isalpha() else slug


def _safe_brief_tag(raw: object) -> str:
    """Coerce arbitrary ``epic.brief_tag`` values into a schema-valid slug.

    The schema accepts bare slugs (``filefree``) and prefixed slugs
    (``track:filefree``). We pass conforming values through unchanged and
    scrub anything else into a bare slug.
    """
    if not isinstance(raw, str):
        return "general"
    s = raw.strip().lower()
    if not s:
        return "general"
    if ":" in s:
        prefix, _, tail = s.partition(":")
        prefix_clean = _SLUG_SCRUB_RE.sub("-", prefix).strip("-")
        tail_clean = _SLUG_SCRUB_RE.sub("-", tail).strip("-")
        if prefix_clean and tail_clean:
            return f"{prefix_clean}:{tail_clean}"
        return tail_clean or prefix_clean or "general"
    return _SLUG_SCRUB_RE.sub("-", s).strip("-") or "general"


def epic_to_workstream(epic: Epic, *, priority_rank: int) -> Workstream:
    """Map one ``Epic`` row to legacy ``Workstream`` shape (stable unique ``priority_rank``)."""
    md: dict[str, Any] = epic.metadata_ or {}
    track_raw = str(md.get("track", "Z")).strip().upper()[:3] or "Z"
    track = track_raw if _TRACK_RE.match(track_raw) else "Z"
    wf_raw = md.get("github_actions_workflow")
    github_wf = str(wf_raw).strip() if wf_raw not in (None, "") else "agent-sprint-runner"
    est = md.get("estimated_pr_count", 1)
    try:
        est_pr = int(est) if est is not None else 1
    except (TypeError, ValueError):
        est_pr = 1
    if est_pr <= 0:
        est_pr = 1

    return Workstream(
        id=_safe_workstream_id(epic.id),
        title=_safe_title(epic.title, epic.id),
        track=track,
        priority=priority_rank,
        status=_epic_status_to_workstream(epic.status),
        percent_done=epic.percent_done,
        owner=_owner_slug_to_workstream_owner(epic.owner_employee_slug),
        brief_tag=_safe_brief_tag(epic.brief_tag),
        blockers=_blockers_as_str_list(epic.blockers),
        last_pr=None,
        last_activity=_dt_activity_iso(epic.last_activity),
        last_dispatched_at=_dt_dispatch_iso(epic.last_dispatched_at),
        notes=(epic.description or "")[:500],
        estimated_pr_count=est_pr,
        github_actions_workflow=github_wf,
        related_plan=epic.related_plan,
    )


async def load_epics_from_db(db: AsyncSession) -> WorkstreamsFile:
    """Load ``in_progress`` and ``active`` epics and map them to ``WorkstreamsFile``."""
    stmt = (
        select(Epic)
        .where(Epic.status.in_(("in_progress", "active")))
        .order_by(Epic.priority.asc(), Epic.id.asc())
    )
    rows = list((await db.scalars(stmt)).all())
    updated = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    workstreams = [epic_to_workstream(e, priority_rank=i) for i, e in enumerate(rows)]
    return WorkstreamsFile(version=1, updated=updated, workstreams=workstreams)


def load_workstreams_file(*, bypass_cache: bool = False) -> WorkstreamsFile:
    """Deprecated: use ``load_epics_from_db``. Reads JSON from disk if the file still exists."""
    warnings.warn(
        "load_workstreams_file is deprecated; hierarchy lives in Brain DB "
        "(use load_epics_from_db).",
        DeprecationWarning,
        stacklevel=2,
    )
    global _cache_file, _cache_at
    now = time.monotonic()
    if not bypass_cache and _cache_file is not None and (now - _cache_at) < _CACHE_TTL_SEC:
        return _cache_file

    path = workstreams_json_path()
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    parsed = WorkstreamsFile.model_validate(data)
    _cache_file = parsed
    _cache_at = now
    return parsed


def invalidate_workstreams_cache() -> None:
    global _cache_file, _cache_at
    _cache_file = None
    _cache_at = 0.0
