"""Wave PROBE — Brain API endpoints for UX probe results.

GET /v1/probes/results?product=<slug>&since=<iso>
    Returns the last N result rows for a product (or all products).

GET /v1/probes/health
    Returns the latest pass/fail snapshot per product — for Studio dashboard.

Both endpoints read from apis/brain/data/probe_results.json (the same file
the ux_probe_runner scheduler writes to).

No-silent-fallback: if the file is missing or unreadable, return a clear
error payload rather than an empty-list that looks like "no probes run yet".
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.schemas.base import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/probes", tags=["probes"])

_REPO_ROOT = Path(__file__).resolve().parents[5]  # apis/brain/app/api/routes → repo root
_PROBE_RESULTS_JSON = (
    Path(os.environ.get("BRAIN_PROBE_RESULTS_JSON", ""))
    if os.environ.get("BRAIN_PROBE_RESULTS_JSON")
    else _REPO_ROOT / "apis" / "brain" / "data" / "probe_results.json"
)

_DEFAULT_LIMIT = 50


def _load_results() -> list[dict[str, Any]]:
    """Load raw result rows. Raises OSError / JSONDecodeError on file problems."""
    if not _PROBE_RESULTS_JSON.exists():
        return []
    payload = json.loads(_PROBE_RESULTS_JSON.read_text(encoding="utf-8"))
    return payload.get("results", [])


@router.get("/results")
async def get_probe_results(
    product: str | None = Query(None, description="Filter by product slug"),
    since: str | None = Query(None, description="ISO-8601 timestamp lower bound"),
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=1000),
) -> JSONResponse:
    """Return the last *limit* probe result rows, optionally filtered."""
    try:
        rows = _load_results()
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("probe_results: failed to read results file: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": f"probe_results.json unreadable: {exc}",
                "detail": (
                    "This is an infrastructure error, not an empty result set. "
                    "Check that ux_probe_runner has run at least once."
                ),
            },
        )

    if product:
        rows = [r for r in rows if r.get("product") == product]

    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            rows = [
                r
                for r in rows
                if datetime.fromisoformat(
                    (r.get("started_at") or "1970-01-01T00:00:00+00:00").replace("Z", "+00:00")
                )
                >= since_dt
            ]
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"Invalid 'since' timestamp: {exc}"},
            )

    tail = rows[-limit:]
    return success_response(
        {
            "results": tail,
            "count": len(tail),
            "product_filter": product,
            "since_filter": since,
            "fetched_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
    )


@router.get("/health")
async def get_probe_health() -> JSONResponse:
    """Return the latest pass/fail status per product (Studio dashboard snapshot)."""
    try:
        rows = _load_results()
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("probe_health: failed to read results file: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": f"probe_results.json unreadable: {exc}",
                "detail": (
                    "Infrastructure error reading probe results. "
                    "Check that ux_probe_runner has run at least once."
                ),
            },
        )

    # Build latest-per-product map (rows are in append order, so iterate reversed)
    latest: dict[str, dict[str, Any]] = {}
    for row in reversed(rows):
        p = row.get("product")
        if p and p not in latest:
            latest[p] = row

    if not latest:
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "health": {},
                    "note": (
                        "No probe results found. ux_probe_runner has not run yet "
                        "or probe_results.json is empty."
                    ),
                    "fetched_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                },
            },
        )

    health = {
        product: {
            "status": row.get("status"),
            "last_run": row.get("started_at"),
            "base_url": row.get("base_url"),
            "exit_code": row.get("exit_code"),
            "failing_tests": row.get("failing_tests", []),
            "error_message": row.get("error_message"),
        }
        for product, row in latest.items()
    }

    overall = "pass" if all(v["status"] == "pass" for v in health.values()) else "degraded"

    return success_response(
        {
            "overall": overall,
            "health": health,
            "fetched_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
    )
