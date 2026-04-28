"""Poll Render API usage, persist :class:`~app.models.render_quota_snapshot.RenderQuotaSnapshot`.

medallion: ops
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import httpx
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models.render_quota_snapshot import RenderQuotaSnapshot
from app.tools import github as gh

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

API = "https://api.render.com/v1"
_ALARM = 0.8
_ALARM_LABELS = ("infra-alert", "render-quota")
_MAX_PAGES = 120


def calendar_month_start_utc(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def current_month_label_utc(now: datetime) -> str:
    d = now.astimezone(UTC)
    return f"{d.year:04d}-{d.month:02d}"


def _deploy_inner(d: dict[str, Any]) -> dict[str, Any]:
    x = d.get("deploy")
    return x if isinstance(x, dict) else d


def _parse_iso(v: Any) -> datetime | None:
    if not v or not isinstance(v, str):
        return None
    s = v.replace("Z", "+00:00") if v.endswith("Z") else v
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        return None


def deploy_pipeline_minutes(d: dict[str, Any]) -> float | None:
    raw = _deploy_inner(d)
    a = _parse_iso(raw.get("startedAt"))
    b = _parse_iso(raw.get("finishedAt"))
    if a is None or b is None or b < a:
        return None
    return (b - a).total_seconds() / 60.0


def deploy_started_at(d: dict[str, Any]) -> datetime | None:
    return _parse_iso(_deploy_inner(d).get("startedAt"))


def extract_pipeline_minutes_from_usage(payload: dict[str, Any]) -> float | None:
    def walk(o: Any, depth: int = 0) -> float | None:
        if depth > 6:
            return None
        if isinstance(o, dict):
            for k, v in o.items():
                lk = str(k).lower()
                if (
                    isinstance(v, (int, float))
                    and "minute" in lk
                    and ("pipeline" in lk or "build" in lk)
                ):
                    return float(v)
                r = walk(v, depth + 1)
                if r is not None:
                    return r
        if isinstance(o, list):
            for it in o[:40]:
                r = walk(it, depth + 1)
                if r is not None:
                    return r
        return None

    for path in (("pipelineMinutes",), ("usage", "pipelineMinutes")):
        cur: Any = payload
        ok = True
        for part in path:
            if not isinstance(cur, dict) or part not in cur:
                ok = False
                break
            cur = cur[part]
        if ok and isinstance(cur, (int, float)):
            return float(cur)
    return walk(payload)


def _norm_services(body: dict[str, Any]) -> list[dict[str, Any]]:
    raw = body.get("services") or body.get("service") or []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for it in raw:
        if not isinstance(it, dict):
            continue
        inner = it.get("service")
        out.append(inner if isinstance(inner, dict) else it)
    return out


async def _list_services(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> list[dict[str, Any]]:
    acc: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(40):
        q: dict[str, str] = {}
        if cursor:
            q["cursor"] = cursor
        r = await client.get(f"{API}/services", headers=headers, params=q or None, timeout=120.0)
        r.raise_for_status()
        data = r.json()
        acc.extend(_norm_services(data))
        c = data.get("cursor")
        cursor = str(c).strip() if c else None
        if not cursor:
            break
    return acc


async def _sum_month_for_service(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    sid: str,
    month_start: datetime,
    now: datetime,
) -> tuple[float, int]:
    total = 0.0
    tries = 0
    cur: str | None = None
    for _ in range(_MAX_PAGES):
        p = {"limit": "100"}
        if cur:
            p["cursor"] = cur
        r = await client.get(
            f"{API}/services/{sid}/deploys",
            headers=headers,
            params=p,
            timeout=120.0,
        )
        if r.status_code != 200:
            break
        data = r.json()
        raw = data.get("deploys") or data.get("deploy") or []
        if not isinstance(raw, list) or not raw:
            break
        starts: list[datetime] = []
        for d in raw:
            if not isinstance(d, dict):
                continue
            st = deploy_started_at(d)
            if st is None:
                continue
            starts.append(st)
            if month_start <= st <= now:
                tries += 1
                m = deploy_pipeline_minutes(d)
                if m is not None:
                    total += m
        if starts and max(starts) < month_start:
            break
        nxt = data.get("cursor")
        cur = str(nxt).strip() if nxt else None
        if not cur:
            break
    return total, tries


async def _billing_usage(
    client: httpx.AsyncClient,
    headers: dict[str, str],
) -> dict[str, Any] | None:
    try:
        r = await client.get(f"{API}/billing/usage", headers=headers, timeout=60.0)
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    j = r.json()
    return j if isinstance(j, dict) else None


async def _bandwidth(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    m0: datetime,
    now: datetime,
) -> tuple[float | None, float | None, dict[str, Any]]:
    r = await client.get(
        f"{API}/metrics/bandwidth",
        headers=headers,
        params={"startTime": str(int(m0.timestamp())), "endTime": str(int(now.timestamp()))},
        timeout=60.0,
    )
    if r.status_code != 200:
        return None, None, {"http_status": r.status_code}
    j = r.json()
    if not isinstance(j, dict):
        return None, None, {"raw": j}
    u = None
    for k, v in j.items():
        if "total" in k.lower() and isinstance(v, (int, float)):
            u = float(v) / (1024.0**3)
            break
    return u, None, {"keys": list(j)[:20]}


def alarm_decision(used: float, inc: float) -> tuple[bool, list[str]]:
    if inc <= 0:
        return False, []
    if used / inc > _ALARM:
        return True, [
            f"pipeline_minutes_used={used:.2f}/included={inc:.2f} "
            f"ratio={used / inc:.3f} > {_ALARM:.0%}"
        ]
    return False, []


def _gh_repo_prefix() -> str:
    raw = (settings.GITHUB_REPO or "").strip().split("/", 1)
    if len(raw) == 2 and raw[0] and raw[1]:
        return f"repo:{raw[0]}/{raw[1]}"
    return "repo:paperwork-labs/paperwork"


async def _emit_github(
    reasons: list[str],
    snapshot_id: str,
    used: float,
    inc: float,
    excerpt: dict[str, Any],
) -> None:
    if not (settings.GITHUB_TOKEN or "").strip():
        logger.warning("render_quota_monitor: GITHUB_TOKEN missing; skipping issue")
        return
    body = "\n".join(
        [
            "Brain render_quota_monitor: threshold breached.",
            "",
            *[f"- {r}" for r in reasons],
            f"- snapshot: `{snapshot_id}`",
            f"- used/included: **{used:.2f} / {inc:.2f}**",
            "",
            "```json",
            json.dumps(excerpt, indent=2, sort_keys=True)[:11000],
            "```",
            "",
            "`docs/infra/RENDER_QUOTA_AUDIT_2026Q2.md`",
        ]
    )
    lab = " ".join(f'label:"{lab}"' for lab in _ALARM_LABELS)
    q = f"{_gh_repo_prefix()} is:issue is:open {lab}"
    items = await gh.search_github_issues(q, per_page=5, max_pages=1)
    if items and isinstance(items[0].get("number"), int):
        await gh.add_github_issue_comment(
            items[0]["number"],
            "**Update**\n" + "\n".join(f"- {r}" for r in reasons),
        )
        return
    await gh.create_github_issue(
        "[infra] Render quota threshold (Brain monitor)",
        body,
        labels=list(_ALARM_LABELS),
    )


_extract_pipeline_minutes_from_usage = extract_pipeline_minutes_from_usage


async def run_render_quota_monitor_tick(
    *,
    http_client: httpx.AsyncClient | None = None,
    at: datetime | None = None,
) -> None:
    tok = (settings.RENDER_API_KEY or "").strip()
    if not tok:
        logger.info("render_quota_monitor: RENDER_API_KEY unset; skip")
        return
    hdrs = {"Authorization": f"Bearer {tok}", "Accept": "application/json"}
    rec = at.astimezone(UTC) if at is not None else datetime.now(UTC)
    m0 = calendar_month_start_utc(rec)
    month = current_month_label_utc(rec)
    inc = float(settings.RENDER_PIPELINE_MINUTES_INCLUDED or 500.0)
    ref = str(uuid.uuid4())
    extra: dict[str, Any] = {"snapshot_ref": ref, "billing": {}}
    derived = "deploy_sum"
    pipes = 0.0

    close = False
    if http_client is None:
        http_client = httpx.AsyncClient()
        close = True
    svcs: list[dict[str, Any]] = []
    busage: dict[str, Any] | None = None
    bw_u: float | None = None
    bw_cap: float | None = None
    wp: str | None = None

    try:
        busage = await _billing_usage(http_client, hdrs)
        if busage:
            extra["billing"]["usage_payload"] = busage
            ex = extract_pipeline_minutes_from_usage(busage)
            if ex is not None:
                pipes = float(ex)
                derived = "render_api_usage"

        bw_u, bw_cap, bw_meta = await _bandwidth(http_client, hdrs, m0, rec)
        if bw_meta:
            extra["bandwidth_probe"] = bw_meta

        try:
            svcs = await _list_services(http_client, hdrs)
        except httpx.HTTPError as e:
            logger.warning("render_quota_monitor: list services: %s", e)
            svcs = []

        extra["services_total"] = len(svcs)

        sem = asyncio.Semaphore(8)

        async def one(svc: dict[str, Any]) -> tuple[str, str, float, int]:
            sid = str(svc.get("id") or "").strip()
            name = str(svc.get("name") or sid or "unknown")
            if not sid:
                return sid, name, 0.0, 0
            async with sem:
                mins, nt = await _sum_month_for_service(http_client, hdrs, sid, m0, rec)
            return sid, name, mins, nt

        results = await asyncio.gather(*(one(s) for s in svcs), return_exceptions=True)
        roll: list[tuple[str, str, float, int]] = []
        derived_sum = 0.0
        for raw in results:
            if isinstance(raw, Exception):
                logger.warning("render_quota_monitor service task error: %s", raw)
                continue
            a, b, c, _ = cast("tuple[str, str, float, int]", raw)
            derived_sum += c
            roll.append((a, b, c, _))
        tops = [
            {"service_id": a, "name": b, "approx_minutes": round(c, 2)}
            for a, b, c, _ in sorted(roll, key=lambda z: -z[2])[:20]
        ]

        if derived == "deploy_sum" or busage is None:
            pipes = derived_sum

        plans = []
        for s in svcs:
            t = ""
            rt = s.get("type")
            if isinstance(rt, str) and rt.strip():
                t = rt.strip()
            sd = s.get("serviceDetails")
            if not t and isinstance(sd, dict):
                pl = sd.get("plan")
                if isinstance(pl, str) and pl.strip():
                    t = pl.strip()
            if t:
                plans.append(t)
        if plans and len(set(plans)) == 1:
            wp = plans[0]

        extra["top_services_by_minutes"] = tops
        extra["month_window_utc"] = {"start": m0.isoformat(), "end": rec.isoformat()}
    finally:
        if close:
            await http_client.aclose()

    ratio = pipes / inc if inc else 0.0
    snap = RenderQuotaSnapshot(
        recorded_at=rec,
        month=month,
        pipeline_minutes_used=pipes,
        pipeline_minutes_included=inc,
        bandwidth_gb_used=bw_u,
        bandwidth_gb_included=bw_cap,
        unbilled_charges_usd=None,
        services_count=len(svcs),
        datastores_storage_gb=None,
        workspace_plan=wp,
        derived_from=derived,
        extra_json=extra,
    )
    async with async_session_factory() as session:
        session.add(snap)
        await session.commit()

    fire, reasons = alarm_decision(pipes, inc)
    if ratio > _ALARM:
        logger.warning(
            "render_quota_monitor: ratio %.4f (>%.0f%%)",
            ratio,
            _ALARM * 100,
            extra={
                "event": "render_quota_alarm",
                "usage_ratio": round(ratio, 6),
                "pipeline_minutes_used": pipes,
                "pipeline_minutes_included": inc,
                "derived_from": derived,
            },
        )
    if fire:
        await _emit_github(
            reasons,
            ref,
            pipes,
            inc,
            {
                "month": month,
                "usage_ratio": round(ratio, 6),
                "derived_from": derived,
            },
        )


async def latest_render_quota_snapshot(session: AsyncSession) -> RenderQuotaSnapshot | None:
    stmt = select(RenderQuotaSnapshot).order_by(RenderQuotaSnapshot.recorded_at.desc()).limit(1)
    r = await session.execute(stmt)
    return r.scalars().first()


def build_render_quota_admin_data(row: RenderQuotaSnapshot | None) -> dict[str, Any]:
    if row is None:
        return {"snapshot": None, "top_services_by_minutes": []}
    ex = row.extra_json or {}
    rt = ex.get("top_services_by_minutes")
    tops: list[Any] = rt if isinstance(rt, list) else []
    inc = row.pipeline_minutes_included
    ur = row.pipeline_minutes_used / inc if inc else 0.0
    return {
        "snapshot": {
            "recorded_at": row.recorded_at.isoformat(),
            "month": row.month,
            "pipeline_minutes_used": row.pipeline_minutes_used,
            "pipeline_minutes_included": row.pipeline_minutes_included,
            "usage_ratio": round(ur, 6),
            "derived_from": row.derived_from,
            "bandwidth_gb_used": row.bandwidth_gb_used,
            "bandwidth_gb_included": row.bandwidth_gb_included,
            "unbilled_charges_usd": row.unbilled_charges_usd,
        },
        "top_services_by_minutes": tops,
    }


render_quota_alarm_decision = alarm_decision


async def emit_render_quota_alarm(
    *,
    reasons: list[str],
    snapshot_id: str,
    pipeline_used: float,
    pipeline_included: float,
    excerpt: dict[str, Any],
) -> None:
    """Public entry for tests/alerts; forwards to :func:`_emit_github`."""

    await _emit_github(reasons, snapshot_id, pipeline_used, pipeline_included, excerpt)
