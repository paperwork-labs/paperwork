"""Brain-owned sprint auto-logger — merged PRs → ``## Outcome`` bullets via bot PR.

Opens **one** batched PR per tick (design A: single source of truth in git
markdown). Gated by :envvar:`BRAIN_OWNS_SPRINT_AUTO_LOGGER`.

# OPERATIONAL GATE — default off because this opens real GitHub PRs that edit
# ``docs/sprints/*.md`` (repo writes, not n8n shadow compare). There is no n8n
# mirror for this job. Flip ``BRAIN_OWNS_SPRINT_AUTO_LOGGER=true`` in Render
# after validating ``GITHUB_TOKEN`` scopes and reviewing one dry-run tick in
# staging or a canary deploy.
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.database import async_session_factory
from app.models.scheduler_run import SchedulerRun
from app.schedulers._history import run_with_scheduler_record
from app.tools import github as gh

logger = logging.getLogger(__name__)

_JOB_ID = "sprint_auto_logger"

# Mirrors Studio ``apps/studio/src/app/admin/sprints/page.tsx`` (keep in sync).
PR_REF_RE = re.compile(r"(?:#|PR\s*#|pull/)(\d{2,5})", re.I)
SHIPPED_DATE_RE = re.compile(r"(?:^shipped\s+|\bshipped\s+)(\d{4}-\d{2}-\d{2})", re.I)

SPRINT_BODY_LINE_RE = re.compile(r"(?im)^[ \t]*Sprint:\s*(.+?)\s*$")
_CC_PREFIX_RE = re.compile(
    r"^(?:(?:feat|fix|chore|docs|style|refactor|perf|test|build|ci|revert)(?:\([^)]*\))?!?:\s*)+",
    re.I,
)

OUTCOME_HEADERS = ("## Outcome", "## Outcomes")
SECTION_HEADER_RE = re.compile(r"^##\s+", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
SAFE_SPRINT_PATH_RE = re.compile(r"\Adocs/sprints/[a-zA-Z0-9_-]+\.md\Z")


def _owns_sprint_autologger() -> bool:
    return os.getenv("BRAIN_OWNS_SPRINT_AUTO_LOGGER", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def strip_conventional_prefix(title: str) -> str:
    t = (title or "").strip()
    if not t:
        return ""
    while True:
        m = _CC_PREFIX_RE.match(t)
        if not m:
            break
        t = t[m.end() :].strip()
    return t or (title or "").strip()


def normalize_sprint_paths_from_body_line(token: str) -> list[str]:
    raw = (token or "").strip()
    if not raw:
        return []
    if raw.startswith("docs/sprints/"):
        if not raw.endswith(".md"):
            return [f"{raw}.md"]
        return [raw]
    stem = raw.removesuffix(".md")
    return [f"docs/sprints/{stem}.md"]


def sprint_paths_from_body(body: str | None) -> list[str]:
    out: list[str] = []
    for m in SPRINT_BODY_LINE_RE.finditer(body or ""):
        out.extend(normalize_sprint_paths_from_body_line(m.group(1)))
    seen: set[str] = set()
    uniq: list[str] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def sprint_paths_from_labels(label_names: Iterable[str]) -> list[str]:
    out: list[str] = []
    for name in label_names:
        if name.lower().startswith("sprint:"):
            stem = name.split(":", 1)[1].strip()
            if stem:
                stem = stem.removesuffix(".md")
                out.append(f"docs/sprints/{stem}.md")
    seen: set[str] = set()
    uniq: list[str] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def is_safe_sprint_path(path: str) -> bool:
    return bool(SAFE_SPRINT_PATH_RE.match(path))


def collect_sprint_paths(body: str | None, label_names: list[str]) -> list[str]:
    paths = [*sprint_paths_from_body(body), *sprint_paths_from_labels(label_names)]
    seen: set[str] = set()
    uniq: list[str] = []
    for p in paths:
        if not is_safe_sprint_path(p):
            continue
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def find_section_block(text: str, headers: tuple[str, ...]) -> tuple[int, int, str] | None:
    for header in headers:
        idx = text.find(header)
        if idx == -1:
            continue
        nxt = SECTION_HEADER_RE.search(text, idx + len(header))
        end = nxt.start() if nxt else len(text)
        return idx, end, header
    return None


def outcome_section_references_pr(outcome_text: str, pr_num: int) -> bool:
    for line in outcome_text.splitlines():
        for m in PR_REF_RE.finditer(line):
            if int(m.group(1)) == pr_num:
                return True
    return False


def insert_outcome_bullet(full_doc: str, ship_date: str, title_clean: str, pr_num: int) -> str:
    bullet = f"- shipped {ship_date}: {title_clean} PR #{pr_num}\n"
    outcome = find_section_block(full_doc, OUTCOME_HEADERS)
    if not outcome:
        raise ValueError("no ## Outcome section")
    o_start, o_end, o_header = outcome
    block = full_doc[o_start:o_end]
    lines = block.splitlines(keepends=True)
    if not lines:
        new_block = f"{o_header}\n\n{bullet}"
    else:
        header_line = lines[0]
        rest = lines[1:]
        insert_at = 0
        if rest and "_Tracking" in rest[0] and rest[0].lstrip().startswith("-"):
            insert_at = 1
            while insert_at < len(rest) and rest[insert_at].strip() == "":
                insert_at += 1
        new_rest = rest[:insert_at] + [bullet] + rest[insert_at:]
        new_block = header_line + "".join(new_rest)
    return full_doc[:o_start] + new_block + full_doc[o_end:]


def merge_related_prs_frontmatter(full_doc: str, new_nums: list[int]) -> str:
    m = FRONTMATTER_RE.match(full_doc)
    if not m:
        return full_doc
    fm_raw = m.group(1)
    try:
        data: dict[str, Any] = yaml.safe_load(fm_raw) or {}
    except yaml.YAMLError:
        return full_doc
    existing = data.get("related_prs") or []
    cur: set[int] = set()
    if isinstance(existing, list):
        for x in existing:
            try:
                cur.add(int(x))
            except (TypeError, ValueError):
                continue
    for n in new_nums:
        cur.add(int(n))
    data["related_prs"] = sorted(cur)
    new_fm = yaml.dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False).strip()
    return f"---\n{new_fm}\n---\n" + full_doc[m.end() :]


def apply_sprint_file_updates(
    content: str,
    additions: list[tuple[int, str, str]],
) -> tuple[str, list[int]] | None:
    """Return ``(new_markdown, pr_numbers_appended)`` or None if nothing to do.

    ``additions`` rows: ``(pr_num, title_clean, ship_date_yyyy_mm_dd)``.
    """
    new_content = content
    merged_prs: list[int] = []
    for pr_num, title_clean, ship_date in additions:
        outcome = find_section_block(new_content, OUTCOME_HEADERS)
        if not outcome:
            logger.warning("sprint_auto_logger: skipping file — no Outcome section")
            return None
        o_start, o_end, _ = outcome
        outcome_text = new_content[o_start:o_end]
        if outcome_section_references_pr(outcome_text, pr_num):
            continue
        new_content = insert_outcome_bullet(new_content, ship_date, title_clean, pr_num)
        merged_prs.append(pr_num)
    if not merged_prs:
        return None
    new_content = merge_related_prs_frontmatter(new_content, merged_prs)
    return new_content, merged_prs


async def _last_success_cutoff() -> datetime:
    async with async_session_factory() as db:
        r = await db.execute(
            select(SchedulerRun.finished_at)
            .where(SchedulerRun.job_id == _JOB_ID, SchedulerRun.status == "success")
            .order_by(SchedulerRun.finished_at.desc())
            .limit(1)
        )
        row = r.scalar_one_or_none()
    if row:
        if row.tzinfo is None:
            return row.replace(tzinfo=timezone.utc)
        return row
    return datetime.now(timezone.utc) - timedelta(hours=1)


async def _run_body(*, since_override: datetime | None = None) -> None:
    from app.config import settings

    if not settings.GITHUB_TOKEN.strip():
        logger.warning("sprint_auto_logger: GITHUB_TOKEN empty — skipping")
        return

    since = since_override or await _last_success_cutoff()
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    pr_nums = await gh.search_merged_pr_numbers_since(since)
    if not pr_nums:
        logger.info("sprint_auto_logger: no merged PRs since %s", since.isoformat())
        return

    by_path: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    for num in pr_nums:
        pr = await gh.get_github_pull_dict(num)
        if not pr:
            continue
        if not pr.get("merged_at"):
            continue
        try:
            merged_at = datetime.fromisoformat(str(pr["merged_at"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        if merged_at <= since:
            continue
        labels = [str(x.get("name", "")) for x in (pr.get("labels") or []) if isinstance(x, dict)]
        paths = collect_sprint_paths(str(pr.get("body") or ""), labels)
        if not paths:
            continue
        title_clean = strip_conventional_prefix(str(pr.get("title") or ""))
        if not title_clean:
            title_clean = str(pr.get("title") or "").strip() or f"PR #{num}"
        ship_date = merged_at.astimezone(timezone.utc).date().isoformat()
        for p in paths:
            by_path[p].append((num, title_clean, ship_date))

    if not by_path:
        logger.info("sprint_auto_logger: no sprint-tagged merged PRs in window")
        return

    updates: dict[str, str] = {}
    logged_pr_nums: list[int] = []
    for path, additions in sorted(by_path.items()):
        raw = await gh.read_github_file(path, ref="main", max_chars=600_000)
        if raw.startswith("Not found:") or "read_github_file error" in raw:
            logger.warning("sprint_auto_logger: cannot read %s", path)
            continue
        applied = apply_sprint_file_updates(raw, additions)
        if applied:
            new_text, prs_appended = applied
            updates[path] = new_text
            logged_pr_nums.extend(prs_appended)

    if not updates:
        logger.info("sprint_auto_logger: all PRs already logged or no valid files")
        return

    ts = int(time.time())
    branch = f"auto/sprint-log-{ts}"
    main_sha = await gh.get_git_ref_sha("main")
    if not main_sha:
        logger.error("sprint_auto_logger: could not resolve main")
        return
    if not await gh.create_git_ref(branch, main_sha):
        logger.error("sprint_auto_logger: could not create branch %s", branch)
        return

    all_nums = sorted(set(logged_pr_nums))
    msg_nums = " ".join(f"#{n}" for n in all_nums[:20])
    if len(all_nums) > 20:
        msg_nums += " …"
    message = f"chore(sprints): auto-log shipped PRs ({msg_nums.strip()})"

    commit_sha = await gh.commit_files_to_branch(branch, message, updates)
    if not commit_sha:
        logger.error("sprint_auto_logger: commit failed")
        return

    table_lines: list[str] = []
    for path in sorted(updates.keys()):
        prs_h = ", ".join(f"#{n}" for n, _, _ in by_path[path])
        table_lines.append(f"| `{path}` | {prs_h} |")
    rows_md = "\n".join(table_lines)
    body_lines = [
        "[autologger]",
        "",
        "Automated **Outcome** bullets + `related_prs` for merged PRs (batched).",
        "",
        "| Sprint doc | Representative PR |",
        "| --- | --- |",
        rows_md,
        "",
        f"_Commit: `{commit_sha[:7]}`_",
    ]
    title = f"chore(sprints): auto-log shipped PRs ({msg_nums.strip()})"
    pr_payload = await gh.create_github_pull(
        head=branch,
        base="main",
        title=title[:256],
        body="\n".join(body_lines),
    )
    if pr_payload:
        num = pr_payload.get("number")
        logger.info("sprint_auto_logger: opened PR #%s", num)
    else:
        logger.error("sprint_auto_logger: failed to open PR (branch %s)", branch)


async def run_sprint_auto_logger(*, since_override: datetime | None = None) -> None:
    await run_with_scheduler_record(
        _JOB_ID,
        lambda: _run_body(since_override=since_override),
        metadata={"source": "sprint_auto_logger"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    if not _owns_sprint_autologger():
        logger.info("BRAIN_OWNS_SPRINT_AUTO_LOGGER is not true — skipping sprint_auto_logger job")
        return
    scheduler.add_job(
        run_sprint_auto_logger,
        trigger=CronTrigger.from_crontab("*/15 * * * *", timezone=timezone.utc),
        id=_JOB_ID,
        name="Sprint auto-logger (merged PRs → docs/sprints Outcome)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("sprint_auto_logger installed: every 15 minutes (UTC)")
