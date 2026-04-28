"""Poll GitHub Actions billing + cache endpoints; persist snapshots; log quota alarms.

Uses ``settings.GITHUB_TOKEN`` (classic PAT or fine-grained with ``actions:read`` and
``repo`` / org billing as token allows).

medallion: ops
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.github_actions_quota_snapshot import GitHubActionsQuotaSnapshot

logger = logging.getLogger(__name__)

GH_API = "https://api.github.com"

# ~80% of GitHub Free included private minutes (proxy for “near limit”).
_PRIVATE_INCLUDED_FRACTION_ALARM = 0.80
_PRIVATE_ABSOLUTE_MINUTES_WARN = 1600.0


def _token() -> str:
    return (settings.GITHUB_TOKEN or "").strip()


def _repo_parts() -> tuple[str, str]:
    raw = settings.GITHUB_REPO.strip()
    parts = raw.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return "paperwork-labs", "paperwork"
    return parts[0], parts[1]


def _gh_headers() -> dict[str, str]:
    return {
        "Authorization": f"token {_token()}",
        "Accept": "application/vnd.github+json",
    }


def github_actions_quota_alarm_decision(
    *,
    is_public: bool,
    minutes_used: float | None,
    included_minutes: int | None,
    paid_minutes_used: float | None,
) -> tuple[bool, list[str]]:
    """Return ``(should_log_warning, reasons)`` when billing looks risky."""
    reasons: list[str] = []
    mu = float(minutes_used) if minutes_used is not None else None
    paid = float(paid_minutes_used) if paid_minutes_used is not None else None

    if paid is not None and paid > 0:
        reasons.append(f"total_paid_minutes_used={paid:.1f} (>0, check spend)")

    if is_public:
        return (bool(reasons), reasons)

    if mu is None:
        return (bool(reasons), reasons)

    inc = float(included_minutes) if included_minutes is not None else None
    if inc is not None and inc > 0 and mu >= inc * _PRIVATE_INCLUDED_FRACTION_ALARM:
        reasons.append(
            f"total_minutes_used={mu:.1f} >= {_PRIVATE_INCLUDED_FRACTION_ALARM:.0%} of "
            f"included_minutes={included_minutes}"
        )
    if mu >= _PRIVATE_ABSOLUTE_MINUTES_WARN:
        reasons.append(
            f"total_minutes_used={mu:.1f} >= {_PRIVATE_ABSOLUTE_MINUTES_WARN:.0f} "
            "(private-repo burn proxy)"
        )

    return (bool(reasons), reasons)


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _int_or_none(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return None


def _parse_billing_body(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize GitHub Actions billing JSON across org/repo endpoint variants."""
    minutes_used: float | None = None
    for _mk in ("total_minutes_used", "minutes_used", "total_usage_minutes"):
        mv = _num(data.get(_mk))
        if mv is not None:
            minutes_used = mv
            break
    included_i = _int_or_none(data.get("included_minutes"))
    paid: float | None = None
    for _k in ("total_paid_minutes_used", "paid_minutes_used"):
        pn = _num(data.get(_k))
        if pn is not None:
            paid = pn
            break

    raw_break = data.get("minutes_used_breakdown")
    paid_break = data.get("total_paid_minutes_used_breakdown")

    mub: dict[str, Any] | None
    if isinstance(raw_break, dict):
        mub = raw_break
    elif raw_break is None:
        mub = None
    else:
        mub = {"_raw": raw_break}

    pub: dict[str, Any] | None
    if isinstance(paid_break, dict):
        pub = paid_break
    elif paid_break is None:
        pub = None
    else:
        pub = {"_raw": paid_break}

    limit_n = _num(data.get("minutes_limit"))
    minutes_limit: float | None
    if limit_n is not None:
        minutes_limit = limit_n
    elif included_i is not None:
        minutes_limit = float(included_i)
    else:
        minutes_limit = None

    return {
        "minutes_used": minutes_used,
        "minutes_limit": minutes_limit,
        "included_minutes": included_i,
        "paid_minutes_used": paid,
        "total_paid_minutes_used_breakdown": pub,
        "minutes_used_breakdown": mub,
    }


