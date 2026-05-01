"""Probe-failure → persona dispatch loop (Wave PROBE PR-PB4).

Reads probe results from ``apis/brain/data/probe_results.json`` (the same
file written by ``ux_probe_runner`` every 5 min).  When a probe has failed
within the last hour, this scheduler creates a dispatch entry for the Brain
Autopilot to route to the appropriate persona (e.g. ``ux-lead`` for UI
regressions, ``infra-ops`` for 5xx / infrastructure errors).

Dispatch entries are persisted to ``data/dispatch_queue.json`` in the Brain
data directory.  The Autopilot reads this queue and fans out work items.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._history import run_with_scheduler_record
from app.schedulers._kill_switch_guard import skip_if_brain_paused

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "brain_probe_failure_dispatcher"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_FAILURE_WINDOW_MINUTES = int(
    os.environ.get("PROBE_DISPATCH_WINDOW_MINUTES", "60"),
)


def _repo_root() -> Path:
    env = os.environ.get("REPO_ROOT", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[4]


def _probe_results_path() -> Path:
    env = os.environ.get("BRAIN_PROBE_RESULTS_JSON", "").strip()
    if env:
        return Path(env)
    return _repo_root() / "apis" / "brain" / "data" / "probe_results.json"


def _dispatch_queue_path() -> Path:
    env = os.environ.get("BRAIN_DISPATCH_QUEUE_JSON", "").strip()
    if env:
        return Path(env)
    return _repo_root() / "apis" / "brain" / "data" / "dispatch_queue.json"


# ---------------------------------------------------------------------------
# Persona routing table
# ---------------------------------------------------------------------------

_STATUS_PERSONA_MAP: dict[str, str] = {
    "infrastructure_error": "infra-ops",
    "timeout": "infra-ops",
    "failure": "ux-lead",
}

_ERROR_KEYWORD_PERSONA: list[tuple[str, str]] = [
    ("5xx", "infra-ops"),
    ("500", "infra-ops"),
    ("502", "infra-ops"),
    ("503", "infra-ops"),
    ("504", "infra-ops"),
    ("timeout", "infra-ops"),
    ("dns", "infra-ops"),
    ("certificate", "infra-ops"),
    ("ssl", "infra-ops"),
    ("connection refused", "infra-ops"),
    ("playwright", "infra-ops"),
    ("browser", "infra-ops"),
    ("pnpm", "infra-ops"),
    ("404", "ux-lead"),
    ("element not found", "ux-lead"),
    ("selector", "ux-lead"),
    ("accessibility", "ux-lead"),
    ("contrast", "ux-lead"),
    ("layout", "ux-lead"),
    ("visual", "ux-lead"),
    ("render", "ux-lead"),
]


def suggest_persona(
    status: str,
    error_message: str,
    failing_tests: list[dict[str, Any]],
) -> str:
    """Determine which persona should handle this probe failure.

    Priority order:
    1. Status-based mapping (infrastructure_error → infra-ops)
    2. Error keyword scanning (5xx → infra-ops, selector → ux-lead)
    3. Failing-test error keyword scanning
    4. Default: ux-lead (most probes test UI behaviour)
    """
    persona: str = _STATUS_PERSONA_MAP.get(status, "")
    if persona:
        return persona

    lower_err = error_message.lower()
    for keyword, p in _ERROR_KEYWORD_PERSONA:
        if keyword in lower_err:
            return p

    for test in failing_tests:
        test_err: str = str(test.get("error", "")).lower()
        for keyword, p in _ERROR_KEYWORD_PERSONA:
            if keyword in test_err:
                return p

    return "ux-lead"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def load_probe_results(path: Path) -> list[dict[str, Any]]:
    """Load probe result rows from the JSON file.

    Returns an empty list if the file does not exist or is unreadable.
    """
    if not path.exists():
        logger.warning(
            "probe_failure_dispatcher: %s does not exist",
            path,
        )
        return []
    try:
        payload: dict[str, Any] = json.loads(
            path.read_text(encoding="utf-8"),
        )
        results: list[dict[str, Any]] = payload.get("results", [])
        return results
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "probe_failure_dispatcher: cannot read %s: %s",
            path,
            exc,
        )
        return []


def filter_recent_failures(
    results: list[dict[str, Any]],
    *,
    window_minutes: int = 60,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return probe rows that failed within the last *window_minutes*."""
    ref = now or datetime.now(UTC)
    cutoff = ref - timedelta(minutes=window_minutes)
    failures: list[dict[str, Any]] = []
    for row in results:
        status: str = str(row.get("status", ""))
        if status in ("pass", "skipped"):
            continue
        started_raw: str = str(row.get("started_at", ""))
        if not started_raw:
            continue
        try:
            started = datetime.fromisoformat(
                started_raw.replace("Z", "+00:00"),
            )
        except ValueError:
            continue
        if started >= cutoff:
            failures.append(row)
    return failures


