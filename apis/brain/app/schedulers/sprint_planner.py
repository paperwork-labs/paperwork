"""Autonomous sprint planning prompt (Mondays, America/Los_Angeles).

Reads ``docs/sprints/*.md`` and plan candidates, builds a structured planning
prompt, runs :func:`app.services.agent.process` with ``persona_pin=strategy``,
posts to Slack ``#strategy``, and optionally appends a snapshot to
``docs/KNOWLEDGE.md`` when :envvar:`GITHUB_TOKEN` is set.

Gated by :envvar:`BRAIN_OWNS_SPRINT_PLANNER` (default ``false``).
"""

from __future__ import annotations

import base64
import contextlib
import logging
import os
import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import httpx
import yaml
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import async_session_factory
from app.redis import get_redis
from app.schedulers._history import run_with_scheduler_record
from app.services import agent as brain_agent
from app.services import slack_outbound

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "brain_sprint_planner"
_LA_TZ = ZoneInfo("America/Los_Angeles")
# Strategy owner channel (persona routing); public copy posts to #strategy by name.
_STRATEGY_SLACK_CHANNEL = "#strategy"
_STRATEGY_CHANNEL_ID = "C0AM2310P8A"
_ORG_ID = "paperwork-labs"
_ORG_NAME = "Paperwork Labs"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL | re.MULTILINE)
_PRIORITY_RE = re.compile(r"priority\s*:\s*(P[0-3]|high|medium|low)", re.I)


def _repo_root() -> Path:
    return Path(
        os.environ.get(
            "REPO_ROOT",
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        )
    ).resolve()


def _owns_sprint_planner() -> bool:
    raw = os.environ.get("BRAIN_OWNS_SPRINT_PLANNER")
    if raw is not None:
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    return bool(getattr(settings, "BRAIN_OWNS_SPRINT_PLANNER", False))


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, text[m.end() :]


def _count_todos(body: str) -> tuple[int, int]:
    """Return (pending_or_in_progress, done) checkbox counts."""
    pending = 0
    done = 0
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("- ["):
            continue
        if s.startswith(("- [x", "- [X")):
            done += 1
        elif s.startswith(("- [ ]", "- [~]")):
            pending += 1
    return pending, done


def _parse_date(val: Any) -> date | None:
    if val is None:
        return None
    s = str(val).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _priority_weight(path: Path, body: str) -> int:
    m = _PRIORITY_RE.search(body[:4000])
    if m:
        p = m.group(1).upper()
        return {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "HIGH": 0, "MEDIUM": 2, "LOW": 4}.get(p, 5)
    # Prefer shallow plan files (root of plans/) over deep READMEs
    if path.name.upper() == "README.MD":
        return 10
    return 3


@dataclass
class SprintRecord:
    path: Path
    title: str
    meta: dict[str, Any]
    body: str
    pending_todos: int = 0
    done_todos: int = 0

    @property
    def status(self) -> str:
        return str(self.meta.get("status") or "").strip().lower()

    @property
    def last_reviewed(self) -> date | None:
        return _parse_date(self.meta.get("last_reviewed"))

    @property
    def end_date(self) -> date | None:
        sp = self.meta.get("sprint")
        if isinstance(sp, dict):
            return _parse_date(sp.get("end"))
        return None

    @property
    def lessons_excerpt(self) -> str:
        if "## What we learned" not in self.body:
            return ""
        part = self.body.split("## What we learned", 1)[1]
        if "##" in part:
            part = part.split("##", 1)[0]
        lines = [ln for ln in part.strip().splitlines() if ln.strip()][:12]
        return "\n".join(lines).strip()


def load_sprint_records(repo_root: Path) -> list[SprintRecord]:
    d = repo_root / "docs" / "sprints"
    if not d.is_dir():
        return []
    out: list[SprintRecord] = []
    for p in sorted(d.glob("*.md")):
        raw = p.read_text(encoding="utf-8", errors="replace")
        meta, body = _parse_frontmatter(raw)
        title = (meta.get("title") or p.stem.replace("_", " ")).strip()
        pend, done = _count_todos(body)
        out.append(
            SprintRecord(
                path=p,
                title=title,
                meta=meta,
                body=body,
                pending_todos=pend,
                done_todos=done,
            )
        )
    return out


def collect_referenced_plans(records: list[SprintRecord]) -> set[str]:
    """Plan paths already tied to a sprint (frontmatter)."""
    seen: set[str] = set()
    for r in records:
        sp = r.meta.get("sprint")
        if isinstance(sp, dict):
            for pl in sp.get("plans") or []:
                if isinstance(pl, str) and pl.strip():
                    seen.add(pl.strip().lstrip("/"))
    return seen


