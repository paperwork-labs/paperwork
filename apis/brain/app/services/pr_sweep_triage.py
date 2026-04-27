"""Optional PR classifiers (stale, ready-to-review nudge, rebase assist).

Gated by ``settings.BRAIN_OWNS_PR_TRIAGE``. When disabled, this module
returns immediately without calling GitHub.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings
from app.tools.github import _gh_client, _repo_parts

logger = logging.getLogger(__name__)

STALE_DAYS = 7
READY_REVIEW_HOURS = 24
REBASE_DIRTY_HOURS = 4

# Issue/PR body markers (HTML comments, hidden in rendered markdown)
STALE_MARKER_PREFIX = "<!-- brain-triage:stale:"
THIN_REVIEW_MARKER_PREFIX = "<!-- brain-triage:thin-review:"
DIRTY_FIRST_SEEN_PREFIX = "<!-- brain-triage:merge-dirty-seen:"
REBASE_DISPATCHED_PREFIX = "<!-- brain-triage:rebase-dispatched:"


def _parse_github_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except (ValueError, TypeError):
        return None


def find_last_activity_at(
    *,
    pr_updated: str | None,
    last_commit: str | None,
    last_issue_comment: str | None,
) -> datetime | None:
    cands = [x for x in (_parse_github_ts(pr_updated), _parse_github_ts(last_commit), _parse_github_ts(last_issue_comment)) if x]
    if not cands:
        return None
    return max(cands)


def is_stale_inactive(*, last_activity: datetime | None, now: datetime, stale_days: int = STALE_DAYS) -> bool:
    if last_activity is None:
        return False
    return (now - last_activity).total_seconds() >= stale_days * 86400


def has_marker(body: str | None, prefix: str) -> bool:
    if not body:
        return False
    return prefix in body


def extract_marker_timestamps(body: str, prefix: str) -> list[datetime]:
    if not body:
        return []
    return [d for m in re.finditer(re.escape(prefix) + r"([^>]+)-->", body) if (d := _parse_github_ts(m.group(1).strip()))]


def stale_ping_cooldown_ok(*, issue_comment_bodies: list[str], now: datetime) -> bool:
    """At most one stale nudge per 7d (same window as inactivity)."""
    latest: datetime | None = None
    for b in issue_comment_bodies:
        for t in extract_marker_timestamps(b or "", STALE_MARKER_PREFIX):
            if latest is None or t > latest:
                latest = t
    if latest is None:
        return True
    return (now - latest).total_seconds() >= STALE_DAYS * 86400


def should_dispatch_rebase(
    *,
    first_dirty_marked: datetime | None,
    now: datetime,
    rebase_already_dispatched: bool,
    hours: float = REBASE_DIRTY_HOURS,
) -> bool:
    if rebase_already_dispatched or first_dirty_marked is None:
        return False
    return (now - first_dirty_marked).total_seconds() >= hours * 3600


def has_thin_review_for_sha(issue_comment_bodies: list[str], head_sha: str) -> bool:
    token = f"{THIN_REVIEW_MARKER_PREFIX}{head_sha}-->"
    for b in issue_comment_bodies:
        if token in (b or ""):
            return True
    return False


def should_post_ready_nudge(
    *,
    has_green_ci: bool,
    last_activity_on_thread: datetime | None,
    now: datetime,
    head_sha: str,
    issue_comment_bodies: list[str],
    hours: float = READY_REVIEW_HOURS,
) -> bool:
    if not has_green_ci or not head_sha:
        return False
    if has_thin_review_for_sha(issue_comment_bodies, head_sha):
        return False
    if last_activity_on_thread and (now - last_activity_on_thread).total_seconds() < hours * 3600:
        return False
    return True


def format_stale_nudge(author: str) -> str:
    handle = f"@{author}" if author and not author.endswith("[bot]") else author or "author"
    return (
        f"### Stale PR nudge (Brain triage)\n\n"
        f"{handle} This PR has been **quiet for {STALE_DAYS}+ days** — no recent commits or discussion. "
        f"Please drop a short status update or close if it is no longer needed.\n\n"
        f"{STALE_MARKER_PREFIX}{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}-->"
    )


def format_thin_copilot_style_review(head_sha: str) -> str:
    return (
        "### Copilot-style quick pass (Brain triage)\n\n"
        "**🟢 GREEN** — CI is green. From a **queue-health** perspective this is ready for human review; "
        "this is a lightweight nudge, not a full diff audit.\n\n"
        f"{THIN_REVIEW_MARKER_PREFIX}{head_sha}-->\n"
    )


def format_dirty_first_seen(mergeable_state: str | None) -> str:
    return (
        "### Merge conflict (Brain triage)\n\n"
        f"Recorded `mergeable_state={mergeable_state!r}`. A rebase/merge from `main` can be attempted "
        f"if this remains unmergeable (cooldown: {int(REBASE_DIRTY_HOURS)}h).\n\n"
        f"{DIRTY_FIRST_SEEN_PREFIX}{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}-->"
    )


def format_rebase_queued() -> str:
    return (
        "### Rebase assist (Brain triage)\n\n"
        f"Queueing the `rebase-pr` workflow to rebase this branch onto `main` (best effort).\n\n"
        f"{REBASE_DISPATCHED_PREFIX}{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}-->"
    )


def is_merge_conflict(mergeable: bool | None, mergeable_state: str | None) -> bool:
    """True when GitHub reports merge **conflicts** (DIRTY), not check failures."""
    st = (mergeable_state or "").lower()
    if st == "dirty":
        return True
    if mergeable is False and st in ("", "unknown"):
        return True
    return False


def _triage_globally_off() -> bool:
    return not bool(getattr(settings, "BRAIN_OWNS_PR_TRIAGE", False))


async def _get_json(client: httpx.AsyncClient, path: str, params: dict[str, Any] | None = None) -> Any:
    r = await client.get(path, params=params)
    r.raise_for_status()
    return r.json()


async def _post_comment(client: httpx.AsyncClient, owner: str, repo: str, pr_number: int, body: str) -> bool:
    r = await client.post(
        f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
        json={"body": body},
    )
    if r.status_code not in (200, 201):
        logger.warning("post comment PR#%s failed: %s", pr_number, r.text[:300])
        return False
    return True


async def _dispatch_rebase_workflow(client: httpx.AsyncClient, owner: str, repo: str, pr_number: int) -> bool:
    r = await client.post(
        f"/repos/{owner}/{repo}/actions/workflows/rebase-pr.yaml/dispatches",
        json={"ref": "main", "inputs": {"pr_number": str(pr_number)}},
    )
    if r.status_code not in (200, 204):
        logger.warning("rebase dispatch failed #%s: %s", pr_number, r.text[:300])
        return False
    return True


def _earliest_first_dirty_marker(issue_comment_bodies: list[str]) -> datetime | None:
    out: list[datetime] = []
    for b in issue_comment_bodies:
        out.extend(extract_marker_timestamps(b or "", DIRTY_FIRST_SEEN_PREFIX))
    if not out:
        return None
    return min(out)


def rebase_was_dispatched(issue_comment_bodies: list[str]) -> bool:
    for b in issue_comment_bodies:
        if REBASE_DISPATCHED_PREFIX in (b or ""):
            return True
    return False


async def run_pr_triage_sweep(
    *,
    org_id: str = "paperwork-labs",
    limit: int = 30,
) -> dict[str, Any]:
    _ = org_id
    if _triage_globally_off():
        return {"ok": True, "skipped": "BRAIN_OWNS_PR_TRIAGE=false", "stale": [], "ready": [], "rebase": []}

    if not settings.GITHUB_TOKEN.strip():
        return {"ok": False, "error": "no GITHUB_TOKEN", "stale": [], "ready": [], "rebase": []}

    owner, repo = _repo_parts()
    now = datetime.now(timezone.utc)
    stale_out: list[dict[str, Any]] = []
    ready_out: list[dict[str, Any]] = []
    rebase_out: list[dict[str, Any]] = []

    try:
        async with _gh_client() as client:
            r = await client.get(
                f"/repos/{owner}/{repo}/pulls",
                params={"state": "open", "per_page": min(max(limit, 1), 100), "sort": "updated", "direction": "desc"},
            )
            r.raise_for_status()
            prs: list[dict[str, Any]] = r.json()

            for pr in prs:
                number = int(pr.get("number") or 0)
                if not number or pr.get("draft"):
                    continue
                user = (pr.get("user") or {}).get("login") or ""
                if user in ("dependabot[bot]", "dependabot-preview[bot]"):
                    continue

                pr_full = await _get_json(client, f"/repos/{owner}/{repo}/pulls/{number}")
                mergeable = pr_full.get("mergeable")
                mergeable_state = pr_full.get("mergeable_state")
                mst = (str(mergeable_state) or None)
                head_sha = str(((pr_full.get("head") or {}).get("sha") or "")).strip()
                pr_updated = str(pr_full.get("updated_at") or "")

                commits = await _get_json(
                    client, f"/repos/{owner}/{repo}/pulls/{number}/commits", params={"per_page": 100}
                )
                last_commit: str | None = None
                if isinstance(commits, list) and commits:
                    last = commits[-1] if isinstance(commits[-1], dict) else {}
                    cobj = (last.get("commit") or {}) if isinstance(last, dict) else {}
                    if isinstance(cobj, dict):
                        last_commit = (cobj.get("author") or {}).get("date") or (cobj.get("committer") or {}).get("date")

                ic = await _get_json(
                    client, f"/repos/{owner}/{repo}/issues/{number}/comments", params={"per_page": 100}
                )
                ic_list = ic if isinstance(ic, list) else []
                last_ic: str | None = None
                last_activity_on_thread: datetime | None = None
                bodies: list[str] = []
                for c in ic_list:
                    cb = c.get("body") or ""
                    bodies.append(cb)
                    t = c.get("created_at")
                    if t:
                        last_ic = t
                    d = _parse_github_ts(c.get("created_at"))
                    if d and (last_activity_on_thread is None or d > last_activity_on_thread):
                        last_activity_on_thread = d

                last_act = find_last_activity_at(
                    pr_updated=pr_updated, last_commit=last_commit, last_issue_comment=last_ic
                )
                if (
                    is_stale_inactive(last_activity=last_act, now=now)
                    and stale_ping_cooldown_ok(issue_comment_bodies=bodies, now=now)
                ):
                    body = format_stale_nudge(user)
                    if await _post_comment(client, owner, repo, number, body):
                        stale_out.append({"number": number, "action": "stale_nudge"})

                check_runs = await _get_json(
                    client,
                    f"/repos/{owner}/{repo}/commits/{head_sha}/check-runs",
                    params={"per_page": 100},
                )
                not_ready: list[dict[str, Any]] = []
                for c in (check_runs or {}).get("check_runs", []) or []:
                    st = c.get("status")
                    concl = (c.get("conclusion") or "").lower()
                    if st == "completed" and concl in ("success", "skipped", "neutral"):
                        continue
                    not_ready.append(c)
                has_green = len(not_ready) == 0 and bool(head_sha)

                if should_post_ready_nudge(
                    has_green_ci=has_green,
                    last_activity_on_thread=last_activity_on_thread,
                    now=now,
                    head_sha=head_sha,
                    issue_comment_bodies=bodies,
                ):
                    t_body = format_thin_copilot_style_review(head_sha)
                    if await _post_comment(client, owner, repo, number, t_body):
                        ready_out.append({"number": number, "action": "thin_ready_nudge"})

                if mergeable is None or rebase_was_dispatched(bodies):
                    continue
                if not is_merge_conflict(mergeable, mst):
                    continue

                first_dirty = _earliest_first_dirty_marker(bodies)
                if first_dirty is None and mergeable is False:
                    d_body = format_dirty_first_seen(mst)
                    if await _post_comment(client, owner, repo, number, d_body):
                        first_dirty = now
                    else:
                        first_dirty = _earliest_first_dirty_marker(bodies)
                if first_dirty is None:
                    first_dirty = _earliest_first_dirty_marker(bodies)

                if not should_dispatch_rebase(
                    first_dirty_marked=first_dirty,
                    now=now,
                    rebase_already_dispatched=rebase_was_dispatched(bodies),
                ):
                    continue

                if await _dispatch_rebase_workflow(client, owner, repo, number):
                    await _post_comment(client, owner, repo, number, format_rebase_queued())
                    rebase_out.append({"number": number, "action": "rebase_workflow"})

    except (httpx.HTTPError, ValueError) as e:
        logger.exception("run_pr_triage_sweep: %s", e)
        return {
            "ok": False,
            "error": str(e)[:200],
            "stale": stale_out,
            "ready": ready_out,
            "rebase": rebase_out,
        }

    return {"ok": True, "stale": stale_out, "ready": ready_out, "rebase": rebase_out}