def build_dispatch_entries(
    failures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create dispatch-queue entries from a list of probe failures."""
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in failures:
        product: str = str(row.get("product", "unknown"))
        status: str = str(row.get("status", "unknown"))
        dedup_key = f"{product}:{status}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        error_msg: str = str(row.get("error_message", ""))
        failing_tests: list[dict[str, Any]] = (
            row.get(
                "failing_tests",
                [],
            )
            or []
        )

        if not error_msg and failing_tests:
            first_err: str = str(
                failing_tests[0].get("error", ""),
            )
            error_msg = first_err[:300]

        persona = suggest_persona(status, error_msg, failing_tests)

        entry: dict[str, Any] = {
            "id": (f"probe-dispatch-{product}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"),
            "product": product,
            "probe_status": status,
            "failed_probe": _probe_name_from_row(row),
            "error_message": error_msg[:500],
            "suggested_persona": persona,
            "created_at": (datetime.now(UTC).isoformat().replace("+00:00", "Z")),
            "dispatched": False,
        }
        entries.append(entry)
    return entries


def _probe_name_from_row(row: dict[str, Any]) -> str:
    """Derive a human-readable probe name from a result row."""
    product: str = str(row.get("product", "unknown"))
    status: str = str(row.get("status", "unknown"))
    failing: list[dict[str, Any]] = row.get("failing_tests", []) or []
    if failing:
        first_title: str = str(failing[0].get("title", ""))
        if first_title:
            return f"{product}/{first_title}"
    return f"{product}/{status}"


def load_dispatch_queue(path: Path) -> list[dict[str, Any]]:
    """Load the existing dispatch queue (or empty list)."""
    if not path.exists():
        return []
    try:
        payload: dict[str, Any] = json.loads(
            path.read_text(encoding="utf-8"),
        )
        entries: list[dict[str, Any]] = payload.get("entries", [])
        return entries
    except (json.JSONDecodeError, OSError):
        return []


def save_dispatch_queue(
    path: Path,
    entries: list[dict[str, Any]],
) -> None:
    """Write dispatch queue entries to disk (rolling 500)."""
    pruned = entries[-500:]
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema": "dispatch_queue/v1",
        "description": (
            "Probe-failure dispatch entries for Brain Autopilot. "
            "Written by probe_failure_dispatcher.py."
        ),
        "entries": pruned,
    }
    path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Scheduler plumbing
# ---------------------------------------------------------------------------


async def _run_probe_failure_dispatcher_body() -> None:
    results_path = _probe_results_path()
    queue_path = _dispatch_queue_path()

    results = load_probe_results(results_path)
    if not results:
        logger.info("probe_failure_dispatcher: no probe results found")
        return

    failures = filter_recent_failures(
        results,
        window_minutes=_FAILURE_WINDOW_MINUTES,
    )
    if not failures:
        logger.info(
            "probe_failure_dispatcher: no failures in last %d min",
            _FAILURE_WINDOW_MINUTES,
        )
        return

    new_entries = build_dispatch_entries(failures)
    if not new_entries:
        logger.info(
            "probe_failure_dispatcher: failures found but no new entries",
        )
        return

    existing = load_dispatch_queue(queue_path)
    existing_ids: set[str] = {str(e.get("id", "")) for e in existing}
    added = 0
    for entry in new_entries:
        entry_id: str = str(entry.get("id", ""))
        if entry_id not in existing_ids:
            existing.append(entry)
            existing_ids.add(entry_id)
            added += 1

    save_dispatch_queue(queue_path, existing)
    logger.info(
        "probe_failure_dispatcher: dispatched %d entries (%d failures, %d total queue)",
        added,
        len(failures),
        len(existing),
    )


@skip_if_brain_paused(JOB_ID)
async def run_probe_failure_dispatcher() -> None:
    """Public entry point invoked by APScheduler."""
    await run_with_scheduler_record(
        JOB_ID,
        _run_probe_failure_dispatcher_body,
        metadata={
            "source": "probe_failure_dispatcher",
            "wave": "PROBE PR-PB4",
        },
        reraise=True,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the probe-failure dispatch loop (every 15 min)."""
    scheduler.add_job(
        run_probe_failure_dispatcher,
        trigger=CronTrigger.from_crontab(
            "*/15 * * * *",
            timezone="UTC",
        ),
        id=JOB_ID,
        name=("Probe Failure → Persona Dispatcher (Wave PROBE PR-PB4)"),
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info(
        "APScheduler job %r registered (*/15 * * * * UTC)",
        JOB_ID,
    )
