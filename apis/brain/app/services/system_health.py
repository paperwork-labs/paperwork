"""Read-only filesystem snapshot for Studio admin system-health (WS-43).

Aggregates Brain pause state, on-disk freshness markers, queue depth, and
workstream/procedural-memory counts.  Must never raise — callers expect a dict.

medallion: ops
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from app.services.kill_switch import is_brain_paused
from app.services.kill_switch import reason as brain_pause_reason

_TS_FIELDS = frozenset(
    {
        "finished_at",
        "at",
        "run_at",
        "timestamp",
        "checked_at",
        "started_at",
        "last_run_at",
        "opened_at",
    }
)


def _monorepo_root() -> Path:
    env = (os.environ.get("REPO_ROOT") or "").strip()
    if env:
        return Path(env)
    # apis/brain/app/services/system_health.py → repo root
    return Path(__file__).resolve().parent.parent.parent.parent.parent


def _brain_data_dir() -> Path:
    return _monorepo_root() / "apis" / "brain" / "data"


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _parse_iso_to_utc(dt_raw: str) -> datetime | None:
    s = dt_raw.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _to_rfc3339z(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_ts_string(raw: str | None) -> str | None:
    if raw is None:
        return None
    dt = _parse_iso_to_utc(raw)
    if dt is None:
        return None
    return _to_rfc3339z(dt)


def _latest_ts_from_objects(objs: list[dict[str, Any]]) -> str | None:
    best: datetime | None = None
    for obj in objs:
        if not isinstance(obj, dict):
            continue
        for key in _TS_FIELDS:
            if key not in obj:
                continue
            val = obj[key]
            if not isinstance(val, str):
                continue
            parsed = _parse_iso_to_utc(val)
            if parsed is None:
                continue
            if best is None or parsed > best:
                best = parsed
    return _to_rfc3339z(best) if best is not None else None


def _writeback_last_run(data: Any) -> str | None:
    if data is None:
        return None
    if isinstance(data, dict):
        for top_key in ("last_run_at", "writeback_last_run", "latest"):
            if top_key in data and isinstance(data[top_key], str):
                norm = _normalize_ts_string(data[top_key])
                if norm:
                    return norm
        runs = data.get("runs")
        if isinstance(runs, list):
            ts = _latest_ts_from_objects([r for r in runs if isinstance(r, dict)])
            if ts:
                return ts
    if isinstance(data, list):
        ts = _latest_ts_from_objects([r for r in data if isinstance(r, dict)])
        if ts:
            return ts
    return None


def _drift_last_check(data: Any) -> str | None:
    if data is None:
        return None
    if isinstance(data, dict):
        for top_key in ("last_check_at", "last_drift_check", "latest"):
            if top_key in data and isinstance(data[top_key], str):
                norm = _normalize_ts_string(data[top_key])
                if norm:
                    return norm
        runs = data.get("runs") or data.get("checks")
        if isinstance(runs, list):
            ts = _latest_ts_from_objects([r for r in runs if isinstance(r, dict)])
            if ts:
                return ts
    if isinstance(data, list):
        ts = _latest_ts_from_objects([r for r in data if isinstance(r, dict)])
        if ts:
            return ts
    return None


def _last_pr_opened(data: Any) -> dict[str, Any] | None:
    if data is None or not isinstance(data, dict):
        return None
    cand: dict[str, Any] | None = None
    if isinstance(data.get("last"), dict):
        cand = data["last"]
    elif isinstance(data.get("last_opened"), dict):
        cand = data["last_opened"]
    else:
        opens = data.get("opens") or data.get("pr_opens")
        if isinstance(opens, list):
            best: dict[str, Any] | None = None
            best_ts: datetime | None = None
            for row in opens:
                if not isinstance(row, dict):
                    continue
                oa = row.get("opened_at")
                if not isinstance(oa, str):
                    continue
                parsed = _parse_iso_to_utc(oa)
                if parsed is None:
                    continue
                if best_ts is None or parsed > best_ts:
                    best_ts = parsed
                    best = row
            cand = best
    if cand is None:
        return None
    prn = cand.get("pr_number")
    branch = cand.get("branch")
    opened = cand.get("opened_at")
    if not isinstance(prn, int) or not isinstance(branch, str):
        return None
    opened_norm = _normalize_ts_string(opened) if isinstance(opened, str) else None
    if opened_norm is None:
        return None
    return {"pr_number": prn, "branch": branch, "opened_at": opened_norm}


def _merge_queue_depth(data: Any) -> int:
    if not isinstance(data, dict):
        return 0
    q = data.get("queue")
    if isinstance(q, list):
        return len(q)
    return 0


def _pending_workstreams(path: Path) -> int:
    data = _read_json(path)
    if not isinstance(data, dict):
        return 0
    rows = data.get("workstreams")
    if not isinstance(rows, list):
        return 0
    return sum(1 for w in rows if isinstance(w, dict) and w.get("status") == "pending")


def _procedural_rules_count(path: Path) -> int:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, UnicodeDecodeError):
        return 0
    if not isinstance(raw, dict):
        return 0
    rules = raw.get("rules")
    if not isinstance(rules, list):
        return 0
    return sum(1 for r in rules if isinstance(r, dict))


def system_health_snapshot() -> dict[str, Any]:
    """Return a JSON-serializable dict for ``GET /admin/system-health``."""
    root = _monorepo_root()
    brain_data = _brain_data_dir()

    paused = is_brain_paused()
    writeback_raw = _read_json(brain_data / "writeback_runs.json")
    pr_open_raw = _read_json(brain_data / "pr_opens.json")
    drift_raw = _read_json(brain_data / "drift_check_runs.json")
    mq_raw = _read_json(brain_data / "merge_queue.json")

    return {
        "brain_paused": paused,
        "brain_paused_reason": brain_pause_reason() if paused else None,
        "writeback_last_run": _writeback_last_run(writeback_raw),
        "last_pr_opened": _last_pr_opened(pr_open_raw),
        "last_drift_check": _drift_last_check(drift_raw),
        "scheduler_skew_seconds": None,
        "merge_queue_depth": _merge_queue_depth(mq_raw),
        "pending_workstreams": _pending_workstreams(
            root / "apps" / "studio" / "src" / "data" / "workstreams.json"
        ),
        "procedural_rules_count": _procedural_rules_count(brain_data / "procedural_memory.yaml"),
    }
