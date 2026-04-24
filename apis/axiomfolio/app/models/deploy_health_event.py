"""DeployHealthEvent — one observed Render deploy transition.

G28 deploy-health guardrail (D120). The Beat poller inserts one row per
deploy state change per service; the admin-health composite queries the
last N rows per service to decide the ``deploys`` dimension colour.

Why a write-only event log (not a latest-only row per service):

* Deploy failures cluster in time (see 2026-04-20 midnight-merge-storm:
  7 consecutive build_failed inside one hour). Storing each event lets
  the dimension surface *consecutive failures* and *failures in 24h*
  honestly — a single "latest status" would hide the flap.
* The UI timeline needs the sequence to render.
* Event-log rows are append-only, which maps naturally onto idempotent
  poll behaviour: (service_id, deploy_id) is unique, so a second poll
  that sees the same deploy short-circuits.

A future migration can add a ``DeployHealthSummary`` latest-only table
materialised off this log if query volume requires it.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from . import Base


class DeployHealthEvent(Base):
    """One observed Render deploy (terminal or in-flight snapshot)."""

    __tablename__ = "deploy_health_events"

    id = Column(Integer, primary_key=True, index=True)

    # Render service id (e.g., ``srv-d64mkqi4d50c73eite20``).
    service_id = Column(String(64), nullable=False, index=True)

    # Stable slug (``axiomfolio-api``) denormalised for UI + alerts so the
    # admin route doesn't need a second Render API call just to render a
    # human-readable name.
    service_slug = Column(String(128), nullable=False, default="")

    # ``web_service`` | ``background_worker`` | ``cron_job`` | ``static_site``.
    service_type = Column(String(32), nullable=False, default="")

    deploy_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    trigger = Column(String(64), nullable=True)

    commit_sha = Column(String(64), nullable=True, index=True)
    # Render sends the full commit message; we truncate at the edge because
    # the admin UI only renders the first line anyway.
    commit_message = Column(Text, nullable=True)

    # Render-reported timestamps, not our clock.
    render_created_at = Column(DateTime(timezone=True), nullable=False)
    render_finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # ``True`` for ``poll_error`` synthetic rows (network/auth failure).
    # We still write a row so the admin dim can say "last poll failed"
    # instead of silently showing stale data.
    is_poll_error = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )
    poll_error_message = Column(Text, nullable=True)

    polled_at = Column(
        DateTime(timezone=True),
        nullable=False,
        # Use timezone-aware UTC to match the ``DateTime(timezone=True)``
        # column; ``datetime.utcnow()`` is naive and produced psycopg2 mixed
        # naive/aware comparisons depending on session settings.
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        # One row per (service, deploy) — repeat polls of the same deploy
        # in the same terminal state should short-circuit at insert time.
        UniqueConstraint(
            "service_id",
            "deploy_id",
            "status",
            name="uq_deploy_health_service_deploy_status",
        ),
        # Primary dimension-query path: last N rows per service by created.
        Index(
            "ix_deploy_health_service_created",
            "service_id",
            "render_created_at",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<DeployHealthEvent id={self.id} service={self.service_slug} "
            f"deploy={self.deploy_id} status={self.status}>"
        )
