"""Sync ``WorkstreamProgressSnapshot`` + dispatch evidence into ``workstreams.json`` (Track Z).

Opens (or amends) a single bot PR so Studio's static JSON matches Brain's Postgres board.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from apscheduler.triggers.cron import CronTrigger
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.config import settings
from app.database import async_session_factory
from app.models.workstream_board import WorkstreamDispatchLog, WorkstreamProgressSnapshot
from app.schedulers._history import run_with_scheduler_record
from app.schemas.workstream import Workstream, WorkstreamsFile, workstreams_file_to_json_dict
from app.services.workstreams_loader import invalidate_workstreams_cache, load_workstreams_file
from app.tools import github as gh
from app.tools.redis import release_scheduler_lock, try_acquire_scheduler_lock

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "workstream_progress_writeback"
_JSON_PATH = "apps/studio/src/data/workstreams.json"
_PR_TITLE = "chore(brain): workstream progress sync (auto)"
_HEAD_PREFIX = "bot/workstream-progress-"
_SCHEDULER_LOCK_KEY = "brain:scheduler:workstream_progress_writeback:lock"
_SCHEDULER_LOCK_TTL_SECONDS = 300


@dataclass
class WorkstreamWritebackResult:
    skipped: bool = False
    skip_reason: str | None = None
    no_drift: bool = False
    workstreams_changed: int = 0
    pr_number: int | None = None
    pr_url: str | None = None
    amended_existing_pr: bool = False


@dataclass
class _RowDelta:
    wid: str
    pct_before: int
    pct_after: int
    status_before: str
    status_after: str
    last_pr_before: int | None
    last_pr_after: int | None


@dataclass
class _WritebackState:
    deltas: list[_RowDelta] = field(default_factory=list)


def _iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pr_from_dispatch_inputs(inputs: dict[str, Any] | None) -> int | None:
    if not inputs:
        return None
    for key in ("pr_number", "ticket_pr_number", "ticket_pr"):
        v = inputs.get(key)
        if isinstance(v, int) and v > 0:
            return v
        if isinstance(v, str) and v.strip().isdigit():
            n = int(v.strip())
            if n > 0:
                return n
    return None


def _merge_status(current: str, proposed: str) -> str | None:
    """Return new status or None to keep current. Never auto-revert or un-block."""
    if current == "blocked":
        return None
    if current == "completed":
        return None
    if proposed == "pending" and current == "in_progress":
        return None
    if current == "pending":
        if proposed in ("in_progress", "completed"):
            return proposed
        return None
    if current == "in_progress":
        if proposed == "completed":
            return "completed"
        return None
    return None


async def _latest_snapshots_by_id(session: AsyncSession) -> dict[str, WorkstreamProgressSnapshot]:
    sub = (
        select(
            WorkstreamProgressSnapshot.workstream_id,
            func.max(WorkstreamProgressSnapshot.recorded_at).label("mx"),
        )
        .group_by(WorkstreamProgressSnapshot.workstream_id)
        .subquery()
    )
    stmt = select(WorkstreamProgressSnapshot).join(
        sub,
        (WorkstreamProgressSnapshot.workstream_id == sub.c.workstream_id)
        & (WorkstreamProgressSnapshot.recorded_at == sub.c.mx),
    )
    rows = (await session.execute(stmt)).scalars().all()
    by_id: dict[str, WorkstreamProgressSnapshot] = {}
    for r in rows:
        cur = by_id.get(r.workstream_id)
        if cur is None or (r.id > cur.id):
            by_id[r.workstream_id] = r
    return by_id


async def _latest_dispatch_by_id(session: AsyncSession) -> dict[str, WorkstreamDispatchLog]:
    sub = (
        select(
            WorkstreamDispatchLog.workstream_id,
            func.max(WorkstreamDispatchLog.dispatched_at).label("mx"),
        )
        .group_by(WorkstreamDispatchLog.workstream_id)
        .subquery()
    )
    stmt = select(WorkstreamDispatchLog).join(
        sub,
        (WorkstreamDispatchLog.workstream_id == sub.c.workstream_id)
        & (WorkstreamDispatchLog.dispatched_at == sub.c.mx),
    )
    rows = (await session.execute(stmt)).scalars().all()
    by_id: dict[str, WorkstreamDispatchLog] = {}
    for r in rows:
        cur = by_id.get(r.workstream_id)
        if cur is None or (r.id > cur.id):
            by_id[r.workstream_id] = r
    return by_id


async def _load_snapshot_dispatch_maps() -> tuple[
    dict[str, WorkstreamProgressSnapshot], dict[str, WorkstreamDispatchLog]
]:
    async with async_session_factory() as db:
        snaps = await _latest_snapshots_by_id(db)
        disp = await _latest_dispatch_by_id(db)
    return snaps, disp


def _pretty_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2) + "\n"


def _build_pr_body(deltas: list[_RowDelta], commit_sha: str) -> str:
    lines = [
        "Automated workstream board sync from Brain snapshots + dispatch log.",
        "",
        "| id | percent_done | status | last_pr |",
        "| --- | --- | --- | --- |",
    ]
    for d in deltas:
        lines.append(
            f"| `{d.wid}` | {d.pct_before} → {d.pct_after} | "
            f"{d.status_before} → {d.status_after} | "
            f"{d.last_pr_before} → {d.last_pr_after} |"
        )
    lines.extend(["", f"_Commit: `{commit_sha[:7]}`_"])
    return "\n".join(lines)


def _patch_one_workstream(
    ws: Workstream,
    snap: WorkstreamProgressSnapshot | None,
    dispatch_pr: int | None,
    dispatch_row: WorkstreamDispatchLog | None,
    state: _WritebackState,
) -> Workstream:
    pct_before = ws.percent_done
    status_before = ws.status
    last_pr_before = ws.last_pr

    new_pct = ws.percent_done
    new_status = ws.status
    new_last_pr = ws.last_pr

    if snap is not None:
        new_pct = snap.percent_done
        merged = _merge_status(ws.status, snap.computed_status)
        if merged is not None:
            new_status = merged  # type: ignore[assignment]
        if new_status == "completed" or ws.status == "completed":
            new_pct = 100

    if dispatch_pr is not None and (new_last_pr is None or dispatch_pr > new_last_pr):
        new_last_pr = dispatch_pr

    material = new_pct != pct_before or new_status != status_before or new_last_pr != last_pr_before
    if not material:
        return ws

    new_last_activity = ws.last_activity
    if snap is not None:
        new_last_activity = _iso_z(snap.recorded_at)
    elif dispatch_row is not None:
        new_last_activity = _iso_z(dispatch_row.dispatched_at)

    updated = ws.model_copy(
        update={
            "percent_done": new_pct,
            "status": new_status,
            "last_pr": new_last_pr,
            "last_activity": new_last_activity,
        }
    )
    state.deltas.append(
        _RowDelta(
            wid=ws.id,
            pct_before=pct_before,
            pct_after=new_pct,
            status_before=status_before,
            status_after=new_status,
            last_pr_before=last_pr_before,
            last_pr_after=new_last_pr,
        )
    )
    return updated


def _apply_patches_validated(
    base: WorkstreamsFile,
    snaps: dict[str, WorkstreamProgressSnapshot],
    disp: dict[str, WorkstreamDispatchLog],
) -> tuple[WorkstreamsFile | None, _WritebackState]:
    """Return updated file + deltas, or None if every patch was rejected."""
    state = _WritebackState()
    new_streams: list[Workstream] = []
    updated_ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    for i, orig in enumerate(base.workstreams):
        snap = snaps.get(orig.id)
        drow = disp.get(orig.id)
        dpr = _pr_from_dispatch_inputs(drow.inputs_json if drow else None)
        if snap is None and dpr is None:
            new_streams.append(orig)
            continue

        before_len = len(state.deltas)
        candidate = _patch_one_workstream(orig, snap, dpr, drow, state)
        if candidate is orig:
            new_streams.append(orig)
            continue

        suffix = [base.workstreams[j].model_copy() for j in range(i + 1, len(base.workstreams))]
        trial_list = [*new_streams, candidate, *suffix]
        trial = WorkstreamsFile(version=base.version, updated=updated_ts, workstreams=trial_list)
        try:
            validated = WorkstreamsFile.model_validate(trial.model_dump(mode="json"))
        except ValidationError as e:
            logger.warning(
                "workstream_progress_writeback: rejecting invalid patch for %s: %s",
                orig.id,
                e,
            )
            if len(state.deltas) > before_len:
                state.deltas.pop()
            new_streams.append(orig)
            continue

        new_streams.append(validated.workstreams[len(new_streams)])

    if not state.deltas:
        return None, state

    final_try = WorkstreamsFile(version=base.version, updated=updated_ts, workstreams=new_streams)
    try:
        final = WorkstreamsFile.model_validate(final_try.model_dump(mode="json"))
    except ValidationError as e:
        logger.warning("workstream_progress_writeback: full file invalid after patches: %s", e)
        return None, _WritebackState()

    return final, state


async def _find_open_writeback_pr() -> tuple[int, str] | None:
    """Return (pr_number, head_ref) for an open progress-sync PR, if any."""
    pulls = await gh.list_repo_pull_requests(state="open", per_page=100, max_pages=2)
    for p in pulls:
        head = p.get("head") or {}
        ref = str(head.get("ref") or "")
        if ref.startswith(_HEAD_PREFIX):
            num = p.get("number")
            if isinstance(num, int):
                return num, ref
    return None


async def _finalize_amend_existing_pr(
    pr_num: int,
    branch: str,
    new_file: WorkstreamsFile,
) -> dict[str, Any]:
    text = _pretty_json(workstreams_file_to_json_dict(new_file))
    commit_msg = "chore(brain): workstream progress sync (auto) [skip ci]"
    commit_sha = await gh.commit_files_to_branch(
        branch,
        commit_msg,
        {_JSON_PATH: text},
    )
    if not commit_sha:
        raise RuntimeError("commit_files_to_branch failed (amend)")
    pr_url = f"https://github.com/{settings.GITHUB_REPO.strip()}/pull/{pr_num}"
    invalidate_workstreams_cache()
    return {
        "number": pr_num,
        "html_url": pr_url,
        "commit_sha": commit_sha,
        "amended": True,
    }


async def _finalize_new_pr_on_branch(
    branch: str,
    new_file: WorkstreamsFile,
    state: _WritebackState,
) -> dict[str, Any]:
    text = _pretty_json(workstreams_file_to_json_dict(new_file))
    commit_msg = "chore(brain): workstream progress sync (auto) [skip ci]"
    commit_sha = await gh.commit_files_to_branch(
        branch,
        commit_msg,
        {_JSON_PATH: text},
    )
    if not commit_sha:
        raise RuntimeError("commit_files_to_branch failed")

    body = _build_pr_body(state.deltas, commit_sha)
    pr = await gh.create_github_pull(
        head=branch,
        base="main",
        title=_PR_TITLE,
        body=body,
    )
    if pr:
        invalidate_workstreams_cache()
        pr["commit_sha"] = commit_sha
        pr["amended"] = False
        return pr

    existing = await _find_open_writeback_pr()
    if existing:
        pr_num, ref = existing
        logger.info(
            "workstream_progress_writeback: open PR already exists for head %s (#%s)",
            ref,
            pr_num,
        )
        pr_url = f"https://github.com/{settings.GITHUB_REPO.strip()}/pull/{pr_num}"
        invalidate_workstreams_cache()
        return {
            "number": pr_num,
            "html_url": pr_url,
            "commit_sha": commit_sha,
            "amended": True,
        }
    raise RuntimeError("create_github_pull failed")


async def _open_or_amend_writeback_pr(
    new_file: WorkstreamsFile,
    state: _WritebackState,
) -> dict[str, Any]:
    if not settings.GITHUB_TOKEN.strip():
        raise RuntimeError("GITHUB_TOKEN not configured")

    existing = await _find_open_writeback_pr()
    if existing is not None:
        pr_num, branch = existing
        return await _finalize_amend_existing_pr(pr_num, branch, new_file)

    main_sha = await gh.get_git_ref_sha("main")
    if not main_sha:
        raise RuntimeError("could not resolve main")

    last_tried = ""
    for attempt in range(2):
        ts = int(time.time())
        branch = f"{_HEAD_PREFIX}{ts}"
        last_tried = branch

        if await gh.create_git_ref(branch, main_sha):
            return await _finalize_new_pr_on_branch(branch, new_file, state)

        raced = await _find_open_writeback_pr()
        if raced is not None:
            pr_num, ref = raced
            return await _finalize_amend_existing_pr(pr_num, ref, new_file)

        if await gh.get_branch_sha(branch):
            return await _finalize_new_pr_on_branch(branch, new_file, state)

        logger.warning(
            "workstream_progress_writeback: create_git_ref failed for %s with no visible ref "
            "(attempt %s/2)",
            branch,
            attempt + 1,
        )

    raise RuntimeError(f"could not create branch {last_tried}")


async def run_workstream_progress_writeback() -> WorkstreamWritebackResult:
    if not settings.BRAIN_SCHEDULER_ENABLED:
        return WorkstreamWritebackResult(skipped=True, skip_reason="BRAIN_SCHEDULER_ENABLED=false")

    acquired = await try_acquire_scheduler_lock(_SCHEDULER_LOCK_KEY, _SCHEDULER_LOCK_TTL_SECONDS)
    if not acquired:
        logger.info("workstream_progress_writeback: another worker holds the lock, skipping")
        return WorkstreamWritebackResult(skipped=True, skip_reason="scheduler_lock_held")

    try:
        base = load_workstreams_file(bypass_cache=True)
        snaps, disp = await _load_snapshot_dispatch_maps()

        new_file, wstate = _apply_patches_validated(base, snaps, disp)
        if new_file is None or not wstate.deltas:
            logger.info("workstream_progress_writeback: no drift")
            return WorkstreamWritebackResult(no_drift=True)

        pr_meta = await _open_or_amend_writeback_pr(new_file, wstate)
        logger.info(
            "workstream_progress_writeback: %s PR #%s (%d workstreams)",
            "amended" if pr_meta.get("amended") else "opened",
            pr_meta.get("number"),
            len(wstate.deltas),
        )
        return WorkstreamWritebackResult(
            workstreams_changed=len(wstate.deltas),
            pr_number=int(pr_meta["number"]) if pr_meta.get("number") is not None else None,
            pr_url=str(pr_meta.get("html_url") or ""),
            amended_existing_pr=bool(pr_meta.get("amended")),
        )
    finally:
        await release_scheduler_lock(_SCHEDULER_LOCK_KEY)


async def _writeback_job_body() -> None:
    await run_workstream_progress_writeback()


async def run_workstream_progress_writeback_job() -> None:
    await run_with_scheduler_record(
        _JOB_ID,
        _writeback_job_body,
        metadata={"source": "workstream_progress_writeback", "track": "workstreams-board"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_workstream_progress_writeback_job,
        trigger=CronTrigger.from_crontab("15 * * * *", timezone=UTC),
        id=_JOB_ID,
        name="Workstream progress JSON writeback (Track Z)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job %r registered (15 * * * * UTC)", _JOB_ID)
