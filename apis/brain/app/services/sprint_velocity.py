"""Sprint velocity service — PRs merged per week, story points, by-author breakdown.

Weekly compute: read pr_outcomes.json for merged PRs in the window, read git log on
workstreams.json to detect status→completed transitions, then classify contributors
as founder / brain-self-dispatch / cheap-agent.

medallion: ops
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

from app.schemas.sprint_velocity import (
    ByAuthor,
    SprintVelocityEntry,
    SprintVelocityFile,
)

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

_ENV_JSON = "BRAIN_SPRINT_VELOCITY_JSON"
_ENV_REPO_ROOT = "REPO_ROOT"
_TMP_SUFFIX = ".tmp"
_WS_JSON_REL = "apps/studio/src/data/workstreams.json"

_BRAIN_AGENT_PREFIX = "brain-"
_FOUNDER_AGENT_NAMES = frozenset({"founder", "human", "", "none"})


def _brain_data_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    brain_app = os.path.dirname(here)
    return os.path.join(brain_app, "data")


def sprint_velocity_file_path() -> str:
    env = os.environ.get(_ENV_JSON, "").strip()
    if env:
        return env
    return os.path.join(_brain_data_dir(), "sprint_velocity.json")


def _lock_path() -> str:
    return sprint_velocity_file_path() + ".lock"


def _monorepo_root() -> str:
    env = os.environ.get(_ENV_REPO_ROOT, "").strip()
    if env:
        return env
    current = Path(__file__).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".cursor" / "rules").is_dir() and (candidate / "apis" / "brain").is_dir():
            return str(candidate)
    raise RuntimeError("Paperwork monorepo root not found; set REPO_ROOT env var")


def _week_window(week_offset: int = 0) -> tuple[datetime, datetime]:
    """Return (week_start, week_end) for the last-complete Mon-Sun week.

    ``week_offset=0`` → most recently completed week.
    ``week_offset=1`` → the week before that.
    """
    today = datetime.now(UTC).date()
    # Last complete Sunday: go back (weekday + 1) days from today.
    # If today is Monday (weekday=0), that's 1 day back → yesterday (Sunday).
    days_to_last_sunday = today.weekday() + 1
    last_sunday = today - timedelta(days=days_to_last_sunday)

    # Apply offset
    w_end_date = last_sunday - timedelta(weeks=week_offset)
    w_start_date = w_end_date - timedelta(days=6)

    week_start = datetime(w_start_date.year, w_start_date.month, w_start_date.day, tzinfo=UTC)
    week_end = datetime(w_end_date.year, w_end_date.month, w_end_date.day, 23, 59, 59, tzinfo=UTC)
    return week_start, week_end


def _parse_iso(s: str) -> datetime | None:
    try:
        clean = s.strip()
        if clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, AttributeError):
        return None


def _in_week(ts_str: str, week_start: datetime, week_end: datetime) -> bool:
    dt = _parse_iso(ts_str)
    if dt is None:
        return False
    return week_start <= dt <= week_end


def _classify_agent(merged_by_agent: str) -> str:
    """Classify a merged_by_agent string into founder / brain-self-dispatch / cheap-agent."""
    if not merged_by_agent or merged_by_agent.lower() in _FOUNDER_AGENT_NAMES:
        return "founder"
    if merged_by_agent.startswith(_BRAIN_AGENT_PREFIX):
        return "brain-self-dispatch"
    return "cheap-agent"


def _load_pr_outcomes_file() -> dict[str, Any]:
    """Load raw pr_outcomes.json — returns empty outcomes list on any error."""
    data_dir = _brain_data_dir()
    path = os.path.join(data_dir, "pr_outcomes.json")
    if not os.path.isfile(path):
        return {"outcomes": []}
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            return {"outcomes": []}
        return raw
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("sprint_velocity: cannot read pr_outcomes.json — %s", exc)
        return {"outcomes": []}


def _get_file_at_ref(ref: str, rel_path: str, repo_root: str) -> dict[str, Any] | None:
    """Return parsed JSON for ``rel_path`` at git ``ref``, or None on error."""
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{rel_path}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        parsed: dict[str, Any] = json.loads(result.stdout)
        return parsed
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return None


def _completed_workstreams_in_week(
    week_start: datetime,
    week_end: datetime,
    repo_root: str,
) -> list[tuple[str, int | None]]:
    """Return list of (ws_id, estimated_pr_count) for workstreams that flipped to completed.

    Reads git log on workstreams.json and diffs before/after per commit.
    Falls back to empty list on any subprocess or parse failure.
    """
    ws_rel = _WS_JSON_REL
    try:
        since = week_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        until = week_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        commits_result = subprocess.run(
            [
                "git",
                "log",
                "--format=%H",
                f"--since={since}",
                f"--until={until}",
                "--",
                ws_rel,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if commits_result.returncode != 0:
            return []

        commit_hashes = [h for h in commits_result.stdout.strip().splitlines() if h]
        if not commit_hashes:
            return []

        newly_completed: dict[str, int | None] = {}
        for sha in commit_hashes:
            current_data = _get_file_at_ref(sha, ws_rel, repo_root)
            parent_data = _get_file_at_ref(f"{sha}^", ws_rel, repo_root)
            if current_data is None:
                continue

            curr_map: dict[str, dict[str, Any]] = {
                ws["id"]: ws
                for ws in current_data.get("workstreams", [])
                if isinstance(ws, dict) and "id" in ws
            }
            prev_map: dict[str, dict[str, Any]] = {}
            if parent_data is not None:
                prev_map = {
                    ws["id"]: ws
                    for ws in parent_data.get("workstreams", [])
                    if isinstance(ws, dict) and "id" in ws
                }

            for ws_id, ws in curr_map.items():
                prev = prev_map.get(ws_id)
                was_completed_before = prev is not None and prev.get("status") == "completed"
                is_completed_now = ws.get("status") == "completed"
                if is_completed_now and not was_completed_before:
                    newly_completed[ws_id] = ws.get("estimated_pr_count")

        return list(newly_completed.items())

    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("sprint_velocity: git log for workstreams failed — %s", exc)
        return []


def compute_velocity(week_offset: int = 0) -> SprintVelocityEntry:
    """Compute sprint velocity for the last-complete week (or N weeks ago).

    Bootstrap: if pr_outcomes has no entries AND no workstream completions are
    detected, returns an entry with ``measured=False``.
    """
    week_start, week_end = _week_window(week_offset)
    week_start_str = week_start.date().isoformat()
    week_end_str = week_end.date().isoformat()
    computed_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    outcomes_raw = _load_pr_outcomes_file()
    outcomes = outcomes_raw.get("outcomes", []) or []
    if not isinstance(outcomes, list):
        outcomes = []

    week_outcomes = [
        o
        for o in outcomes
        if isinstance(o, dict) and _in_week(o.get("merged_at", ""), week_start, week_end)
    ]

    try:
        repo_root = _monorepo_root()
        completed_ws = _completed_workstreams_in_week(week_start, week_end, repo_root)
    except RuntimeError as exc:
        logger.warning("sprint_velocity: cannot find repo root — %s", exc)
        completed_ws = []

    if not week_outcomes and not completed_ws:
        logger.info(
            "sprint_velocity: bootstrap - no pr_outcomes and no completed workstreams for %s-%s",
            week_start_str,
            week_end_str,
        )
        return SprintVelocityEntry(
            week_start=week_start_str,
            week_end=week_end_str,
            prs_merged=0,
            by_author=ByAuthor(),
            workstreams_completed=0,
            workstreams_completed_estimated_pr_count=0,
            story_points_burned=0,
            throughput_per_day=0.0,
            measured=False,
            notes="Bootstrap: pr_outcomes empty and no git-detected workstream completions.",
            computed_at=computed_at,
        )

    # by_author breakdown
    founder_count = 0
    brain_count = 0
    cheap_count = 0
    for outcome in week_outcomes:
        bucket = _classify_agent(str(outcome.get("merged_by_agent") or ""))
        if bucket == "founder":
            founder_count += 1
        elif bucket == "brain-self-dispatch":
            brain_count += 1
        else:
            cheap_count += 1

    prs_merged = len(week_outcomes)

    ws_completed = len(completed_ws)
    ws_estimated_prs = sum(
        (epc if isinstance(epc, int) else 0) for _, epc in completed_ws
    )
    story_points_burned = ws_estimated_prs

    days_in_week = 7.0
    throughput_per_day = round(prs_merged / days_in_week, 2)

    return SprintVelocityEntry(
        week_start=week_start_str,
        week_end=week_end_str,
        prs_merged=prs_merged,
        by_author=ByAuthor(
            **{
                "founder": founder_count,
                "brain-self-dispatch": brain_count,
                "cheap-agent": cheap_count,
            }
        ),
        workstreams_completed=ws_completed,
        workstreams_completed_estimated_pr_count=ws_estimated_prs,
        story_points_burned=story_points_burned,
        throughput_per_day=throughput_per_day,
        measured=True,
        computed_at=computed_at,
    )


def _atomic_write_json(path: str, data: dict[str, Any]) -> None:
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    tmp = f"{path}{_TMP_SUFFIX}"
    raw = json.dumps(data, indent=2, sort_keys=True) + "\n"
    with open(tmp, "w", encoding="utf-8") as wf:
        wf.write(raw)
    os.replace(tmp, path)


def _with_lock(exclusive: bool, fn: "Callable[[], _T]") -> _T:
    lp = _lock_path()
    os.makedirs(os.path.dirname(lp) or ".", exist_ok=True)
    lock_mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    with open(lp, "a+", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f.fileno(), lock_mode)
        try:
            return fn()
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def _read_file_unlocked() -> SprintVelocityFile:
    path = sprint_velocity_file_path()
    if not os.path.isfile(path):
        return SprintVelocityFile()
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            return SprintVelocityFile()
        return SprintVelocityFile.model_validate(raw)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("sprint_velocity: could not read %s — %s; starting empty", path, exc)
        return SprintVelocityFile()


def read_velocity_file() -> SprintVelocityFile:
    """Read ``sprint_velocity.json`` under a shared flock."""
    return _with_lock(exclusive=False, fn=_read_file_unlocked)


def _write_unlocked(data: SprintVelocityFile) -> None:
    path = sprint_velocity_file_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    _atomic_write_json(path, data.model_dump(mode="json", by_alias=True))


def record_weekly_velocity(entry: SprintVelocityEntry | None = None) -> SprintVelocityEntry:
    """Compute current-week velocity, append to bounded history, atomic write.

    Returns the entry that was recorded.
    """
    if entry is None:
        entry = compute_velocity(week_offset=0)

    def _apply() -> SprintVelocityEntry:
        blob = _read_file_unlocked()
        blob.current = entry
        # Bounded history: keep last 26 weeks
        blob.history = [*blob.history, entry][-26:]
        _write_unlocked(blob)
        return entry

    return _with_lock(exclusive=True, fn=_apply)


def latest_velocity() -> SprintVelocityEntry | None:
    return read_velocity_file().current
