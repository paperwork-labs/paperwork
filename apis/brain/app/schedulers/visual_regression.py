"""Wave PROBE PR-PB2 — Visual regression diffs for critical pages.

Captures daily screenshots of critical product pages and compares against
baseline images using simple pixel diff. Results stored in
``apis/brain/data/visual_regression/``.

medallion: ops
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._history import run_with_scheduler_record
from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.services.workstreams_loader import _repo_root

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "brain_visual_regression_daily"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_REPO_ROOT = _repo_root()
_DATA_DIR = (
    Path(os.environ.get("BRAIN_VISUAL_REGRESSION_DIR", ""))
    if os.environ.get("BRAIN_VISUAL_REGRESSION_DIR")
    else _REPO_ROOT / "apis" / "brain" / "data" / "visual_regression"
)
_RESULTS_JSON = _DATA_DIR / "results.json"
_BASELINES_DIR = _DATA_DIR / "baselines"
_SNAPSHOTS_DIR = _DATA_DIR / "snapshots"
_DIFFS_DIR = _DATA_DIR / "diffs"

DIFF_THRESHOLD_PERCENT = float(os.environ.get("VISUAL_DIFF_THRESHOLD_PERCENT", "0.5"))
RESULTS_LIMIT = int(os.environ.get("VISUAL_REGRESSION_RESULTS_LIMIT", "100"))

CRITICAL_PAGES: dict[str, list[str]] = {
    "filefree": ["/", "/sign-in", "/dashboard"],
    "axiomfolio": ["/", "/portfolios"],
    "launchfree": ["/", "/dashboard"],
    "distill": ["/", "/reports"],
    "studio": ["/", "/admin"],
}


# ---------------------------------------------------------------------------
# Screenshot capture (placeholder)
# ---------------------------------------------------------------------------


def capture_screenshot(url: str, output_path: Path) -> bool:
    """Capture a screenshot of the given URL.

    Placeholder implementation — returns False indicating no screenshot taken.
    Real implementation would use Playwright or similar.

    Returns True if screenshot was captured successfully, False otherwise.
    """
    logger.info("visual_regression: placeholder capture for %s -> %s", url, output_path)
    return False


# ---------------------------------------------------------------------------
# Pixel diff comparison (placeholder)
# ---------------------------------------------------------------------------


def compute_pixel_diff(baseline_path: Path, snapshot_path: Path, diff_output_path: Path) -> float:
    """Compare two images and compute pixel difference percentage.

    Placeholder implementation — returns 0.0 (no diff).
    Real implementation would use PIL/Pillow or similar for pixel comparison.

    Returns percentage of pixels that differ (0.0 to 100.0).
    """
    logger.info(
        "visual_regression: placeholder diff %s vs %s -> %s",
        baseline_path,
        snapshot_path,
        diff_output_path,
    )
    return 0.0


def images_are_identical(path_a: Path, path_b: Path) -> bool:
    """Quick check if two image files are byte-identical."""
    if not path_a.exists() or not path_b.exists():
        return False
    return _file_hash(path_a) == _file_hash(path_b)


def _file_hash(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Result persistence
# ---------------------------------------------------------------------------


def _load_results() -> list[dict[str, Any]]:
    if not _RESULTS_JSON.exists():
        return []
    try:
        payload = json.loads(_RESULTS_JSON.read_text(encoding="utf-8"))
        results: list[dict[str, Any]] = payload.get("results", [])
        return results
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("visual_regression results.json unreadable (%s); starting fresh", exc)
        return []


def _save_results(results: list[dict[str, Any]]) -> None:
    """Persist results, pruning to the rolling window."""
    pruned = results[-RESULTS_LIMIT:]
    _RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "visual_regression/v1",
        "description": "Wave PROBE PR-PB2 visual regression results (rolling window)",
        "results": pruned,
    }
    _RESULTS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _append_result(row: dict[str, Any]) -> None:
    results = _load_results()
    results.append(row)
    _save_results(results)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _run_comparison(product: str, page_path: str, base_url: str) -> dict[str, Any]:
    """Run visual comparison for a single page.

    Returns a result row for the results JSON.
    """
    started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    page_slug = page_path.strip("/").replace("/", "_") or "home"
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    _BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    _SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    _DIFFS_DIR.mkdir(parents=True, exist_ok=True)

    baseline_path = _BASELINES_DIR / f"{product}_{page_slug}.png"
    snapshot_path = _SNAPSHOTS_DIR / f"{product}_{page_slug}_{timestamp}.png"
    diff_path = _DIFFS_DIR / f"{product}_{page_slug}_{timestamp}_diff.png"

    url = f"{base_url.rstrip('/')}{page_path}"

    captured = capture_screenshot(url, snapshot_path)
    if not captured:
        return {
            "product": product,
            "page": page_path,
            "url": url,
            "status": "skipped",
            "reason": "screenshot_capture_not_implemented",
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }

    if not baseline_path.exists():
        import shutil

        shutil.copy(snapshot_path, baseline_path)
        return {
            "product": product,
            "page": page_path,
            "url": url,
            "status": "baseline_created",
            "baseline_path": str(baseline_path),
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }

    if images_are_identical(baseline_path, snapshot_path):
        return {
            "product": product,
            "page": page_path,
            "url": url,
            "status": "pass",
            "diff_percent": 0.0,
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }

    diff_percent = compute_pixel_diff(baseline_path, snapshot_path, diff_path)
    status = "pass" if diff_percent <= DIFF_THRESHOLD_PERCENT else "regression"

    return {
        "product": product,
        "page": page_path,
        "url": url,
        "status": status,
        "diff_percent": diff_percent,
        "threshold_percent": DIFF_THRESHOLD_PERCENT,
        "baseline_path": str(baseline_path),
        "snapshot_path": str(snapshot_path),
        "diff_path": str(diff_path) if diff_percent > 0 else None,
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


def _load_production_urls() -> dict[str, str]:
    """Load product URLs from production-urls.json."""
    from app.schedulers.ux_probe_runner import _load_production_urls as load_urls

    return load_urls()


# ---------------------------------------------------------------------------
# Scheduler body
# ---------------------------------------------------------------------------


async def _run_visual_regression_body() -> None:
    """Execute visual regression checks for all critical pages."""
    try:
        prod_urls = _load_production_urls()
    except FileNotFoundError as exc:
        logger.error("visual_regression: cannot load production URLs: %s", exc)
        _append_result(
            {
                "product": "all",
                "status": "infrastructure_error",
                "error_message": str(exc),
                "started_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
        )
        return

    total = 0
    regressions = 0

    for product, pages in CRITICAL_PAGES.items():
        base_url = prod_urls.get(product)
        if not base_url:
            logger.warning("visual_regression: no URL for product=%s; skipping", product)
            _append_result(
                {
                    "product": product,
                    "status": "infrastructure_error",
                    "error_message": f"No entry for '{product}' in production-urls.json",
                    "started_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                }
            )
            continue

        for page_path in pages:
            row = _run_comparison(product, page_path, base_url)
            _append_result(row)
            total += 1
            if row.get("status") == "regression":
                regressions += 1
                logger.warning(
                    "visual_regression: REGRESSION %s%s diff=%.2f%%",
                    product,
                    page_path,
                    row.get("diff_percent", 0),
                )

    logger.info(
        "visual_regression: cycle complete total=%d regressions=%d",
        total,
        regressions,
    )


@skip_if_brain_paused(JOB_ID)
async def run_visual_regression_job() -> None:
    """Entry point for the APScheduler job."""
    await run_with_scheduler_record(
        JOB_ID,
        _run_visual_regression_body,
        metadata={"source": "visual_regression", "products": list(CRITICAL_PAGES.keys())},
        reraise=True,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the visual regression daily job (runs at 06:00 UTC)."""
    scheduler.add_job(
        run_visual_regression_job,
        trigger=CronTrigger(hour=6, minute=0, timezone="UTC"),
        id=JOB_ID,
        name="Visual Regression (Wave PROBE PR-PB2)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info(
        "APScheduler job %r registered (daily at 06:00 UTC, products=%s)",
        JOB_ID,
        list(CRITICAL_PAGES.keys()),
    )
