"""Scheduled sprint doc auto-close (``closes_pr_urls`` / ``closes_workstreams``).

Pairs with :mod:`app.services.sprint_md_auto_close` — opens one batched PR when
any sprint markdown should transition to ``status: closed``.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC
from typing import TYPE_CHECKING

from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.schedulers._history import run_with_scheduler_record
from app.services import sprint_md_auto_close as smac
from app.tools import github as gh
from app.tools.redis import release_scheduler_lock, try_acquire_scheduler_lock

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "sprint_md_auto_close"
_SCHEDULER_LOCK_KEY = "brain:scheduler:sprint_md_auto_close:lock"
_SCHEDULER_LOCK_TTL_SECONDS = 300


async def _run_body() -> None:
    if not settings.GITHUB_TOKEN.strip():
        logger.warning("sprint_md_auto_close: GITHUB_TOKEN empty — skipping")
        return

    updates = await smac.collect_sprint_auto_close_updates()
    if not updates:
        logger.info("sprint_md_auto_close: no sprint files to close")
        return

    ts = int(time.time())
    branch = f"auto/sprint-close-{ts}"
    main_sha = await gh.get_git_ref_sha("main")
    if not main_sha:
        logger.error(
            "INCIDENT_CANDIDATE sprint_md_auto_close: could not resolve main — cannot open PR"
        )
        return
    if not await gh.create_git_ref(branch, main_sha):
        logger.error(
            "INCIDENT_CANDIDATE sprint_md_auto_close: could not create branch %s",
            branch,
        )
        return

    message = "chore(sprints): auto-close sprint frontmatter (PRs + workstreams done)"
    commit_sha = await gh.commit_files_to_branch(branch, message, updates)
    if not commit_sha:
        logger.error(
            "INCIDENT_CANDIDATE sprint_md_auto_close: commit_files_to_branch failed for %s",
            branch,
        )
        return

    paths = ", ".join(f"`{p}`" for p in sorted(updates.keys())[:12])
    if len(updates) > 12:
        paths += " …"
    body = "\n".join(
        [
            "[auto-close]",
            "",
            "Automated sprint closure: all configured `closes_pr_urls` merged and "
            "all `closes_workstreams` are `completed` on the workstreams board.",
            "",
            paths,
            "",
            f"_Commit: `{commit_sha[:7]}`_",
        ]
    )
    title = "chore(sprints): auto-close sprint frontmatter"
    pr_payload = await gh.create_github_pull(
        head=branch,
        base="main",
        title=title[:256],
        body=body,
    )
    if pr_payload:
        logger.info("sprint_md_auto_close: opened PR #%s", pr_payload.get("number"))
    else:
        logger.error(
            "INCIDENT_CANDIDATE sprint_md_auto_close: create_github_pull failed for branch %s",
            branch,
        )


async def run_sprint_md_auto_close_job() -> None:
    async def _runner() -> None:
        acquired = await try_acquire_scheduler_lock(
            _SCHEDULER_LOCK_KEY,
            _SCHEDULER_LOCK_TTL_SECONDS,
        )
        if not acquired:
            logger.info("sprint_md_auto_close: another worker holds the lock, skipping")
            return
        try:
            await _run_body()
        finally:
            await release_scheduler_lock(_SCHEDULER_LOCK_KEY)

    await run_with_scheduler_record(
        _JOB_ID,
        _runner,
        metadata={"source": "sprint_md_auto_close"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_sprint_md_auto_close_job,
        trigger=IntervalTrigger(hours=12, timezone=UTC),
        id=_JOB_ID,
        name="Sprint auto-close (merged PRs + completed workstreams → status: closed)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=120,
    )
    logger.info("sprint_md_auto_close installed: every 12 hours at :17 UTC")
