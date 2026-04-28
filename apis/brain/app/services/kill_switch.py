"""Filesystem kill switch: when ``data/brain_paused.flag`` is non-empty, Brain schedulers no-op.

medallion: ops
"""

from __future__ import annotations

import os
from pathlib import Path


def brain_paused_flag_path() -> Path:
    """Path to the pause flag file (override with ``BRAIN_PAUSED_FLAG_PATH`` for tests)."""
    override = (os.environ.get("BRAIN_PAUSED_FLAG_PATH") or "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent.parent / "data" / "brain_paused.flag"


def is_brain_paused() -> bool:
    """True when the flag file exists and has non-whitespace content."""
    path = brain_paused_flag_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(raw.strip())


def reason() -> str | None:
    """First line of the flag file when paused; otherwise ``None``."""
    if not is_brain_paused():
        return None
    path = brain_paused_flag_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    first = raw.splitlines()[0] if raw.splitlines() else ""
    return first if first.strip() else None
