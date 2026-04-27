"""Format Slack slash command replies from ``tracker-index.json`` (Studio).

medallion: ops
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings

TRACKER_UNAVAILABLE_MSG = (
    "Tracker index unavailable. Run `python3 scripts/generate_tracker_index.py`."
)
_GITHUB_REF = "main"


def _repo_root() -> Path:
    # apis/brain/app/services/this_file.py → parents[4] = monorepo root
    # parents[0]=services, [1]=app, [2]=brain, [3]=apis, [4]=repo
    return Path(__file__).resolve().parents[4]


def default_tracker_index_path() -> Path:
    return _repo_root() / "apps" / "studio" / "src" / "data" / "tracker-index.json"


def load_tracker_index(path: Path | None = None) -> dict[str, Any] | None:
    p = path or default_tracker_index_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _github_blob_url(rel_path: str) -> str:
    repo = (settings.GITHUB_REPO or "paperwork-labs/paperwork").strip()
    clean = rel_path.lstrip("/")
    return f"https://github.com/{repo}/blob/{_GITHUB_REF}/{clean}"


def _is_critical_date_open(status: str | None) -> bool:
    if not status:
        return True
    s = status.strip().upper()
    return not (s == "COMPLETE" or s.startswith("DONE"))


def _critical_status_emoji(status: str | None) -> str:
    s = (status or "").strip().upper()
    if s.startswith("DONE") or s == "COMPLETE":
        return "🟢"
    if "PROGRESS" in s:
        return "🟡"
    return "🔴"


def _is_sprint_active(status: str | None) -> bool:
    if not status:
        return True
    return status.strip().lower() not in {"shipped", "complete", "done"}


def slack_response_sprint(index: dict[str, Any] | None, text: str) -> dict[str, Any]:
    if index is None:
        return {"response_type": "ephemeral", "text": TRACKER_UNAVAILABLE_MSG}

    sub = text.strip().lower()
    if sub not in ("", "shipped"):
        return {
            "response_type": "ephemeral",
            "text": "Usage: `/sprint` (active sprints) or `/sprint shipped` (last 5 shipped).",
        }

    raw = index.get("sprints") or []
    sprints = raw if isinstance(raw, list) else []

    if sub == "shipped":
        shipped = [
            sp
            for sp in sprints
            if isinstance(sp, dict) and str(sp.get("status") or "").strip().lower() == "shipped"
        ]
        shipped.sort(key=lambda sp: str(sp.get("end") or ""), reverse=True)
        picked = shipped[:5]
        if not picked:
            body = "_No shipped sprints in the tracker index._"
        else:
            lines = []
            for sp in picked:
                title = sp.get("title") or sp.get("slug") or "(untitled)"
                pr_url = (sp.get("pr_url") or "").strip()
                pr_num = sp.get("pr")
                if pr_url and pr_num is not None:
                    lines.append(f"• *{title}* — <{pr_url}|PR #{pr_num}>")
                elif pr_url:
                    lines.append(f"• *{title}* — <{pr_url}|PR>")
                else:
                    lines.append(f"• *{title}*")
            body = "*Last shipped sprints*\n" + "\n".join(lines)
        return {"response_type": "in_channel", "text": body}

    active = [sp for sp in sprints if isinstance(sp, dict) and _is_sprint_active(sp.get("status"))]
    if not active:
        body = "_No active sprints in the tracker index._"
    else:
        lines = []
        for sp in active:
            title = sp.get("title") or sp.get("slug") or "(untitled)"
            st = sp.get("status") or "—"
            start = sp.get("start") or "—"
            end = sp.get("end") or "—"
            lines.append(f"• *{title}* — {st} — {start} → {end}")
        body = "*Active sprints*\n" + "\n".join(lines)
    return {"response_type": "in_channel", "text": body}


def slack_response_tasks(index: dict[str, Any] | None, text: str) -> dict[str, Any]:
    if index is None:
        return {"response_type": "ephemeral", "text": TRACKER_UNAVAILABLE_MSG}

    sub = text.strip().lower()
    show_all = sub == "all"

    company = index.get("company")
    if not isinstance(company, dict):
        return {"response_type": "in_channel", "text": "_No `company` section in tracker index._"}

    raw_dates = company.get("critical_dates") or []
    dates = raw_dates if isinstance(raw_dates, list) else []
    rows: list[dict[str, Any]] = [d for d in dates if isinstance(d, dict)]
    if not show_all:
        rows = [d for d in rows if _is_critical_date_open(d.get("status"))]

    if not rows:
        body = "_No matching critical dates._" if not show_all else "_No critical dates in index._"
        return {"response_type": "in_channel", "text": body}

    lines = []
    for d in rows:
        milestone = d.get("milestone") or "(milestone)"
        deadline = d.get("deadline") or "—"
        st = d.get("status") or "—"
        emoji = _critical_status_emoji(d.get("status"))
        lines.append(f"{emoji} {milestone} — {deadline} — {st}")
    header = "*Critical dates (open)*\n" if not show_all else "*Critical dates (all)*\n"
    return {"response_type": "in_channel", "text": header + "\n".join(lines)}


def slack_response_plan(index: dict[str, Any] | None, text: str) -> dict[str, Any]:
    if index is None:
        return {"response_type": "ephemeral", "text": TRACKER_UNAVAILABLE_MSG}

    raw_products = index.get("products") or []
    products = raw_products if isinstance(raw_products, list) else []
    product_dicts = [p for p in products if isinstance(p, dict)]

    sub = text.strip()
    if not sub:
        if not product_dicts:
            return {"response_type": "in_channel", "text": "_No products in tracker index._"}
        lines = []
        for p in product_dicts:
            slug = p.get("slug") or "(unknown)"
            label = p.get("label") or slug
            plans = p.get("plans") or []
            n = len(plans) if isinstance(plans, list) else 0
            lines.append(f"• *{label}* (`{slug}`): {n} plan(s)")
        return {
            "response_type": "in_channel",
            "text": "*Products (plan counts)*\n" + "\n".join(lines),
        }

    want = sub.lower()
    for p in product_dicts:
        if str(p.get("slug") or "").lower() != want:
            continue
        label = p.get("label") or want
        plans_raw = p.get("plans") or []
        plans = plans_raw if isinstance(plans_raw, list) else []
        if not plans:
            return {
                "response_type": "in_channel",
                "text": f"_{label}: no plans in the index._",
            }
        lines = []
        for pl in plans:
            if not isinstance(pl, dict):
                continue
            title = pl.get("title") or pl.get("slug") or "(untitled)"
            st = pl.get("status") or "—"
            path = (pl.get("path") or "").strip()
            if path:
                url = _github_blob_url(path)
                lines.append(f"• <{url}|{title}> [{st}]")
            else:
                lines.append(f"• *{title}* [{st}]")
        return {"response_type": "in_channel", "text": f"*{label} plans*\n" + "\n".join(lines)}

    known = ", ".join(
        sorted(str(p.get("slug")) for p in product_dicts if p.get("slug")),
    )
    return {
        "response_type": "ephemeral",
        "text": f"Unknown product `{sub}`. Known: {known or '(none)'}",
    }
