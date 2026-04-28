"""Track G — weekly QA health digest.

Sunday 17:00 UTC (≈10am PT): Brain posts a compact "how are the agents
holding up?" digest to the #qa channel. Zero LLM spend — this is a
deterministic readout of registry state, so it stays reliable even if
upstream LLMs are down.

What lands in #qa:
1. Persona coverage: counts of specs, rules files, router keywords.
2. Guardrail coverage: personas missing ceilings / rate limits / output
   caps.
3. Golden-suite pointer: link to the latest nightly CI run so QA can
   open it if something looks off.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.personas import list_specs
from app.services import slack_outbound

logger = logging.getLogger(__name__)


def _drift_baseline_path() -> Path:
    """Locate ``docs/.doc-drift-baseline.json`` from anywhere we might be running.

    In dev (monorepo checkout) ``parents[4]`` is the repo root. In the Brain
    Docker image the file is bundled at ``/app/docs/.doc-drift-baseline.json``
    (see ``apis/brain/Dockerfile``), so we prefer ``$REPO_ROOT`` / ``/app`` and
    fall back to the parents-based lookup. Never raise at import time.
    """
    env = os.environ.get("REPO_ROOT")
    if env:
        return Path(env) / "docs" / ".doc-drift-baseline.json"
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / ".doc-drift-baseline.json"
        if candidate.exists():
            return candidate
    # Final fallback: container layout (`/app/docs/...`). Returned even if it
    # does not exist; callers are expected to handle missing files via
    # ``_load_drift_baseline`` which fails open to ``(0, 0)``.
    return Path("/app") / "docs" / ".doc-drift-baseline.json"


_DRIFT_BASELINE = _drift_baseline_path()


def _load_drift_baseline() -> tuple[int, int]:
    """Return (dead_refs, stale_lines) from the baseline snapshot.

    Track K: the baseline is the snapshot of known doc/code drift. CI
    catches *new* drift; the weekly report surfaces the residual debt so
    we remember to pay it down. Fails open to (0, 0) if the file is
    missing.
    """
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
        f"*QA · weekly agent health — {today}*",
        "",
        f"• *Personas registered:* {total}",
        f"• *Compliance-flagged:* {len(compliance)} (`{', '.join(sorted(compliance)) or 'none'}`)",
    ]

    if missing_ceiling or missing_rate_limit or missing_output_cap:
        lines.append("")
        lines.append(":warning: *Guardrail gaps:*")
        if missing_ceiling:
            lines.append(
                f"• Missing `daily_cost_ceiling_usd`: `{', '.join(sorted(missing_ceiling))}`"
            )
        if missing_rate_limit:
            lines.append(
                f"• Missing `requests_per_minute`: `{', '.join(sorted(missing_rate_limit))}`"
            )
        if missing_output_cap:
            lines.append(
                f"• Missing `max_output_tokens`: `{', '.join(sorted(missing_output_cap))}`"
            )
    else:
        lines.append("")
        lines.append(":white_check_mark: All personas have ceilings, rate limits, and output caps.")

    dead_refs, stale_lines = _load_drift_baseline()
    lines.append("")
    if dead_refs or stale_lines:
        lines.append(
            f":books: *Doc ↔ code drift debt:* {dead_refs} dead refs, "
            f"{stale_lines} stale line numbers (baseline)."
        )
    else:
        lines.append(":books: *Doc ↔ code drift:* clean :sparkles:")

    lines.append("")
    lines.append(
        "_Nightly golden-suite results: "
        "<https://github.com/paperwork-labs/paperwork/actions/workflows/"
        "brain-golden-suite.yaml|GitHub Actions>._"
    )
    return "\n".join(lines)


async def _run_weekly_tick() -> None:
    body = _build_digest()
    channel_id = settings.SLACK_QA_CHANNEL_ID or settings.SLACK_ENGINEERING_CHANNEL_ID
    if not channel_id:
        logger.info("qa weekly: no target channel configured, skipping")
        return
    await slack_outbound.post_message(
        channel=channel_id,
        text=body,
        username="QA",
        icon_emoji=":detective:",
        unfurl_links=False,
    )
    logger.info("qa weekly digest posted to %s", channel_id)


def install(scheduler) -> None:
    scheduler.add_job(
        _run_weekly_tick,
        trigger=CronTrigger(day_of_week="sun", hour=17, minute=0, timezone="UTC"),
        id="qa_weekly_report",
        name="QA weekly agent health digest",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("APScheduler job 'qa_weekly_report' registered (Sunday 17:00 UTC)")
