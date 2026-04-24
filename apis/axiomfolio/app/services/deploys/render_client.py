"""Render REST API client scoped to deploy-health telemetry.

G28 guardrail (D120): read-only wrapper around the ``/v1/services/{id}/deploys``
endpoint so the Beat poller, the ``/admin/health`` dimension, and tests can
share one typed surface.

Why a dedicated client rather than reusing
:class:`app.services.core.render_sync_service.RenderCronSyncService`:

* That class is focused on cron-job CRUD (creating / updating Render cron
  services) and carries a lot of mutation code we don't want on the
  read-only deploy-health path.
* Deploy-health polling runs every 5 minutes on the worker; the surface
  must be fail-closed on missing credentials (no-op) and never throw
  during Beat ticks (``no-silent-fallback.mdc`` — log + raise typed
  exception; the poll_service layer catches and records an incident).
* A separate module makes it easy to mock in tests with ``respx`` and to
  reason about timeouts / retries independently of the cron surface.

Threading model: ``httpx.Client`` (sync) instantiated per call. The poll
cadence is 5 min with <= 4 service lookups per tick, so connection
pooling buys us nothing and a per-call client keeps the worker memory
footprint flat.

medallion: ops
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

RENDER_API_BASE = "https://api.render.com/v1"

# Render deploy statuses we care about. ``live`` is the only terminal
# success state. ``build_failed``, ``update_failed``, ``canceled`` and
# ``deactivated`` are terminal failures (from the deploy-health POV).
# ``created``, ``build_in_progress``, ``update_in_progress``,
# ``pre_deploy_in_progress`` are in-flight.
TERMINAL_FAILURE_STATUSES = {
    "build_failed",
    "update_failed",
    "canceled",
    "pre_deploy_failed",
}
TERMINAL_SUCCESS_STATUSES = {"live"}
IN_FLIGHT_STATUSES = {
    "created",
    "build_in_progress",
    "update_in_progress",
    "pre_deploy_in_progress",
}
# ``deactivated`` means a later deploy superseded this one before it went
# live. We treat it as "skipped" rather than failure for summary counts.
SUPERSEDED_STATUSES = {"deactivated"}


class RenderDeployClientError(RuntimeError):
    """Raised when a Render API call fails in a way the caller must handle.

    The poll_service layer catches this, logs with full context, writes a
    ``DeployHealthEvent`` row with ``status='poll_error'`` so the admin
    UI surfaces the gap, and never re-raises — Beat must keep running.
    """


@dataclass(frozen=True)
class DeployRecord:
    """One Render deploy as seen from the List Deploys endpoint."""

    service_id: str
    deploy_id: str
    status: str
    trigger: str | None
    commit_sha: str | None
    commit_message: str | None
    created_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None
    raw: dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def is_terminal(self) -> bool:
        return (
            self.status in TERMINAL_FAILURE_STATUSES
            or self.status in TERMINAL_SUCCESS_STATUSES
            or self.status in SUPERSEDED_STATUSES
        )

    @property
    def is_failure(self) -> bool:
        return self.status in TERMINAL_FAILURE_STATUSES

    @property
    def is_live(self) -> bool:
        return self.status in TERMINAL_SUCCESS_STATUSES

    @property
    def is_superseded(self) -> bool:
        return self.status in SUPERSEDED_STATUSES

    @property
    def short_sha(self) -> str:
        return (self.commit_sha or "")[:8]


def _parse_iso(value: Any) -> datetime | None:
    """Parse ``2026-04-21T04:11:05.827366Z`` etc. into a UTC-aware datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def _duration_seconds(created: datetime | None, finished: datetime | None) -> float | None:
    if not created or not finished:
        return None
    return max(0.0, (finished - created).total_seconds())


def _record_from_api(payload: dict[str, Any], *, service_id: str) -> DeployRecord:
    """Convert one Render API deploy payload into a :class:`DeployRecord`.

    Render returns slightly different shapes across endpoints; we defensively
    read ``commit`` or ``commit.id`` for the SHA and fall back to an empty
    string when the field is missing (e.g., manual deploys).
    """
    commit = payload.get("commit") or {}
    created = _parse_iso(payload.get("createdAt"))
    finished = _parse_iso(payload.get("finishedAt"))
    return DeployRecord(
        service_id=service_id,
        deploy_id=str(payload.get("id") or ""),
        status=str(payload.get("status") or "unknown").strip().lower(),
        trigger=payload.get("trigger"),
        commit_sha=(commit.get("id") if isinstance(commit, dict) else None),
        commit_message=(commit.get("message") if isinstance(commit, dict) else None),
        created_at=created or datetime.now(UTC),
        finished_at=finished,
        duration_seconds=_duration_seconds(created, finished),
        raw=dict(payload),
    )


