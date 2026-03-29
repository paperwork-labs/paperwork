"""GitHub REST tools for Brain MCP — scoped repo operations with trimmed, scrubbed output."""

import base64
import json
import logging
from typing import Any
from urllib.parse import quote

import httpx

from app.config import settings
from app.services.pii import scrub_pii

logger = logging.getLogger(__name__)

GH_API = "https://api.github.com"

_MAX_FILE_READ = 5000
_MAX_PR_BODY = 8000
_MAX_SEARCH_LINE = 500


def _gh_headers(*, text_match: bool = False) -> dict[str, str]:
    accept = "application/vnd.github.v3+json"
    if text_match:
        accept = "application/vnd.github.v3.text-match+json"
    return {
        "Authorization": f"token {settings.GITHUB_TOKEN}",
        "Accept": accept,
    }


def _gh_client(*, text_match: bool = False) -> httpx.AsyncClient:
    if not settings.GITHUB_TOKEN.strip():
        raise ValueError("GITHUB_TOKEN not configured")
    return httpx.AsyncClient(
        base_url=GH_API,
        headers=_gh_headers(text_match=text_match),
        timeout=httpx.Timeout(60.0),
    )


def _repo_parts() -> tuple[str, str]:
    raw = settings.GITHUB_REPO.strip()
    parts = raw.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("GITHUB_REPO must be 'owner/repo'")
    return parts[0], parts[1]


def _scrub(s: str) -> str:
    return scrub_pii(s)


def _error_message(prefix: str, response: httpx.Response) -> str:
    detail = ""
    try:
        body = response.json()
        if isinstance(body, dict) and "message" in body:
            detail = str(body["message"])
    except (json.JSONDecodeError, ValueError, TypeError):
        detail = (response.text or "")[:500]
    return _scrub(f"{prefix} HTTP {response.status_code}: {detail}".strip())


async def read_github_file(path: str, ref: str = "main") -> str:
    """Read one file from the configured repo at ref.

    Returns UTF-8 text, truncated to 5000 characters if larger.
    """
    owner, repo = _repo_parts()
    enc_path = quote(path.strip().lstrip("/"), safe="/")
    url = f"/repos/{owner}/{repo}/contents/{enc_path}"
    try:
        async with _gh_client() as client:
            r = await client.get(url, params={"ref": ref})
            if r.status_code == 404:
                return _scrub(f"Not found: {path} (ref={ref})")
            r.raise_for_status()
            parsed: Any = r.json()
    except httpx.HTTPStatusError as e:
        logger.warning("read_github_file failed: %s %s", path, e)
        return _error_message("read_github_file", e.response)
    except (httpx.RequestError, ValueError) as e:
        logger.warning("read_github_file failed: %s %s", path, e)
        return _scrub(f"read_github_file error: {e}")

    if isinstance(parsed, list):
        return _scrub(f"Path is a directory ({len(parsed)} entries): {path}")
    if not isinstance(parsed, dict):
        return _scrub("Unexpected GitHub API response for file path")
    data = parsed

    if data.get("type") != "file":
        return _scrub(f"Path is not a file (type={data.get('type')}): {path}")

    b64 = data.get("content")
    if not isinstance(b64, str):
        return _scrub("Missing file content in API response")

    try:
        raw = base64.b64decode(b64.replace("\n", "")).decode("utf-8", errors="replace")
    except (ValueError, OSError) as e:
        logger.warning("read_github_file decode failed: %s %s", path, e)
        return _scrub(f"Could not decode file content: {e}")

    if len(raw) > _MAX_FILE_READ:
        raw = raw[:_MAX_FILE_READ] + f"\n… truncated ({_MAX_FILE_READ} chars)"
    return _scrub(raw)


