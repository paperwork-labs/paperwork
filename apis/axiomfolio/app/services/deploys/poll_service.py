"""Deploy-health poll + summarise service layer.

Separated from :mod:`render_client` so Celery tasks and the health
dimension builder can depend on pure DB + record logic without pulling
``httpx`` for tests that don't need network.

Responsibilities:

* ``poll_and_record`` — given a Session and a list of Render service ids,
  fetch recent deploys for each, upsert ``DeployHealthEvent`` rows, emit
  structured counters (``no-silent-fallback.mdc``).
* ``summarize_service_health`` — pure function over DeployHealthEvent rows
  returning ``{status, consecutive_failures, failures_24h, last_status,
  last_live_sha, last_deploy_sha, last_deploy_at, ...}``. Used by both
  the admin dimension builder and the admin route.

medallion: ops
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.deploy_health_event import DeployHealthEvent

from .render_client import (
    IN_FLIGHT_STATUSES,
    SUPERSEDED_STATUSES,
    TERMINAL_FAILURE_STATUSES,
    TERMINAL_SUCCESS_STATUSES,
    DeployRecord,
    RenderDeployClient,
    RenderDeployClientError,
)

logger = logging.getLogger(__name__)

# Minimum number of recent rows the summary needs to reason about flaps.
_SUMMARY_WINDOW = 20

# Proportional thresholds — three consecutive terminal failures or four
# failures in 24h flips the dimension red. Two in 24h is yellow.
FAILURE_CONSECUTIVE_RED = 3
FAILURE_24H_RED = 4
FAILURE_24H_YELLOW = 2


@dataclass(frozen=True)
class ServiceHealthSummary:
    """Rollup of one Render service's recent deploy state."""

    service_id: str
    service_slug: str
    service_type: str
    status: str  # green | yellow | red
    reason: str
    last_status: str | None
    last_deploy_sha: str | None
    last_deploy_at: str | None
    last_live_sha: str | None
    last_live_at: str | None
    consecutive_failures: int
    failures_24h: int
    deploys_24h: int
    in_flight: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "service_id": self.service_id,
            "service_slug": self.service_slug,
            "service_type": self.service_type,
            "status": self.status,
            "reason": self.reason,
            "last_status": self.last_status,
            "last_deploy_sha": self.last_deploy_sha,
            "last_deploy_at": self.last_deploy_at,
            "last_live_sha": self.last_live_sha,
            "last_live_at": self.last_live_at,
            "consecutive_failures": self.consecutive_failures,
            "failures_24h": self.failures_24h,
            "deploys_24h": self.deploys_24h,
            "in_flight": self.in_flight,
        }


def _record_to_event(
    record: DeployRecord,
    *,
    service_slug: str,
    service_type: str,
) -> DeployHealthEvent:
    return DeployHealthEvent(
        service_id=record.service_id,
        service_slug=service_slug,
        service_type=service_type,
        deploy_id=record.deploy_id,
        status=record.status,
        trigger=record.trigger,
        commit_sha=record.commit_sha,
        commit_message=(record.commit_message or "")[:4000] or None,
        render_created_at=record.created_at,
        render_finished_at=record.finished_at,
        duration_seconds=record.duration_seconds,
        is_poll_error=False,
    )


def _upsert_event(db: Session, event: DeployHealthEvent) -> bool:
    """Insert ``event`` if (service_id, deploy_id, status) is new.

    Returns True when a row was inserted, False when it already existed.

    Uses a SAVEPOINT (``Session.begin_nested``) so that a duplicate row
    on one deploy id rolls back only this insert, not the rest of the
    poll cycle. Relying on the unique constraint instead of a
    SELECT-then-INSERT keeps parallel pollers race-free.
    """
    sp = db.begin_nested()
    db.add(event)
    try:
        sp.commit()
    except IntegrityError:
        sp.rollback()
        return False
    return True


