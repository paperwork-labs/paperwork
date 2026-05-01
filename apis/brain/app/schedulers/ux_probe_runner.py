"""Wave PROBE — Brain APScheduler job that drives synthetic UX probes.

Runs Playwright probes for every registered product every PROBE_INTERVAL_SECONDS
(default 300 / 5 min). Results are appended to
``apis/brain/data/probe_results.json`` (rolling 1000 entries).

No-silent-fallback contract
---------------------------
- If Playwright binary is missing    → status=infrastructure_error, not a skip
- If ``pnpm`` is not on PATH         → status=infrastructure_error, not a skip
- If subprocess times out             → status=timeout, not a skip
- Any unhandled exception            → status=infrastructure_error + traceback fragment

The Brain scheduler __init__.py registers install() like all other schedulers.
"""

from __future__ import annotations

import asyncio
import glob
import json
import logging
import os
import shutil
import subprocess
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from apscheduler.triggers.interval import IntervalTrigger

from app.schedulers._history import run_with_scheduler_record
from app.schedulers._kill_switch_guard import skip_if_brain_paused
from app.services.workstreams_loader import _repo_root

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "brain_ux_probe_runner"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Resolve monorepo root like other Brain modules (Docker flat /app vs dev tree).
# See app.services.workstreams_loader._repo_root for pattern.
_REPO_ROOT = _repo_root()
_PROBE_RESULTS_JSON = (
    Path(os.environ.get("BRAIN_PROBE_RESULTS_JSON", ""))
    if os.environ.get("BRAIN_PROBE_RESULTS_JSON")
    else _REPO_ROOT / "apis" / "brain" / "data" / "probe_results.json"
)
_PRODUCTION_URLS_JSON = (
    Path(os.environ.get("BRAIN_PROBE_PRODUCTION_URLS_JSON", ""))
    if os.environ.get("BRAIN_PROBE_PRODUCTION_URLS_JSON")
    else _REPO_ROOT / "apps" / "probes" / "config" / "production-urls.json"
)
_PROBE_RESULTS_LIMIT = int(os.environ.get("PROBE_RESULTS_LIMIT", "1000"))
_PROBE_TIMEOUT_SECONDS = int(os.environ.get("PROBE_TIMEOUT_SECONDS", "120"))
PROBE_INTERVAL_SECONDS = int(os.environ.get("PROBE_INTERVAL_SECONDS", "300"))

PRODUCTS = ["filefree", "axiomfolio", "launchfree", "distill", "studio"]


# ---------------------------------------------------------------------------
# URL config loading
# ---------------------------------------------------------------------------


def _load_production_urls() -> dict[str, str]:
    """Load product → URL map from config/production-urls.json.

    Raises FileNotFoundError explicitly — no silent fallback to empty dict,
    because an empty map would silently skip all probes.
    """
    if not _PRODUCTION_URLS_JSON.exists():
        raise FileNotFoundError(
            f"production-urls.json not found at {_PRODUCTION_URLS_JSON}. "
            "Set BRAIN_PROBE_PRODUCTION_URLS_JSON env to override path."
        )
    data = json.loads(_PRODUCTION_URLS_JSON.read_text(encoding="utf-8"))
    # Strip internal comment key
    return {k: v for k, v in data.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Result persistence
# ---------------------------------------------------------------------------


def _load_results() -> list[dict[str, Any]]:
    if not _PROBE_RESULTS_JSON.exists():
        return []
    try:
        payload = json.loads(_PROBE_RESULTS_JSON.read_text(encoding="utf-8"))
        return payload.get("results", [])
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("probe_results.json unreadable (%s); starting fresh", exc)
        return []


def _save_results(results: list[dict[str, Any]]) -> None:
    """Persist results, pruning to the rolling window."""
    pruned = results[-_PROBE_RESULTS_LIMIT:]
    _PROBE_RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "probe_results/v1",
        "description": "Wave PROBE synthetic UX probe results (rolling 1000 entries)",
        "results": pruned,
    }
    _PROBE_RESULTS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _append_result(row: dict[str, Any]) -> None:
    results = _load_results()
    results.append(row)
    _save_results(results)


# ---------------------------------------------------------------------------
# Playwright result parsing
# ---------------------------------------------------------------------------


