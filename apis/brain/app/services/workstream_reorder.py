"""Open a GitHub PR that rewrites ``workstreams.json`` priorities (Track Z).

medallion: ops
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from app.config import settings
from app.schemas.workstream import Workstream, WorkstreamsFile, workstreams_file_to_json_dict
from app.services.workstreams_loader import invalidate_workstreams_cache, load_workstreams_file
from app.tools import github as gh

logger = logging.getLogger(__name__)

_JSON_PATH = "apps/studio/src/data/workstreams.json"


def _apply_reorder(file: WorkstreamsFile, ordered_ids: list[str]) -> WorkstreamsFile:
    by_id: dict[str, Workstream] = {w.id: w for w in file.workstreams}
    new_list: list[Workstream] = []
    for i, wid in enumerate(ordered_ids):
        w = by_id[wid]
        new_list.append(w.model_copy(update={"priority": i}))
    updated_ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return WorkstreamsFile(version=1, updated=updated_ts, workstreams=new_list)


def _pretty_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2) + "\n"


async def open_reorder_workstreams_pr(ordered_ids: list[str]) -> dict[str, Any]:
    """Validate order, commit JSON, open PR. Returns GitHub pull response dict."""
    if len(ordered_ids) != len(set(ordered_ids)):
        raise ValueError("ordered_ids must not contain duplicates")

    file = load_workstreams_file(bypass_cache=True)
    current = {w.id for w in file.workstreams}
    if set(ordered_ids) != current:
        raise ValueError(
            "ordered_ids must match the current workstream id set exactly "
            f"(got {len(ordered_ids)} ids, {len(current)} unique in file)"
        )

    new_file = _apply_reorder(file, ordered_ids)
    text = _pretty_json(workstreams_file_to_json_dict(new_file))

    if not settings.GITHUB_TOKEN.strip():
        raise RuntimeError("GITHUB_TOKEN not configured")

    ts = int(time.time())
    branch = f"chore/workstreams-reorder-{ts}"
    main_sha = await gh.get_git_ref_sha("main")
    if not main_sha:
        raise RuntimeError("could not resolve main")
    if not await gh.create_git_ref(branch, main_sha):
        raise RuntimeError(f"could not create branch {branch}")

    commit_sha = await gh.commit_files_to_branch(
        branch,
        "chore(workstreams): reorder via Studio",
        {_JSON_PATH: text},
    )
    if not commit_sha:
        raise RuntimeError("commit_files_to_branch failed")

    pr = await gh.create_github_pull(
        head=branch,
        base="main",
        title="chore(workstreams): reorder via Studio",
        body=(
            f"Automated priority rewrite from Studio drag-reorder.\n\n_Commit: `{commit_sha[:7]}`_"
        ),
    )
    if not pr:
        raise RuntimeError("create_github_pull failed")

    invalidate_workstreams_cache()
    logger.info("workstream_reorder: opened PR #%s", pr.get("number"))
    return pr
