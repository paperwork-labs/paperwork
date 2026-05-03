"""Autopilot dispatcher — the closed dispatch loop.

Reads ``data/dispatch_queue.json`` for pending entries, selects a
persona, chooses an agent model mapped to a T-Shirt size (cheap-agent-fleet
Rule #2), creates dispatch records, and appends results to
``data/agent_dispatch_log.jsonl``.

T-Shirt size taxonomy (Wave L — locked):
  XS: composer-1.5         ~$0.10  narrow scaffold, generator, README stub
  S:  composer-2-fast      ~$0.40  single-file extraction, mechanical refactor
  M:  gpt-5.5-medium       ~$1.00  moderate cross-file, simple multi-step
  L:  claude-4.6-sonnet-medium-thinking  ~$3.00  cross-file reasoning, security

Opus is FORBIDDEN as subagent. The hook at .cursor/hooks/enforce-cheap-agent-model.sh
blocks such dispatches at the tool layer; this file enforces at the Python layer too.

Runs every 5 minutes via APScheduler.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from apscheduler.triggers.cron import CronTrigger

from app.models.dispatch import (
    CheapModel,
    DispatchEntry,
    DispatchResult,
    normalize_legacy_model,
)
from app.schedulers._history import run_with_scheduler_record
from app.schedulers._kill_switch_guard import (
    skip_if_brain_paused,
)

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import (
        AsyncIOScheduler,
    )

logger = logging.getLogger(__name__)

JOB_ID = "brain_autopilot_dispatcher"

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------

_DISPATCH_QUEUE_REL = Path("apis") / "brain" / "data" / "dispatch_queue.json"
_DISPATCH_LOG_REL = Path("apis") / "brain" / "data" / "agent_dispatch_log.jsonl"


def _repo_root() -> Path:
    env: str = os.environ.get("REPO_ROOT", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[4]


def _dispatch_queue_path() -> Path:
    env: str = os.environ.get("BRAIN_DISPATCH_QUEUE_JSON", "").strip()
    if env:
        return Path(env)
    return _repo_root() / _DISPATCH_QUEUE_REL


def _dispatch_log_path() -> Path:
    env: str = os.environ.get("BRAIN_DISPATCH_LOG_JSONL", "").strip()
    if env:
        return Path(env)
    return _repo_root() / _DISPATCH_LOG_REL


# ------------------------------------------------------------------
# Persona selection
# ------------------------------------------------------------------

_PRODUCT_PERSONA_MAP: dict[str, str] = {
    "axiomfolio": "ux-lead",
    "studio": "ux-lead",
    "filefree": "ux-lead",
    "distill": "engineering",
    "brain": "ops-engineer",
    "infra": "infra-ops",
}


def select_persona(
    entry: dict[str, Any],
) -> str:
    """Pick the best persona for a dispatch queue entry.

    Checks ``suggested_persona`` first (set by probe dispatcher),
    then falls back to product-based mapping, then ``ops-engineer``.
    """
    suggested: str = str(entry.get("suggested_persona", "")).strip()
    if suggested:
        return suggested

    product: str = str(entry.get("product", "")).lower()
    mapped: str = _PRODUCT_PERSONA_MAP.get(product, "")
    if mapped:
        return mapped

    return "ops-engineer"


# ------------------------------------------------------------------
# Agent model selection — T-Shirt sized (Wave L)
# ------------------------------------------------------------------

_COMPLEXITY_TO_SIZE: dict[str, CheapModel] = {
    "xs": "composer-1.5",
    "s": "composer-2-fast",
    "m": "gpt-5.5-medium",
    "l": "claude-4.6-sonnet-medium-thinking",
}

_EXPENSIVE_KEYWORDS: list[str] = [
    "architecture",
    "refactor",
    "migration",
    "security",
    "database",
    "schema",
]


def select_agent_model(
    entry: dict[str, Any],
) -> CheapModel:
    """Choose a T-Shirt sized model from the cheap allow-list.

    Priority order:
    1. ``agent_model`` explicitly set in the queue entry and valid → use it
    2. ``t_shirt_size`` explicitly set → map to model
    3. High-complexity keywords in description → L (claude-4.6-sonnet-medium-thinking)
    4. Default → S (composer-2-fast)

    Opus models are NEVER returned — this function enforces at the Python layer.
    The hook at .cursor/hooks/enforce-cheap-agent-model.sh enforces at the tool layer.
    """
    raw_model: str = str(entry.get("agent_model", "")).strip()
    normalized = normalize_legacy_model(raw_model)

    if normalized and normalized in _COMPLEXITY_TO_SIZE.values():
        return normalized  # type: ignore[return-value]

    explicit_size: str = str(entry.get("t_shirt_size", "")).strip().lower()
    if explicit_size in _COMPLEXITY_TO_SIZE:
        return _COMPLEXITY_TO_SIZE[explicit_size]

    desc: str = str(entry.get("description", "")).lower()
    error_msg: str = str(entry.get("error_message", "")).lower()
    combined: str = f"{desc} {error_msg}"
    for kw in _EXPENSIVE_KEYWORDS:
        if kw in combined:
            return "claude-4.6-sonnet-medium-thinking"

    return "composer-2-fast"


# ------------------------------------------------------------------
# Queue I/O
# ------------------------------------------------------------------


def load_dispatch_queue(
    path: Path,
) -> list[dict[str, Any]]:
    """Read pending entries from dispatch_queue.json."""
    if not path.exists():
        return []
    try:
        raw: dict[str, Any] = json.loads(
            path.read_text(encoding="utf-8"),
        )
        entries: list[dict[str, Any]] = raw.get("entries", [])
        return entries
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "autopilot_dispatcher: cannot read %s: %s",
            path,
            exc,
        )
        return []


def save_dispatch_queue(
    path: Path,
    entries: list[dict[str, Any]],
) -> None:
    """Write updated entries back to dispatch_queue.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema": "dispatch_queue/v1",
        "entries": entries[-500:],
    }
    path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