async def _http_json(
    client: httpx.AsyncClient,
    path: str,
    *,
    label: str,
    extra: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        r = await client.get(path, headers=_gh_headers())
        if r.status_code != 200:
            extra[label] = {"status": r.status_code, "snippet": (r.text or "")[:400]}
            return None
        parsed: Any = r.json()
        return parsed if isinstance(parsed, dict) else None
    except Exception as e:
        extra[label] = {"error": str(e)[:500]}
        return None


async def collect_github_actions_quota_payload(
    *,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Gather repo metadata, billing (best effort), and Actions cache usage."""
    owner, repo = _repo_parts()
    extra: dict[str, Any] = {}

    close_client = False
    if http_client is None:
        http_client = httpx.AsyncClient(base_url=GH_API, timeout=httpx.Timeout(120.0))
        close_client = True

    billing_parsed: dict[str, Any] | None = None
    billing_source = ""

    try:
        repo_meta = await _http_json(
            http_client, f"/repos/{owner}/{repo}", label="repo_fetch", extra=extra
        )
        is_public = True
        visibility = "unknown"
        if repo_meta:
            is_public = not bool(repo_meta.get("private"))
            vis = repo_meta.get("visibility")
            visibility = str(vis) if isinstance(vis, str) else str(repo_meta.get("visibility"))
        else:
            extra["repo_visibility_unknown"] = True

        paths_billing: list[tuple[str, str]] = [
            ("repo_actions_billing_usage", f"/repos/{owner}/{repo}/actions/billing/usage"),
            ("repo_settings_billing_actions", f"/repos/{owner}/{repo}/settings/billing/actions"),
            ("org_settings_billing_actions", f"/orgs/{owner}/settings/billing/actions"),
        ]
        for label, path in paths_billing:
            data = await _http_json(http_client, path, label=label, extra=extra)
            if data:
                billing_parsed = data
                billing_source = label
                break

        cache_raw = await _http_json(
            http_client,
            f"/repos/{owner}/{repo}/actions/cache/usage",
            label="actions_cache_usage",
            extra=extra,
        )
        cache_bytes: int | None = None
        cache_count: int | None = None
        if cache_raw:
            acb = cache_raw.get("active_caches_size_in_bytes")
            acc = cache_raw.get("active_caches_count")
            if isinstance(acb, int):
                cache_bytes = acb
            if isinstance(acc, int):
                cache_count = acc

        extras: dict[str, Any] = dict(extra)
        extras["billing_source"] = billing_source
        extras["visibility"] = visibility

        base: dict[str, Any] = {
            "repo": f"{owner}/{repo}",
            "is_public": is_public,
            "cache_size_bytes": cache_bytes,
            "cache_count": cache_count,
            "extra_json": extras,
        }

        if billing_parsed:
            base.update(_parse_billing_body(billing_parsed))

        return base
    finally:
        if close_client:
            await http_client.aclose()


async def persist_github_actions_quota_snapshot(payload: dict[str, Any]) -> None:
    row = GitHubActionsQuotaSnapshot(
        repo=str(payload["repo"]),
        is_public=bool(payload["is_public"]),
        minutes_used=_num(payload.get("minutes_used")),
        minutes_limit=_num(payload.get("minutes_limit")),
        included_minutes=_int_or_none(payload.get("included_minutes")),
        paid_minutes_used=_num(payload.get("paid_minutes_used")),
        total_paid_minutes_used_breakdown=payload.get("total_paid_minutes_used_breakdown"),
        minutes_used_breakdown=payload.get("minutes_used_breakdown"),
        cache_size_bytes=(
            int(payload["cache_size_bytes"])
            if isinstance(payload.get("cache_size_bytes"), int)
            else None
        ),
        cache_count=(
            int(payload["cache_count"]) if isinstance(payload.get("cache_count"), int) else None
        ),
        extra_json=payload.get("extra_json") if isinstance(payload.get("extra_json"), dict) else {},
    )
    async with async_session_factory() as session:
        session.add(row)
        await session.commit()


async def latest_github_actions_quota_snapshots(
    session: AsyncSession, *, limit: int = 30
) -> list[GitHubActionsQuotaSnapshot]:
    lim = max(1, min(limit, 500))
    stmt = (
        select(GitHubActionsQuotaSnapshot)
        .order_by(GitHubActionsQuotaSnapshot.recorded_at.desc())
        .limit(lim)
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def run_github_actions_quota_monitor_tick(
    *,
    http_client: httpx.AsyncClient | None = None,
) -> None:
    tok = _token()
    if not tok:
        logger.info("github_actions_quota_monitor: GITHUB_TOKEN not set, skipping")
        return

    payload = await collect_github_actions_quota_payload(http_client=http_client)
    recorded = datetime.now(UTC).isoformat()

    warn, reasons = github_actions_quota_alarm_decision(
        is_public=bool(payload["is_public"]),
        minutes_used=_num(payload.get("minutes_used")),
        included_minutes=_int_or_none(payload.get("included_minutes")),
        paid_minutes_used=_num(payload.get("paid_minutes_used")),
    )
    if warn:
        logger.warning(
            "github_actions_quota_threshold %s",
            json.dumps(
                {
                    "recorded_at_hint": recorded,
                    "repo": payload.get("repo"),
                    "is_public": payload.get("is_public"),
                    "reasons": reasons,
                    "minutes_used": payload.get("minutes_used"),
                    "included_minutes": payload.get("included_minutes"),
                    "paid_minutes_used": payload.get("paid_minutes_used"),
                },
                default=str,
            ),
        )
    else:
        logger.info(
            "github_actions_quota_snapshot recorded_at=%s repo=%s public=%s mu=%s inc=%s paid=%s",
            recorded,
            payload.get("repo"),
            payload.get("is_public"),
            payload.get("minutes_used"),
            payload.get("included_minutes"),
            payload.get("paid_minutes_used"),
        )

    await persist_github_actions_quota_snapshot(payload)
