"""Brain-owned application log ingestion, storage, querying, and anomaly detection.

Brain is the first-class log owner — no third-party vendor (see procedural_memory.yaml).
Apps push high-signal events via POST /admin/logs/ingest; Brain also pulls from
Vercel and Render APIs on an hourly APScheduler job (see schedulers/log_pull.py).

External API auth
-----------------
``pull_vercel_logs()``  — requires ``VERCEL_API_TOKEN`` in env.
``pull_render_logs()``  — requires ``RENDER_API_KEY`` in env.
On missing / invalid credentials both functions log a structured warning at
WARNING level and return an empty list. They do NOT raise.

Anomaly detection
-----------------
``evaluate_log_anomalies()`` checks error rate per (app, service) over the last
hour against a rolling 24 h baseline (mean ± stddev). When the current error
rate exceeds baseline_p95 + 3*stddev it fires a Conversation alert via PR E's
``create_conversation`` helper.

PR E guard
----------
``create_conversation`` lives in ``app.services.conversations`` (PR E). When
that module has not yet merged the call is stubbed and guarded by the env flag
``BRAIN_CONVERSATIONS_API_ENABLED`` (default False until PR E ships). Set the
env var to ``1`` to activate real conversation creation.

medallion: ops
"""

from __future__ import annotations

import fcntl
import gzip
import json
import logging
import os
import statistics
import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

from app.schemas.app_logs import AppLogEntry, AppLogsFile, severity_gte

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

LOG_CAP = 10_000
ANOMALY_WINDOW_HOURS = 1
ANOMALY_BASELINE_HOURS = 24
ANOMALY_SIGMA_THRESHOLD = 3.0
ANOMALY_COOLDOWN_HOURS = 1  # minimum gap between repeated fires for same (app, service)

_ENV_APP_LOGS_JSON = "BRAIN_APP_LOGS_JSON"
_ENV_CONVERSATIONS_ENABLED = "BRAIN_CONVERSATIONS_API_ENABLED"
_TMP_SUFFIX = ".tmp"


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _brain_data_dir() -> Path:
    env = os.environ.get("BRAIN_DATA_DIR", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "data"


def app_logs_file_path() -> Path:
    env = os.environ.get(_ENV_APP_LOGS_JSON, "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "app_logs.json"


def _lock_path() -> Path:
    p = app_logs_file_path()
    return p.with_suffix(p.suffix + ".lock")


# ---------------------------------------------------------------------------
# File-locked atomic I/O (same _with_lock pattern as self_improvement.py)
# ---------------------------------------------------------------------------


def _with_lock(func: Callable[[], _T]) -> _T:
    lock = _lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            return func()
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + _TMP_SUFFIX)
    raw = json.dumps(data, indent=2, sort_keys=True, default=str) + "\n"
    tmp.write_text(raw, encoding="utf-8")
    os.replace(tmp, path)


def _read_logs_file_unlocked() -> AppLogsFile:
    path = app_logs_file_path()
    if not path.is_file():
        return AppLogsFile()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return AppLogsFile()
        return AppLogsFile.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "app_logs: could not read %s — %s; returning empty store",
            path,
            exc,
            extra={"component": "app_logs", "op": "read", "error": str(exc)},
        )
        return AppLogsFile()


def _write_logs_file_unlocked(file: AppLogsFile) -> None:
    path = app_logs_file_path()
    _atomic_write(path, file.model_dump(mode="json", by_alias=True))


# ---------------------------------------------------------------------------
# Daily rotation (gzip archives)
# ---------------------------------------------------------------------------


def _rotate_daily() -> None:
    """Compress yesterday's snapshot to .gz if the main file is dated yesterday."""
    data_dir = _brain_data_dir()
    today = datetime.now(UTC).date()
    archive_name = f"app_logs_{(today - timedelta(days=1)).isoformat()}.json.gz"
    archive_path = data_dir / archive_name
    if archive_path.exists():
        return
    main = app_logs_file_path()
    if not main.is_file():
        return
    # Archive everything that's older than yesterday's cutoff
    cutoff = datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC)
    try:
        store = _read_logs_file_unlocked()
        old = [e for e in store.logs if e.ingested_at < cutoff]
        if not old:
            return
        payload = {
            "logs": [e.model_dump(mode="json") for e in old],
            "archived_at": cutoff.isoformat(),
        }
        with gzip.open(archive_path, "wt", encoding="utf-8") as gz:
            json.dump(payload, gz)
        logger.info(
            "app_logs: archived %d entries to %s",
            len(old),
            archive_name,
            extra={"component": "app_logs", "op": "rotate", "count": len(old)},
        )
    except Exception as exc:
        logger.warning(
            "app_logs: daily rotation failed — %s (non-fatal)",
            exc,
            extra={"component": "app_logs", "op": "rotate_error", "error": str(exc)},
        )
    _prune_old_archives(data_dir, keep_days=14)


