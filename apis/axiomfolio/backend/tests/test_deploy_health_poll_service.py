"""Unit tests for ``backend.services.deploys.poll_service``.

Covers the end-to-end Beat path: an injected :class:`RenderDeployClient`
stub produces deploy records, ``poll_and_record`` writes events, and
:func:`summarize_service_health` / :func:`summarize_composite` reduce the
event log to an admin-dim payload with the colour + reason shape the UI
consumes.

This file is also the regression test for D120: the 2026-04-20
midnight-merge-storm scenario of 7 consecutive build_failed events must
flip the dimension red before the 8th deploy.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict

import pytest

from backend.models.deploy_health_event import DeployHealthEvent
from backend.services.deploys.poll_service import (
    FAILURE_24H_RED,
    FAILURE_24H_YELLOW,
    FAILURE_CONSECUTIVE_RED,
    poll_and_record,
    summarize_composite,
    summarize_service_health,
)
from backend.services.deploys.render_client import DeployRecord


@pytest.fixture
def SERVICE() -> Dict[str, str]:
    """Unique synthetic service per-test so ``(service_id, deploy_id, status)``
    unique constraint doesn't collide across tests that happen to share
    the DB connection when nested-transaction rollback misbehaves."""
    suffix = uuid.uuid4().hex[:8]
    return {
        "service_id": f"srv-api-{suffix}",
        "service_slug": f"axiomfolio-api-{suffix}",
        "service_type": "web_service",
    }


class _StubClient:
    """Minimal stub matching the public surface ``poll_and_record`` calls."""

    def __init__(self, records_by_service):
        self._records = records_by_service
        self.enabled = True
        self.calls: list[str] = []

    def list_deploys(self, service_id: str, *, limit: int = 10):
        self.calls.append(service_id)
        return list(self._records.get(service_id, []))


def _make_record(
    service: Dict[str, str],
    deploy_id: str,
    status: str,
    *,
    created: datetime,
    duration_s: float = 60.0,
    sha: str = "deadbeef",
) -> DeployRecord:
    return DeployRecord(
        service_id=service["service_id"],
        deploy_id=deploy_id,
        status=status,
        trigger="new_commit",
        commit_sha=sha,
        commit_message=f"{status} commit",
        created_at=created,
        finished_at=created + timedelta(seconds=duration_s),
        duration_seconds=duration_s,
    )


def _seed(
    db_session,
    service: Dict[str, str],
    deploy_id: str,
    status: str,
    *,
    minutes_ago: float,
    duration_s: float = 60.0,
    sha: str | None = None,
    finished: bool = True,
) -> None:
    now = datetime.now(timezone.utc)
    created_at = now - timedelta(minutes=minutes_ago)
    finished_at = (
        created_at + timedelta(seconds=duration_s) if finished else None
    )
    db_session.add(
        DeployHealthEvent(
            service_id=service["service_id"],
            service_slug=service["service_slug"],
            service_type=service["service_type"],
            deploy_id=deploy_id,
            status=status,
            trigger="new_commit",
            commit_sha=sha or deploy_id,
            commit_message=deploy_id,
            render_created_at=created_at,
            render_finished_at=finished_at,
            duration_seconds=duration_s if finished else None,
        )
    )


def test_poll_and_record_inserts_new_and_skips_duplicates(db_session, SERVICE):
    now = datetime.now(timezone.utc)
    records = [
        _make_record(SERVICE, "d-1", "live", created=now - timedelta(minutes=1)),
        _make_record(SERVICE, "d-2", "build_failed", created=now - timedelta(minutes=10)),
    ]
    client = _StubClient({SERVICE["service_id"]: records})

    first = poll_and_record(db_session, [SERVICE], client=client)
    db_session.commit()
    assert first["services_polled"] == 1
    assert first["events_inserted"] == 2
    assert first["events_skipped"] == 0
    assert first["poll_errors"] == 0

    client2 = _StubClient({SERVICE["service_id"]: records})
    second = poll_and_record(db_session, [SERVICE], client=client2)
    db_session.commit()
    assert second["events_inserted"] == 0
    assert second["events_skipped"] == 2

    rows = (
        db_session.query(DeployHealthEvent)
        .filter(DeployHealthEvent.service_id == SERVICE["service_id"])
        .order_by(DeployHealthEvent.id)
        .all()
    )
    assert {r.deploy_id for r in rows} == {"d-1", "d-2"}
    assert all(r.service_slug == SERVICE["service_slug"] for r in rows)


def test_poll_and_record_no_services_is_noop(db_session):
    result = poll_and_record(db_session, [], client=_StubClient({}))
    assert result["services_polled"] == 0
    assert result["events_inserted"] == 0


def test_poll_and_record_records_api_error_as_poll_error(db_session, SERVICE):
    class _BoomClient:
        enabled = True

        def list_deploys(self, *_a, **_kw):
            from backend.services.deploys.render_client import RenderDeployClientError
            raise RenderDeployClientError("Render 503")

    result = poll_and_record(db_session, [SERVICE], client=_BoomClient())
    db_session.commit()
    assert result["poll_errors"] == 1
    rows = (
        db_session.query(DeployHealthEvent)
        .filter(DeployHealthEvent.service_id == SERVICE["service_id"])
        .all()
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.is_poll_error is True
    assert row.status == "poll_error"
    assert "503" in (row.poll_error_message or "")


def test_poll_and_record_records_disabled_client_as_poll_error(db_session, SERVICE):
    class _Disabled:
        enabled = False

    result = poll_and_record(db_session, [SERVICE], client=_Disabled())
    db_session.commit()
    assert result["poll_errors"] == 1
    assert result["services_polled"] == 0
    rows = (
        db_session.query(DeployHealthEvent)
        .filter(DeployHealthEvent.service_id == SERVICE["service_id"])
        .all()
    )
    assert len(rows) == 1 and rows[0].is_poll_error is True


def test_summarize_empty_events_is_yellow_with_note(db_session, SERVICE):
    summary = summarize_service_health(db_session, SERVICE)
    assert summary.status == "yellow"
    assert "no deploy events" in summary.reason
    assert summary.consecutive_failures == 0
    assert summary.last_deploy_sha is None


def test_summarize_green_when_all_recent_live(db_session, SERVICE):
    for i in range(3):
        _seed(db_session, SERVICE, f"d-{i}", "live", minutes_ago=i * 10, sha=f"abc{i}")
    db_session.commit()

    summary = summarize_service_health(db_session, SERVICE)
    assert summary.status == "green"
    assert summary.consecutive_failures == 0
    assert summary.failures_24h == 0
    assert summary.last_live_sha == "abc0"


def test_midnight_merge_storm_flips_red_at_threshold(db_session, SERVICE):
    """D120 regression: 7 consecutive build_failed must be red."""
    # Newest first: d-0 is most recent.
    for i in range(7):
        _seed(db_session, SERVICE, f"d-{i}", "build_failed", minutes_ago=i * 10 + 1)
    db_session.commit()

    summary = summarize_service_health(db_session, SERVICE)
    assert summary.status == "red"
    assert summary.consecutive_failures >= FAILURE_CONSECUTIVE_RED
    assert summary.failures_24h >= FAILURE_24H_RED
    assert "failed deploys" in summary.reason


def test_yellow_when_live_after_storm_has_since_succeeded(db_session, SERVICE):
    """Live deploy after failure streak: consecutive resets, 24h still counts."""
    _seed(db_session, SERVICE, "d-0", "build_failed", minutes_ago=60)
    _seed(db_session, SERVICE, "d-1", "build_failed", minutes_ago=50)
    _seed(db_session, SERVICE, "d-2", "live", minutes_ago=10)
    db_session.commit()

    summary = summarize_service_health(db_session, SERVICE)
    assert summary.consecutive_failures == 0
    assert summary.failures_24h == 2
    assert summary.status == "yellow"
    assert summary.last_live_sha == "d-2"


def test_yellow_when_two_failures_in_24h(db_session, SERVICE):
    _seed(db_session, SERVICE, "d-0", "build_failed", minutes_ago=60)
    _seed(db_session, SERVICE, "d-1", "live", minutes_ago=30)
    _seed(db_session, SERVICE, "d-2", "build_failed", minutes_ago=20)
    _seed(db_session, SERVICE, "d-3", "live", minutes_ago=5)
    db_session.commit()
    summary = summarize_service_health(db_session, SERVICE)
    assert summary.failures_24h == FAILURE_24H_YELLOW
    assert summary.status == "yellow"


def test_summarize_composite_takes_worst(db_session, SERVICE):
    other = {
        "service_id": SERVICE["service_id"] + "-worker",
        "service_slug": SERVICE["service_slug"] + "-worker",
        "service_type": "background_worker",
    }
    _seed(db_session, SERVICE, "a-1", "live", minutes_ago=5, sha="aaaa")
    for i in range(4):
        _seed(
            db_session,
            other,
            f"b-{i}",
            "build_failed",
            minutes_ago=60 * (i + 1),
            duration_s=2.0,
        )
    db_session.commit()
    result = summarize_composite(db_session, [SERVICE, other])
    assert result["status"] == "red"
    assert len(result["services"]) == 2
    assert result["failures_24h_total"] >= FAILURE_24H_RED


def test_in_flight_status_reported_but_does_not_reset_consecutive(db_session, SERVICE):
    # Newest event (d-3) is in_progress; three failures precede it.
    _seed(db_session, SERVICE, "d-0", "build_failed", minutes_ago=30)
    _seed(db_session, SERVICE, "d-1", "build_failed", minutes_ago=20)
    _seed(db_session, SERVICE, "d-2", "build_failed", minutes_ago=10)
    _seed(
        db_session,
        SERVICE,
        "d-3",
        "build_in_progress",
        minutes_ago=2,
        finished=False,
    )
    db_session.commit()

    summary = summarize_service_health(db_session, SERVICE)
    assert summary.in_flight is True
    assert summary.consecutive_failures == 3
    assert summary.status == "red"