# ------------------------------------------------------------------
# Dispatch log (append-only JSONL)
# ------------------------------------------------------------------


def append_dispatch_log(
    path: Path,
    result: DispatchResult,
) -> None:
    """Append a single dispatch result as one JSONL line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line: str = result.model_dump_json()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# ------------------------------------------------------------------
# Core dispatch logic
# ------------------------------------------------------------------


def pending_entries(
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter to entries that have not been dispatched."""
    return [e for e in entries if not e.get("dispatched", False)]


def dispatch_entry(
    raw: dict[str, Any],
) -> tuple[DispatchEntry, DispatchResult]:
    """Process one queue row into a typed entry + result.

    agent_model MUST be set to a valid cheap model slug. No 'cheap'/'expensive' defaults.
    """
    persona: str = select_persona(raw)
    model: CheapModel = select_agent_model(raw)
    now = datetime.now(UTC)

    task_id: str = str(raw.get("id", ""))
    source_raw: str = str(raw.get("source", "probe"))
    if source_raw not in ("probe", "goal", "manual"):
        source_raw = "probe"

    entry = DispatchEntry(
        task_id=task_id,
        source=source_raw,
        description=str(raw.get("error_message", ""))[:500],
        product=str(raw.get("product", "")),
        persona_id=persona,
        agent_model=model,
        status="dispatched",
        created_at=now,
        dispatched_at=now,
    )

    result = DispatchResult(
        task_id=task_id,
        persona_id=persona,
        agent_model=model,
        outcome="dispatched",
    )

    return entry, result


def run_autopilot_dispatch_sync(
    *,
    queue_path: Path | None = None,
    log_path: Path | None = None,
) -> int:
    """Synchronous core: read queue, dispatch pending, log.

    Returns count of newly dispatched entries.
    """
    q_path: Path = queue_path or _dispatch_queue_path()
    l_path: Path = log_path or _dispatch_log_path()

    all_entries = load_dispatch_queue(q_path)
    todo = pending_entries(all_entries)

    if not todo:
        logger.info("autopilot_dispatcher: nothing pending")
        return 0

    dispatched: int = 0
    for raw in todo:
        _entry, result = dispatch_entry(raw)
        raw["dispatched"] = True
        raw["dispatched_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        raw["assigned_persona"] = _entry.persona_id
        raw["assigned_model"] = _entry.agent_model
        raw["t_shirt_size"] = _entry.t_shirt_size
        append_dispatch_log(l_path, result)
        dispatched += 1

    save_dispatch_queue(q_path, all_entries)
    logger.info(
        "autopilot_dispatcher: dispatched %d entries",
        dispatched,
    )
    return dispatched


# ------------------------------------------------------------------
# APScheduler plumbing
# ------------------------------------------------------------------


async def _run_autopilot_dispatcher_body() -> None:
    count = run_autopilot_dispatch_sync()
    logger.info(
        "autopilot_dispatcher tick: dispatched=%d",
        count,
    )


@skip_if_brain_paused(JOB_ID)
async def run_autopilot_dispatcher() -> None:
    """Public entry point invoked by APScheduler."""
    await run_with_scheduler_record(
        JOB_ID,
        _run_autopilot_dispatcher_body,
        metadata={
            "source": "autopilot_dispatcher",
            "wave": "AUTO PR-AU3",
        },
        reraise=True,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the autopilot dispatch loop (every 5 min)."""
    scheduler.add_job(
        run_autopilot_dispatcher,
        trigger=CronTrigger.from_crontab(
            "*/5 * * * *",
            timezone="UTC",
        ),
        id=JOB_ID,
        name=("Autopilot Dispatcher (Wave AUTO PR-AU3)"),
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info(
        "APScheduler job %r registered (*/5 * * * * UTC)",
        JOB_ID,
    )