def poll_and_record(
    db: Session,
    services: list[dict[str, str]],
    *,
    client: RenderDeployClient | None = None,
    limit_per_service: int = 10,
) -> dict[str, Any]:
    """Poll Render for recent deploys and record any new events.

    Args:
        db: SQLAlchemy session (caller owns the transaction).
        services: List of ``{"service_id": ..., "service_slug": ...,
            "service_type": ...}`` dicts — the services we observe.
        client: Injected RenderDeployClient (for tests). Default constructs
            one from ``settings.RENDER_API_KEY``.
        limit_per_service: Number of deploys to fetch per poll. 10 covers a
            10x merge storm between 5-minute ticks comfortably.

    Returns:
        Structured counters per ``no-silent-fallback.mdc``::

            {
                "services_polled": int,
                "events_inserted": int,
                "events_skipped": int,  # already in DB
                "poll_errors": int,
                "details": [{...per service...}],
            }

    Never raises — network/auth errors are caught and recorded as
    ``poll_error`` rows so the admin dim surfaces the gap.
    """
    client = client or RenderDeployClient()
    inserted = 0
    skipped = 0
    poll_errors = 0
    details: list[dict[str, Any]] = []

    if not services:
        logger.info("poll_and_record: no services configured — skipping")
        return {
            "services_polled": 0,
            "events_inserted": 0,
            "events_skipped": 0,
            "poll_errors": 0,
            "details": [],
        }

    if not client.enabled:
        logger.warning(
            "poll_and_record: RENDER_API_KEY not set — recording poll_error "
            "events so the admin dim surfaces the gap (fail-closed-but-observable)"
        )
        now = datetime.now(UTC)
        for svc in services:
            poll_errors += 1
            detail = {
                "service_id": svc.get("service_id"),
                "service_slug": svc.get("service_slug", ""),
                "polled": False,
                "error": "render_api_key_unset",
            }
            try:
                event = DeployHealthEvent(
                    service_id=str(svc.get("service_id") or ""),
                    service_slug=str(svc.get("service_slug") or ""),
                    service_type=str(svc.get("service_type") or ""),
                    deploy_id=f"poll-error-{int(now.timestamp())}",
                    status="poll_error",
                    trigger=None,
                    commit_sha=None,
                    commit_message=None,
                    render_created_at=now,
                    render_finished_at=now,
                    duration_seconds=0.0,
                    is_poll_error=True,
                    poll_error_message="RENDER_API_KEY unset — deploy-health observability disabled",
                )
                if _upsert_event(db, event):
                    inserted += 1
                else:
                    skipped += 1
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("failed to record poll_error event: %s", exc)
            details.append(detail)
        return {
            "services_polled": 0,
            "events_inserted": inserted,
            "events_skipped": skipped,
            "poll_errors": poll_errors,
            "details": details,
        }

    for svc in services:
        service_id = str(svc.get("service_id") or "")
        service_slug = str(svc.get("service_slug") or "")
        service_type = str(svc.get("service_type") or "")
        if not service_id:
            continue

        detail: dict[str, Any] = {
            "service_id": service_id,
            "service_slug": service_slug,
            "inserted": 0,
            "skipped": 0,
        }
        try:
            records = client.list_deploys(service_id, limit=limit_per_service)
        except RenderDeployClientError as exc:
            logger.warning(
                "deploy poll failed for %s (%s): %s",
                service_slug or service_id,
                service_id,
                exc,
            )
            poll_errors += 1
            now = datetime.now(UTC)
            event = DeployHealthEvent(
                service_id=service_id,
                service_slug=service_slug,
                service_type=service_type,
                deploy_id=f"poll-error-{int(now.timestamp())}",
                status="poll_error",
                trigger=None,
                commit_sha=None,
                commit_message=None,
                render_created_at=now,
                render_finished_at=now,
                duration_seconds=0.0,
                is_poll_error=True,
                poll_error_message=str(exc)[:2000],
            )
            if _upsert_event(db, event):
                inserted += 1
                detail["inserted"] = 1
            detail["error"] = str(exc)[:200]
            details.append(detail)
            continue

        per_service_inserted = 0
        per_service_skipped = 0
        for record in records:
            event = _record_to_event(
                record,
                service_slug=service_slug,
                service_type=service_type,
            )
            if _upsert_event(db, event):
                per_service_inserted += 1
            else:
                per_service_skipped += 1

        inserted += per_service_inserted
        skipped += per_service_skipped
        detail["inserted"] = per_service_inserted
        detail["skipped"] = per_service_skipped
        details.append(detail)

    logger.info(
        "deploy-health poll: services=%d inserted=%d skipped=%d errors=%d",
        len(services),
        inserted,
        skipped,
        poll_errors,
    )
    return {
        "services_polled": len(services),
        "events_inserted": inserted,
        "events_skipped": skipped,
        "poll_errors": poll_errors,
        "details": details,
    }