def q_boundary_sentence(as_of: date) -> str:
    q = (as_of.month - 1) // 3 + 1
    y = as_of.year
    end_m = q * 3
    last_d = monthrange(y, end_m)[1]
    end = date(y, end_m, last_d)
    days_left = (end - as_of).days
    weeks_left = max(0, days_left // 7)
    return f"Q{q} {y} ends {end.isoformat()} (~{weeks_left} weeks left at {as_of.isoformat()})."


def classify_sprints(
    records: list[SprintRecord],
    as_of: date,
) -> dict[str, list[SprintRecord]]:
    archive: list[SprintRecord] = []
    stale_in_progress: list[SprintRecord] = []
    paused: list[SprintRecord] = []
    recent_shipped: list[SprintRecord] = []
    in_progress: list[SprintRecord] = []

    for r in records:
        st = r.status
        if st == "paused":
            paused.append(r)
            continue
        if st == "shipped":
            end = r.end_date
            if end and (as_of - end).days > 7:
                archive.append(r)
            if end and (as_of - end).days <= 28:
                recent_shipped.append(r)
            continue
        if st == "in_progress":
            in_progress.append(r)
            lr = r.last_reviewed
            if lr and (as_of - lr).days > 14:
                stale_in_progress.append(r)

    return {
        "archive_candidates": archive,
        "stale_in_progress": stale_in_progress,
        "paused": paused,
        "recent_shipped": recent_shipped,
        "in_progress": in_progress,
    }


def iter_plan_candidates(repo_root: Path, referenced: set[str]) -> list[tuple[Path, int, str]]:
    """Plans under docs/**/plans/*.md not referenced by active sprints, sorted by priority."""
    roots = [
        repo_root / "docs" / "axiomfolio" / "plans",
        repo_root / "docs" / "plans",
    ]
    found: list[tuple[Path, int, str]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.rglob("*.md"):
            try:
                rel = p.relative_to(repo_root)
            except ValueError:
                continue
            rel_s = str(rel).replace("\\", "/")
            if rel_s in referenced:
                continue
            body = p.read_text(encoding="utf-8", errors="replace")
            meta, _ = _parse_frontmatter(body)
            st = str(meta.get("status") or "").strip().lower()
            if st in ("archived", "superseded"):
                continue
            w = _priority_weight(p, body)
            found.append((p, w, rel_s))
    found.sort(key=lambda t: (t[1], t[2]))
    return found[:12]


def build_sprint_planning_prompt(
    repo_root: Path,
    as_of: date | None = None,
) -> str:
    """Deterministic markdown payload for :func:`agent.process` (unit-tested)."""
    day = as_of or datetime.now(_LA_TZ).date()
    records = load_sprint_records(repo_root)
    buckets = classify_sprints(records, day)
    ref_plans = collect_referenced_plans(records)
    plan_hits = iter_plan_candidates(repo_root, ref_plans)

    lines: list[str] = [
        "You are preparing the **weekly sprint planning brief** for Paperwork Labs.",
        "",
        "### Calendar",
        f"- {q_boundary_sentence(day)}",
        "",
        "### Shipped in the last ~4 weeks (summarize outcomes + lessons)",
    ]
    recent = buckets["recent_shipped"]
    if not recent:
        lines.append("- _(none parsed in window — check docs/sprints/*.md frontmatter)_")
    for r in recent[:8]:
        lessons = r.lessons_excerpt
        lines.append(f"- **{r.title}** (`{r.path.name}`){'  ' + lessons[:400] if lessons else ''}")

    lines.extend(["", "### In-progress sprints (status, todo progress, blockers)"])
    inprog = buckets["in_progress"]
    if not inprog:
        lines.append("- _(no `status: in_progress` sprints)_")
    for r in inprog:
        total = r.pending_todos + r.done_todos
        pct = round(100 * r.done_todos / total) if total else 0
        lines.append(
            f"- **{r.title}**: ~{pct}% checkbox progress ({r.done_todos} done, "
            f"{r.pending_todos} open); last_reviewed={r.last_reviewed or 'n/a'}"
        )

    lines.extend(["", "### Stale in-progress (last_reviewed > 14d)"])
    for r in buckets["stale_in_progress"][:8]:
        lines.append(
            f"- **{r.title}**: needs founder review/refresh (last reviewed {r.last_reviewed})"
        )
    if not buckets["stale_in_progress"]:
        lines.append("- _(none)_")

    lines.extend(["", "### Paused sprints (decision needed)"])
    for r in buckets["paused"][:8]:
        lines.append(f"- **{r.title}** — review resume vs close")
    if not buckets["paused"]:
        lines.append("- _(none)_")

    lines.extend(["", "### Archive candidates (shipped & closed >7d ago)"])
    for r in buckets["archive_candidates"][:8]:
        lines.append(
            f"- **{r.title}** (ended {r.end_date}) — "
            "consider moving narrative to KNOWLEDGE / archive"
        )
    if not buckets["archive_candidates"]:
        lines.append("- _(none)_")

    open_ip = list(inprog)
    if open_ip:
        total_p = sum(r.pending_todos for r in open_ip)
        total_d = sum(r.done_todos for r in open_ip)
        lines.extend(
            [
                "",
                f"### Open todos across in-progress sprints: {total_p} pending vs {total_d} done",
            ]
        )

    lines.extend(["", "### Suggested next sprint seeds (unreferenced plan docs, priority-sorted)"])
    for _p, _w, rel in plan_hits[:8]:
        lines.append(f"- `{rel}`")
    if not plan_hits:
        lines.append("- _(no extra plan files found under docs/**/plans/)_")

    lines.extend(
        [
            "",
            "Respond with **Slack-ready markdown** for #strategy: "
            "Executive summary, 3 focus recommendations, 1 explicit founder decision, "
            "and risks. Keep it under ~900 words.",
        ]
    )
    return "\n".join(lines)


async def _append_knowledge_snapshot(slack_body: str) -> None:
    token = (settings.GITHUB_TOKEN or "").strip()
    if not token:
        logger.info("sprint_planner: GITHUB_TOKEN unset — skipping KNOWLEDGE.md snapshot append")
        return
    repo = (settings.GITHUB_REPO or "paperwork-labs/paperwork").strip()
    path = "docs/KNOWLEDGE.md"
    today = datetime.now(UTC).date().isoformat()
    block = (
        f"\n\n## Weekly sprint planning snapshot ({today})\n\n"
        f"_Autogenerated by `brain_sprint_planner`._\n\n"
        f"{(slack_body or '')[:8000]}\n"
    )
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                url,
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            if r.status_code != 200:
                logger.warning("sprint_planner: KNOWLEDGE.md GET %s", r.status_code)
                return
            data = r.json()
            b64 = data.get("content", "")
            if not isinstance(b64, str):
                return
            sha = data.get("sha")
            existing = base64.b64decode(b64.replace("\n", "")).decode("utf-8", errors="replace")
            new_content = existing + block
            put_body = {
                "message": f"chore(docs): weekly sprint planning snapshot {today}",
                "content": base64.b64encode(new_content.encode("utf-8")).decode("ascii"),
            }
            if sha:
                put_body["sha"] = sha
            pr = await client.put(
                url,
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json=put_body,
            )
            if pr.status_code not in (200, 201):
                logger.warning("sprint_planner: KNOWLEDGE.md PUT %s", pr.status_code)
    except Exception:
        logger.exception("sprint_planner: KNOWLEDGE.md append failed — continuing")


async def _run_sprint_planner_body() -> None:
    request_id = f"sprint-planner:brain:{datetime.now(UTC).isoformat()}"
    root = _repo_root()
    prompt = build_sprint_planning_prompt(root, None)
    redis_client = None
    with contextlib.suppress(RuntimeError):
        redis_client = get_redis()
    async with async_session_factory() as db:
        result = await brain_agent.process(
            db,
            redis_client,
            organization_id=_ORG_ID,
            org_name=_ORG_NAME,
            user_id="brain-scheduler:sprint-planner",
            message=prompt,
            channel="slack",
            channel_id=_STRATEGY_CHANNEL_ID,
            request_id=request_id,
            persona_pin="strategy",
            slack_username="Sprint planner",
            slack_icon_emoji=":calendar:",
        )
        await db.commit()
    text = (result.get("response") or "").strip() or "Brain returned an empty response."
    date_s = datetime.now(_LA_TZ).date().isoformat()
    out = f"*Sprint planning — {date_s} (PT)*\n\n{text[:12000]}"
    await slack_outbound.post_message(
        channel=_STRATEGY_SLACK_CHANNEL,
        text=out,
        username="Sprint planner",
        icon_emoji=":spiral_calendar_pad:",
    )
    await _append_knowledge_snapshot(out)


async def run_sprint_planner() -> None:
    await run_with_scheduler_record(
        _JOB_ID,
        _run_sprint_planner_body,
        metadata={"source": "brain_sprint_planner", "track": "J+L"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register Monday 14:00 America/Los_Angeles for sprint planning.

    Active when :envvar:`BRAIN_OWNS_SPRINT_PLANNER` is true.
    """
    if not _owns_sprint_planner():
        logger.info("BRAIN_OWNS_SPRINT_PLANNER is not true — skipping brain_sprint_planner job")
        return
    scheduler.add_job(
        run_sprint_planner,
        trigger=CronTrigger.from_crontab("0 14 * * 1", timezone=_LA_TZ),
        id=_JOB_ID,
        name="Sprint planning prompt (Brain, strategy → #strategy)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("APScheduler job %r registered (14:00 America/Los_Angeles Mondays)", _JOB_ID)
