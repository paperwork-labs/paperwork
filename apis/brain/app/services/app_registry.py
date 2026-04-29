"""App registry reader for Brain systemwide ops decisions.

medallion: ops
"""

from __future__ import annotations

import fcntl
import json
import os
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

from app.schemas.app_registry import AppEntry, AppRegistry

_T = TypeVar("_T")
_ENV_REGISTRY = "BRAIN_APP_REGISTRY_JSON"


def registry_path() -> Path:
    env = os.environ.get(_ENV_REGISTRY, "").strip()
    if env:
        return Path(env)
    repo_root = os.environ.get("REPO_ROOT", "").strip()
    if repo_root:
        return Path(repo_root) / "apis" / "brain" / "data" / "app_registry.json"
    return Path(__file__).parent.parent.parent / "data" / "app_registry.json"


def _lock_path() -> Path:
    return registry_path().with_suffix(registry_path().suffix + ".lock")


def _with_file_lock_shared(fn: Callable[[], _T]) -> _T:
    lock_path = _lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH)
        try:
            return fn()
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def load_registry() -> AppRegistry:
    """Load and validate app_registry.json with a shared file lock."""

    def _read() -> AppRegistry:
        raw = registry_path().read_text(encoding="utf-8")
        data = json.loads(raw)
        return AppRegistry.model_validate(data)

    return _with_file_lock_shared(_read)


def list_apps() -> list[AppEntry]:
    return load_registry().apps


def app_by_name(name: str) -> AppEntry | None:
    for app in load_registry().apps:
        if app.name == name:
            return app
    return None


def apps_by_type(type: str) -> list[AppEntry]:  # noqa: A002 - API mirrors the registry field.
    return [app for app in load_registry().apps if app.type == type]


def conformance_summary() -> dict[str, object]:
    registry = load_registry()
    apps = registry.apps
    scores = sorted(app.conformance.score for app in apps)
    p95_score = _percentile(scores, 0.95) if scores else 0.0
    low_conformance = [
        {
            "name": app.name,
            "path": app.path,
            "type": app.type,
            "score": app.conformance.score,
            "missing_markers": app.conformance.missing_markers,
        }
        for app in apps
        if app.conformance.score < 0.8
    ]
    return {
        "total": len(apps),
        "by_type": dict(sorted(Counter(app.type for app in apps).items())),
        "p95_score": round(p95_score, 4),
        "low_conformance": low_conformance,
    }


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = percentile * (len(sorted_values) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
