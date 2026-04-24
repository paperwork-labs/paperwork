"""
AutoOps Anomaly Explanation Model
=================================

Persisted output of :class:`app.services.agent.anomaly_explainer.AnomalyExplainer`
so the admin UI can poll a stable endpoint instead of re-running the LLM
on every render, and so we have an audit trail of what AutoOps told the
operator on each composite-health failure.

One row per ``(anomaly_id, generated_at)``. Anomaly ids are deterministic
per dimension+window (see :func:`anomaly_builder.deterministic_id`) so a
flapping dimension produces a small, queryable history rather than an
unbounded fan-out.

Storage choices:

* ``payload_json`` holds the full :class:`Explanation` dict from
  :func:`explanation_to_dict` (steps, runbook excerpts, narrative,
  confidence as string, ...). This means schema evolution lives entirely
  inside the dataclass / serializer; no Alembic columns to chase when a
  new step field appears.
* The flat columns (``category``, ``severity``, ``confidence``,
  ``is_fallback``, ``model``) are denormalized copies of the most useful
  fields so the list view can sort/filter without parsing JSON in
  Postgres on every request.
* ``Numeric(4, 3)`` for confidence to preserve the explainer's Decimal
  output without IEEE-754 surprises.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)

from . import Base


class AutoOpsExplanation(Base):
    """One AnomalyExplainer output, persisted for audit + UI surfacing."""

    __tablename__ = "auto_ops_explanations"

    id = Column(Integer, primary_key=True, index=True)

    # Nullable: system / Celery persist rows with no tenant; MCP tools scope
    # to ``user_id == authenticated user`` and must not surface other users.
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    schema_version = Column(String(16), nullable=False)
    anomaly_id = Column(String(128), nullable=False, index=True)
    category = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)

    confidence = Column(Numeric(4, 3), nullable=False)
    is_fallback = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )
    model = Column(String(64), nullable=False)

    payload_json = Column(JSON, nullable=False)

    generated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        # Fast "latest explanation per anomaly" reads for the admin UI
        # poll endpoint. Composite index avoids a sort + filter scan.
        Index(
            "ix_auto_ops_explanations_anomaly_generated",
            "anomaly_id",
            "generated_at",
        ),
        Index(
            "ix_auto_ops_explanations_category_generated",
            "category",
            "generated_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AutoOpsExplanation id={self.id} anomaly_id={self.anomaly_id} "
            f"category={self.category} confidence={self.confidence} "
            f"fallback={self.is_fallback}>"
        )