def _parse_playwright_json(product: str) -> dict[str, Any] | None:
    """Return the latest Playwright JSON reporter output for *product*, or None."""
    results_dir = _REPO_ROOT / "apps" / "probes" / "results"
    pattern = str(results_dir / f"{product}-*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        return None
    try:
        return json.loads(Path(files[-1]).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not parse Playwright JSON for %s: %s", product, exc)
        return None


def _extract_failure_info(pw_json: dict[str, Any] | None) -> dict[str, Any]:
    """Pull failing test title + error message out of the Playwright JSON report."""
    if not pw_json:
        return {}
    failing: list[dict[str, Any]] = []
    for suite in pw_json.get("suites", []):
        for spec in suite.get("specs", []):
            for result in spec.get("tests", [spec]):
                for r in result.get("results", [result]):
                    if r.get("status") not in ("passed", "skipped"):
                        failing.append(
                            {
                                "title": spec.get("title", ""),
                                "status": r.get("status"),
                                "error": (r.get("error") or {}).get("message", "")[:500],
                                "screenshot": (
                                    r.get("attachments", [{}])[0].get("path")
                                    if r.get("attachments")
                                    else None
                                ),
                            }
                        )
    return {"failing_tests": failing} if failing else {}


# ---------------------------------------------------------------------------
# Per-product probe runner
# ---------------------------------------------------------------------------


def _run_product_probe(product: str, base_url: str) -> dict[str, Any]:
    """Shell out to ``pnpm --filter @paperwork/probes test:<product>``.

    Returns a result row suitable for probe_results.json.
    No-silent-fallback: infrastructure errors produce a row with
    status=infrastructure_error, never a silent skip.
    """
    started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    # Guard 1: pnpm must be on PATH
    pnpm_path = shutil.which("pnpm")
    if not pnpm_path:
        msg = (
            "pnpm not found on PATH. Install pnpm or add it to the Brain service's PATH. "
            "Probe cannot run without pnpm."
        )
        logger.error("probe[%s] infrastructure_error: %s", product, msg)
        return _error_row(product, started_at, "infrastructure_error", msg)

    env = {**os.environ, "PROBE_BASE_URL": base_url, "PROBE_PRODUCT": product}

    try:
        proc = subprocess.run(
            [pnpm_path, "--filter", "@paperwork/probes", f"test:{product}"],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
            cwd=str(_REPO_ROOT),
            env=env,
        )
    except subprocess.TimeoutExpired:
        msg = (
            f"Playwright probe for {product} timed out after {_PROBE_TIMEOUT_SECONDS}s. "
            "Increase PROBE_TIMEOUT_SECONDS or investigate slow test."
        )
        logger.warning("probe[%s] timeout", product)
        return _error_row(product, started_at, "timeout", msg)
    except FileNotFoundError as exc:
        # pnpm was found above but exec failed — binary mismatch or permission
        msg = f"pnpm exec failed: {exc}"
        logger.error("probe[%s] infrastructure_error: %s", product, msg)
        return _error_row(product, started_at, "infrastructure_error", msg)
    except OSError as exc:
        msg = f"OS error running pnpm: {exc}"
        logger.error("probe[%s] infrastructure_error: %s", product, msg)
        return _error_row(product, started_at, "infrastructure_error", msg)

    finished_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    exit_code = proc.returncode

    # Guard 2: detect "Playwright browsers not installed" specifically
    combined_output = (proc.stdout or "") + (proc.stderr or "")
    low = combined_output.lower()
    playwright_infra = ("playwright" in low or "browsertype.launch" in combined_output) and (
        "browserType.launch" in combined_output
        or "browsertype.launch" in low
        or "browser was not found" in combined_output
        or "run playwright install" in low
        or "executable doesn't exist" in low
    )
    if playwright_infra:
        msg = (
            "Playwright browser binaries are not installed. "
            "Run: pnpm --filter @paperwork/probes exec playwright install chromium. "
            f"Raw error snippet: {combined_output[:400]}"
        )
        logger.error("probe[%s] infrastructure_error: missing browser binaries", product)
        return _error_row(product, started_at, "infrastructure_error", msg, finished_at=finished_at)

    pw_json = _parse_playwright_json(product)
    failure_info = _extract_failure_info(pw_json) if exit_code != 0 else {}

    status = "pass" if exit_code == 0 else "failure"
    row: dict[str, Any] = {
        "product": product,
        "base_url": base_url,
        "status": status,
        "exit_code": exit_code,
        "started_at": started_at,
        "finished_at": finished_at,
        "stdout_tail": (proc.stdout or "")[-1000:],
        "stderr_tail": (proc.stderr or "")[-500:],
    }
    if failure_info:
        row.update(failure_info)

    logger.info("probe[%s] status=%s exit_code=%d", product, status, exit_code)
    return row


def _error_row(
    product: str,
    started_at: str,
    status: str,
    message: str,
    *,
    finished_at: str | None = None,
) -> dict[str, Any]:
    return {
        "product": product,
        "base_url": None,
        "status": status,
        "exit_code": None,
        "started_at": started_at,
        "finished_at": finished_at or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "error_message": message,
    }


# ---------------------------------------------------------------------------
# Scheduler body
# ---------------------------------------------------------------------------


async def _run_ux_probe_body() -> None:
    try:
        prod_urls = _load_production_urls()
    except FileNotFoundError as exc:
        logger.error("probe_runner: cannot load production URLs: %s", exc)
        _append_result(
            _error_row(
                "all",
                datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "infrastructure_error",
                str(exc),
            )
        )
        return

    written = 0
    errors = 0

    for product in PRODUCTS:
        base_url = prod_urls.get(product)
        if not base_url:
            logger.warning("probe_runner: no production URL for product=%s; skipping", product)
            # Write a visible infrastructure_error row — not a silent skip
            row = _error_row(
                product,
                datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "infrastructure_error",
                f"No entry for '{product}' in production-urls.json. Add the URL to run this probe.",
            )
            _append_result(row)
            errors += 1
            continue

        try:
            row = await asyncio.to_thread(_run_product_probe, product, base_url)
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("probe_runner: unhandled exception for %s: %s\n%s", product, exc, tb)
            row = _error_row(
                product,
                datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "infrastructure_error",
                f"Unhandled exception: {exc!r} — {tb[:500]}",
            )
            errors += 1

        _append_result(row)
        written += 1

    logger.info(
        "probe_runner: cycle complete written=%d errors=%d",
        written,
        errors,
    )


@skip_if_brain_paused(JOB_ID)
async def run_ux_probe_job() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_ux_probe_body,
        metadata={"source": "ux_probe_runner", "products": PRODUCTS},
        reraise=True,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the UX probe runner (every PROBE_INTERVAL_SECONDS, default 5 min)."""
    scheduler.add_job(
        run_ux_probe_job,
        trigger=IntervalTrigger(seconds=PROBE_INTERVAL_SECONDS),
        id=JOB_ID,
        name="UX Probe Runner (Wave PROBE PR-PB1)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info(
        "APScheduler job %r registered (interval=%ds, products=%s)",
        JOB_ID,
        PROBE_INTERVAL_SECONDS,
        PRODUCTS,
    )
