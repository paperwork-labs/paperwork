"""Decommissions service — load and query the decommissions data file (WS-48).

The canonical data file is ``apis/brain/data/decommissions.json``.
All mutations happen via direct file edits (or the decommission scripts under
``scripts/decommission/``); this service is read-only.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path

from app.schemas.decommissions import DecommissionEntry, DecommissionsFile

logger = logging.getLogger(__name__)

_DEFAULT_DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "decommissions.json"


def _data_path() -> Path:
    env = os.environ.get("DECOMMISSIONS_DATA_PATH", "").strip()
    return Path(env) if env else _DEFAULT_DATA_PATH


@lru_cache(maxsize=1)
def _load_cached(mtime: float) -> DecommissionsFile:  # noqa: ARG001
    raw = _data_path().read_text(encoding="utf-8")
    data = json.loads(raw)
    return DecommissionsFile.model_validate(data)


def load_decommissions_file(*, bypass_cache: bool = False) -> DecommissionsFile:
    """Load and parse ``decommissions.json``.

    Uses an mtime-keyed ``lru_cache`` so repeated calls within a request
    context don't re-read from disk, but a changed file on disk is always
    picked up within the next call.

    Parameters
    ----------
    bypass_cache:
        When ``True``, clears the lru_cache before loading so the freshest
        on-disk state is always returned (used by admin endpoints).
    """
    path = _data_path()
    if not path.exists():
        logger.warning("decommissions.json not found at %s; returning empty file", path)
        return DecommissionsFile(entries=[])

    if bypass_cache:
        _load_cached.cache_clear()

    mtime = path.stat().st_mtime
    return _load_cached(mtime)


def list_entries(
    *,
    status: str | None = None,
    bypass_cache: bool = False,
) -> list[DecommissionEntry]:
    """Return all decommission entries, optionally filtered by status.

    Parameters
    ----------
    status:
        One of ``"proposed"``, ``"scheduled"``, ``"done"``.  ``None`` = all.
    bypass_cache:
        Forwarded to :func:`load_decommissions_file`.
    """
    file = load_decommissions_file(bypass_cache=bypass_cache)
    entries = file.entries
    if status is not None:
        entries = [e for e in entries if e.status == status]
    return entries


def get_entry(entry_id: str, *, bypass_cache: bool = False) -> DecommissionEntry | None:
    """Return a single entry by ``id``, or ``None`` if not found."""
    for entry in list_entries(bypass_cache=bypass_cache):
        if entry.id == entry_id:
            return entry
    return None
