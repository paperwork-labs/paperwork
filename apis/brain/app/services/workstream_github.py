"""GitHub Actions workflow_dispatch + search helpers for workstreams (Track Z)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_GH = "https://api.github.com"


def _repo_parts() -> tuple[str, str]:
    raw = settings.GITHUB_REPO.strip()
    parts = raw.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("GITHUB_REPO must be 'owner/repo'")
    return parts[0], parts[1]


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"token {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }


def _normalize_workflow_file(workflow: str | None) -> str:
    w = (workflow or "").strip() or "agent-sprint-runner"
    if w.endswith((".yml", ".yaml")):
        return w
    return f"{w}.yml"


async def workflow_dispatch(
    workflow: str | None,
    *,
    brief_tag: str,
    title: str,
    notes: str,
    related_plan: str | None,
    ref: str = "main",
) -> bool:
    """POST ``workflow_dispatch``. Returns True on 204."""
    if not settings.GITHUB_TOKEN.strip():
        logger.warning("workstream workflow_dispatch: GITHUB_TOKEN empty")
        return False
    owner, repo = _repo_parts()
    wf_file = _normalize_workflow_file(workflow)
    inputs: dict[str, str] = {
        "brief_tag": brief_tag,
        "title": title,
        "notes": notes or "",
        "related_plan": (related_plan or "") or "",
    }
    url = f"{_GH}/repos/{owner}/{repo}/actions/workflows/{wf_file}/dispatches"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            r = await client.post(
                url,
                headers=_headers(),
                json={"ref": ref, "inputs": inputs},
            )
        if r.status_code not in (200, 204):
            logger.warning(
                "workflow_dispatch %s failed: HTTP %s %s",
                wf_file,
                r.status_code,
                (r.text or "")[:400],
            )
            return False
        return True
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("workflow_dispatch %s error: %s", wf_file, e)
        return False


async def _search_total_count(client: httpx.AsyncClient, q: str) -> int:
    r = await client.get(
        f"{_GH}/search/issues",
        headers=_headers(),
        params={"q": q, "per_page": 1},
    )
    if r.status_code != 200:
        return 0
    payload: dict[str, Any] = r.json()
    return int(payload.get("total_count", 0) or 0)


async def search_prs_with_brief_tag_in_body(brief_tag: str) -> tuple[int, int]:
    """Return ``(merged_count, open_count)`` for PRs whose body contains ``brief_tag``.

    Uses GitHub search ``total_count`` with ``is:open`` / ``is:merged`` qualifiers.
    """
    if not settings.GITHUB_TOKEN.strip():
        return 0, 0
    owner, repo = _repo_parts()
    base = f"repo:{owner}/{repo} is:pr {brief_tag} in:body"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            merged = await _search_total_count(client, f"{base} is:merged")
            open_n = await _search_total_count(client, f"{base} is:open")
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("search_prs_with_brief_tag_in_body: %s", e)
        return 0, 0
    return merged, open_n
