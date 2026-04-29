"""Auto-revert Brain-self-merged PRs when main CI fails soon after merge.

medallion: ops
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import uuid4

from app.schemas.incidents import BrainMergeRevertIncident, IncidentsFile
from app.schemas.pr_outcomes import PrOutcomesFile

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

_T = TypeVar("_T")
_PR_OUTCOMES_ENV = "BRAIN_PR_OUTCOMES_JSON"
_INCIDENTS_ENV = "BRAIN_INCIDENTS_JSON"
_TMP_SUFFIX = ".tmp"
_FAILING_CONCLUSIONS = {"failure", "timed_out", "cancelled", "startup_failure"}
_AUTO_REVERT_TITLE = "revert: auto-revert PR #{pr_number} — main CI red within 30 min"


def _data_dir() -> Path:
    repo_root = os.environ.get("REPO_ROOT", "").strip()
    if repo_root:
        return Path(repo_root) / "apis" / "brain" / "data"
    return Path(__file__).resolve().parents[2] / "data"


def _pr_outcomes_path() -> Path:
    env = os.environ.get(_PR_OUTCOMES_ENV, "").strip()
    return Path(env) if env else _data_dir() / "pr_outcomes.json"


def incidents_file_path() -> Path:
    """Path to ``incidents.json``; override with ``BRAIN_INCIDENTS_JSON`` for tests."""
    env = os.environ.get(_INCIDENTS_ENV, "").strip()
    return Path(env) if env else _data_dir() / "incidents.json"


def _lock_path() -> Path:
    return incidents_file_path().with_suffix(incidents_file_path().suffix + ".lock")


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _rfc3339_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_rfc3339(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _load_json_file(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        msg = f"{path} must contain a JSON object"
        raise ValueError(msg)
    return raw


def _load_pr_outcomes_file() -> PrOutcomesFile:
    return PrOutcomesFile.model_validate(_load_json_file(_pr_outcomes_path()))


def _load_incidents_unlocked() -> IncidentsFile:
    return IncidentsFile.model_validate(_load_json_file(incidents_file_path()))


def _atomic_write_incidents_unlocked(data: IncidentsFile) -> None:
    path = incidents_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}{_TMP_SUFFIX}")
    raw = json.dumps(data.model_dump(mode="json", by_alias=True), indent=2, sort_keys=True) + "\n"
    tmp.write_text(raw, encoding="utf-8")
    os.replace(tmp, path)


def _with_incidents_lock(func: Callable[[], _T]) -> _T:
    lock_path = _lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            return func()
        finally:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        timeout=60,
        capture_output=True,
        text=True,
    )


def _parse_pr_number(output: str) -> int:
    match = re.search(r"/pull/(\d+)", output) or re.search(r"#(\d+)", output)
    if not match:
        msg = f"could not parse PR number from gh output: {output!r}"
        raise RuntimeError(msg)
    return int(match.group(1))


def recent_brain_merges(window_minutes: int = 30) -> list[dict[str, Any]]:
    """Return Brain-self-merged PR outcome rows merged within ``window_minutes``."""
    if window_minutes <= 0:
        msg = "window_minutes must be positive"
        raise ValueError(msg)

    cutoff = _now_utc() - timedelta(minutes=window_minutes)
    outcomes = _load_pr_outcomes_file()
    recent: list[dict[str, Any]] = []
    for row in outcomes.outcomes:
        merged_by = row.merged_by_agent.strip()
        if not merged_by.startswith("brain-"):
            continue
        merged_at = _parse_rfc3339(row.merged_at)
        if merged_at >= cutoff:
            item = row.model_dump(mode="json")
            item["merged_at_dt"] = merged_at
            recent.append(item)
    return sorted(recent, key=lambda r: r["merged_at_dt"], reverse=True)


def is_main_ci_failed_after(merged_at: datetime) -> tuple[bool, str | None]:
    """Detect a failing main GitHub Actions run that started after ``merged_at``."""
    baseline = merged_at.astimezone(UTC) if merged_at.tzinfo else merged_at.replace(tzinfo=UTC)
    proc = _run(
        [
            "gh",
            "run",
            "list",
            "--branch",
            "main",
            "--json",
            "status,conclusion,headSha,startedAt,url",
        ]
    )
    runs = json.loads(proc.stdout)
    if not isinstance(runs, list):
        msg = "gh run list returned non-list JSON"
        raise ValueError(msg)

    for run in runs:
        if not isinstance(run, dict):
            msg = f"gh run list returned malformed run row: {run!r}"
            raise ValueError(msg)
        started_raw = str(run.get("startedAt") or "")
        started_at = _parse_rfc3339(started_raw)
        conclusion = str(run.get("conclusion") or "").lower()
        if started_at > baseline and conclusion in _FAILING_CONCLUSIONS:
            url = run.get("url")
            if not isinstance(url, str) or not url.strip():
                msg = f"failing main CI run missing url: {run!r}"
                raise ValueError(msg)
            return True, url
    return False, None


def open_revert_pr(pr_number: int, ci_failure_run_url: str) -> int:
    """Open a PR that reverts ``pr_number`` and return the revert PR number."""
    title = _AUTO_REVERT_TITLE.format(pr_number=pr_number)
    body = (
        "Automated safety revert opened by Brain.\n\n"
        f"- Reverted PR: #{pr_number}\n"
        f"- Trigger: main CI failed within 30 minutes\n"
        f"- Failing run: {ci_failure_run_url}\n"
    )

    try:
        _run(["gh", "pr", "revert", "--help"])
        proc = _run(
            ["gh", "pr", "revert", str(pr_number), "--yes", "--title", title, "--body", body]
        )
        return _parse_pr_number(proc.stdout + proc.stderr)
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.info("gh pr revert unavailable for #%s; falling back to git revert", pr_number)

    view = _run(["gh", "pr", "view", str(pr_number), "--json", "mergeCommit"]).stdout
    payload = json.loads(view)
    merge_commit = ((payload.get("mergeCommit") or {}).get("oid") or "").strip()
    if not merge_commit:
        msg = f"PR #{pr_number} has no merge commit to revert"
        raise RuntimeError(msg)

    branch = f"brain-auto-revert-pr-{pr_number}-{uuid4().hex[:8]}"
    _run(["git", "checkout", "-B", branch])
    _run(["git", "revert", "--no-edit", merge_commit])
    _run(["git", "push", "-u", "origin", branch])
    created = _run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            "main",
            "--head",
            branch,
            "--title",
            title,
            "--body",
            body,
        ]
    )
    return _parse_pr_number(created.stdout + created.stderr)


def auto_merge_revert(revert_pr_number: int) -> None:
    _run(["gh", "pr", "merge", str(revert_pr_number), "--squash", "--admin", "--delete-branch"])


def list_incidents(limit: int = 20) -> list[BrainMergeRevertIncident]:
    """Return most recently opened incidents first."""
    if limit <= 0:
        return []

    def _read() -> list[BrainMergeRevertIncident]:
        data = _load_incidents_unlocked()
        rows = sorted(data.incidents, key=lambda i: i.opened_at, reverse=True)
        return rows[:limit]

    return _with_incidents_lock(_read)


def _incident_exists(pr_number_reverted: int) -> bool:
    def _read() -> bool:
        data = _load_incidents_unlocked()
        return any(i.pr_number_reverted == pr_number_reverted for i in data.incidents)

    return _with_incidents_lock(_read)


def record_incident(
    *,
    pr_number_reverted: int,
    revert_pr_number: int,
    ci_failure_run_url: str,
    detected_at: datetime | None = None,
    closed_at: datetime | None = None,
    root_cause: str | None = None,
    notes: str | None = None,
) -> BrainMergeRevertIncident:
    """Append a Brain auto-revert incident via locked atomic write."""
    detected = detected_at or _now_utc()
    incident = BrainMergeRevertIncident(
        incident_id=uuid4(),
        opened_at=_rfc3339_z(detected),
        kind="brain-merge-revert",
        pr_number_reverted=pr_number_reverted,
        revert_pr_number=revert_pr_number,
        ci_failure_run_url=ci_failure_run_url,
        detected_at=_rfc3339_z(detected),
        closed_at=_rfc3339_z(closed_at) if closed_at else None,
        root_cause=root_cause,
        notes=notes,
    )

    def _append() -> BrainMergeRevertIncident:
        data = _load_incidents_unlocked()
        if any(i.pr_number_reverted == pr_number_reverted for i in data.incidents):
            msg = f"incident already recorded for reverted PR #{pr_number_reverted}"
            raise ValueError(msg)
        data.incidents.append(incident)
        _atomic_write_incidents_unlocked(data)
        return incident

    return _with_incidents_lock(_append)


def run_auto_revert_check() -> list[BrainMergeRevertIncident]:
    """Check recent Brain merges, revert if main CI failed, and record incidents."""
    recorded: list[BrainMergeRevertIncident] = []
    for merge in recent_brain_merges(window_minutes=30):
        pr_number = int(merge["pr_number"])
        if _incident_exists(pr_number):
            logger.info("auto_revert: incident already exists for PR #%s; skipping", pr_number)
            continue

        failed, run_url = is_main_ci_failed_after(merge["merged_at_dt"])
        if not failed:
            continue
        if run_url is None:
            msg = f"main CI failure detected for PR #{pr_number} without run URL"
            raise RuntimeError(msg)

        detected_at = _now_utc()
        revert_pr_number = open_revert_pr(pr_number, run_url)
        auto_merge_revert(revert_pr_number)
        recorded.append(
            record_incident(
                pr_number_reverted=pr_number,
                revert_pr_number=revert_pr_number,
                ci_failure_run_url=run_url,
                detected_at=detected_at,
                closed_at=_now_utc(),
                root_cause="main_ci_failed_after_brain_self_merge",
                notes=(
                    "Auto-opened and auto-merged revert PR because main CI went red "
                    "within 30 minutes."
                ),
            )
        )
    return recorded