async def search_github_code(query: str, max_results: int = 5) -> str:
    """Search code in the configured repo.

    Returns paths plus short line snippets, not full files.
    """
    owner, repo = _repo_parts()
    capped = max(1, min(max_results, 20))
    q = f"{query.strip()} repo:{owner}/{repo}"
    try:
        async with _gh_client(text_match=True) as client:
            r = await client.get("/search/code", params={"q": q, "per_page": capped})
            if r.status_code == 422:
                return _scrub(_error_message("search_github_code", r))
            r.raise_for_status()
            payload: dict[str, Any] = r.json()
    except httpx.HTTPStatusError as e:
        logger.warning("search_github_code failed: %s", e)
        return _error_message("search_github_code", e.response)
    except (httpx.RequestError, ValueError) as e:
        logger.warning("search_github_code failed: %s", e)
        return _scrub(f"search_github_code error: {e}")

    items = payload.get("items") or []
    lines_out: list[str] = []
    for item in items[:capped]:
        path = item.get("path", "?")
        matches = item.get("text_matches") or []
        if matches:
            for m in matches[:3]:
                frag = (m.get("fragment") or "")[:_MAX_SEARCH_LINE].replace("\n", " ")
                lines_out.append(f"{path}: {frag}")
        else:
            lines_out.append(f"{path} (no snippet)")

    if not lines_out:
        return _scrub("No code matches.")
    return _scrub("\n".join(lines_out))


async def list_github_prs(state: str = "open", limit: int = 10) -> str:
    """List PRs: number, title, author, labels, created time."""
    if state not in ("open", "closed", "all"):
        return _scrub(f"Invalid state '{state}' (use open, closed, or all)")
    owner, repo = _repo_parts()
    capped = max(1, min(limit, 30))
    try:
        async with _gh_client() as client:
            r = await client.get(
                f"/repos/{owner}/{repo}/pulls",
                params={
                    "state": state,
                    "per_page": capped,
                    "sort": "created",
                    "direction": "desc",
                },
            )
            r.raise_for_status()
            prs: list[dict[str, Any]] = r.json()
    except httpx.HTTPStatusError as e:
        logger.warning("list_github_prs failed: %s", e)
        return _error_message("list_github_prs", e.response)
    except (httpx.RequestError, ValueError) as e:
        logger.warning("list_github_prs failed: %s", e)
        return _scrub(f"list_github_prs error: {e}")

    rows: list[str] = []
    for pr in prs[:capped]:
        user = (pr.get("user") or {}).get("login", "?")
        raw_labels = pr.get("labels") or []
        labels = [lbl.get("name", "") for lbl in raw_labels if isinstance(lbl, dict)]
        label_s = ",".join(labels) if labels else "-"
        num = pr.get("number")
        title = pr.get("title", "")
        created = pr.get("created_at", "")
        rows.append(f"#{num} | {title} | @{user} | [{label_s}] | {created}")
    return _scrub("\n".join(rows) if rows else "No pull requests.")


async def get_github_pr(number: int) -> str:
    """Get PR details: title, body, changed file names, additions/deletions."""
    owner, repo = _repo_parts()
    try:
        async with _gh_client() as client:
            pr_r = await client.get(f"/repos/{owner}/{repo}/pulls/{number}")
            if pr_r.status_code == 404:
                return _scrub(f"PR #{number} not found")
            pr_r.raise_for_status()
            pr: dict[str, Any] = pr_r.json()

            files_r = await client.get(
                f"/repos/{owner}/{repo}/pulls/{number}/files",
                params={"per_page": 100},
            )
            files_r.raise_for_status()
            files_payload: list[dict[str, Any]] | dict[str, Any] = files_r.json()
    except httpx.HTTPStatusError as e:
        logger.warning("get_github_pr failed: #%s %s", number, e)
        return _error_message("get_github_pr", e.response)
    except (httpx.RequestError, ValueError) as e:
        logger.warning("get_github_pr failed: #%s %s", number, e)
        return _scrub(f"get_github_pr error: {e}")

    file_list: list[str] = []
    if isinstance(files_payload, list):
        for entry in files_payload:
            if isinstance(entry, dict) and entry.get("filename"):
                file_list.append(str(entry["filename"]))

    body = pr.get("body") or ""
    if len(body) > _MAX_PR_BODY:
        body = body[:_MAX_PR_BODY] + f"\n… truncated ({_MAX_PR_BODY} chars)"

    adds = pr.get("additions", 0)
    dels = pr.get("deletions", 0)
    n_files = pr.get("changed_files", len(file_list))
    parts = [
        f"#{pr.get('number')} {pr.get('title', '')}",
        f"State: {pr.get('state', '')} merged={pr.get('merged', False)}",
        f"Additions: {adds} Deletions: {dels} Files: {n_files}",
        "",
        "Body:",
        body,
        "",
        "Files:",
        "\n".join(file_list) if file_list else "(none listed)",
    ]
    return _scrub("\n".join(parts))


