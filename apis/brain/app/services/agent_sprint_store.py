"""Persistence for generated cheap-agent sprints (JSON + optional tracker-index digest)."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from zoneinfo import ZoneInfo

from app.config import settings
from app.schemas.agent_tasks import AgentSprintDayMetrics, AgentSprintRecord

logger = logging.getLogger(__name__)

_STORE_NAME = "agent_sprints_store.json"
_TZ_DEFAULT = "America/Los_Angeles"


def _brain_data_dir() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(root, "data")
    os.makedirs(d, exist_ok=True)
    return d


def _store_path() -> str:
    return os.path.join(_brain_data_dir(), _STORE_NAME)


def _atomic_write_json(path: str, data: dict[str, Any]) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def _load_store() -> dict[str, Any]:
    path = _store_path()
    if not os.path.isfile(path):
        return {"version": 1, "sprints": []}
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, dict) else {"version": 1, "sprints": []}
    except (OSError, json.JSONDecodeError):
        logger.warning("agent_sprint_store: could not read %s", path)
        return {"version": 1, "sprints": []}


def _repo_root() -> str:
    env = os.environ.get("REPO_ROOT")
    if env:
        return env
    here = os.path.abspath(os.path.dirname(__file__))
    brain_pkg = os.path.dirname(os.path.dirname(here))  # .../apis/brain
    return os.path.abspath(os.path.join(brain_pkg, "..", ".."))


def in_flight_task_ids(*, lookback_days: int = 7) -> set[str]:
    """Task ids already placed in a non-terminal sprint."""
    store = _load_store()
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    out: set[str] = set()
    for sp in store.get("sprints") or []:
        if not isinstance(sp, dict):
            continue
        status = sp.get("status") or ""
        if status not in ("pending_review", "dispatched"):
            continue
        try:
            gen_at = datetime.fromisoformat(str(sp.get("generated_at", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if gen_at < cutoff:
            continue
        for t in sp.get("tasks") or []:
            if isinstance(t, dict) and t.get("task_id"):
                out.add(str(t["task_id"]))
    return out


def append_sprint(record: AgentSprintRecord) -> None:
    store = _load_store()
    sprints = list(store.get("sprints") or [])
    sprints.append(json.loads(record.model_dump_json()))
    # cap history
    sprints = sprints[-200:]
    store["sprints"] = sprints
    _atomic_write_json(_store_path(), store)
    _maybe_merge_tracker_digest(record)


def _maybe_merge_tracker_digest(record: AgentSprintRecord) -> None:
    if not getattr(settings, "BRAIN_AGENT_SPRINT_WRITE_TRACKER", False):
        return
    tracker = os.path.join(
        _repo_root(),
        "apps",
        "studio",
        "src",
        "data",
        "tracker-index.json",
    )
    if not os.path.isfile(tracker):
        return
    try:
        with open(tracker, encoding="utf-8") as f:
            idx = json.load(f)
        if not isinstance(idx, dict):
            return
        digest = idx.get("cheap_agent_sprints")
        if not isinstance(digest, list):
            digest = []
        digest.append({
            "sprint_id": record.sprint_id,
            "generated_at": record.generated_at,
            "total_minutes": record.total_minutes,
            "task_count": len(record.tasks),
            "titles": [t.title for t in record.tasks[:12]],
        })
        idx["cheap_agent_sprints"] = digest[-20:]
        idx["cheap_agent_sprints_updated"] = record.generated_at
        with open(f"{tracker}.tmp", "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2)
            f.write("\n")
        os.replace(f"{tracker}.tmp", tracker)
    except OSError:
        logger.warning("agent_sprint_store: tracker-index merge skipped", exc_info=True)


def load_sprints_since(since_utc: datetime) -> list[AgentSprintRecord]:
    store = _load_store()
    out: list[AgentSprintRecord] = []
    for sp in store.get("sprints") or []:
        if not isinstance(sp, dict):
            continue
        try:
            gen_at = datetime.fromisoformat(str(sp.get("generated_at", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if gen_at >= since_utc.replace(tzinfo=gen_at.tzinfo or timezone.utc):
            try:
                out.append(AgentSprintRecord.model_validate(sp))
            except Exception:
                logger.debug("skip invalid sprint record", exc_info=True)
    out.sort(key=lambda r: r.generated_at, reverse=True)
    return out


def today_metrics(tz_name: str = _TZ_DEFAULT) -> AgentSprintDayMetrics:
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start.astimezone(timezone.utc)
    sprints = load_sprints_since(start_utc)
    if not sprints:
        return AgentSprintDayMetrics(
            tasks_generated_today=0,
            sprints_generated_today=0,
            average_sprint_size=0.0,
        )
    task_count = sum(len(s.tasks) for s in sprints)
    return AgentSprintDayMetrics(
        tasks_generated_today=task_count,
        sprints_generated_today=len(sprints),
        average_sprint_size=round(task_count / len(sprints), 2),
    )


def new_sprint_id() -> str:
    return str(uuid.uuid4())
