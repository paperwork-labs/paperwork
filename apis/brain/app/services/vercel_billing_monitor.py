"""Vercel on-demand budget monitor — alerts BEFORE the cap is hit.

Why this exists
---------------
We discovered the on-demand budget at 91% ($36.58 / $40) with zero
warning. The existing ``vercel_quota_monitor`` watches *deployment count*
and *build minutes* against included caps; it is silent about the *dollar*
spend on metered resources. This service closes that gap.

Operation
---------
Hourly cron polls the Vercel billing endpoint, persists a snapshot to
``apis/brain/data/vercel_billing.json``, and returns threshold-crossing
records from :func:`evaluate_alerts`. The APScheduler job in
``app.schedulers.vercel_billing_monitor`` turns each alert into a Brain
Conversation (tags ``vercel-budget``, ``paperwork-labs``, ``bill-pending``).
Each threshold fires at most once per billing cycle (dedup via the
``alerts_fired`` field).

medallion: ops
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Constants
_VERCEL_API = "https://api.vercel.com"
_TEAM_ID = "team_RwfzJ9ySyLuVcoWdKJfXC7h5"

# Alert thresholds (fraction of on-demand budget). Order matters — lowest first.
_ALERT_THRESHOLDS = (0.5, 0.75, 0.9, 1.0)

# Severity per threshold
_SEVERITY = {0.5: "info", 0.75: "warning", 0.9: "critical", 1.0: "critical"}


def _data_path() -> Path:
    override = os.environ.get("BRAIN_VERCEL_BILLING_JSON", "").strip()
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    # services/ -> app/ -> brain/ ; data lives at brain/data
    return here.parent.parent.parent / "data" / "vercel_billing.json"


def _vercel_token() -> str | None:
    for key in ("VERCEL_TOKEN", "VERCEL_API_TOKEN"):
        v = os.environ.get(key, "").strip()
        if v:
            return v
    return None


def _budget_threshold_usd() -> float:
    # Default $40 when unset. Set ``VERCEL_ONDEMAND_BUDGET_USD=0`` to mirror a
    # Vercel team on-demand hard cap of $0: ``evaluate_alerts`` then uses
    # any-spend mode (alert on any spend > $0 for the period).
    raw = os.environ.get("VERCEL_ONDEMAND_BUDGET_USD", "40").strip()
    try:
        return float(raw)
    except ValueError:
        return 40.0


def _fetch_team_metadata(token: str) -> dict[str, Any]:
    """Returns billing metadata. Real schema: ``data.billing.spend.amountUsd``,
    ``data.spendManagement.budgetUsd``. Falls back gracefully if Vercel
    changes shape — caller checks for required fields."""
    url = f"{_VERCEL_API}/v1/teams/{_TEAM_ID}?slug=paperwork-labs"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data: dict[str, Any] = json.load(resp)
        return data


def _fetch_usage_summary(token: str) -> dict[str, Any]:
    """Returns ``{spent_usd, budget_usd, period_start, period_end}``.

    Vercel's stable on-demand spend endpoint is ``/v1/teams/{teamId}/usage-events``;
    the public ``/v1/usage`` endpoint requires a precise date range that Vercel
    rejects with arbitrary precision. Until we have a stable contract here we
    fall back to scraping the on-demand budget from team metadata. Document
    every field we read so a Vercel API change is easy to spot.
    """
    meta = _fetch_team_metadata(token)
    billing = meta.get("billing", {}) or {}
    spend = billing.get("spend", {}) or {}
    spend_management = billing.get("spendManagement", {}) or {}

    # Vercel returns spend in cents on some endpoints, dollars on others.
    spent_cents = spend.get("amountCents")
    spent_usd_raw = spend.get("amountUsd")
    if isinstance(spent_cents, (int, float)):
        spent_usd: float | None = float(spent_cents) / 100.0
    elif isinstance(spent_usd_raw, (int, float)):
        spent_usd = float(spent_usd_raw)
    else:
        spent_usd = None

    budget_usd_raw = spend_management.get("budgetUsd")
    budget_usd = (
        float(budget_usd_raw)
        if isinstance(budget_usd_raw, (int, float))
        else _budget_threshold_usd()
    )

    return {
        "spent_usd": spent_usd,
        "budget_usd": budget_usd,
        "period_start": billing.get("currentPeriodStart"),
        "period_end": billing.get("currentPeriodEnd"),
    }


def _load_state() -> dict[str, Any]:
    p = _data_path()
    if not p.exists():
        return {"alerts_fired": {}, "history": []}
    try:
        loaded: dict[str, Any] = json.loads(p.read_text())
        return loaded
    except json.JSONDecodeError:
        logger.warning("vercel_billing.json corrupt; starting fresh")
        return {"alerts_fired": {}, "history": []}


def _save_state(state: dict[str, Any]) -> None:
    p = _data_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    os.replace(tmp, p)


def _period_key(period_end: str | None) -> str:
    if not period_end:
        return datetime.now(UTC).strftime("%Y-%m")
    try:
        # Accepts ISO timestamps or millisecond epoch.
        if isinstance(period_end, (int, float)):
            return datetime.fromtimestamp(period_end / 1000, UTC).strftime("%Y-%m")
        return datetime.fromisoformat(period_end.replace("Z", "+00:00")).strftime("%Y-%m")
    except (TypeError, ValueError):
        return datetime.now(UTC).strftime("%Y-%m")


def evaluate_alerts(
    spent_usd: float,
    budget_usd: float,
    fired: dict[str, list[float | str]],
    period_key: str,
) -> list[dict[str, Any]]:
    """Pure helper for tests: returns new alerts to fire. Mutates `fired`."""
    new_alerts: list[dict[str, Any]] = []
    if budget_usd <= 0:
        if spent_usd <= 0:
            return new_alerts
        period_fired = set(fired.get(period_key, []))
        if "any_spend" in period_fired:
            return new_alerts
        new_alerts.append(
            {
                "level": "any_spend",
                "severity": "high",
                "spent_usd": round(spent_usd, 2),
                "budget_usd": 0.0,
                "pct": None,
                "message": "Vercel on-demand spend > $0 against $0 cap",
            }
        )
        period_fired.add("any_spend")
        fired[period_key] = ["any_spend"]
        return new_alerts

    pct = spent_usd / budget_usd
    period_fired = set(fired.get(period_key, []))
    for threshold in _ALERT_THRESHOLDS:
        if pct >= threshold and threshold not in period_fired:
            new_alerts.append(
                {
                    "threshold": threshold,
                    "severity": _SEVERITY[threshold],
                    "spent_usd": round(spent_usd, 2),
                    "budget_usd": round(budget_usd, 2),
                    "pct": round(pct * 100, 1),
                }
            )
            period_fired.add(threshold)
    if period_fired:
        fired[period_key] = sorted(period_fired)
    return new_alerts


def run() -> dict[str, Any]:
    """Single poll. Returns ``{ok, spent_usd, budget_usd, pct, alerts}``.

    On token absence, returns ``{ok: False, reason: "no_token"}`` and
    does NOT raise — Brain workers should not crash on missing config.
    """
    token = _vercel_token()
    if not token:
        return {"ok": False, "reason": "no_token"}

    try:
        usage = _fetch_usage_summary(token)
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as e:
        logger.exception("vercel_billing_monitor: fetch failed")
        return {"ok": False, "reason": "fetch_error", "error": str(e)}

    spent_raw = usage.get("spent_usd")
    budget_raw = usage.get("budget_usd")

    if spent_raw is None:
        logger.warning("vercel_billing_monitor: spent_usd absent from billing response")
        return {"ok": False, "reason": "no_spend_field"}

    spent: float = float(spent_raw)
    budget: float = float(budget_raw) if budget_raw is not None else _budget_threshold_usd()

    state = _load_state()
    period_key = _period_key(usage.get("period_end"))
    alerts = evaluate_alerts(spent, budget, state.setdefault("alerts_fired", {}), period_key)

    snapshot = {
        "computed_at": datetime.now(UTC).isoformat(),
        "spent_usd": round(spent, 2),
        "budget_usd": round(budget, 2),
        "pct": round((spent / budget) * 100, 1) if budget > 0 else 0.0,
        "period_key": period_key,
        "new_alerts_count": len(alerts),
    }
    history = state.setdefault("history", [])
    history.append(snapshot)
    state["history"] = history[-200:]  # keep last ~200 polls

    _save_state(state)

    return {
        "ok": True,
        "spent_usd": snapshot["spent_usd"],
        "budget_usd": snapshot["budget_usd"],
        "pct": snapshot["pct"],
        "alerts": alerts,
        "period_key": period_key,
    }