class RenderDeployClient:
    """Read-only Render deploy telemetry client.

    Usage::

        client = RenderDeployClient()
        if client.enabled:
            records = client.list_deploys("srv-xxx", limit=10)
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = RENDER_API_BASE,
        timeout_s: float = 10.0,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.RENDER_API_KEY
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    @property
    def enabled(self) -> bool:
        """True when we have credentials; otherwise the client is a no-op.

        Callers must check this before dispatching. The poll task logs a
        warning and records no events when disabled — fail-closed but
        observable (``no-silent-fallback.mdc``).
        """
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

    def list_deploys(self, service_id: str, *, limit: int = 10) -> list[DeployRecord]:
        """Fetch the ``limit`` most recent deploys for one service, newest first.

        Raises :class:`RenderDeployClientError` on non-2xx responses or
        network errors. The poll_service catches this and surfaces it
        via a ``poll_error`` event.
        """
        if not self.enabled:
            raise RenderDeployClientError(
                "RenderDeployClient.list_deploys called with no RENDER_API_KEY"
            )
        url = f"{self._base_url}/services/{service_id}/deploys"
        params = {"limit": str(max(1, min(int(limit), 50)))}
        try:
            resp = httpx.get(
                url,
                params=params,
                headers=self._headers(),
                timeout=self._timeout_s,
            )
        except httpx.HTTPError as exc:
            raise RenderDeployClientError(
                f"Render API network error listing deploys for {service_id}: {exc}"
            ) from exc

        if resp.status_code >= 400:
            raise RenderDeployClientError(
                f"Render API {resp.status_code} listing deploys for {service_id}: {resp.text[:200]}"
            )

        try:
            payload = resp.json()
        except ValueError as exc:
            raise RenderDeployClientError(
                f"Render API returned non-JSON listing deploys for {service_id}: {exc}"
            ) from exc

        rows: list[dict[str, Any]] = []
        if isinstance(payload, list):
            # The v1 list endpoint returns either a bare list or a list of
            # ``{"deploy": {...}, "cursor": "..."}`` pairs depending on the
            # API version; normalise both.
            for entry in payload:
                if not isinstance(entry, dict):
                    continue
                deploy_payload = entry.get("deploy") if "deploy" in entry else entry
                if isinstance(deploy_payload, dict):
                    rows.append(deploy_payload)
        elif isinstance(payload, dict):
            # Some accounts return ``{"deploys": [...]}``.
            deploys = payload.get("deploys")
            if isinstance(deploys, list):
                for entry in deploys:
                    if isinstance(entry, dict):
                        rows.append(entry)

        return [_record_from_api(r, service_id=service_id) for r in rows]

    def get_service(self, service_id: str) -> dict[str, Any]:
        """Fetch service metadata (slug, name, type) for UI labeling."""
        if not self.enabled:
            raise RenderDeployClientError(
                "RenderDeployClient.get_service called with no RENDER_API_KEY"
            )
        url = f"{self._base_url}/services/{service_id}"
        try:
            resp = httpx.get(url, headers=self._headers(), timeout=self._timeout_s)
        except httpx.HTTPError as exc:
            raise RenderDeployClientError(
                f"Render API network error fetching service {service_id}: {exc}"
            ) from exc
        if resp.status_code >= 400:
            raise RenderDeployClientError(
                f"Render API {resp.status_code} fetching service {service_id}: {resp.text[:200]}"
            )
        try:
            return resp.json() or {}
        except ValueError as exc:
            raise RenderDeployClientError(
                f"Render API returned non-JSON for service {service_id}: {exc}"
            ) from exc


__all__ = [
    "IN_FLIGHT_STATUSES",
    "RENDER_API_BASE",
    "SUPERSEDED_STATUSES",
    "TERMINAL_FAILURE_STATUSES",
    "TERMINAL_SUCCESS_STATUSES",
    "DeployRecord",
    "RenderDeployClient",
    "RenderDeployClientError",
]