def _recent_events(
    db: Session,
    service_id: str,
    *,
    limit: int = _SUMMARY_WINDOW,
) -> list[DeployHealthEvent]:
    return (
        db.query(DeployHealthEvent)
        .filter(DeployHealthEvent.service_id == service_id)
        .order_by(DeployHealthEvent.render_created_at.desc(), DeployHealthEvent.id.desc())
        .limit(limit)
        .all()
    )


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def summarize_service_health(
    db: Session,
    service: dict[str, str],
    *,
    now: datetime | None = None,
) -> ServiceHealthSummary:
    """Build a ``ServiceHealthSummary`` for one Render service."""
    service_id = str(service.get("service_id") or "")
    service_slug = str(service.get("service_slug") or "")
    service_type = str(service.get("service_type") or "")

    events = _recent_events(db, service_id)
    now = now or datetime.now(UTC)
    cutoff_24h = now - timedelta(hours=24)

    if not events:
        return ServiceHealthSummary(
            service_id=service_id,
            service_slug=service_slug,
            service_type=service_type,
            status="yellow",
            reason="no deploy events recorded yet",
            last_status=None,
            last_deploy_sha=None,
            last_deploy_at=None,
            last_live_sha=None,
            last_live_at=None,
            consecutive_failures=0,
            failures_24h=0,
            deploys_24h=0,
            in_flight=False,
        )

    events_24h = [e for e in events if e.render_created_at and e.render_created_at >= cutoff_24h]

    # Only count terminal failures (build_failed, update_failed, canceled,
    # pre_deploy_failed, poll_error). ``deactivated`` is a normal supersede;
    # in_flight is neither success nor failure.
    def is_failure(ev: DeployHealthEvent) -> bool:
        if ev.is_poll_error:
            return True
        return ev.status in TERMINAL_FAILURE_STATUSES

    def is_live(ev: DeployHealthEvent) -> bool:
        return ev.status in TERMINAL_SUCCESS_STATUSES

    failures_24h = sum(1 for e in events_24h if is_failure(e))
    deploys_24h = sum(1 for e in events_24h if e.status not in {"poll_error"})

    consecutive = 0
    for ev in events:
        if ev.status in IN_FLIGHT_STATUSES or ev.status in SUPERSEDED_STATUSES:
            continue
        if is_failure(ev):
            consecutive += 1
        else:
            break

    in_flight = bool(events) and events[0].status in IN_FLIGHT_STATUSES

    last = events[0]
    last_status = last.status
    last_deploy_sha = last.commit_sha
    last_deploy_at = _iso(last.render_created_at)
    last_live = next((e for e in events if is_live(e)), None)
    last_live_sha = last_live.commit_sha if last_live else None
    last_live_at = _iso(last_live.render_finished_at) if last_live else None

    reasons: list[str] = []
    status = "green"
    if consecutive >= FAILURE_CONSECUTIVE_RED:
        status = "red"
        reasons.append(
            f"{consecutive} consecutive failed deploys (threshold {FAILURE_CONSECUTIVE_RED})"
        )
    elif failures_24h >= FAILURE_24H_RED:
        status = "red"
        reasons.append(f"{failures_24h} failed deploys in last 24h (threshold {FAILURE_24H_RED})")
    elif failures_24h >= FAILURE_24H_YELLOW:
        status = "yellow"
        reasons.append(
            f"{failures_24h} failed deploys in last 24h (threshold {FAILURE_24H_YELLOW})"
        )
    elif last_status in TERMINAL_FAILURE_STATUSES:
        # Single failure still worth flagging — we expect green
        # immediately after a successful deploy; amber until a subsequent
        # build succeeds.
        status = "yellow"
        reasons.append(f"last deploy {last_status}")

    if last.is_poll_error:
        status = "red" if status != "red" else status
        reasons.append("poll error — telemetry gap")

    if not reasons:
        reasons.append("all recent deploys healthy")

    return ServiceHealthSummary(
        service_id=service_id,
        service_slug=service_slug,
        service_type=service_type,
        status=status,
        reason="; ".join(reasons),
        last_status=last_status,
        last_deploy_sha=last_deploy_sha,
        last_deploy_at=last_deploy_at,
        last_live_sha=last_live_sha,
        last_live_at=last_live_at,
        consecutive_failures=consecutive,
        failures_24h=failures_24h,
        deploys_24h=deploys_24h,
        in_flight=in_flight,
    )


def summarize_composite(
    db: Session,
    services: Iterable[dict[str, str]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the composite-health ``deploys`` dimension payload.

    Composite rule:

    * ``red`` if any monitored service is red
    * ``yellow`` if any monitored service is yellow and none red
    * ``green`` otherwise (including the "no events yet" case, with an
      info string so the UI doesn't scream pre-first-deploy)
    """
    services_list = list(services)
    summaries: list[ServiceHealthSummary] = []
    for svc in services_list:
        summaries.append(summarize_service_health(db, svc, now=now))

    if not summaries:
        return {
            "status": "yellow",
            "reason": "no render services configured",
            "services": [],
            "services_configured": 0,
            "consecutive_failures_max": 0,
            "failures_24h_total": 0,
        }

    worst = "green"
    reasons: list[str] = []
    consecutive_max = 0
    failures_24h_total = 0
    for s in summaries:
        if s.status == "red":
            worst = "red"
        elif s.status == "yellow" and worst != "red":
            worst = "yellow"
        if s.status in ("red", "yellow"):
            reasons.append(f"{s.service_slug or s.service_id}: {s.reason}")
        consecutive_max = max(consecutive_max, s.consecutive_failures)
        failures_24h_total += s.failures_24h

    if not reasons:
        reasons.append("all monitored Render services deployed cleanly in last 24h")

    return {
        "status": worst,
        "reason": "; ".join(reasons),
        "services": [s.to_dict() for s in summaries],
        "services_configured": len(services_list),
        "consecutive_failures_max": consecutive_max,
        "failures_24h_total": failures_24h_total,
    }


__all__ = [
    "FAILURE_24H_RED",
    "FAILURE_24H_YELLOW",
    "FAILURE_CONSECUTIVE_RED",
    "ServiceHealthSummary",
    "poll_and_record",
    "summarize_composite",
    "summarize_service_health",
]