def _prune_old_archives(data_dir: Path, keep_days: int) -> None:
    cutoff = datetime.now(UTC).date() - timedelta(days=keep_days)
    with suppress(OSError):
        for gz in data_dir.glob("app_logs_*.json.gz"):
            date_str = gz.stem.removeprefix("app_logs_").removesuffix(".json")
            with suppress(ValueError):
                if datetime.strptime(date_str, "%Y-%m-%d").date() < cutoff:  # noqa: DTZ007
                    gz.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Cap enforcement
# ---------------------------------------------------------------------------


def _enforce_cap(file: AppLogsFile) -> AppLogsFile:
    if len(file.logs) <= LOG_CAP:
        return file
    # Sort ascending, keep newest LOG_CAP entries
    sorted_logs = sorted(file.logs, key=lambda e: e.occurred_at)
    file.logs = sorted_logs[-LOG_CAP:]
    if file.logs:
        file.window_start = file.logs[0].occurred_at
    return file


def _update_window(file: AppLogsFile) -> AppLogsFile:
    if not file.logs:
        file.window_start = None
        file.window_end = None
        return file
    times = [e.occurred_at for e in file.logs]
    file.window_start = min(times)
    file.window_end = max(times)
    return file


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ingest_logs(entries: list[AppLogEntry]) -> int:
    """Append *entries*, dedup by id, evict oldest beyond LOG_CAP.

    Returns the number of net-new entries added.
    """
    if not entries:
        return 0

    def _do() -> int:
        store = _read_logs_file_unlocked()
        existing_ids = {e.id for e in store.logs}
        new_entries = [e for e in entries if e.id not in existing_ids]
        if not new_entries:
            return 0
        store.logs.extend(new_entries)
        store = _enforce_cap(store)
        store = _update_window(store)
        _write_logs_file_unlocked(store)
        return len(new_entries)

    return _with_lock(_do)


