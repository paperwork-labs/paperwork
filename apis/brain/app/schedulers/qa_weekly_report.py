"""Track G — weekly QA health digest via Brain Conversations (WS-69 PR J).

Sunday 17:00 UTC (≈10am PT): Brain creates a compact "how are the agents
holding up?" Conversation. Zero LLM spend — deterministic readout of registry
state. Replaces the previous Slack post to #qa.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from apscheduler.triggers.cron import CronTrigger

from app.personas import list_specs
from app.schemas.conversation import ConversationCreate
from app.services.conversations import create_conversation

logger = logging.getLogger(__name__)


def _drift_baseline_path() -> Path:
    env = os.environ.get("REPO_ROOT")
    if env:
        return Path(env) / "docs" / ".doc-drift-baseline.json"
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / ".doc-drift-baseline.json"
        if candidate.exists():
            return candidate
    return Path("/app") / "docs" / ".doc-drift-baseline.json"


_DRIFT_BASELINE = _drift_baseline_path()


def _load_drift_baseline() -> tuple[int, int]:
    if not _DRIFT_BASELINE.exists():
        return (0, 0)
    try:
        payload = json.loads(_DRIFT_BASELINE.read_text())
    except (OSError, json.JSONDecodeError):
        return (0, 0)
    return (
        len(payload.get("dead", []) or []),
        len(payload.get("stale", []) or []),
    )


def _build_digest() -> str:
    specs = list_specs()
    total = len(specs)

    missing_ceiling = [s.name for s in specs if s.daily_cost_ceiling_usd is None]
    missing_rate_limit = [s.name for s in specs if s.requests_per_minute is None]
    missing_output_cap = [s.name for s in specs if s.max_output_tokens is None]
    compliance = [s.name for s in specs if s.compliance_flagged]

    today = datetime.now(UTC).date().isoformat()
    lines = [
        f"**QA · weekly agent health — {today}**",
        "",
        f"- **Personas registered:** {total}",
        f"- **Compliance-flagged:** {len(compliance)}"
        f" (`{', '.join(sorted(compliance)) or 'none'}`)",
    ]

    if missing_ceiling or missing_rate_limit or missing_output_cap:
        lines.append("")
        lines.append("**Guardrail gaps:**")
        if missing_ceiling:
            lines.append(
                f"- Missing `daily_cost_ceiling_usd`: `{', '.join(sorted(missing_ceiling))}`"
            )
        if missing_rate_limit:
            lines.append(
                f"- Missing `requests_per_minute`: `{', '.join(sorted(missing_rate_limit))}`"
            )
        if missing_output_cap:
            lines.append(
                f"- Missing `max_output_tokens`: `{', '.join(sorted(missing_output_cap))}`"
            )
    else:
        lines.append("")
        lines.append("All personas have ceilings, rate limits, and output caps.")

    dead_refs, stale_lines = _load_drift_baseline()
    lines.append("")
    if dead_refs or stale_lines:
        lines.append(
            f"**Doc ↔ code drift debt:** {dead_refs} dead refs, "
            f"{stale_lines} stale line numbers (baseline)."
        )
    else:
        lines.append("**Doc ↔ code drift:** clean")

    lines.append("")
    lines.append(
        "Nightly golden-suite: "
        "https://github.com/paperwork-labs/paperwork/actions/workflows/brain-golden-suite.yaml"
    )
    return "\n".join(lines)


async def _run_weekly_tick() -> None:
    body = _build_digest()
    today = datetime.now(UTC).date().isoformat()
    create_conversation(
        ConversationCreate(
            title=f"QA Weekly Agent Health — {today}",
            body_md=body,
            tags=["qa"],
            urgency="normal",
            persona="qa",
            needs_founder_action=False,
        )
    )
    logger.info("qa weekly digest created as conversation")


def install(scheduler) -> None:
    scheduler.add_job(
        _run_weekly_tick,
        trigger=CronTrigger(day_of_week="sun", hour=17, minute=0, timezone="UTC"),
        id="qa_weekly_report",
        name="QA weekly agent health digest",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job 'qa_weekly_report' registered (Sunday 17:00 UTC)")
