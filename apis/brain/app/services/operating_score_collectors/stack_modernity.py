"""Stack modernity pillar — quarterly STACK_AUDIT markdown (KEEP / UPGRADE / REPLACE).

Parses ``docs/STACK_AUDIT_2026-Q2.md`` (override ``BRAIN_STACK_AUDIT_MD``).
Penalizes stale audits (>90 d mtime) and audits older than WS-49 ``last_activity``.

medallion: ops
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import UTC, date, datetime
from pathlib import Path

_BOOTSTRAP = (65.0, False, "stack audit doc not found — run WS-49")

_KEEP_RE = re.compile(r"(?mi)^\s*[-*]?\s*KEEP:\s*(\d+)")
_UPGRADE_RE = re.compile(r"(?mi)^\s*[-*]?\s*UPGRADE:\s*(\d+)")
_REPLACE_RE = re.compile(r"(?mi)^\s*[-*]?\s*REPLACE:\s*(\d+)")
_AUDIT_DATE_RE = re.compile(r"\*\*Audit date:\*\*\s*(\d{4}-\d{2}-\d{2})")


def _repo_root() -> Path | None:
    env = os.environ.get("BRAIN_REPO_ROOT", "").strip()
    if env:
        p = Path(env)
        return p if p.is_dir() else None
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / "apps").is_dir() and (anc / "docs").is_dir():
            return anc
    return None


def _audit_doc_path() -> Path | None:
    env = os.environ.get("BRAIN_STACK_AUDIT_MD", "").strip()
    if env:
        return Path(env)
    root = _repo_root()
    if root is None:
        return None
    return root / "docs" / "STACK_AUDIT_2026-Q2.md"


def _parse_keep_upgrade_replace(text: str) -> tuple[int, int, int] | None:
    mk = _KEEP_RE.search(text)
    mu = _UPGRADE_RE.search(text)
    mr = _REPLACE_RE.search(text)
    if mk is None or mu is None or mr is None:
        return None
    return (int(mk.group(1)), int(mu.group(1)), int(mr.group(1)))


def _parse_audit_claimed_date(text: str) -> date | None:
    m = _AUDIT_DATE_RE.search(text)
    if m is None:
        return None
    raw = m.group(1).strip()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=UTC).date()
    except ValueError:
        return None


def _ws49_last_activity_date(repo_root: Path) -> date | None:
    ws_path = repo_root / "apps" / "studio" / "src" / "data" / "workstreams.json"
    if not ws_path.is_file():
        return None
    try:
        blob = json.loads(ws_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    rows = blob.get("workstreams")
    if not isinstance(rows, list):
        return None
    for ws in rows:
        if not isinstance(ws, dict):
            continue
        if ws.get("id") != "WS-49-stack-truth-audit":
            continue
        la = ws.get("last_activity")
        if not isinstance(la, str):
            return None
        txt = la.strip()
        if txt.endswith("Z"):
            txt = txt[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(txt)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).date()
    return None


def collect() -> tuple[float, bool, str]:
    ap = _audit_doc_path()
    if ap is None or not ap.is_file():
        return _BOOTSTRAP

    try:
        body = ap.read_text(encoding="utf-8")
    except OSError:
        return _BOOTSTRAP

    triple = _parse_keep_upgrade_replace(body)
    if triple is None:
        return _BOOTSTRAP

    keep, upgrade, replace = triple
    denom = keep + upgrade + replace
    if denom <= 0:
        return _BOOTSTRAP

    score = float(keep * 100 + upgrade * 50 + replace * 0) / float(denom)

    now = datetime.now(tz=UTC)
    mtime_dt = datetime.fromtimestamp(ap.stat().st_mtime, tz=UTC)
    stale_days = max(0, int((now - mtime_dt).total_seconds() // 86400))

    penalty = 0.0
    extras: list[str] = []

    if stale_days > 90:
        penalty += 15.0
        extras.append(f"(audit stale: {stale_days} days old; trigger refresh)")

    rr = _repo_root()
    audit_date = _parse_audit_claimed_date(body)
    ws49_d = _ws49_last_activity_date(rr) if rr is not None else None
    if ws49_d is not None and audit_date is not None and audit_date < ws49_d:
        penalty += 15.0
        extras.append("(audit older than WS-49 last_activity — refresh audit doc)")

    note_tail = ""
    if stale_days > 75:
        note_tail = f" audit_stale_days={stale_days}"

    score = max(0.0, min(100.0, score - penalty))
    score = math.floor(score * 10000 + 0.5) / 10000

    fname = ap.name
    notes = (
        f"from {fname} ({keep} KEEP / {upgrade} UPGRADE / {replace} REPLACE)"
        + ((" " + " ".join(extras)) if extras else "")
        + note_tail
    )
    return (score, True, notes.strip())
