"""Data architecture pillar — medallion tag coverage, schema coverage, data dict freshness.

Sub-score weights (DAMA-DMBOK + medallion architecture):
  35%  medallion tag coverage      (% of brain service .py files carrying a valid medallion tag)
  30%  schema validation coverage  (% of data/*.json files with a Pydantic schema in app/schemas/)
  20%  data dictionary freshness   (docs/data-dictionary.md exists and was updated ≤90 days ago)
  15%  migration discipline        (Alembic migrations present in any DB-backed api)

Bootstrap: neither apis/brain/data/ nor apis/brain/app/schemas/ exists → measured=False.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SCHEMA = "data_architecture_metrics/v1"
_SECONDS_90_DAYS = 90 * 24 * 3600


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _brain_dir() -> Path:
    env = os.environ.get("BRAIN_PACKAGE_ROOT", "").strip()
    if env:
        return Path(env)
    from app.utils.paths import brain_root

    return brain_root()


def _monorepo_root() -> Path:
    env = os.environ.get("BRAIN_REPO_ROOT", "").strip()
    if env:
        return Path(env)
    from app.utils.paths import repo_root

    return repo_root()


# ---------------------------------------------------------------------------
# Sub-score 1: Medallion tag coverage (35%)
# ---------------------------------------------------------------------------


def _medallion_tag_coverage(monorepo_root: Path, brain_dir: Path) -> tuple[float, str]:
    """Return (coverage_0_to_100, notes).

    Runs ``scripts/medallion/check_imports.py --app-dir apis/brain --stats``.
    Parses stdout for the per-layer file counts (tagged) and stderr for
    untagged-file error messages.  Falls back to 50.0 on subprocess failure.
    """
    script = monorepo_root / "scripts" / "medallion" / "check_imports.py"
    if not script.is_file():
        return (50.0, "medallion script not found")
    try:
        cp = subprocess.run(
            [sys.executable, str(script), "--app-dir", "apis/brain", "--stats"],
            cwd=str(monorepo_root),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("data_architecture: medallion check failed — %s", exc)
        return (50.0, f"medallion check unavailable: {exc}")

    # Sum files per layer from "Files by layer:" block in stdout
    tagged_count = 0
    for line in cp.stdout.splitlines():
        m = re.search(r"^\s+(bronze|silver|gold|execution|ops)\s+(\d+)\s*$", line)
        if m:
            tagged_count += int(m.group(2))

    # Untagged files reported in stderr as "error: N .py files ... missing medallion tag"
    untagged_count = 0
    if cp.returncode == 2:
        m2 = re.search(r"error:\s+(\d+)\s+\.py\s+files", cp.stderr)
        if m2:
            untagged_count = int(m2.group(1))

    total = tagged_count + untagged_count
    if total == 0:
        # Script ran but reported nothing — count directly as fallback
        py_files = [f for f in (brain_dir / "app").rglob("*.py") if "__pycache__" not in f.parts]
        total = len(py_files)
        tagged_count = total  # assume clean if script returned no data

    coverage = (tagged_count / max(total, 1)) * 100.0
    return (
        coverage,
        f"medallion: {tagged_count}/{total} tagged ({coverage:.0f}%)",
    )


# ---------------------------------------------------------------------------
# Sub-score 2: Schema validation coverage (30%)
# ---------------------------------------------------------------------------

_SCHEMA_NAME_ALIASES: dict[str, str] = {
    "weekly_retros": "weekly_retro",
    "self_merge_promotions": "self_merge",
    "brain": "brain",
}


def _schema_coverage(brain_dir: Path) -> tuple[float, str]:
    """Return (coverage_0_to_100, notes)."""
    data_dir = brain_dir / "data"
    schemas_dir = brain_dir / "app" / "schemas"

    if not data_dir.is_dir():
        return (0.0, "data dir missing")

    json_stems = {p.stem for p in data_dir.glob("*.json")}
    if not json_stems:
        return (0.0, "no data/*.json files")

    schema_stems = {p.stem for p in schemas_dir.glob("*.py")} if schemas_dir.is_dir() else set()
    # Remove non-schema files
    schema_stems.discard("__init__")
    schema_stems.discard("base")

    def _has_schema(stem: str) -> bool:
        if stem in schema_stems:
            return True
        alias = _SCHEMA_NAME_ALIASES.get(stem)
        if alias and alias in schema_stems:
            return True
        # Fuzzy: try singular (strip trailing 's')
        singular = stem.rstrip("s")
        return singular in schema_stems

    covered = sum(1 for s in json_stems if _has_schema(s))
    total = len(json_stems)
    coverage = (covered / max(total, 1)) * 100.0
    return (
        coverage,
        f"schemas: {covered}/{total} data files have Pydantic schema ({coverage:.0f}%)",
    )


# ---------------------------------------------------------------------------
# Sub-score 3: Data dictionary freshness (20%)
# ---------------------------------------------------------------------------


def _data_dict_freshness(monorepo_root: Path) -> tuple[float, str]:
    """Return (score_0_to_100, notes)."""
    candidates = [
        monorepo_root / "docs" / "data-dictionary.md",
        monorepo_root / "docs" / "DATA_DICTIONARY.md",
    ]
    for path in candidates:
        if path.is_file():
            age_secs = time.time() - path.stat().st_mtime
            if age_secs <= _SECONDS_90_DAYS:
                return (100.0, f"data-dictionary.md fresh ({age_secs / 86400:.0f}d old)")
            return (50.0, f"data-dictionary.md stale ({age_secs / 86400:.0f}d old, >90d)")
    return (0.0, "data-dictionary.md missing")


# ---------------------------------------------------------------------------
# Sub-score 4: Migration discipline (15%)
# ---------------------------------------------------------------------------


def _migration_discipline(monorepo_root: Path) -> tuple[float, str]:
    """Return (score_0_to_100, notes)."""
    alembic_version_dirs = list((monorepo_root / "apis").glob("*/alembic/versions"))
    migration_count = 0
    for vdir in alembic_version_dirs:
        if vdir.is_dir():
            migration_count += len(list(vdir.glob("*.py")))
    if migration_count > 0:
        return (100.0, f"alembic migrations present ({migration_count} version files)")
    return (50.0, "no alembic migrations found (non-DB-only app OK)")


# ---------------------------------------------------------------------------
# Metrics writer
# ---------------------------------------------------------------------------


def _write_metrics(blob: dict[str, Any], brain_dir: Path) -> None:
    out = brain_dir / "data" / "data_architecture_metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Public collector
# ---------------------------------------------------------------------------


def collect() -> tuple[float, bool, str]:
    brain = _brain_dir()
    repo = _monorepo_root()

    data_dir = brain / "data"
    schemas_dir = brain / "app" / "schemas"

    # Bootstrap: neither data dir nor schemas dir exists → nothing to measure
    if not data_dir.is_dir() and not schemas_dir.is_dir():
        return (55.0, False, "bootstrap estimate — data dir and schemas missing")

    try:
        s_medallion, note_medallion = _medallion_tag_coverage(repo, brain)
        s_schema, note_schema = _schema_coverage(brain)
        s_dict, note_dict = _data_dict_freshness(repo)
        s_migration, note_migration = _migration_discipline(repo)

        total_raw = 0.35 * s_medallion + 0.30 * s_schema + 0.20 * s_dict + 0.15 * s_migration
        total = max(0.0, min(100.0, math.floor(total_raw * 10000 + 0.5) / 10000))

        now = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
        blob: dict[str, Any] = {
            "schema": _SCHEMA,
            "computed_at": now,
            "sub_scores": {
                "medallion_tag_coverage": round(s_medallion, 4),
                "schema_validation_coverage": round(s_schema, 4),
                "data_dict_freshness": round(s_dict, 4),
                "migration_discipline": round(s_migration, 4),
            },
            "notes": {
                "medallion": note_medallion,
                "schema": note_schema,
                "data_dict": note_dict,
                "migration": note_migration,
            },
        }
        _write_metrics(blob, brain)

        notes = (
            f"data_architecture: "
            f"medallion={s_medallion:.1f} ({note_medallion}) | "
            f"schema={s_schema:.1f} ({note_schema}) | "
            f"dict={s_dict:.1f} ({note_dict}) | "
            f"migration={s_migration:.1f} ({note_migration})"
        )
        return (total, True, notes)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        logger.warning("data_architecture: unexpected error — %s", exc)
        return (55.0, False, f"data_architecture collector error: {exc}")
