"""Auto-close sprint markdown when configured PRs + workstreams are done.

Reads optional ``closes_pr_urls`` / ``closes_workstreams`` in ``docs/sprints/*.md``
frontmatter. When every linked PR is merged on GitHub and every listed workstream
is ``completed``, sets ``status: closed`` and ``last_auto_status_check_at``.

If GitHub cannot answer for a configured PR, the sprint is **not** closed (no
silent success).

medallion: ops
"""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from app.schemas.workstream import Workstream

from app.services.workstreams_loader import load_workstreams_file
from app.tools import github as gh

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_PULL_NUM_RE = re.compile(
    r"github\.com/[^/\s]+/[^/\s]+/pull/(?P<num>\d+)",
    re.IGNORECASE,
)
_TERMINAL_STATUSES = frozenset(
    {
        "shipped",
        "closed",
        "deferred",
        "dropped",
    }
)


def _repo_root() -> Path:
    return Path(
        os.environ.get(
            "REPO_ROOT",
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            ),
        )
    ).resolve()


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str] | None:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(meta, dict):
        return None
    return meta, text


def _replace_frontmatter_block(full: str, new_meta: dict[str, Any]) -> str:
    m = _FRONTMATTER_RE.match(full)
    if not m:
        return full
    dumped = yaml.dump(
        new_meta,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    return f"---\n{dumped}\n---\n" + full[m.end() :]


def _coerce_url_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
    return out


def _coerce_ws_id_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
    return out


def _pr_numbers_from_urls(urls: list[str]) -> list[int]:
    nums: list[int] = []
    for u in urls:
        m = _PULL_NUM_RE.search(u)
        if not m:
            logger.warning("sprint_md_auto_close: could not parse PR number from URL %r", u)
            continue
        nums.append(int(m.group("num")))
    seen: set[int] = set()
    ordered: list[int] = []
    for n in nums:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered


async def _all_prs_merged(nums: list[int]) -> bool:
    for n in nums:
        pr = await gh.get_github_pull_dict(n)
        if pr is None:
            logger.warning(
                "sprint_md_auto_close: GitHub returned no data for PR #%s — aborting close check",
                n,
            )
            return False
        if not pr.get("merged_at"):
            return False
    return True


def _all_workstreams_completed(ids: list[str], by_id: dict[str, Workstream]) -> bool:
    for wid in ids:
        row = by_id.get(wid)
        if row is None:
            logger.info(
                "sprint_md_auto_close: workstream %r not found on board — not closing",
                wid,
            )
            return False
        if row.status != "completed":
            return False
    return True


async def collect_sprint_auto_close_updates(
    *,
    repo_root: Path | None = None,
) -> dict[str, str]:
    """Return ``{repo-relative-path: new_markdown}`` for sprints that should close."""
    root = repo_root or _repo_root()
    sprints_dir = root / "docs" / "sprints"
    if not sprints_dir.is_dir():
        return {}

    try:
        board = load_workstreams_file(bypass_cache=True)
    except Exception:
        logger.exception("sprint_md_auto_close: could not load workstreams.json")
        return {}

    by_id = {w.id: w for w in board.workstreams}
    updates: dict[str, str] = {}

    for path in sorted(sprints_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            logger.warning("sprint_md_auto_close: cannot read %s", path)
            continue
        split = _split_frontmatter(raw)
        if split is None:
            continue
        meta, _rest = split
        st = str(meta.get("status") or "").lower()
        if st in _TERMINAL_STATUSES:
            continue

        urls = _coerce_url_list(meta.get("closes_pr_urls"))
        ws_ids = _coerce_ws_id_list(meta.get("closes_workstreams"))
        if not urls and not ws_ids:
            continue

        pr_nums = _pr_numbers_from_urls(urls)
        if urls and len(pr_nums) != len(urls):
            continue

        if pr_nums and not await _all_prs_merged(pr_nums):
            continue
        if ws_ids and not _all_workstreams_completed(ws_ids, by_id):
            continue

        check_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_meta = dict(meta)
        new_meta["status"] = "closed"
        new_meta["last_auto_status_check_at"] = check_iso
        new_doc = _replace_frontmatter_block(raw, new_meta)
        if new_doc != raw:
            rel = str(path.relative_to(root)).replace(os.sep, "/")
            updates[rel] = new_doc

    return updates
