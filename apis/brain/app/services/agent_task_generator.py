"""Rule-based cheap-agent task specs from open work (no LLM).

Sources: open PRs, issues labeled ``ready``, optional founder-actions doc,
Studio ``tracker-index.json`` open items.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.config import settings
from app.schemas.agent_tasks import AgentTaskSpec
from app.services.sprint_planner import add_path_collision_dependencies, normalize_estimate, stable_task_hash

logger = logging.getLogger(__name__)

_GH = "https://api.github.com"
_URL_RE = re.compile(r"https?://\S+", re.I)
_LINT_RE = re.compile(r"lint|ruff|eslint|prettier|black|mypy|style|format", re.I)


def _repo_root() -> str:
    env = os.environ.get("REPO_ROOT")
    if env:
        return env
    here = os.path.abspath(os.path.dirname(__file__))
    brain_pkg = os.path.dirname(os.path.dirname(here))
    return os.path.abspath(os.path.join(brain_pkg, "..", ".."))


def _gh_headers() -> dict[str, str]:
    return {
        "Authorization": f"token {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }


def _repo_parts() -> tuple[str, str]:
    raw = settings.GITHUB_REPO.strip()
    parts = raw.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("GITHUB_REPO must be 'owner/repo'")
    return parts[0], parts[1]


PRBucket = Literal["DIRTY", "UNSTABLE", "MERGEABLE", "RED", "UNKNOWN"]


@dataclass
class _PRSnapshot:
    number: int
    title: str
    html_url: str
    head_sha: str
    base_ref: str
    draft: bool
    labels: list[str]
    mergeable: bool | None
    mergeable_state: str | None
    behind_by: int
    bucket: PRBucket
    failed_checks: list[str]
    pending_checks: int


async def _compare_behind(client: httpx.AsyncClient, owner: str, repo: str, base: str, head: str) -> int:
    try:
        r = await client.get(f"/repos/{owner}/{repo}/compare/{base}...{head}")
        if r.status_code != 200:
            return 0
        data: dict[str, Any] = r.json()
        return int(data.get("behind_by") or 0)
    except (httpx.HTTPError, ValueError, TypeError):
        return 0


async def _check_run_status(
    client: httpx.AsyncClient, owner: str, repo: str, sha: str
) -> tuple[list[str], int]:
    """Failed check names (completed + failure/cancelled/timed_out) and pending count."""
    failed: list[str] = []
    pending = 0
    page = 1
    try:
        while page <= 5:
            r = await client.get(
                f"/repos/{owner}/{repo}/commits/{sha}/check-runs",
                params={"per_page": 100, "page": page},
            )
            if r.status_code != 200:
                break
            payload: dict[str, Any] = r.json()
            rows = payload.get("check_runs") or []
            if not rows:
                break
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or "check")
                status = str(row.get("status") or "")
                conclusion = str(row.get("conclusion") or "")
                if status == "completed":
                    if conclusion in ("failure", "timed_out", "cancelled", "action_required"):
                        failed.append(name)
                elif status in ("queued", "in_progress", "waiting", "pending", "requested"):
                    pending += 1
            if len(rows) < 100:
                break
            page += 1
    except httpx.HTTPError:
        logger.warning("check-runs fetch failed for %s", sha[:7], exc_info=True)
    return failed, pending


def _classify_pr(
    *,
    behind_by: int,
    mergeable: bool | None,
    mergeable_state: str | None,
    failed: list[str],
    pending: int,
) -> PRBucket:
    if failed:
        return "RED"
    ms = (mergeable_state or "").lower()
    if behind_by > 0 or ms == "dirty":
        return "DIRTY"
    if pending > 0 or ms in ("blocked", "unstable"):
        return "UNSTABLE"
    if mergeable is True and ms == "clean":
        return "MERGEABLE"
    if mergeable is False and ms == "dirty":
        return "DIRTY"
    return "UNKNOWN"


async def _collect_open_prs(client: httpx.AsyncClient, owner: str, repo: str, limit: int = 25) -> list[_PRSnapshot]:
    r = await client.get(
        f"/repos/{owner}/{repo}/pulls",
        params={"state": "open", "per_page": min(limit, 30), "sort": "updated", "direction": "desc"},
    )
    r.raise_for_status()
    raw_prs: list[dict[str, Any]] = r.json()
    out: list[_PRSnapshot] = []
    for pr in raw_prs:
        if not isinstance(pr, dict):
            continue
        if pr.get("draft"):
            continue
        num = int(pr["number"])
        head = pr.get("head") or {}
        base = pr.get("base") or {}
        head_sha = str(head.get("sha") or "")
        base_ref = str(base.get("ref") or "main")
        if not head_sha:
            continue
        behind = await _compare_behind(client, owner, repo, base_ref, head_sha)
        failed, pending = await _check_run_status(client, owner, repo, head_sha)
        labels = [str(x.get("name", "")) for x in (pr.get("labels") or []) if isinstance(x, dict)]
        ms_raw = pr.get("mergeable_state")
        ms_val = str(ms_raw) if isinstance(ms_raw, str) else None
        mg = pr.get("mergeable")
        mergeable: bool | None = mg if isinstance(mg, bool) else None
        bucket = _classify_pr(
            behind_by=behind,
            mergeable=mergeable,
            mergeable_state=ms_val,
            failed=failed,
            pending=pending,
        )
        out.append(
            _PRSnapshot(
                number=num,
                title=str(pr.get("title") or ""),
                html_url=str(pr.get("html_url") or ""),
                head_sha=head_sha,
                base_ref=base_ref,
                draft=False,
                labels=labels,
                mergeable=mergeable,
                mergeable_state=ms_val,
                behind_by=behind,
                bucket=bucket,
                failed_checks=failed,
                pending_checks=pending,
            )
        )
    return out


def _pr_specs(pr: _PRSnapshot) -> list[AgentTaskSpec]:
    specs: list[AgentTaskSpec] = []
    base_paths = [f"pr-{pr.number}"]

    if (pr.bucket == "DIRTY" or pr.behind_by > 0) and not pr.failed_checks:
        tid = stable_task_hash(f"pr:{pr.number}:rebase")
        scope = (
            f"PR #{pr.number} is behind {pr.base_ref} (behind_by={pr.behind_by}). "
            f"Rebase or merge {pr.base_ref} into this branch, resolve any conflicts, run local checks, and push. "
            f"PR: {pr.html_url}"
        )
        specs.append(
            AgentTaskSpec(
                task_id=tid,
                title=f"PR #{pr.number}: rebase + push"[:80],
                scope=scope,
                estimated_minutes=15,
                agent_type="shell",
                model_hint="composer-2-fast",
                depends_on=[],
                touches_paths=list(base_paths),
                source={"kind": "pr", "ref": f"#{pr.number}", "bucket": "DIRTY", "url": pr.html_url},
            )
        )

    lint_fails = [n for n in pr.failed_checks if _LINT_RE.search(n)]
    non_lint_fails = [n for n in pr.failed_checks if not _LINT_RE.search(n)]
    if len(pr.failed_checks) == 1 and lint_fails and not non_lint_fails:
        tid = stable_task_hash(f"pr:{pr.number}:lint")
        scope = (
            f"Fix the single failing lint check `{pr.failed_checks[0]}` on PR #{pr.number}. "
            f"Run the same command CI uses, fix issues minimally, push. PR: {pr.html_url}"
        )
        specs.append(
            AgentTaskSpec(
                task_id=tid,
                title=f"PR #{pr.number}: fix lint ({pr.failed_checks[0][:40]})"[:80],
                scope=scope,
                estimated_minutes=5,
                agent_type="shell",
                model_hint="composer-2-fast",
                depends_on=[],
                touches_paths=list(base_paths),
                source={"kind": "pr", "ref": f"#{pr.number}", "bucket": "RED", "url": pr.html_url},
            )
        )
    elif pr.bucket == "RED" and pr.failed_checks:
        tid = stable_task_hash(f"pr:{pr.number}:ci")
        scope = (
            f"PR #{pr.number} has failing checks: {', '.join(pr.failed_checks[:8])}. "
            f"Reproduce locally or read CI logs, fix root cause, push. PR: {pr.html_url}"
        )
        specs.append(
            AgentTaskSpec(
                task_id=tid,
                title=f"PR #{pr.number}: fix failing CI"[:80],
                scope=scope,
                estimated_minutes=60,
                agent_type="generalPurpose",
                model_hint="gpt-5.5-medium",
                depends_on=[],
                touches_paths=list(base_paths),
                source={"kind": "pr", "ref": f"#{pr.number}", "bucket": "RED", "url": pr.html_url},
            )
        )

    if pr.bucket == "UNSTABLE" and not pr.failed_checks:
        tid = stable_task_hash(f"pr:{pr.number}:unstable")
        scope = (
            f"PR #{pr.number} is unstable/blocked or has pending checks ({pr.pending_checks} pending). "
            f"Review GitHub checks, wait or unblock, follow up until green. PR: {pr.html_url}"
        )
        specs.append(
            AgentTaskSpec(
                task_id=tid,
                title=f"PR #{pr.number}: unblock CI / merge"[:80],
                scope=scope,
                estimated_minutes=15,
                agent_type="shell",
                model_hint="composer-2-fast",
                depends_on=[],
                touches_paths=list(base_paths),
                source={"kind": "pr", "ref": f"#{pr.number}", "bucket": "UNSTABLE", "url": pr.html_url},
            )
        )

    return specs


async def _collect_ready_issues(client: httpx.AsyncClient, owner: str, repo: str, limit: int = 20) -> list[AgentTaskSpec]:
    specs: list[AgentTaskSpec] = []
    r = await client.get(
        f"/repos/{owner}/{repo}/issues",
        params={"state": "open", "labels": "ready", "per_page": min(limit, 30)},
    )
    if r.status_code != 200:
        return specs
    issues: list[dict[str, Any]] = r.json()
    for it in issues:
        if not isinstance(it, dict):
            continue
        if "pull_request" in it:
            continue
        num = int(it.get("number") or 0)
        if not num:
            continue
        labels = [str(x.get("name", "")).lower() for x in (it.get("labels") or []) if isinstance(x, dict)]
        if "bug" not in labels:
            continue
        url = str(it.get("html_url") or "")
        title = str(it.get("title") or "")[:80]
        body = str(it.get("body") or "")[:1200]
        tid = stable_task_hash(f"issue:{num}:bug")
        scope = (
            f"Issue #{num} is labeled `ready` and `bug`. Reproduce the defect, locate root cause, "
            f"implement a minimal fix with tests if applicable, open a PR. "
            f"\n\nTitle: {title}\n\nBody excerpt:\n{body}"
        )
        specs.append(
            AgentTaskSpec(
                task_id=tid,
                title=f"Issue #{num}: reproduce + fix"[:80],
                scope=scope,
                estimated_minutes=60,
                agent_type="generalPurpose",
                model_hint="gpt-5.5-medium",
                depends_on=[],
                touches_paths=[f"issue-{num}"],
                source={"kind": "issue", "ref": f"#{num}", "url": url},
            )
        )
    return specs


def _parse_founder_actions(repo_root: str) -> list[AgentTaskSpec]:
    fp = os.path.join(repo_root, "docs", "infra", "FOUNDER_ACTIONS.md")
    if not os.path.isfile(fp):
        return []
    specs: list[AgentTaskSpec] = []
    try:
        with open(fp, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _URL_RE.search(stripped):
            continue
        if len(stripped) < 12:
            continue
        tid = stable_task_hash(f"founder:{i}:{stripped[:60]}")
        scope = (
            "Founder action from FOUNDER_ACTIONS.md (no URL — safe for agent execution). "
            f"Complete the action, document outcome.\n\nLine:\n{stripped}"
        )
        specs.append(
            AgentTaskSpec(
                task_id=tid,
                title=stripped[:80],
                scope=scope,
                estimated_minutes=30,
                agent_type="generalPurpose",
                model_hint="gpt-5.5-medium",
                depends_on=[],
                touches_paths=["docs/infra/FOUNDER_ACTIONS.md"],
                source={"kind": "founder-action", "ref": f"line:{i + 1}"},
            )
        )
    return specs


def _tracker_open_items(repo_root: str) -> list[AgentTaskSpec]:
    path = os.path.join(repo_root, "apps", "studio", "src", "data", "tracker-index.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            idx: Any = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(idx, dict):
        return []
    specs: list[AgentTaskSpec] = []

    company = idx.get("company")
    if isinstance(company, dict):
        critical_rows = [r for r in (company.get("critical_dates") or []) if isinstance(r, dict)]
        for row in critical_rows[:12]:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "")
            if "DONE" in status.upper() and "partial" not in status.lower():
                continue
            milestone = str(row.get("milestone") or "")
            notes = str(row.get("notes") or "")
            acceptance = str(row.get("acceptance_criteria") or row.get("acceptance") or "")
            concrete = (acceptance and len(acceptance) > 20) or (len(notes) > 80)
            if not concrete or not milestone:
                continue
            tid = stable_task_hash(f"tracker:critical:{milestone[:80]}")
            minutes = 120 if len(notes) > 200 else 60
            scope = (
                f"Tracker item (company critical_dates): {milestone}\n\n"
                f"Notes:\n{notes[:1500]}\n\n"
                f"Acceptance:\n{acceptance or '(derive clear acceptance from notes and ship a minimal change)'}"
            )
            specs.append(
                AgentTaskSpec(
                    task_id=tid,
                    title=f"Tracker: {milestone[:72]}"[:80],
                    scope=scope,
                    estimated_minutes=normalize_estimate(minutes),
                    agent_type="generalPurpose",
                    model_hint="gpt-5.5-medium",
                    depends_on=[],
                    touches_paths=["apps/studio/src/data/tracker-index.json", "docs/TASKS.md"],
                    source={"kind": "tracker", "ref": f"critical:{milestone[:40]}"},
                )
            )

    plan_budget = 15
    for product in idx.get("products") or []:
        if plan_budget <= 0:
            break
        if not isinstance(product, dict):
            continue
        slug = str(product.get("slug") or "product")
        for plan in product.get("plans") or []:
            if plan_budget <= 0:
                break
            if not isinstance(plan, dict):
                continue
            st = str(plan.get("status") or plan.get("raw_status") or "")
            if st.lower() not in ("active", "in_progress"):
                continue
            ptitle = str(plan.get("title") or "")
            ppath = str(plan.get("path") or "")
            if not ppath or not ptitle:
                continue
            tid = stable_task_hash(f"tracker:plan:{slug}:{ppath}")
            scope = (
                f"Implement or advance active plan `{ptitle}` ({slug}). "
                f"Primary doc: `{ppath}`. Read the plan, pick the next shippable slice, implement, and open a PR."
            )
            specs.append(
                AgentTaskSpec(
                    task_id=tid,
                    title=f"Plan: {ptitle[:64]}"[:80],
                    scope=scope,
                    estimated_minutes=120,
                    agent_type="generalPurpose",
                    model_hint="gpt-5.5-medium",
                    depends_on=[],
                    touches_paths=[ppath],
                    source={"kind": "tracker", "ref": ppath, "product": slug},
                )
            )
            plan_budget -= 1

    return specs


async def generate() -> list[AgentTaskSpec]:
    """Collect and normalize task specs from all sources."""
    repo_root = _repo_root()
    tasks: list[AgentTaskSpec] = []
    tasks.extend(_parse_founder_actions(repo_root))
    tasks.extend(_tracker_open_items(repo_root))

    token = settings.GITHUB_TOKEN.strip()
    if token:
        owner, repo = _repo_parts()
        try:
            async with httpx.AsyncClient(base_url=_GH, headers=_gh_headers(), timeout=httpx.Timeout(60.0)) as client:
                prs = await _collect_open_prs(client, owner, repo)
                for pr in prs:
                    tasks.extend(_pr_specs(pr))
                tasks.extend(await _collect_ready_issues(client, owner, repo))
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("agent_task_generator: GitHub phase skipped: %s", e)
    else:
        logger.info("agent_task_generator: GITHUB_TOKEN empty — skipping PR/issue sources")

    for t in tasks:
        t.estimated_minutes = normalize_estimate(t.estimated_minutes)

    add_path_collision_dependencies(tasks)
    by_id: dict[str, AgentTaskSpec] = {}
    for t in tasks:
        by_id[t.task_id] = t
    return list(by_id.values())
