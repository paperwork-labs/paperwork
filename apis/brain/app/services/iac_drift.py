"""IaC drift detection against canonical provider state.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import yaml

from app.schemas.iac_state import VercelStateFile

logger = logging.getLogger(__name__)

DriftClassification = Literal["ui-only", "semantic"]
DriftKind = Literal["added", "removed", "changed"]

_RUNS_ENV = "BRAIN_IAC_DRIFT_RUNS_JSON"
_ALERTS_ENV = "BRAIN_IAC_DRIFT_ALERTS_JSON"
_STATE_DIR_ENV = "BRAIN_IAC_STATE_DIR"
_FOLLOW_UP = "WS-42 follow-up: implement after Vercel proof-of-life lands"
_VERCEL_ENV_KEYS = ("key", "target", "value", "type", "gitBranch")


@dataclass(frozen=True)
class DriftItem:
    surface: str
    key: str
    canonical: dict[str, Any] | None
    live: dict[str, Any] | None
    kind: DriftKind


class DriftSurface(Protocol):
    name: str

    def load_canonical(self) -> dict[str, Any]:
        """Load and validate canonical state for this surface."""

    def fetch_live(self) -> dict[str, Any]:
        """Fetch live provider state."""

    def compute_drift(self, canonical: dict[str, Any], live: dict[str, Any]) -> list[DriftItem]:
        """Return concrete drift items."""

    def classify(self, item: DriftItem) -> DriftClassification:
        """Classify a drift item for reconcile policy."""


def _repo_root() -> Path:
    env = os.environ.get("REPO_ROOT", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[4]


def _state_dir() -> Path:
    env = os.environ.get(_STATE_DIR_ENV, "").strip()
    if env:
        return Path(env)
    return _repo_root() / "infra" / "state"


def _brain_data_dir() -> Path:
    return _repo_root() / "apis" / "brain" / "data"


def runs_path() -> Path:
    env = os.environ.get(_RUNS_ENV, "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "drift_check_runs.json"


def alerts_path() -> Path:
    env = os.environ.get(_ALERTS_ENV, "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "drift_alerts.json"


def _rfc3339z(dt: datetime | None = None) -> str:
    now = dt or datetime.now(UTC)
    return now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        msg = f"{path} must contain a JSON array"
        raise ValueError(msg)
    return [item for item in raw if isinstance(item, dict)]


def _write_json_array(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _append_json_row(path: Path, row: dict[str, Any]) -> None:
    rows = _load_json_array(path)
    rows.append(row)
    _write_json_array(path, rows)


def _target_key(target: Any) -> str:
    if isinstance(target, list):
        return ",".join(sorted(str(v) for v in target))
    if target is None:
        return "all"
    return str(target)


def _normalize_env(env: dict[str, Any]) -> dict[str, Any]:
    normalized = {k: env[k] for k in _VERCEL_ENV_KEYS if k in env and env[k] is not None}
    if "name" in env and "key" not in normalized:
        normalized["key"] = env["name"]
    return normalized


def _vercel_env_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if isinstance(data.get("projects"), list):
        projects = data["projects"]
    elif isinstance(data.get("envs"), list):
        projects = [{"name": data.get("project", "default"), "envs": data["envs"]}]
    else:
        projects = []

    out: dict[str, dict[str, Any]] = {}
    for project in projects:
        if not isinstance(project, dict):
            continue
        project_name = str(project.get("name") or project.get("id") or "default")
        envs = project.get("envs") or project.get("env") or []
        if not isinstance(envs, list):
            continue
        for raw_env in envs:
            if not isinstance(raw_env, dict):
                continue
            env = _normalize_env(raw_env)
            key = env.get("key")
            if not key:
                continue
            drift_key = f"{project_name}:{_target_key(env.get('target'))}:{key}"
            out[drift_key] = env
    return out


def _strip_comment_lines(value: str) -> str:
    return "\n".join(
        line for line in value.splitlines() if not line.strip().startswith("#")
    ).strip()


def _is_cosmetic_value_change(canonical: str, live: str) -> bool:
    if canonical.strip() == live.strip():
        return True
    return _strip_comment_lines(canonical) == _strip_comment_lines(live)


class VercelEnvSurface:
    name = "vercel"

    def __init__(self, state_path: Path | None = None) -> None:
        self.state_path = state_path or (_state_dir() / "vercel.yaml")

    def load_canonical(self) -> dict[str, Any]:
        if not self.state_path.exists():
            msg = f"Missing canonical Vercel state file: {self.state_path}"
            raise FileNotFoundError(msg)
        data = yaml.safe_load(self.state_path.read_text(encoding="utf-8"))
        state = VercelStateFile.model_validate(data)
        return state.model_dump(mode="json")

    def fetch_live(self) -> dict[str, Any]:
        result = subprocess.run(
            ["vercel", "env", "ls", "--json"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(result.stdout)
        if isinstance(payload, list):
            return {"projects": [{"name": "default", "envs": payload}]}
        if not isinstance(payload, dict):
            msg = "vercel env ls --json returned a non-object payload"
            raise ValueError(msg)
        if "projects" in payload or "envs" in payload:
            return payload
        return {
            "projects": [
                {"name": payload.get("project", "default"), "envs": payload.get("envs", [])}
            ]
        }

    def compute_drift(self, canonical: dict[str, Any], live: dict[str, Any]) -> list[DriftItem]:
        canonical_envs = _vercel_env_map(canonical)
        live_envs = _vercel_env_map(live)
        drift: list[DriftItem] = []
        for key in sorted(canonical_envs.keys() - live_envs.keys()):
            drift.append(
                DriftItem(
                    surface=self.name,
                    key=key,
                    canonical=canonical_envs[key],
                    live=None,
                    kind="removed",
                )
            )
        for key in sorted(live_envs.keys() - canonical_envs.keys()):
            drift.append(
                DriftItem(
                    surface=self.name,
                    key=key,
                    canonical=None,
                    live=live_envs[key],
                    kind="added",
                )
            )
        for key in sorted(canonical_envs.keys() & live_envs.keys()):
            canonical_row = canonical_envs[key]
            live_row = live_envs[key]
            if canonical_row != live_row:
                drift.append(
                    DriftItem(
                        surface=self.name,
                        key=key,
                        canonical=canonical_row,
                        live=live_row,
                        kind="changed",
                    )
                )
        return drift

    def classify(self, item: DriftItem) -> DriftClassification:
        if item.kind in {"added", "removed"}:
            return "semantic"
        canonical = item.canonical or {}
        live = item.live or {}
        canonical_value = canonical.get("value")
        live_value = live.get("value")
        if (
            set(canonical.keys()) == set(live.keys())
            and canonical.keys() <= {"key", "target", "value", "type", "gitBranch"}
            and isinstance(canonical_value, str)
            and isinstance(live_value, str)
            and {k: v for k, v in canonical.items() if k != "value"}
            == {k: v for k, v in live.items() if k != "value"}
            and _is_cosmetic_value_change(canonical_value, live_value)
        ):
            return "ui-only"
        return "semantic"


class CloudflareDNSSurface:
    name = "cloudflare"

    def load_canonical(self) -> dict[str, Any]:
        raise NotImplementedError(_FOLLOW_UP)

    def fetch_live(self) -> dict[str, Any]:
        raise NotImplementedError(_FOLLOW_UP)

    def compute_drift(self, canonical: dict[str, Any], live: dict[str, Any]) -> list[DriftItem]:
        raise NotImplementedError(_FOLLOW_UP)

    def classify(self, item: DriftItem) -> DriftClassification:
        raise NotImplementedError(_FOLLOW_UP)


class RenderEnvSurface:
    name = "render"

    def load_canonical(self) -> dict[str, Any]:
        raise NotImplementedError(_FOLLOW_UP)

    def fetch_live(self) -> dict[str, Any]:
        raise NotImplementedError(_FOLLOW_UP)

    def compute_drift(self, canonical: dict[str, Any], live: dict[str, Any]) -> list[DriftItem]:
        raise NotImplementedError(_FOLLOW_UP)

    def classify(self, item: DriftItem) -> DriftClassification:
        raise NotImplementedError(_FOLLOW_UP)


class ClerkConfigSurface:
    name = "clerk"

    def load_canonical(self) -> dict[str, Any]:
        raise NotImplementedError(_FOLLOW_UP)

    def fetch_live(self) -> dict[str, Any]:
        raise NotImplementedError(_FOLLOW_UP)

    def compute_drift(self, canonical: dict[str, Any], live: dict[str, Any]) -> list[DriftItem]:
        raise NotImplementedError(_FOLLOW_UP)

    def classify(self, item: DriftItem) -> DriftClassification:
        raise NotImplementedError(_FOLLOW_UP)


def enabled_surfaces() -> list[DriftSurface]:
    raw = os.environ.get("BRAIN_IAC_DRIFT_SURFACES", "vercel")
    names = {part.strip().lower() for part in raw.split(",") if part.strip()}
    surfaces: list[DriftSurface] = []
    if "vercel" in names:
        surfaces.append(VercelEnvSurface())
    if "cloudflare" in names:
        surfaces.append(CloudflareDNSSurface())
    if "render" in names:
        surfaces.append(RenderEnvSurface())
    if "clerk" in names:
        surfaces.append(ClerkConfigSurface())
    return surfaces


def _record_semantic_alerts(run_at: str, items: list[DriftItem]) -> None:
    if not items:
        return
    alerts = _load_json_array(alerts_path())
    for item in items:
        logger.critical(
            "iac drift semantic alert: surface=%s key=%s kind=%s", item.surface, item.key, item.kind
        )
        alerts.append(
            {
                "surface": item.surface,
                "key": item.key,
                "kind": item.kind,
                "status": "open",
                "opened_at": run_at,
                "closed_at": None,
                "canonical": item.canonical,
                "live": item.live,
                "channel": "#brain-status",
            }
        )
    _write_json_array(alerts_path(), alerts)


def run_drift_check(surfaces: list[DriftSurface] | None = None) -> dict[str, dict[str, Any]]:
    run_at = _rfc3339z()
    active_surfaces = surfaces if surfaces is not None else enabled_surfaces()
    summary: dict[str, dict[str, Any]] = {}
    semantic_items: list[DriftItem] = []

    for surface in active_surfaces:
        canonical = surface.load_canonical()
        live = surface.fetch_live()
        drift = surface.compute_drift(canonical, live)
        semantic_count = 0
        ui_count = 0
        for item in drift:
            if surface.classify(item) == "semantic":
                semantic_count += 1
                semantic_items.append(item)
            else:
                ui_count += 1
        summary[surface.name] = {
            "drift_count": len(drift),
            "semantic_drift_count": semantic_count,
            "ui_drift_count": ui_count,
            "last_run": run_at,
        }

    _append_json_row(
        runs_path(),
        {
            "ran_at": run_at,
            "summary": summary,
            "drift": [asdict(item) for item in semantic_items],
        },
    )
    _record_semantic_alerts(run_at, semantic_items)
    return summary


def latest_run_summary() -> dict[str, Any] | None:
    rows = _load_json_array(runs_path())
    if not rows:
        return None
    return rows[-1]


def open_alerts() -> list[dict[str, Any]]:
    return [row for row in _load_json_array(alerts_path()) if row.get("status") == "open"]
