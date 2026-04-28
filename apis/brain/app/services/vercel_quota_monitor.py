"""Poll Vercel deployment usage, persist snapshots, and raise GitHub quota alarms.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.quota_snapshot import VercelQuotaSnapshot
from app.tools import github as gh

logger = logging.getLogger(__name__)

VERCEL_API_BASE = "https://api.vercel.com"
DEFAULT_TEAM_ID = "team_RwfzJ9ySyLuVcoWdKJfXC7h5"
DEPLOY_DAILY_CAP = 100
BUILD_MINUTES_30D_CAP = 6000.0
ALARM_FRACTION = 0.8
_MAX_DEPLOYMENT_PAGES = 400
_ALARM_LABELS = ("infra-alert", "vercel-quota")


def vercel_deployments_list_params(
    team_id: str,
    project_id: str,
    *,
    limit: int = 100,
    until: str | None = None,
) -> dict[str, str]:
    """Build query params for ``GET /v6/deployments`` (test seam)."""
    p: dict[str, str] = {
        "teamId": team_id,
        "projectId": project_id,
        "limit": str(limit),
    }
    if until:
        p["until"] = until
    return p


def _as_ms(val: Any) -> int | None:
    if val is None:
        return None
    try:
        n = int(val)
    except (TypeError, ValueError):
        return None
    if n < 1_000_000_000_000:
        return n * 1000
    return n


def deployment_created_ms(d: dict[str, Any]) -> int:
    for key in ("createdAt", "created"):
        v = _as_ms(d.get(key))
        if v is not None:
            return v
    return 0


def build_minutes_for_deploy(d: dict[str, Any]) -> float | None:
    b = _as_ms(d.get("buildingAt"))
    r = _as_ms(d.get("ready"))
    if b is None or r is None or r < b:
        return None
    return (r - b) / 60_000.0


def source_bucket(raw: Any) -> str:
    if raw is None or raw == "":
        return "null"
    s = str(raw).strip().lower()
    if s in ("git", "cli", "api", "import", "redeploy"):
        return s
    return s or "null"


def next_deployments_until_token(last_deployment: dict[str, Any]) -> str | None:
    uid = last_deployment.get("uid")
    if uid:
        return str(uid)
    cm = deployment_created_ms(last_deployment)
    return str(cm) if cm else None


def merge_source_breakdown(into: dict[str, int], add: dict[str, int]) -> None:
    for k, v in add.items():
        into[k] = into.get(k, 0) + v


def aggregate_window(
    deploys: list[dict[str, Any]],
    start_ms: int,
    end_ms: int,
) -> tuple[int, float, dict[str, int]]:
    breakdown: dict[str, int] = {}
    deploy_count = 0
    build_sum = 0.0
    for d in deploys:
        if not isinstance(d, dict):
            continue
        cm = deployment_created_ms(d)
        if cm < start_ms or cm > end_ms:
            continue
        deploy_count += 1
        k = source_bucket(d.get("source"))
        breakdown[k] = breakdown.get(k, 0) + 1
        bm = build_minutes_for_deploy(d)
        if bm is not None:
            build_sum += bm
    return deploy_count, build_sum, breakdown


def utc_midnight_ms(now_ms: int) -> int:
    dt = datetime.fromtimestamp(now_ms / 1000.0, tz=UTC)
    day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(day.timestamp() * 1000)


def vercel_quota_alarm_decision(
    deploy_count_24h: int,
    build_minutes_30d: float,
    *,
    deploy_cap: int = DEPLOY_DAILY_CAP,
    build_cap: float = BUILD_MINUTES_30D_CAP,
    alarm_fraction: float = ALARM_FRACTION,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    deploy_threshold = deploy_cap * alarm_fraction
    build_threshold = build_cap * alarm_fraction
    if deploy_count_24h >= deploy_threshold:
        reasons.append(
            f"rolling_24h_deploy_count={deploy_count_24h} >= {deploy_threshold:.0f} "
            f"({alarm_fraction:.0%} of hobby {deploy_cap}/day proxy)"
        )
    if build_minutes_30d >= build_threshold:
        reasons.append(
            f"rolling_30d_build_minutes={build_minutes_30d:.2f} >= {build_threshold:.1f} "
            f"({alarm_fraction:.0%} of {build_cap:.0f} min / 30d proxy)"
        )
    return (bool(reasons), reasons)


async def fetch_team_projects(
    client: httpx.AsyncClient,
    token: str,
    team_id: str,
) -> list[tuple[str | None, str]]:
    r = await client.get(
        f"{VERCEL_API_BASE}/v9/projects",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        params={"teamId": team_id, "limit": "100"},
        timeout=httpx.Timeout(120.0),
    )
    r.raise_for_status()
    data = r.json()
    projects = data.get("projects") or []
    out: list[tuple[str | None, str]] = []
    if not isinstance(projects, list):
        return out
    for p in projects:
        if not isinstance(p, dict):
            continue
        pid = p.get("id")
        name = str(p.get("name") or pid or "unknown")
        out.append((str(pid) if pid else None, name))
    return out


async def fetch_deployments_since(
    client: httpx.AsyncClient,
    token: str,
    team_id: str,
    project_id: str,
    since_ms: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    until: str | None = None
    pages = 0
    while pages < _MAX_DEPLOYMENT_PAGES:
        pages += 1
        params = vercel_deployments_list_params(team_id, project_id, limit=100, until=until)
        r = await client.get(
            f"{VERCEL_API_BASE}/v6/deployments",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params=params,
            timeout=httpx.Timeout(120.0),
        )
        r.raise_for_status()
        body = r.json()
        batch = body.get("deployments") or []
        if not isinstance(batch, list) or not batch:
            break
        oldest_in_page = deployment_created_ms(batch[-1] if isinstance(batch[-1], dict) else {})
        stop_after_page = False
        for d in batch:
            if not isinstance(d, dict):
                continue
            cm = deployment_created_ms(d)
            if cm >= since_ms:
                out.append(d)
            if cm < since_ms:
                stop_after_page = True
        if oldest_in_page < since_ms or stop_after_page:
            break
        last = batch[-1]
        if not isinstance(last, dict):
            break
        nxt = next_deployments_until_token(last)
        if not nxt or nxt == until:
            break
        until = nxt
    return out


def _github_repo_search_prefix() -> str:
    raw = (settings.GITHUB_REPO or "").strip()
    parts = raw.split("/", 1)
    if len(parts) == 2 and parts[0] and parts[1]:
        return f"repo:{parts[0]}/{parts[1]}"
    return "repo:paperwork-labs/paperwork"


def _open_vercel_quota_search_query() -> str:
    lab = " ".join(f'label:"{lab}"' for lab in _ALARM_LABELS)
    return f"{_github_repo_search_prefix()} is:issue is:open {lab}"


async def _emit_quota_alarm(
    *,
    reasons: list[str],
    batch_id: str,
    team_24_deploys: int,
    team_30_build: float,
    excerpt: dict[str, Any],
) -> None:
    if not (settings.GITHUB_TOKEN or "").strip():
        logger.warning("vercel quota alarm skipped: GITHUB_TOKEN not configured")
        return

    body_md = "\n".join(
        [
            "Brain **vercel_quota_monitor** detected threshold breach.",
            "",
            "**Reasons**",
            *[f"- {r}" for r in reasons],
            "",
            f"- rolling_24h team deploy count: **{team_24_deploys}**",
            f"- rolling_30d team build minutes: **{team_30_build:.2f}**",
            f"- snapshot `batch_id`: `{batch_id}`",
            "",
            "<details><summary>snapshot excerpt (JSON)</summary>",
            "",
            "```json",
            json.dumps(excerpt, indent=2, sort_keys=True)[:12000],
            "```",
            "",
            "</details>",
            "",
            "Spec: `docs/infra/VERCEL_QUOTA_AUDIT_2026Q2.md`",
        ]
    )
    comment_md = "\n".join(
        [
            f"**Update** ({datetime.now(UTC).isoformat()})",
            "",
            *[f"- {r}" for r in reasons],
            f"- rolling_24h deploys: **{team_24_deploys}**",
            f"- rolling_30d build min: **{team_30_build:.2f}**",
            f"- `batch_id`: `{batch_id}`",
        ]
    )

    q = _open_vercel_quota_search_query()
    items = await gh.search_github_issues(q, per_page=5, max_pages=1)
    if items:
        num = items[0].get("number")
        if isinstance(num, int):
            await gh.add_github_issue_comment(num, comment_md)
            logger.info("vercel quota alarm: commented on issue #%s", num)
            return

    title = "[infra] Vercel quota threshold (Brain monitor)"
    result = await gh.create_github_issue(
        title,
        body_md,
        labels=[*_ALARM_LABELS],
    )
    logger.info("vercel quota alarm: create issue result=%s", result[:200] if result else "")


async def persist_snapshots(
    session: AsyncSession,
    *,
    batch_at: datetime,
    batch_id: str,
    team_id: str,
    now_ms: int,
    per_project: list[dict[str, Any]],
    team_by_window: dict[int, tuple[int, float, dict[str, int]]],
) -> None:
    rows: list[VercelQuotaSnapshot] = []
    cal_start = utc_midnight_ms(now_ms)

    for w in (1, 30):
        t_count, t_build, t_break = team_by_window[w]
        rows.append(
            VercelQuotaSnapshot(
                created_at=batch_at,
                project_id=None,
                project_name="(team)",
                window_days=w,
                deploy_count=t_count,
                build_minutes=t_build,
                source_breakdown=dict(t_break),
                meta={
                    "batch_id": batch_id,
                    "team_id": team_id,
                    "window_note": "window_days=1 is rolling 24h; window_days=30 is rolling 30d",
                },
            )
        )

    for proj in per_project:
        pid = proj.get("project_id")
        pname = str(proj.get("project_name") or "")
        deploys: list[dict[str, Any]] = proj.get("deploys") or []
        cal_deploys = sum(
            1
            for d in deploys
            if isinstance(d, dict) and cal_start <= deployment_created_ms(d) <= now_ms
        )
        for w in (1, 30):
            start_ms = now_ms - (86400000 if w == 1 else 30 * 86400000)
            dc, bm, br = aggregate_window(deploys, start_ms, now_ms)
            rows.append(
                VercelQuotaSnapshot(
                    created_at=batch_at,
                    project_id=str(pid) if pid else None,
                    project_name=pname,
                    window_days=w,
                    deploy_count=dc,
                    build_minutes=bm,
                    source_breakdown=dict(br),
                    meta={
                        "batch_id": batch_id,
                        "team_id": team_id,
                        "calendar_day_deploy_count_utc": cal_deploys,
                        "utc_date": datetime.fromtimestamp(
                            now_ms / 1000.0, tz=UTC
                        ).date().isoformat(),
                    },
                )
            )

    session.add_all(rows)
    await session.commit()


async def run_vercel_quota_monitor_tick(
    *,
    team_id: str = DEFAULT_TEAM_ID,
    http_client: httpx.AsyncClient | None = None,
) -> None:
    token = (settings.VERCEL_API_TOKEN or "").strip()
    if not token:
        logger.info("vercel_quota_monitor: VERCEL_API_TOKEN not set, skipping")
        return

    batch_at = datetime.now(UTC)
    batch_id = str(uuid.uuid4())
    now_ms = int(batch_at.timestamp() * 1000)
    since_ms = now_ms - 30 * 86400000

    close_client = False
    if http_client is None:
        http_client = httpx.AsyncClient()
        close_client = True

    try:
        projects = await fetch_team_projects(http_client, token, team_id)
        per_project: list[dict[str, Any]] = []
        team_by_window: dict[int, tuple[int, float, dict[str, int]]] = {
            1: (0, 0.0, {}),
            30: (0, 0.0, {}),
        }

        for pid, pname in projects:
            if not pid:
                continue
            deploys = await fetch_deployments_since(
                http_client, token, team_id, pid, since_ms
            )
            per_project.append(
                {
                    "project_id": pid,
                    "project_name": pname,
                    "deploys": deploys,
                }
            )
            for w in (1, 30):
                start_ms = now_ms - (86400000 if w == 1 else 30 * 86400000)
                dc, bm, br = aggregate_window(deploys, start_ms, now_ms)
                cur = team_by_window[w]
                merged = dict(cur[2])
                merge_source_breakdown(merged, br)
                team_by_window[w] = (cur[0] + dc, cur[1] + bm, merged)
    finally:
        if close_client:
            await http_client.aclose()

    async with async_session_factory() as session:
        await persist_snapshots(
            session,
            batch_at=batch_at,
            batch_id=batch_id,
            team_id=team_id,
            now_ms=now_ms,
            per_project=per_project,
            team_by_window=team_by_window,
        )

    d24 = team_by_window[1][0]
    b30 = team_by_window[30][1]
    fire, reasons = vercel_quota_alarm_decision(d24, b30)
    if fire:
        excerpt = {
            "batch_id": batch_id,
            "team_id": team_id,
            "rolling_24h_deploy_count": d24,
            "rolling_30d_build_minutes": b30,
            "per_project_names": [p.get("project_name") for p in per_project],
        }
        await _emit_quota_alarm(
            reasons=reasons,
            batch_id=batch_id,
            team_24_deploys=d24,
            team_30_build=b30,
            excerpt=excerpt,
        )


async def latest_vercel_quota_snapshots(session: AsyncSession) -> list[VercelQuotaSnapshot]:
    sub = select(func.max(VercelQuotaSnapshot.created_at))
    latest = (await session.execute(sub)).scalar()
    if latest is None:
        return []
    stmt = (
        select(VercelQuotaSnapshot)
        .where(VercelQuotaSnapshot.created_at == latest)
        .order_by(VercelQuotaSnapshot.project_name, VercelQuotaSnapshot.window_days)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
