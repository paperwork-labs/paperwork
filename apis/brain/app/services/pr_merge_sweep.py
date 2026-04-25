"""Brain-owned auto-merge sweep.

Replaces ``.github/workflows/auto-merge-sweep.yaml``. For every open PR, if
it is approved + green + mergeable + not blocked by a safety label, squash-merge
it. Runs from ``app.schedulers.pr_sweep`` on the same cadence as the review
sweep.

Kept deliberately thin — all the heavy lifting (review decisions, risk triage)
is done elsewhere. This function only trusts labels + approvals + check runs.

medallion: ops
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.tools.github import _gh_client, _repo_parts

logger = logging.getLogger(__name__)


# Same semantics as the old workflow: these labels veto any auto-merge.
BLOCK_LABELS = frozenset({"needs-human-review", "do-not-merge", "wip"})
# Major-version dep bumps require the ``risk:low`` LLM verdict to merge.
MAJOR_LABEL = "deps:major"
LOW_RISK_LABEL = "risk:low"


async def merge_ready_prs(*, limit: int = 50) -> dict[str, Any]:
    """Squash-merge every PR that is approved, green, mergeable and unblocked.

    Returns ``{merged, skipped, errors}``. Never raises — callers poll us
    on a schedule.
    """
    owner, repo = _repo_parts()
    merged: list[int] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    try:
        async with _gh_client() as client:
            r = await client.get(
                f"/repos/{owner}/{repo}/pulls",
                params={"state": "open", "per_page": min(max(limit, 1), 100), "sort": "updated", "direction": "desc"},
            )
            r.raise_for_status()
            stubs: list[dict[str, Any]] = r.json()

            for stub in stubs:
                number = int(stub.get("number") or 0)
                if not number:
                    continue
                if stub.get("draft"):
                    skipped.append({"number": number, "reason": "draft"})
                    continue

                labels = {
                    (lbl.get("name") or "").strip()
                    for lbl in (stub.get("labels") or [])
                    if isinstance(lbl, dict)
                }
                blocking = labels & BLOCK_LABELS
                if blocking:
                    skipped.append({"number": number, "reason": f"blocked by labels: {sorted(blocking)}"})
                    continue
                if MAJOR_LABEL in labels and LOW_RISK_LABEL not in labels:
                    skipped.append({"number": number, "reason": "deps:major without risk:low"})
                    continue

                try:
                    pr_res = await client.get(f"/repos/{owner}/{repo}/pulls/{number}")
                    pr_res.raise_for_status()
                    pr = pr_res.json()
                except httpx.HTTPError as e:
                    errors.append({"number": number, "error": f"pulls.get: {e}"})
                    continue

                if pr.get("mergeable") is False:
                    skipped.append({"number": number, "reason": "not mergeable (conflicts?)"})
                    continue

                head_sha = str(((pr.get("head") or {}).get("sha") or "")).strip()
                if not head_sha:
                    skipped.append({"number": number, "reason": "no head SHA"})
                    continue

                try:
                    reviews_res = await client.get(
                        f"/repos/{owner}/{repo}/pulls/{number}/reviews",
                        params={"per_page": 100},
                    )
                    reviews_res.raise_for_status()
                    reviews = reviews_res.json()
                except httpx.HTTPError as e:
                    errors.append({"number": number, "error": f"reviews: {e}"})
                    continue

                latest: dict[str, str] = {}
                for rev in reviews:
                    user = (rev.get("user") or {}).get("login") or ""
                    if user:
                        latest[user] = (rev.get("state") or "").upper()
                if not any(state == "APPROVED" for state in latest.values()):
                    skipped.append({"number": number, "reason": "not approved"})
                    continue
                if any(state == "CHANGES_REQUESTED" for state in latest.values()):
                    skipped.append({"number": number, "reason": "changes requested"})
                    continue

                try:
                    checks_res = await client.get(
                        f"/repos/{owner}/{repo}/commits/{head_sha}/check-runs",
                        params={"per_page": 100},
                    )
                    checks_res.raise_for_status()
                    check_runs: list[dict[str, Any]] = (checks_res.json() or {}).get("check_runs", [])
                except httpx.HTTPError as e:
                    errors.append({"number": number, "error": f"check-runs: {e}"})
                    continue

                not_ready = [
                    c
                    for c in check_runs
                    if not (
                        c.get("status") == "completed"
                        and (c.get("conclusion") or "").lower() in {"success", "skipped", "neutral"}
                    )
                ]
                if not_ready:
                    skipped.append({
                        "number": number,
                        "reason": f"checks not green ({len(not_ready)} pending/failed)",
                    })
                    continue

                try:
                    merge_res = await client.put(
                        f"/repos/{owner}/{repo}/pulls/{number}/merge",
                        json={"merge_method": "squash"},
                    )
                    if merge_res.status_code == 200:
                        merged.append(number)
                    else:
                        errors.append({
                            "number": number,
                            "error": f"merge HTTP {merge_res.status_code}: {merge_res.text[:200]}",
                        })
                except httpx.HTTPError as e:
                    errors.append({"number": number, "error": f"merge: {e}"})

    except httpx.HTTPError as e:
        logger.exception("merge_ready_prs: failed to list PRs")
        errors.append({"error": f"list PRs: {e}"})
    except ValueError as e:
        logger.exception("merge_ready_prs: config error")
        errors.append({"error": f"config: {e}"})

    logger.info(
        "merge_ready_prs: merged=%d skipped=%d errors=%d (settings token set=%s)",
        len(merged),
        len(skipped),
        len(errors),
        bool(settings.GITHUB_TOKEN.strip()),
    )
    return {"merged": merged, "skipped": skipped, "errors": errors}
