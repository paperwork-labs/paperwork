"""Canonical path resolution for Brain runtime + tests + migrations.

Two deployment layouts must both work:

- **Container** (Dockerfile ``COPY apis/brain/ /app/``): brain code lives at
  ``/app/`` with ``/app/{app,alembic,data,scripts}/...``. The Dockerfile also
  copies a few monorepo files into ``/app/`` (``docs/.doc-drift-baseline.json``,
  ``apps/studio/src/data/{workstreams,tracker-index}.json``,
  ``scripts/reconcile_clerk_dns.py``).
- **Repo** (local dev, tests): brain code lives at ``<repo>/apis/brain/`` and
  the rest of the monorepo is reachable above it.

Hardcoded ``Path(__file__).resolve().parents[N]`` calls — the dominant pattern
in this codebase prior to Wave 0 — are brittle: the index is correct in only
one layout. They produce two failure modes:

1. ``IndexError`` when the file is shallower than ``N+1`` parents
   (R1: probe_failure_dispatcher crashed every minute in prod).
2. Silent no-op when the constructed path doesn't exist
   (R2: migration 014's ``_backfill_from_jsonl`` returned early because the
   computed path resolved to ``/data/agent_dispatch_log.json`` instead of
   ``/app/data/agent_dispatch_log.json``).

This module is the single source of truth. Callers should use:

- :func:`brain_root` → ``/app`` in container, ``<repo>/apis/brain`` in repo
- :func:`brain_data_dir` → ``brain_root() / "data"``
- :func:`brain_scripts_dir` → ``brain_root() / "scripts"`` (only relevant in
  container; in repo, scripts live at the repo root)
- :func:`repo_root` → ``/app`` in container (where monorepo data is mirrored),
  ``<repo>`` in repo (real monorepo root)

Env overrides (highest precedence):
- ``BRAIN_ROOT`` — absolute path to brain code root
- ``BRAIN_DATA_DIR`` — absolute path to brain data dir
- ``REPO_ROOT`` — absolute path to monorepo root

medallion: ops
"""

from __future__ import annotations

import os
from pathlib import Path

# Container layout sentinel: the Dockerfile guarantees ``/app/data`` exists.
_CONTAINER_BRAIN_ROOT = Path("/app")


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    return Path(raw) if raw else None


def _is_container() -> bool:
    """Detect container layout (Dockerfile ``COPY apis/brain/ /app/``).

    The check is cheap: the only reliable shape difference between container
    and repo is that the container's ``/app/`` IS the brain root, while in the
    repo the brain root is ``<repo>/apis/brain/``. We sniff for the presence
    of brain-shaped contents directly under ``/app/``.
    """
    return (_CONTAINER_BRAIN_ROOT / "alembic").is_dir() and (
        _CONTAINER_BRAIN_ROOT / "app"
    ).is_dir()


def brain_root() -> Path:
    """Return the brain code root (``apis/brain/`` in repo, ``/app`` in container)."""
    override = _env_path("BRAIN_ROOT")
    if override is not None:
        return override
    if _is_container():
        return _CONTAINER_BRAIN_ROOT
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "alembic").is_dir() and (parent / "app").is_dir() and parent.name == "brain":
            return parent
    return _CONTAINER_BRAIN_ROOT


def brain_data_dir() -> Path:
    """Return the brain ``data/`` directory."""
    override = _env_path("BRAIN_DATA_DIR")
    if override is not None:
        return override
    return brain_root() / "data"


def brain_scripts_dir() -> Path:
    """Return the directory for brain-bundled scripts (e.g. ``reconcile_clerk_dns.py``).

    In container these live at ``/app/scripts/`` (Dockerfile COPY). In repo
    they live at ``<repo>/scripts/`` (monorepo root, NOT under apis/brain).
    """
    if _is_container():
        return _CONTAINER_BRAIN_ROOT / "scripts"
    return repo_root() / "scripts"


def repo_root() -> Path:
    """Return the monorepo root (``/app`` in container — where mirrored data lives).

    In container the Dockerfile copies a small set of monorepo files into
    ``/app/`` preserving their relative paths, so callers asking for
    ``repo_root() / "apps/studio/src/data/workstreams.json"`` get the right
    file in both layouts.
    """
    override = _env_path("REPO_ROOT")
    if override is not None:
        return override
    if _is_container():
        return _CONTAINER_BRAIN_ROOT
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apis" / "brain").is_dir() and (parent / "apps").is_dir():
            return parent
    return _CONTAINER_BRAIN_ROOT
