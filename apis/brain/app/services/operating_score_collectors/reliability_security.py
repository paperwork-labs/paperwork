"""Reliability + security pillar — quota snapshots, IaC canon, secret scan, incidents.

medallion: ops
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

_BOOTSTRAP = (
    60.0,
    False,
    (
        "bootstrap - no canonical IaC state "
        "(iac_state_*.yaml under apis/brain/data or infra/state layers)"
    ),
)

_SCHEMA = "reliability_metrics/v1"
_KNOWN_LAYERS = frozenset({"vercel", "render", "cloudflare", "clerk"})


def _repo_root() -> Path:
    env = os.environ.get("BRAIN_REPO_ROOT", "").strip()
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / "apps").is_dir() and (anc / "docs").is_dir():
            return anc
    return here.parents[5]


def _brain_data_dir() -> Path:
    env = os.environ.get("BRAIN_RELIABILITY_DATA_DIR", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "data"


def _parse_rfc3339(s: str) -> datetime | None:
    if not isinstance(s, str) or not s.strip():
        return None
    txt = s.strip()
    if txt.endswith("Z"):
        txt = txt[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _timestamp_candidates(obj: Any) -> list[datetime]:
    out: list[datetime] = []
    keys = ("recorded_at", "captured_at", "snapshot_at", "probed_at", "last_updated", "updated_at")
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if isinstance(v, str):
                p = _parse_rfc3339(v)
                if p:
                    out.append(p)
            elif isinstance(v, dict):
                out.extend(_timestamp_candidates(v))
        for v in obj.values():
            if isinstance(v, dict):
                out.extend(_timestamp_candidates(v))
    return out


def _quota_snapshot_paths(data: Path) -> list[Path]:
    paths: list[Path] = []
    for pattern in ("render_quota_*.json", "vercel_quota_*.json", "github_actions_quota_*.json"):
        paths.extend(data.glob(pattern))
    uniq = sorted({p.resolve() for p in paths if p.is_file()})
    return list(uniq)


def _uptime_subscore(quota_files: list[Path], now: datetime) -> tuple[float, str]:
    """SLO proxy from latest quota snapshot freshness."""
    if not quota_files:
        return (60.0, "no_quota_json")
    latest: datetime | None = None
    for p in quota_files:
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        times = _timestamp_candidates(doc)
        for t in times:
            if latest is None or t > latest:
                latest = t
        if latest is None:
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
            if latest is None or mtime > latest:
                latest = mtime
    if latest is None:
        return (50.0, "quota_json_unparsed")
    age = now - latest
    if age <= timedelta(days=7):
        return (100.0, f"fresh<{age.days}d")
    if age <= timedelta(days=30):
        return (80.0, f"stale<{age.days}d")
    return (50.0, f"stale>{age.days}d")


def _iac_layers(data: Path, repo: Path) -> set[str]:
    found: set[str] = set()
    for p in data.glob("iac_state_*.yaml"):
        if not p.is_file():
            continue
        stem = p.stem
        if not stem.startswith("iac_state_"):
            continue
        layer = stem.removeprefix("iac_state_")
        if layer in _KNOWN_LAYERS:
            try:
                raw = yaml.safe_load(p.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError):
                continue
            if isinstance(raw, dict) and "schema" in raw:
                found.add(layer)

    state_dir = repo / "infra" / "state"
    for layer in _KNOWN_LAYERS:
        fp = state_dir / f"{layer}.yaml"
        if not fp.is_file():
            continue
        try:
            raw = yaml.safe_load(fp.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(raw, dict) and "schema" in raw:
            found.add(layer)
    return found


def _score_iac_layer_count(n: int) -> float:
    if n >= 4:
        return 100.0
    if n >= 2:
        return 75.0
    if n == 1:
        return 50.0
    return 0.0


def _find_gitleaks_workflow(repo: Path) -> str | None:
    wf_dir = repo / ".github" / "workflows"
    if not wf_dir.is_dir():
        return None
    for p in sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml")):
        try:
            txt = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if "gitleaks" in txt.lower():
            return p.name
    return None


def _secret_scan_subscore(repo: Path, now: datetime) -> tuple[float, str]:
    wf = _find_gitleaks_workflow(repo)
    if wf is None:
        return (0.0, "no_gitleaks_workflow")

    try:
        cp = subprocess.run(
            [
                "gh",
                "run",
                "list",
                "--workflow",
                wf,
                "--branch",
                os.environ.get("BRAIN_RELIABILITY_BASE_BRANCH", "main"),
                "--limit",
                "1",
                "--json",
                "updatedAt,conclusion",
            ],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return (50.0, "gh_unavailable")

    if cp.returncode != 0:
        return (50.0, "gh_run_list_failed")

    try:
        rows = json.loads(cp.stdout or "[]")
    except json.JSONDecodeError:
        return (50.0, "gh_json_invalid")
    if not isinstance(rows, list) or not rows:
        return (50.0, "no_runs")

    updated_s = str((rows[0] or {}).get("updatedAt") or "")
    conclusion = str((rows[0] or {}).get("conclusion") or "")
    ts = _parse_rfc3339(updated_s)
    if ts is None:
        return (50.0, "no_updated_at")
    if now - ts > timedelta(days=7):
        return (50.0, "run_older_than_7d")
    if conclusion == "success":
        return (100.0, "gitleaks_recent_ok")
    return (70.0, f"gitleaks_recent_{conclusion or 'unknown'}")


def _incidents_last_30d(data_dir: Path, now: datetime) -> int:
    path = data_dir / "incidents.json"
    if not path.is_file():
        return 0
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    rows = doc.get("incidents") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return 0
    cutoff = now - timedelta(days=30)
    n = 0
    for it in rows:
        if not isinstance(it, dict):
            continue
        opened = it.get("opened_at")
        if not isinstance(opened, str):
            continue
        ts = _parse_rfc3339(opened)
        if ts is None:
            continue
        if ts >= cutoff:
            n += 1
    return n


def _score_incidents(count: int) -> float:
    if count <= 0:
        return 100.0
    return max(0.0, 100.0 - (count / 10.0) * 100.0)


def _write_metrics(blob: dict[str, Any], data_dir: Path) -> None:
    out = data_dir / "reliability_metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")


def collect() -> tuple[float, bool, str]:
    repo = _repo_root()
    data = _brain_data_dir()
    now = datetime.now(tz=UTC)

    layers = _iac_layers(data, repo)
    if not layers:
        return _BOOTSTRAP

    try:
        sub_iac = _score_iac_layer_count(len(layers))
        quota_files = _quota_snapshot_paths(data)
        sub_uptime, uptime_note = _uptime_subscore(quota_files, now)
        sub_leaks, leaks_note = _secret_scan_subscore(repo, now)
        inc_n = _incidents_last_30d(data, now)
        sub_inc = _score_incidents(inc_n)

        pillars_avg = (sub_iac + sub_uptime + sub_leaks + sub_inc) / 4.0
        total = max(0.0, min(100.0, math.floor(pillars_avg * 10000 + 0.5) / 10000))

        blob = {
            "schema": _SCHEMA,
            "computed_at": now.isoformat().replace("+00:00", "Z"),
            "iac_layers": sorted(layers),
            "iac_layer_count": len(layers),
            "quota_snapshot_count": len(quota_files),
            "incidents_last_30d": inc_n,
            "sub_scores": {
                "iac_drift_coverage": round(sub_iac, 4),
                "uptime_slo": round(sub_uptime, 4),
                "gitleaks_freshness": round(sub_leaks, 4),
                "incident_rate": round(sub_inc, 4),
            },
            "uptime_signal": uptime_note,
            "gitleaks_signal": leaks_note,
        }
        _write_metrics(blob, data)

        notes = (
            f"reliability_security: layers={sorted(layers)} quota_files={len(quota_files)} "
            f"{uptime_note} {leaks_note} incidents_30d={inc_n}"
        )
        return (total, True, notes)
    except (OSError, ValueError, TypeError, yaml.YAMLError):
        return _BOOTSTRAP
