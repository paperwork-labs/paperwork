"""Brain-owned log ingestion, storage, pull, and anomaly detection (WS-69 PR M).

Storage: ``apis/brain/data/app_logs.json`` — capped at MAX_LOG_ENTRIES.
File-level lock mirrors ``pr_outcomes.py`` pattern.

medallion: ops
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

import httpx

from app.schemas.app_log import (
    Anomaly,
    AppLog,
    AppLogIngestRequest,
    AppLogsFile,
    AppLogsListPage,
    AppName,
    Severity,
)

logger = logging.getLogger(__name__)

_TMP_SUFFIX = ".tmp"
MAX_LOG_ENTRIES = 5000
_T = TypeVar("_T")

# Anomaly detection: error-rate spike threshold (ratio vs baseline)
ERROR_SPIKE_RATIO = 5.0
# Minimum errors in the recent window to bother comparing against baseline
MIN_ERRORS_FOR_SPIKE = 3
# Repeated 5xx threshold on same route/service within the window
REPEATED_5XX_THRESHOLD = 5


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _brain_data_dir() -> Path:
    env = os.environ.get("BRAIN_APP_LOGS_JSON", "").strip()
    if env:
        return Path(env).parent
    env_dir = os.environ.get("BRAIN_DATA_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    # services/ -> app/ -> brain/ -> data/
    return Path(__file__).resolve().parents[2] / "data"


def app_logs_file_path() -> Path:
    env = os.environ.get("BRAIN_APP_LOGS_JSON", "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "app_logs.json"


def _lock_path() -> Path:
    return app_logs_file_path().with_suffix(".json.lock")


# ---------------------------------------------------------------------------
# Atomic I/O helpers
# ---------------------------------------------------------------------------


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + _TMP_SUFFIX)
    raw = json.dumps(data, indent=2, sort_keys=True) + "\n"
    tmp.write_text(raw, encoding="utf-8")
    os.replace(tmp, path)


def _load_unlocked() -> AppLogsFile:
    path = app_logs_file_path()
    if not path.is_file():
        return AppLogsFile()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return AppLogsFile()
        return AppLogsFile.model_validate(raw)
    except (OSError, json.JSONDecodeError, Exception) as exc:
        logger.warning("app_logs: could not read %s — %s; starting empty", path, exc)
        return AppLogsFile()


def _write_unlocked(data: AppLogsFile) -> None:
    path = app_logs_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(path, data.model_dump(mode="json", by_alias=True))


def _with_file_lock(func: Callable[[], _T]) -> _T:
    lp = _lock_path()
    lp.parent.mkdir(parents=True, exist_ok=True)
    with lp.open("a+", encoding="utf-8") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            return func()
        finally:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)


def _mutate(mutator: Callable[[AppLogsFile], None]) -> None:
    def _go() -> None:
        f = _load_unlocked()
        mutator(f)
        _write_unlocked(f)

    _with_file_lock(_go)


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def ingest_log(req: AppLogIngestRequest) -> AppLog:
    """Append a log entry pushed by an app. Caps file to MAX_LOG_ENTRIES (oldest dropped)."""
    log = AppLog(
        id=str(uuid.uuid4()),
        app=req.app,
        service=req.service,
        severity=req.severity,
        message=req.message,
        metadata=req.metadata,
        request_id=req.request_id,
        at=req.at if req.at is not None else datetime.now(UTC),
        source="push",
    )

    def _m(f: AppLogsFile) -> None:
        f.logs.append(log)
        if len(f.logs) > MAX_LOG_ENTRIES:
            f.logs = f.logs[-MAX_LOG_ENTRIES:]

    _mutate(_m)
    return log


def list_logs(
    *,
    app: str | None = None,
    severity: str | None = None,
    search: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
    cursor: str | None = None,
) -> AppLogsListPage:
    """Return cursor-paginated logs (newest first) with optional filters.

    ``cursor`` is the ISO8601 timestamp of the *last* entry in the previous page;
    only entries *older* than that timestamp are returned.
    """
    limit = max(1, min(limit, 500))

    def _read() -> AppLogsListPage:
        f = _load_unlocked()
        rows = list(reversed(f.logs))  # newest first

        if app:
            rows = [r for r in rows if r.app == app]
        if severity:
            rows = [r for r in rows if r.severity == severity]
        if since:
            rows = [r for r in rows if r.at >= since]
        if search:
            q = search.lower()
            rows = [
                r for r in rows if q in r.message.lower() or q in json.dumps(r.metadata).lower()
            ]

        total_matched = len(rows)

        if cursor:
            try:
                cutoff = datetime.fromisoformat(cursor)
                rows = [r for r in rows if r.at < cutoff]
            except ValueError:
                pass

        page = rows[:limit]
        next_cur: str | None = None
        if len(page) == limit and len(rows) > limit:
            next_cur = page[-1].at.isoformat()

        return AppLogsListPage(logs=page, total_matched=total_matched, next_cursor=next_cur)

    return _with_file_lock(_read)


def pull_vercel_logs(
    *,
    team_id: str,
    project_ids: list[str],
    since: datetime,
    app_override: AppName = "studio",
) -> int:
    """Pull logs from Vercel deployments API.

    Returns the count of new log entries ingested.
    Failures are ingested as brain-log-puller error entries (no silent swallowing).
    """
    token = os.environ.get("VERCEL_API_TOKEN", "").strip()
    if not token:
        _ingest_puller_error("pull_vercel_logs: VERCEL_API_TOKEN not configured")
        return 0

    headers = {"Authorization": f"Bearer {token}"}
    params: dict[str, str] = {"limit": "100"}
    if team_id:
        params["teamId"] = team_id

    ingested = 0
    since_ms = int(since.timestamp() * 1000)

    for project_id in project_ids:
        try:
            url = f"https://api.vercel.com/v6/projects/{project_id}/deployments"
            with httpx.Client(timeout=20) as client:
                resp = client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                _ingest_puller_error(
                    f"pull_vercel_logs: deployments list HTTP {resp.status_code}"
                    f" for project {project_id}",
                    metadata={"status_code": resp.status_code, "project_id": project_id},
                )
                continue

            deployments = resp.json().get("deployments", [])
            for dep in deployments[:5]:  # check last 5 deployments
                dep_id = dep.get("uid") or dep.get("id")
                if not dep_id:
                    continue
                created_at = dep.get("createdAt", 0)
                if created_at and created_at < since_ms:
                    continue
                try:
                    ev_url = f"https://api.vercel.com/v3/deployments/{dep_id}/events"
                    with httpx.Client(timeout=20) as client:
                        ev_resp = client.get(ev_url, headers=headers)
                    if ev_resp.status_code != 200:
                        continue
                    for event in ev_resp.json():
                        if not isinstance(event, dict):
                            continue
                        text = event.get("text", "") or event.get("payload", {}).get("text", "")
                        if not text:
                            continue
                        ev_type = event.get("type", "")
                        sev: Severity = "info"
                        if ev_type in ("error",) or "error" in text.lower():
                            sev = "error"
                        elif "warn" in text.lower():
                            sev = "warn"
                        req = AppLogIngestRequest(
                            app=app_override,
                            service=f"vercel-{project_id}",
                            severity=sev,
                            message=text[:2000],
                            metadata={
                                "deployment_id": dep_id,
                                "event_type": ev_type,
                                "project_id": project_id,
                            },
                            at=datetime.fromtimestamp(
                                event.get("created", since_ms) / 1000, tz=UTC
                            ),
                        )
                        _ingest_as_pull(req)
                        ingested += 1
                except (httpx.HTTPError, Exception) as exc:
                    _ingest_puller_error(
                        f"pull_vercel_logs: events fetch failed for {dep_id}: {exc}",
                        metadata={"deployment_id": dep_id, "project_id": project_id},
                    )
        except (httpx.HTTPError, Exception) as exc:
            _ingest_puller_error(
                f"pull_vercel_logs: project {project_id} failed: {exc}",
                metadata={"project_id": project_id},
            )

    _update_last_pulled_at("vercel")
    return ingested


def pull_render_logs(
    *,
    service_ids: list[str],
    since: datetime,
    app_override: AppName = "brain",
) -> int:
    """Pull logs from Render services API.

    Returns count of new entries ingested.
    Failures are ingested as brain-log-puller error entries.
    """
    api_key = os.environ.get("RENDER_API_KEY", "").strip()
    if not api_key:
        _ingest_puller_error("pull_render_logs: RENDER_API_KEY not configured")
        return 0

    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    ingested = 0
    since_iso = since.isoformat()

    for service_id in service_ids:
        try:
            url = f"https://api.render.com/v1/services/{service_id}/logs"
            params = {"startTime": since_iso, "limit": "200"}
            with httpx.Client(timeout=20) as client:
                resp = client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                _ingest_puller_error(
                    f"pull_render_logs: HTTP {resp.status_code} for service {service_id}",
                    metadata={"status_code": resp.status_code, "service_id": service_id},
                )
                continue

            for entry in resp.json():
                if not isinstance(entry, dict):
                    continue
                msg = entry.get("message", "") or entry.get("text", "")
                if not msg:
                    continue
                level = (entry.get("level") or "info").lower()
                sev_map: dict[str, Severity] = {
                    "error": "error",
                    "critical": "critical",
                    "warn": "warn",
                    "warning": "warn",
                    "debug": "debug",
                    "info": "info",
                }
                sev = sev_map.get(level, "info")
                ts_str = entry.get("timestamp") or entry.get("time") or since_iso
                try:
                    at = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    at = since
                req = AppLogIngestRequest(
                    app=app_override,
                    service=f"render-{service_id}",
                    severity=sev,
                    message=msg[:2000],
                    metadata={"service_id": service_id},
                    at=at,
                )
                _ingest_as_pull(req)
                ingested += 1
        except (httpx.HTTPError, Exception) as exc:
            _ingest_puller_error(
                f"pull_render_logs: service {service_id} failed: {exc}",
                metadata={"service_id": service_id},
            )

    _update_last_pulled_at("render")
    return ingested


def detect_anomalies(logs: list[AppLog]) -> list[Anomaly]:
    """Detect anomalies in a batch of log entries.

    Patterns:
    - Error-rate spike: >5x baseline (7-day rolling) in the batch window.
    - Repeated 5xx errors for the same service within the batch.
    - Critical severity entries (always fire).

    Returns a list of Anomaly objects; caller is responsible for creating
    alert Conversations (PR I will wire push notifications).
    """
    if not logs:
        return []

    anomalies: list[Anomaly] = []
    now = datetime.now(UTC)

    # 1. Count errors in this batch
    batch_errors = [lg for lg in logs if lg.severity in ("error", "critical")]
    batch_total = len(logs)
    batch_error_rate = len(batch_errors) / batch_total if batch_total > 0 else 0.0

    # Compare against 7-day baseline from stored logs
    seven_days_ago = now - timedelta(days=7)

    def _baseline() -> float:
        f = _load_unlocked()
        historical = [
            lg
            for lg in f.logs
            if lg.at >= seven_days_ago and lg.id not in {b.id for b in batch_errors}
        ]
        if not historical:
            return 0.0
        errs = sum(1 for lg in historical if lg.severity in ("error", "critical"))
        return errs / len(historical)

    if len(batch_errors) >= MIN_ERRORS_FOR_SPIKE:
        try:
            baseline = _with_file_lock(_baseline)
            if baseline > 0 and batch_error_rate >= baseline * ERROR_SPIKE_RATIO:
                sample_ids = [lg.id for lg in batch_errors[:5]]
                anomalies.append(
                    Anomaly(
                        kind="error_rate_spike",
                        description=(
                            f"Error rate {batch_error_rate:.1%} in current batch "
                            f"vs {baseline:.1%} 7-day baseline "
                            f"({batch_error_rate / baseline:.1f}x spike)"
                        ),
                        severity="error",
                        sample_log_ids=sample_ids,
                    )
                )
        except Exception as exc:
            logger.warning("detect_anomalies: baseline comparison failed: %s", exc)

    # 2. Repeated 5xx for same service
    service_5xx: Counter[str] = Counter()
    service_5xx_samples: dict[str, list[str]] = defaultdict(list)
    for lg in batch_errors:
        if "5" in lg.message[:3] or any(
            str(k).startswith("5") and len(str(k)) == 3
            for k in lg.metadata.values()
            if isinstance(k, (int, str))
        ):
            service_5xx[lg.service] += 1
            service_5xx_samples[lg.service].append(lg.id)

    for svc, count in service_5xx.items():
        if count >= REPEATED_5XX_THRESHOLD:
            anomalies.append(
                Anomaly(
                    kind="repeated_5xx",
                    description=f"{count} 5xx errors for service '{svc}' in this batch",
                    severity="critical" if count >= REPEATED_5XX_THRESHOLD * 2 else "error",
                    affected_service=svc,
                    sample_log_ids=service_5xx_samples[svc][:5],
                )
            )

    # 3. Any critical entries always surface as anomalies
    critical_logs = [lg for lg in logs if lg.severity == "critical"]
    if critical_logs:
        anomalies.append(
            Anomaly(
                kind="critical_severity",
                description=f"{len(critical_logs)} critical-severity log(s) in batch",
                severity="critical",
                affected_app=critical_logs[0].app,
                affected_service=critical_logs[0].service,
                sample_log_ids=[lg.id for lg in critical_logs[:5]],
            )
        )

    return anomalies


def get_last_pulled_at() -> dict[str, str]:
    """Return the last_pulled_at map from the stored file."""

    def _read() -> dict[str, str]:
        return _load_unlocked().last_pulled_at

    return _with_file_lock(_read)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ingest_as_pull(req: AppLogIngestRequest) -> AppLog:
    """Ingest a log entry with source='pull'."""
    log = AppLog(
        id=str(uuid.uuid4()),
        app=req.app,
        service=req.service,
        severity=req.severity,
        message=req.message,
        metadata=req.metadata,
        request_id=req.request_id,
        at=req.at if req.at is not None else datetime.now(UTC),
        source="pull",
    )

    def _m(f: AppLogsFile) -> None:
        f.logs.append(log)
        if len(f.logs) > MAX_LOG_ENTRIES:
            f.logs = f.logs[-MAX_LOG_ENTRIES:]

    _mutate(_m)
    return log


def _ingest_puller_error(message: str, metadata: dict[str, Any] | None = None) -> None:
    """Record a pull-failure into app_logs.json with severity=error.

    Per procedural rule: NEVER swallow errors silently. Always surface to founder
    via the next anomaly detection cycle.
    """
    logger.error("brain-log-puller: %s", message)
    try:
        req = AppLogIngestRequest(
            app="brain",
            service="brain-log-puller",
            severity="error",
            message=message,
            metadata=metadata or {},
        )
        _ingest_as_pull(req)
    except Exception as exc:
        logger.error("brain-log-puller: could not self-ingest error entry: %s", exc)


def _update_last_pulled_at(source: str) -> None:
    now_iso = datetime.now(UTC).isoformat()

    def _m(f: AppLogsFile) -> None:
        f.last_pulled_at[source] = now_iso

    try:
        _mutate(_m)
    except Exception as exc:
        logger.warning("app_logs: could not update last_pulled_at[%s]: %s", source, exc)
