"""Strategic objectives manifest — docs/strategy/OBJECTIVES.yaml.

Founder-authored objectives; Brain loads continuously for decomposition.
File updates use shared/exclusive ``fcntl`` locks for read/write consistency.

medallion: ops
"""

from __future__ import annotations

import fcntl
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from app.schemas.strategic_objectives import StrategicObjective, StrategicObjectivesFile


def objectives_file_path() -> Path:
    override = os.environ.get("BRAIN_OBJECTIVES_YAML")
    if override:
        return Path(override)
    repo_root = os.environ.get("REPO_ROOT")
    if repo_root:
        return Path(repo_root) / "docs" / "strategy" / "OBJECTIVES.yaml"
    return Path(__file__).resolve().parents[4] / "docs" / "strategy" / "OBJECTIVES.yaml"


def _read_text_shared(path: Path) -> str:
    with path.open(encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            return f.read()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def load_strategic_objectives_file(path: Path | None = None) -> StrategicObjectivesFile:
    target = path or objectives_file_path()
    if not target.is_file():
        raise FileNotFoundError(f"Strategic objectives file not found: {target}")
    raw = _read_text_shared(target)
    data = yaml.safe_load(raw)
    return StrategicObjectivesFile.model_validate(data)


def load_objectives() -> list[StrategicObjective]:
    return load_strategic_objectives_file().objectives


def objectives_summary() -> dict:
    file = load_strategic_objectives_file()
    horizons = sorted({o.horizon for o in file.objectives})
    return {
        "count": len(file.objectives),
        "horizons": horizons,
        "oldest_review": file.last_reviewed_at,
        "ids": [o.id for o in file.objectives],
    }


def needs_review() -> list[StrategicObjective]:
    now = datetime.now(UTC)
    due: list[StrategicObjective] = []
    for o in load_objectives():
        written = o.written_at if o.written_at.tzinfo else o.written_at.replace(tzinfo=UTC)
        written = written.astimezone(UTC)
        if written + timedelta(days=o.review_cadence_days) < now:
            due.append(o)
    return due


def mark_reviewed_now(path: Path | None = None) -> None:
    target = path or objectives_file_path()
    if not target.is_file():
        raise FileNotFoundError(f"Strategic objectives file not found: {target}")

    with target.open("r+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            raw = f.read()
            data = yaml.safe_load(raw)
            file_model = StrategicObjectivesFile.model_validate(data)
            updated = file_model.model_copy(
                update={"last_reviewed_at": datetime.now(UTC)},
            )
            payload = updated.model_dump(mode="json", by_alias=True)
            out = yaml.dump(
                payload,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
            f.seek(0)
            f.truncate(0)
            f.write(out)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