async def create_github_issue(title: str, body: str, labels: list[str] | None = None) -> str:
    """Open an issue; returns number and HTML URL."""
    owner, repo = _repo_parts()
    payload: dict[str, Any] = {"title": title.strip(), "body": body}
    if labels:
        payload["labels"] = [str(lab).strip() for lab in labels if str(lab).strip()]
    try:
        async with _gh_client() as client:
            r = await client.post(f"/repos/{owner}/{repo}/issues", json=payload)
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except httpx.HTTPStatusError as e:
        logger.warning("create_github_issue failed: %s", e)
        return _error_message("create_github_issue", e.response)
    except (httpx.RequestError, ValueError) as e:
        logger.warning("create_github_issue failed: %s", e)
        return _scrub(f"create_github_issue error: {e}")

    num = data.get("number")
    url = data.get("html_url", "")
    return _scrub(f"Issue #{num} created: {url}")


async def commit_github_file(path: str, content: str, message: str, branch: str = "main") -> str:
    """Create or update a file on a branch; returns new commit SHA."""
    owner, repo = _repo_parts()
    enc_path = quote(path.strip().lstrip("/"), safe="/")
    url = f"/repos/{owner}/{repo}/contents/{enc_path}"
    b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    try:
        async with _gh_client() as client:
            get_r = await client.get(url, params={"ref": branch})
            sha: str | None = None
            if get_r.status_code == 200:
                cur: dict[str, Any] = get_r.json()
                if cur.get("type") == "file" and isinstance(cur.get("sha"), str):
                    sha = cur["sha"]
            elif get_r.status_code != 404:
                get_r.raise_for_status()

            put_body: dict[str, Any] = {
                "message": message.strip(),
                "content": b64,
                "branch": branch.strip(),
            }
            if sha:
                put_body["sha"] = sha

            put_r = await client.put(url, json=put_body)
            put_r.raise_for_status()
            result: dict[str, Any] = put_r.json()
    except httpx.HTTPStatusError as e:
        logger.warning("commit_github_file failed: %s %s", path, e)
        return _error_message("commit_github_file", e.response)
    except (httpx.RequestError, ValueError) as e:
        logger.warning("commit_github_file failed: %s %s", path, e)
        return _scrub(f"commit_github_file error: {e}")

    commit = (result.get("commit") or {}) if isinstance(result.get("commit"), dict) else {}
    commit_sha = commit.get("sha", "")
    if not commit_sha:
        return _scrub("Commit succeeded but response had no commit SHA")
    return _scrub(f"Commit SHA: {commit_sha}")


async def merge_github_pr(number: int, merge_method: str = "squash") -> str:
    """Merge a PR (merge, squash, or rebase); returns merge SHA when present."""
    if merge_method not in ("merge", "squash", "rebase"):
        return _scrub("merge_method must be 'merge', 'squash', or 'rebase'")
    owner, repo = _repo_parts()
    try:
        async with _gh_client() as client:
            r = await client.put(
                f"/repos/{owner}/{repo}/pulls/{number}/merge",
                json={"merge_method": merge_method},
            )
            if r.status_code == 200:
                data: dict[str, Any] = r.json()
                sha = data.get("sha") or data.get("merge_commit_sha") or ""
                if sha:
                    return _scrub(f"Merged. SHA: {sha}")
                return _scrub("Merged (no SHA in response)")
            return _error_message("merge_github_pr", r)
    except httpx.HTTPStatusError as e:
        logger.warning("merge_github_pr failed: #%s %s", number, e)
        return _error_message("merge_github_pr", e.response)
    except (httpx.RequestError, ValueError) as e:
        logger.warning("merge_github_pr failed: #%s %s", number, e)
        return _scrub(f"merge_github_pr error: {e}")
