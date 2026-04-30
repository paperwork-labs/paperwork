"""Record merged PR outcomes from GitHub into ``pr_outcomes.json``.

Runs as an APScheduler interval job. The poller keeps a small state file with
``last_checked_at`` so each tick fetches only newly merged PRs. Missing
``GITHUB_TOKEN`` is a hard, visible skip: the job logs an error and records no
state advancement.

medallion: ops
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.services import pr_outcomes

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "pr_outcome_recorder"
_GH_API = "https://api.github.com"
_STATE_ENV = "BRAIN_PR_OUTCOME_RECORDER_STATE_JSON"
_TMP_SUFFIX = ".tmp"
_SUCCESS_CHECK_CONCLUSIONS = {"success", "skipped", "neutral"}
_FAILURE_CHECK_CONCLUSIONS = {
    "action_required",
    "cancelled",
    "failure",
    "startup_failure",
    "timed_out",
}


@dataclass(frozen=True)
class MergedPullRequest:
    number: int
    merged_at: str
    branch: str
    head_sha: str
    author: str


def _brain_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data"


def state_file_path() -> Path:
    env = os.environ.get(_STATE_ENV, "").strip()
    return Path(env) if env else _brain_data_dir() / "pr_outcome_recorder_state.json"


def _repo_parts() -> tuple[str, str]:
    raw = (settings.GITHUB_REPO or "").strip()
    parts = raw.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        msg = "GITHUB_REPO must be 'owner/repo'"
        raise ValueError(msg)
    return parts[0], parts[1]


def _github_token() -> str:
    return (settings.GITHUB_TOKEN or "").strip()


def _headers() -> dict[str, str]:
    token = _github_token()
    if not token:
        raise RuntimeError("GITHUB_TOKEN not configured; pr_outcome_recorder cannot poll GitHub")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _format_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_z(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _load_state() -> dict[str, Any]:
    path = state_file_path()
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        msg = f"{path} must contain a JSON object"
        raise ValueError(msg)
    return raw


def _write_state(data: dict[str, Any]) -> None:
    path = state_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}{_TMP_SUFFIX}")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _last_checked_at(now: datetime) -> datetime:
    raw = str(_load_state().get("last_checked_at") or "").strip()
    if not raw:
        return now - timedelta(hours=2)
    return _parse_z(raw)


async def _get_json(
    client: httpx.AsyncClient,
    path: str,
    *,
    params: dict[str, Any] | None = None,
) -> Any:
    res = await client.get(path, params=params)
    res.raise_for_status()
    return res.json()


def _parse_pr_payload(pr: dict[str, Any]) -> MergedPullRequest | None:
    merged_at = str(pr.get("merged_at") or "").strip()
    if not merged_at:
        return None
    head_raw = pr.get("head")
    head: dict[str, Any] = head_raw if isinstance(head_raw, dict) else {}
    user_raw = pr.get("user")
    user: dict[str, Any] = user_raw if isinstance(user_raw, dict) else {}
    return MergedPullRequest(
        number=int(pr.get("number") or 0),
        merged_at=merged_at,
        branch=str(head.get("ref") or ""),
        head_sha=str(head.get("sha") or ""),
        author=str(user.get("login") or "unknown"),
    )


async def _fetch_merged_prs_since(
    client: httpx.AsyncClient,
    since: datetime,
    *,
    limit: int = 100,
) -> list[MergedPullRequest]:
    owner, repo = _repo_parts()
    q = f"repo:{owner}/{repo} is:pr is:merged merged:>={since.date().isoformat()}"
    search = await _get_json(
        client,
        "/search/issues",
        params={"q": q, "sort": "updated", "order": "desc", "per_page": min(max(limit, 1), 100)},
    )
    items = search.get("items") if isinstance(search, dict) else None
    if not isinstance(items, list):
        msg = "GitHub search/issues response missing items list"
        raise ValueError(msg)

    out: list[MergedPullRequest] = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("number"), int):
            continue
        pr = await _get_json(client, f"/repos/{owner}/{repo}/pulls/{item['number']}")
        if not isinstance(pr, dict):
            continue
        parsed = _parse_pr_payload(pr)
        if parsed is None:
            continue
        if _parse_z(parsed.merged_at) <= since:
            continue
        out.append(parsed)
    out.sort(key=lambda row: row.merged_at)
    return out


async def _ci_status_for_sha(client: httpx.AsyncClient, sha: str) -> str:
    if not sha:
        return "unknown"
    owner, repo = _repo_parts()
    payload = await _get_json(
        client,
        f"/repos/{owner}/{repo}/commits/{sha}/check-runs",
        params={"per_page": 100},
    )
    runs = payload.get("check_runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list) or not runs:
        return "no_checks"
    conclusions = [
        str(run.get("conclusion") or "").lower() for run in runs if isinstance(run, dict)
    ]
    statuses = [str(run.get("status") or "").lower() for run in runs if isinstance(run, dict)]
    if any(status != "completed" for status in statuses):
        return "pending"
    if any(conclusion in _FAILURE_CHECK_CONCLUSIONS for conclusion in conclusions):
        return "failure"
    if all(conclusion in _SUCCESS_CHECK_CONCLUSIONS for conclusion in conclusions):
        return "success"
    return "unknown"


async def _deploy_success_for_sha(client: httpx.AsyncClient, sha: str) -> bool:
    if not sha:
        return False
    owner, repo = _repo_parts()
    deployments = await _get_json(
        client,
        f"/repos/{owner}/{repo}/deployments",
        params={"sha": sha, "per_page": 20},
    )
    if not isinstance(deployments, list):
        msg = "GitHub deployments response must be a list"
        raise ValueError(msg)
    for deployment in deployments:
        if not isinstance(deployment, dict) or not deployment.get("id"):
            continue
        statuses = await _get_json(
            client,
            f"/repos/{owner}/{repo}/deployments/{deployment['id']}/statuses",
            params={"per_page": 20},
        )
        if isinstance(statuses, list) and any(
            isinstance(status, dict) and status.get("state") == "success" for status in statuses
        ):
            return True
    return False


async def _was_reverted(client: httpx.AsyncClient, pr_number: int) -> bool:
    owner, repo = _repo_parts()
    q = f'repo:{owner}/{repo} is:pr is:merged "PR #{pr_number}" Revert'
    payload = await _get_json(
        client,
        "/search/issues",
        params={"q": q, "per_page": 10},
    )
    total = payload.get("total_count") if isinstance(payload, dict) else None
    if not isinstance(total, int):
        msg = "GitHub revert search response missing total_count"
        raise ValueError(msg)
    return total > 0


def _dispatch_log_path() -> Path:
    env = os.environ.get("BRAIN_AGENT_DISPATCH_LOG_JSON", "").strip()
    return Path(env) if env else _brain_data_dir() / "agent_dispatch_log.json"


def _dispatch_for_pr(pr_number: int) -> dict[str, Any] | None:
    path = _dispatch_log_path()
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    rows = raw.get("dispatches") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("pr_number") == pr_number:
            return row
    return None


def _metadata_for_pr(pr: MergedPullRequest) -> tuple[str, str, str, list[str], list[str]]:
    dispatch = _dispatch_for_pr(pr.number)
    if dispatch is None:
        return (pr.author or "unknown", "unknown", "unknown", [], [])
    dispatch_id = str(dispatch.get("dispatch_id") or "unknown")
    agent_model = str(dispatch.get("agent_model") or "unknown")
    subagent_type = str(dispatch.get("subagent_type") or "unknown")
    workstream_id = str(dispatch.get("workstream_id") or "").strip()
    workstream_type = str(dispatch.get("workstream_type") or "").strip()
    return (
        f"brain-{dispatch_id}",
        agent_model,
        subagent_type,
        [workstream_id] if workstream_id else [],
        [workstream_type] if workstream_type else [],
    )


async def _record_new_pr(
    client: httpx.AsyncClient,
    pr: MergedPullRequest,
    *,
    overwrite_existing: bool,
) -> bool:
    ci_status = await _ci_status_for_sha(client, pr.head_sha)
    merged_by_agent, agent_model, subagent_type, workstream_ids, workstream_types = (
        _metadata_for_pr(pr)
    )
    try:
        pr_outcomes.record_merged_pr(
            pr.number,
            pr.merged_at,
            merged_by_agent,
            agent_model,
            subagent_type,
            workstream_ids,
            workstream_types,
            branch=pr.branch,
            ci_status_at_merge=ci_status,
            overwrite_existing=overwrite_existing,
        )
    except ValueError as exc:
        if "already recorded" in str(exc):
            logger.info("pr_outcome_recorder: PR #%d already recorded; skipping", pr.number)
            return False
        raise
    return True


async def backfill_last_days(days: int = 60) -> dict[str, int]:
    """Backfill merged PR outcomes for the last ``days`` days, idempotently."""
    now = _now_utc()
    since = now - timedelta(days=max(days, 1))
    recorded = 0
    async with httpx.AsyncClient(
        base_url=_GH_API,
        headers=_headers(),
        timeout=httpx.Timeout(90.0),
    ) as client:
        for pr in await _fetch_merged_prs_since(client, since, limit=100):
            if await _record_new_pr(client, pr, overwrite_existing=True):
                recorded += 1
    return {"recorded": recorded}


async def run_once() -> dict[str, int | str | bool]:
    """Poll GitHub once and update newly merged PRs plus due h24 outcomes."""
    try:
        headers = _headers()
    except RuntimeError as exc:
        logger.error("pr_outcome_recorder skipped: %s", exc)
        return {"ok": False, "error": str(exc), "recorded": 0, "h24_updated": 0}

    now = _now_utc()
    since = _last_checked_at(now)
    recorded = 0
    h24_updated = 0
    async with httpx.AsyncClient(
        base_url=_GH_API,
        headers=headers,
        timeout=httpx.Timeout(90.0),
    ) as client:
        for pr in await _fetch_merged_prs_since(client, since):
            if await _record_new_pr(client, pr, overwrite_existing=False):
                recorded += 1

        for row in pr_outcomes.list_pr_outcomes_for_query(limit=1000):
            if row.outcomes.h24 is not None:
                continue
            merged_at = _parse_z(row.merged_at)
            if merged_at > now - timedelta(hours=24):
                continue
            owner, repo = _repo_parts()
            pr_payload = await _get_json(client, f"/repos/{owner}/{repo}/pulls/{row.pr_number}")
            if not isinstance(pr_payload, dict):
                msg = f"GitHub PR payload for #{row.pr_number} must be an object"
                raise ValueError(msg)
            parsed = _parse_pr_payload(pr_payload)
            sha = parsed.head_sha if parsed is not None else ""
            ci_status = await _ci_status_for_sha(client, sha)
            deploy_success = await _deploy_success_for_sha(client, sha)
            reverted = await _was_reverted(client, row.pr_number)
            pr_outcomes.update_outcome_h24(
                row.pr_number,
                ci_pass=ci_status == "success",
                deploy_success=deploy_success,
                reverted=reverted,
            )
            h24_updated += 1

    _write_state({"last_checked_at": _format_z(now), "updated_at": _format_z(now)})
    return {"ok": True, "recorded": recorded, "h24_updated": h24_updated}


@skip_if_brain_paused(JOB_ID)
async def run_pr_outcome_recorder_job() -> None:
    try:
        report = await run_once()
        if report.get("ok"):
            logger.info(
                "pr_outcome_recorder: recorded=%d h24_updated=%d",
                report.get("recorded", 0),
                report.get("h24_updated", 0),
            )
        else:
            logger.error("pr_outcome_recorder: %s", report.get("error", "unknown error"))
    except Exception:
        logger.exception("pr_outcome_recorder raised — will retry next interval")


def install(scheduler: AsyncIOScheduler) -> None:
    minutes = max(1, int(getattr(settings, "SCHEDULER_PR_OUTCOME_RECORDER_MINUTES", 0) or 30))
    scheduler.add_job(
        run_pr_outcome_recorder_job,
        trigger=IntervalTrigger(minutes=minutes, timezone=UTC),
        id=JOB_ID,
        name="Brain PR outcome recorder",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job %r registered (every %d minutes UTC)", JOB_ID, minutes)


def run_backfill_cli(days: int = 60) -> dict[str, int]:
    return asyncio.run(backfill_last_days(days=days))