def query_logs(
    *,
    app: str | None = None,
    service: str | None = None,
    severity_min: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    search: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Query stored logs with optional filters. Returns paginated result dict.

    ``cursor`` is an opaque ISO-8601 timestamp + entry id used for stable
    keyset pagination. Pass the ``next_cursor`` from a previous response to
    get the next page.

    Response shape::

        {
            "logs": [AppLogEntry, ...],
            "next_cursor": str | None,
            "total_matched": int,
        }
    """
    limit = max(1, min(limit, 500))
    store = _with_lock(_read_logs_file_unlocked)

    # Apply filters
    results = store.logs
    if app:
        results = [e for e in results if e.app == app]
    if service:
        results = [e for e in results if e.service == service]
    if severity_min:
        results = [e for e in results if severity_gte(e.severity, severity_min)]
    if since:
        results = [e for e in results if e.occurred_at >= since]
    if until:
        results = [e for e in results if e.occurred_at <= until]
    if search:
        q = search.lower()
        results = [
            e
            for e in results
            if q in e.message.lower() or any(q in str(v).lower() for v in e.attrs.values())
        ]

    # Sort newest-first for display
    results = sorted(results, key=lambda e: (e.occurred_at, e.id), reverse=True)

    total_matched = len(results)

    # Cursor-based pagination: cursor = "<iso_occurred_at>|<id>"
    if cursor:
        with suppress(Exception):
            ts_str, entry_id = cursor.split("|", 1)
            cursor_dt = datetime.fromisoformat(ts_str)
            # Skip everything at or newer than the cursor position
            results = [e for e in results if (e.occurred_at, e.id) < (cursor_dt, entry_id)]

    page = results[:limit]
    next_cursor: str | None = None
    if len(results) > limit:
        last = page[-1]
        next_cursor = f"{last.occurred_at.isoformat()}|{last.id}"

    return {
        "logs": [e.model_dump(mode="json") for e in page],
        "next_cursor": next_cursor,
        "total_matched": total_matched,
    }


# ---------------------------------------------------------------------------
# External API pulls
# ---------------------------------------------------------------------------


def pull_vercel_logs() -> list[AppLogEntry]:
    """Fetch recent deployment log events from the Vercel API.

    Requires ``VERCEL_API_TOKEN`` env var. On missing/invalid token logs a
    structured WARNING and returns []. Never raises.

    Pulls up to 100 deployment log lines per project listed by the team.
    """
    from app.config import settings

    token = settings.VERCEL_API_TOKEN.strip()
    if not token:
        logger.warning(
            "app_logs.pull_vercel_logs: VERCEL_API_TOKEN not set — skipping Vercel pull",
            extra={"component": "app_logs", "op": "pull_vercel", "reason": "no_token"},
        )
        return []

    try:
        import httpx

        headers = {"Authorization": f"Bearer {token}"}
        entries: list[AppLogEntry] = []
        now = datetime.now(UTC)

        with httpx.Client(timeout=15) as client:
            # List projects
            resp = client.get("https://api.vercel.com/v9/projects", headers=headers)
            if resp.status_code == 401:
                logger.warning(
                    "app_logs.pull_vercel_logs: 401 Unauthorized — check VERCEL_API_TOKEN",
                    extra={"component": "app_logs", "op": "pull_vercel", "reason": "auth_failure"},
                )
                return []
            resp.raise_for_status()
            projects_data = resp.json()
            projects = projects_data.get("projects", [])

            for project in projects[:10]:  # cap to avoid rate-limits
                project_id = project.get("id", "")
                project_name = project.get("name", project_id)
                if not project_id:
                    continue
                # Fetch latest deployment
                dep_resp = client.get(
                    "https://api.vercel.com/v6/deployments",
                    headers=headers,
                    params={"projectId": project_id, "limit": "1"},
                )
                if not dep_resp.is_success:
                    continue
                deps = dep_resp.json().get("deployments", [])
                if not deps:
                    continue
                dep_id = deps[0].get("uid", "")
                if not dep_id:
                    continue

                # Fetch build logs for that deployment
                log_resp = client.get(
                    f"https://api.vercel.com/v2/deployments/{dep_id}/events",
                    headers=headers,
                    params={"limit": "50"},
                )
                if not log_resp.is_success:
                    continue

                for event in log_resp.json():
                    if not isinstance(event, dict):
                        continue
                    text = event.get("text") or event.get("payload", {}).get("text", "")
                    if not text:
                        continue
                    event_type = event.get("type", "")
                    severity: str = "info"
                    if event_type in ("error", "fatal"):
                        severity = "error"
                    elif event_type == "warning":
                        severity = "warn"

                    created_ms = event.get("created")
                    try:
                        occurred_at = (
                            datetime.fromtimestamp(created_ms / 1000, tz=UTC)
                            if isinstance(created_ms, (int, float))
                            else now
                        )
                    except (TypeError, ValueError, OSError):
                        occurred_at = now

                    entries.append(
                        AppLogEntry(
                            id=str(
                                uuid.uuid5(
                                    uuid.NAMESPACE_URL,
                                    f"vercel:{dep_id}:{event.get('id', text[:40])}",
                                )
                            ),
                            app=project_name,
                            service=project_name,
                            severity=severity,
                            message=text[:2000],
                            attrs={"deployment_id": dep_id, "event_type": event_type},
                            source="vercel-pull",
                            occurred_at=occurred_at,
                            ingested_at=now,
                        )
                    )

        logger.info(
            "app_logs.pull_vercel_logs: pulled %d entries from Vercel",
            len(entries),
            extra={"component": "app_logs", "op": "pull_vercel", "count": len(entries)},
        )
        return entries

    except Exception as exc:
        logger.warning(
            "app_logs.pull_vercel_logs: error pulling from Vercel API — %s (non-fatal)",
            exc,
            extra={"component": "app_logs", "op": "pull_vercel", "error": str(exc)},
        )
        return []


def pull_render_logs() -> list[AppLogEntry]:
    """Fetch recent deployment logs from the Render API.

    Requires ``RENDER_API_KEY`` env var. On missing/invalid key logs a
    structured WARNING and returns []. Never raises.
    """
    from app.config import settings

    api_key = settings.RENDER_API_KEY.strip()
    if not api_key:
        logger.warning(
            "app_logs.pull_render_logs: RENDER_API_KEY not set — skipping Render pull",
            extra={"component": "app_logs", "op": "pull_render", "reason": "no_token"},
        )
        return []

    try:
        import httpx

        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        entries: list[AppLogEntry] = []
        now = datetime.now(UTC)

        with httpx.Client(timeout=15) as client:
            # List services
            resp = client.get(
                "https://api.render.com/v1/services",
                headers=headers,
                params={"limit": "20"},
            )
            if resp.status_code == 401:
                logger.warning(
                    "app_logs.pull_render_logs: 401 Unauthorized — check RENDER_API_KEY",
                    extra={"component": "app_logs", "op": "pull_render", "reason": "auth_failure"},
                )
                return []
            resp.raise_for_status()
            services = resp.json()

            for item in services[:10]:
                svc = item.get("service", item) if isinstance(item, dict) else {}
                svc_id = svc.get("id", "")
                svc_name = svc.get("name", svc_id)
                if not svc_id:
                    continue

                # Fetch recent deploys for log events
                dep_resp = client.get(
                    f"https://api.render.com/v1/services/{svc_id}/deploys",
                    headers=headers,
                    params={"limit": "1"},
                )
                if not dep_resp.is_success:
                    continue
                deploys = dep_resp.json()
                if not deploys:
                    continue

                dep_item = deploys[0]
                dep = dep_item.get("deploy", dep_item) if isinstance(dep_item, dict) else {}
                dep_id = dep.get("id", "")
                dep_status = dep.get("status", "unknown")

                # Map Render deploy status to severity
                severity: str = "info"
                if dep_status in ("build_failed", "deactivated", "canceled"):
                    severity = "error"
                elif dep_status == "live":
                    severity = "info"

                created_at_str = dep.get("createdAt") or dep.get("updatedAt", "")
                try:
                    s = (
                        created_at_str.replace("Z", "+00:00")
                        if created_at_str.endswith("Z")
                        else created_at_str
                    )
                    occurred_at = datetime.fromisoformat(s) if s else now
                    if occurred_at.tzinfo is None:
                        occurred_at = occurred_at.replace(tzinfo=UTC)
                except (ValueError, AttributeError):
                    occurred_at = now

                entries.append(
                    AppLogEntry(
                        id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"render:{svc_id}:{dep_id}")),
                        app=svc_name,
                        service=svc_name,
                        severity=severity,
                        message=f"Deploy {dep_id} status: {dep_status}",
                        attrs={"deploy_id": dep_id, "deploy_status": dep_status},
                        source="render-pull",
                        occurred_at=occurred_at,
                        ingested_at=now,
                    )
                )

        logger.info(
            "app_logs.pull_render_logs: pulled %d entries from Render",
            len(entries),
            extra={"component": "app_logs", "op": "pull_render", "count": len(entries)},
        )
        return entries

    except Exception as exc:
        logger.warning(
            "app_logs.pull_render_logs: error pulling from Render API — %s (non-fatal)",
            exc,
            extra={"component": "app_logs", "op": "pull_render", "error": str(exc)},
        )
        return []


# ---------------------------------------------------------------------------
# Anomaly detection over logs
# ---------------------------------------------------------------------------


def evaluate_log_anomalies() -> int:
    """Check error rate per (app, service) over the last hour vs 24 h baseline.

    If error rate exceeds baseline_mean + ANOMALY_SIGMA_THRESHOLD * stddev,
    fire a Conversation alert. Idempotent: tracks last-fired per (app, service)
    in the file; skips re-fire within ANOMALY_COOLDOWN_HOURS.

    Returns the number of new anomaly alerts fired.
    """

    def _do() -> int:
        store = _read_logs_file_unlocked()
        now = datetime.now(UTC)
        window_start = now - timedelta(hours=ANOMALY_WINDOW_HOURS)
        baseline_start = now - timedelta(hours=ANOMALY_BASELINE_HOURS)

        # Group logs by (app, service)
        groups: dict[str, list[AppLogEntry]] = {}
        for entry in store.logs:
            key = f"{entry.app}|{entry.service}"
            groups.setdefault(key, []).append(entry)

        fired = 0
        for key, entries in groups.items():
            app_name, service_name = key.split("|", 1)

            # Compute hourly error rate buckets over the baseline window (24 x 1h buckets)
            baseline_entries = [
                e for e in entries if baseline_start <= e.occurred_at < window_start
            ]
            if not baseline_entries:
                continue

            # Build 1-hour error-rate buckets within the baseline window
            bucket_counts: dict[int, dict[str, int]] = {}
            for entry in baseline_entries:
                bucket_hour = int((entry.occurred_at - baseline_start).total_seconds() // 3600)
                bc = bucket_counts.setdefault(bucket_hour, {"total": 0, "error": 0})
                bc["total"] += 1
                if severity_gte(entry.severity, "error"):
                    bc["error"] += 1

            if len(bucket_counts) < 3:
                continue

            error_rates = [bc["error"] / max(bc["total"], 1) for bc in bucket_counts.values()]
            baseline_mean = statistics.mean(error_rates)
            if len(error_rates) < 2:
                continue
            baseline_std = statistics.stdev(error_rates)

            # Current window error rate
            current_entries = [e for e in entries if e.occurred_at >= window_start]
            current_total = len(current_entries)
            if current_total == 0:
                continue
            current_errors = sum(1 for e in current_entries if severity_gte(e.severity, "error"))
            current_rate = current_errors / current_total

            threshold = baseline_mean + ANOMALY_SIGMA_THRESHOLD * baseline_std
            if current_rate <= threshold:
                continue

            # Idempotency: skip if already fired within cooldown window
            last_fired_str = store.last_anomaly_fire.get(key)
            if last_fired_str:
                with suppress(ValueError):
                    last_fired_dt = datetime.fromisoformat(last_fired_str)
                    if (now - last_fired_dt) < timedelta(hours=ANOMALY_COOLDOWN_HOURS):
                        continue

            # Fire alert
            _fire_log_anomaly_alert(
                app=app_name,
                service=service_name,
                current_rate=current_rate,
                baseline_mean=baseline_mean,
                baseline_std=baseline_std,
                current_errors=current_errors,
                current_total=current_total,
            )
            store.last_anomaly_fire[key] = now.isoformat()
            fired += 1

        if fired > 0:
            _write_logs_file_unlocked(store)
        return fired

    return _with_lock(_do)


def _fire_log_anomaly_alert(
    *,
    app: str,
    service: str,
    current_rate: float,
    baseline_mean: float,
    baseline_std: float,
    current_errors: int,
    current_total: int,
) -> None:
    """Create a Conversation alert for the log error spike.

    Guarded by ``BRAIN_CONVERSATIONS_API_ENABLED`` env flag while PR E has not
    yet merged. When disabled, logs a structured WARNING instead.
    """
    conv_enabled = os.environ.get(_ENV_CONVERSATIONS_ENABLED, "0").strip() in ("1", "true", "True")
    message = (
        f"Log anomaly detected for {app}/{service}: "
        f"{current_errors}/{current_total} errors in last {ANOMALY_WINDOW_HOURS}h "
        f"(rate={current_rate:.1%}; baseline={baseline_mean:.1%}±{baseline_std:.1%})"
    )

    if not conv_enabled:
        logger.warning(
            "app_logs.anomaly: %s [Conversation not created"
            " — BRAIN_CONVERSATIONS_API_ENABLED=0 (PR E stub)]",
            message,
            extra={
                "component": "app_logs",
                "op": "anomaly_alert",
                "app": app,
                "service": service,
                "stub": True,
            },
        )
        return

    try:
        from app.schemas.conversation import ConversationCreate
        from app.services.conversations import create_conversation

        create_conversation(
            ConversationCreate(
                title=f"Log anomaly: {app}/{service} error spike",
                body_md=message,
                tags=["alert", "log-anomaly", f"app:{app}"],
                urgency="high",
            )
        )
        logger.info(
            "app_logs.anomaly: Conversation created for %s/%s",
            app,
            service,
            extra={"component": "app_logs", "op": "anomaly_alert", "app": app, "service": service},
        )
    except Exception as exc:
        logger.warning(
            "app_logs.anomaly: create_conversation failed — %s",
            exc,
            extra={"component": "app_logs", "op": "anomaly_alert_error", "error": str(exc)},
        )
