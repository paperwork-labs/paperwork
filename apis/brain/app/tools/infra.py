"""Infra health tools — Render, Vercel, Neon, Upstash (FastMCP-ready)."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 10.0


def _fmt_ts(raw: str | None) -> str:
    if not raw:
        return "unknown"
    try:
        normalized = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(normalized)
        dt = dt.astimezone(UTC) if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return raw[:32] + ("…" if len(raw) > 32 else "")


def _normalize_render_services(body: dict[str, Any]) -> list[dict[str, Any]]:
    raw = body.get("services")
    if raw is None:
        raw = body.get("service") or []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        inner = item.get("service")
        if isinstance(inner, dict):
            out.append(inner)
        else:
            out.append(item)
    return out


async def _render_list_all_services(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> tuple[list[dict[str, Any]], str | None]:
    collected: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(20):
        params: dict[str, str] = {}
        if cursor:
            params["cursor"] = cursor
        r = await client.get(
            "https://api.render.com/v1/services",
            headers=headers,
            params=params or None,
        )
        if r.status_code != 200:
            logger.warning(
                "Render list services failed: HTTP %s %s",
                r.status_code,
                (r.text or "")[:200],
            )
            err = f"list services HTTP {r.status_code}: {(r.text or '')[:300]}"
            return (collected if collected else [], err if not collected else None)
        body = r.json()
        collected.extend(_normalize_render_services(body))
        cursor = body.get("cursor")
        if not cursor:
            break
    return collected, None


def _first_deploy_dict(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    inner = entry.get("deploy")
    if isinstance(inner, dict):
        return inner
    return entry


async def _render_latest_deploy_label(
    client: httpx.AsyncClient, headers: dict[str, str], service_id: str
) -> str:
    try:
        r = await client.get(
            f"https://api.render.com/v1/services/{service_id}/deploys",
            headers=headers,
            params={"limit": "1"},
        )
        if r.status_code != 200:
            return f"deploys unavailable (HTTP {r.status_code})"
        body = r.json()
        deploys = body.get("deploys") or body.get("deploy") or []
        if not isinstance(deploys, list) or not deploys:
            return "no deploys yet"
        d = _first_deploy_dict(deploys[0])
        if not d:
            return "unknown"
        ts = d.get("finishedAt") or d.get("updatedAt") or d.get("createdAt")
        status = d.get("status") or d.get("deployStatus") or ""
        when = _fmt_ts(ts) if ts else "unknown time"
        tail = f", status={status}" if status else ""
        return f"{when}{tail}"
    except Exception as e:
        logger.debug("Render deploy fetch for %s: %s", service_id, e)
        return "deploy fetch failed"


async def check_render_status() -> str:
    """Check health of all Render services."""
    token = (settings.RENDER_API_KEY or "").strip()
    if not token:
        return "Render: not configured (set RENDER_API_KEY)."

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            services, list_err = await _render_list_all_services(client, headers)
            if list_err and not services:
                return f"Render: {list_err}"
            if not services:
                return "Render: no services returned (empty account)."

            sem = asyncio.Semaphore(8)

            async def line_for(svc: dict[str, Any]) -> str:
                sid = str(svc.get("id") or "").strip()
                name = str(svc.get("name") or sid or "unnamed")
                suspended = svc.get("suspended")
                state = "suspended" if suspended else "live"
                if sid:
                    async with sem:
                        deploy = await _render_latest_deploy_label(client, headers, sid)
                else:
                    deploy = "no service id"
                return f"- {name}: {state}; last deploy: {deploy}"

            lines = await asyncio.gather(*[line_for(s) for s in services])
        return "Render services:\n" + "\n".join(lines)
    except Exception as e:
        logger.warning("check_render_status failed: %s", e)
        return f"Render check failed: {e}"


async def check_vercel_status() -> str:
    """Check recent Vercel deployments."""
    token = (settings.VERCEL_API_TOKEN or "").strip()
    if not token:
        return "Vercel: not configured (set VERCEL_API_TOKEN)."

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            r = await client.get(
                "https://api.vercel.com/v6/deployments",
                headers=headers,
                params={"limit": "3"},
            )
            if r.status_code != 200:
                return f"Vercel: HTTP {r.status_code} — {(r.text or '')[:400]}"

            body = r.json()
            deployments = body.get("deployments") or []
            if not isinstance(deployments, list) or not deployments:
                return "Vercel: no recent deployments in response."

            lines: list[str] = []
            for d in deployments[:3]:
                if not isinstance(d, dict):
                    continue
                state = d.get("readyState") or d.get("state") or "unknown"
                url = d.get("url") or d.get("alias") or ""
                if url and not str(url).startswith("http"):
                    url = f"https://{url}"
                created = d.get("createdAt") or d.get("created") or d.get("buildingAt")
                created_s = _fmt_ts(str(created)) if created else "unknown"
                lines.append(f"- state={state}; url={url or 'n/a'}; created={created_s}")
            return "Vercel (last 3 deployments):\n" + "\n".join(lines)
    except Exception as e:
        logger.warning("check_vercel_status failed: %s", e)
        return f"Vercel check failed: {e}"


def _normalize_neon_branches(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("branches") or []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict) and isinstance(item.get("branch"), dict):
            out.append(item["branch"])
        elif isinstance(item, dict):
            out.append(item)
    return out


async def check_neon_status() -> str:
    """Check Neon database projects and branch summary."""
    key = (settings.NEON_API_KEY or "").strip()
    if not key:
        return "Neon: not configured (set NEON_API_KEY)."

    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            r = await client.get(
                "https://console.neon.tech/api/v2/projects",
                headers=headers,
            )
            if r.status_code != 200:
                return f"Neon: HTTP {r.status_code} — {(r.text or '')[:400]}"

            body = r.json()
            projects = body.get("projects") or []
            if not isinstance(projects, list) or not projects:
                return "Neon: no projects returned."

            lines: list[str] = []
            for p in projects[:8]:
                if not isinstance(p, dict):
                    continue
                pid = str(p.get("id") or "")
                pname = str(p.get("name") or pid or "unnamed")
                region = p.get("region_id") or p.get("region") or ""
                prov = p.get("pg_version") or p.get("provisioner") or ""
                meta: list[str] = []
                if region:
                    meta.append(f"region={region}")
                if prov:
                    meta.append(f"pg={prov}")
                meta_bits = ", ".join(meta)
                header = f"- {pname} ({pid})" + (f" — {meta_bits}" if meta_bits else "")

                if not pid:
                    lines.append(f"{header}\n  branches: (no project id)")
                    continue

                br = await client.get(
                    f"https://console.neon.tech/api/v2/projects/{pid}/branches",
                    headers=headers,
                )
                if br.status_code != 200:
                    lines.append(f"{header}\n  branches: HTTP {br.status_code}")
                    continue

                branches = _normalize_neon_branches(br.json())
                default_names = [
                    str(b.get("name") or "")
                    for b in branches
                    if isinstance(b, dict) and b.get("default") is True
                ]
                default_label = default_names[0] if default_names else "n/a"
                preview = []
                for b in branches[:3]:
                    if not isinstance(b, dict):
                        continue
                    nm = b.get("name") or "?"
                    st = b.get("current_state") or b.get("state") or "?"
                    preview.append(f"{nm}:{st}")
                preview_s = ", ".join(preview) if preview else "n/a"
                lines.append(
                    f"{header}\n  branches: {len(branches)} total, default={default_label}; "
                    f"sample=[{preview_s}]"
                )

            return "Neon projects:\n" + "\n".join(lines)
    except Exception as e:
        logger.warning("check_neon_status failed: %s", e)
        return f"Neon check failed: {e}"


def _summarize_redis_info(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    memory_h = next((ln for ln in lines if ln.startswith("used_memory_human:")), "")
    memory = next(
        (ln for ln in lines if ln.startswith("used_memory:") and "human" not in ln),
        "",
    )
    clients = next((ln for ln in lines if ln.startswith("connected_clients:")), "")
    keyspace = [ln for ln in lines if re.match(r"^db\d+:", ln)]
    parts: list[str] = []
    if memory_h:
        parts.append(memory_h.replace("used_memory_human:", "memory").strip())
    elif memory:
        parts.append(memory.replace("used_memory:", "memory_bytes").strip())
    if clients:
        parts.append(clients.replace("connected_clients:", "clients").strip())
    if keyspace:
        parts.append("keyspace: " + "; ".join(keyspace[:4]))
    return "; ".join(parts) if parts else text[:500]


async def check_upstash_status() -> str:
    """Check Upstash Redis via REST INFO."""
    base = (settings.UPSTASH_REDIS_REST_URL or "").strip().rstrip("/")
    token = (settings.UPSTASH_REDIS_REST_TOKEN or "").strip()
    if not base or not token:
        return "Upstash: not configured (set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN)."

    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            r = await client.get(f"{base}/info", headers=headers)
            if r.status_code != 200:
                return f"Upstash: HTTP {r.status_code} — {(r.text or '')[:300]}"
            summary = _summarize_redis_info(r.text)
            return f"Upstash Redis: {summary}"
    except Exception as e:
        logger.warning("check_upstash_status failed: %s", e)
        return f"Upstash check failed: {e}"
