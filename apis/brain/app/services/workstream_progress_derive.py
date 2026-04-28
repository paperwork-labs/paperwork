"""Derive ``derived_percent`` from linked PR merge state (Track Z).

If any linked PR cannot be fetched from GitHub, returns ``None`` for that
workstream (never silently coerces to 0).

medallion: ops
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from app.tools import github as gh

if TYPE_CHECKING:
    from app.schemas.workstream import Workstream

logger = logging.getLogger(__name__)

_PULL_URL_RE = re.compile(
    r"github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+)/pull/(?P<num>\d+)",
    re.IGNORECASE,
)


def collect_linked_pr_numbers(ws: Workstream) -> list[int]:
    """Union ``last_pr``, ``prs``, ``pr_numbers``, and ``pr_url`` deep-links."""
    nums: list[int] = []
    if ws.last_pr is not None and ws.last_pr > 0:
        nums.append(ws.last_pr)
    for n in ws.prs or []:
        if isinstance(n, int) and n > 0:
            nums.append(n)
    for n in ws.pr_numbers or []:
        if isinstance(n, int) and n > 0:
            nums.append(n)
    if ws.pr_url:
        m = _PULL_URL_RE.search(ws.pr_url)
        if m:
            nums.append(int(m.group("num")))
    seen: set[int] = set()
    ordered: list[int] = []
    for n in nums:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered


async def derive_percent_for_workstream(ws: Workstream) -> int | None:
    nums = collect_linked_pr_numbers(ws)
    if not nums:
        return None
    merged = 0
    for n in nums:
        pr = await gh.get_github_pull_dict(n)
        if pr is None:
            logger.warning(
                "workstream_progress_derive: GitHub fetch failed for PR #%s (%s) — "
                "derived_percent=null",
                n,
                ws.id,
            )
            return None
        if pr.get("merged_at"):
            merged += 1
    return round(merged / len(nums) * 100)


async def compute_derived_percents_for_workstreams(
    workstreams: list[Workstream],
) -> dict[str, int | None]:
    out: dict[str, int | None] = {}
    for ws in workstreams:
        out[ws.id] = await derive_percent_for_workstream(ws)
    return out
