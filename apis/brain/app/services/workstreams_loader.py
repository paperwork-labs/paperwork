"""Load and parse ``apps/studio/src/data/workstreams.json`` from the monorepo checkout.

medallion: ops
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from app.schemas.workstream import WorkstreamsFile

_WORKSTREAMS_REL = Path("apps/studio/src/data/workstreams.json")

_cache_file: WorkstreamsFile | None = None
_cache_at: float = 0.0
_CACHE_TTL_SEC = 60.0


def _repo_root() -> Path:
    """Best-effort root of the monorepo checkout where Brain's ``app/`` lives.

    In dev: ``apis/brain/app/services/this_file.py`` → ``parents[4]`` is the
    monorepo root. In the Brain Docker image the layout is flat (``/app/app/``),
    so ``parents[4]`` does NOT exist and the old code raised ``IndexError`` at
    module import. We now honour ``$REPO_ROOT``, then walk parents looking for
    ``apps/studio/src/data/workstreams.json``, then finally fall back to ``/app``
    (the container WORKDIR — see ``apis/brain/Dockerfile``).
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


def load_workstreams_file(*, bypass_cache: bool = False) -> WorkstreamsFile:
    """Read JSON from disk; memoised per process for 60 seconds unless ``bypass_cache``."""
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
