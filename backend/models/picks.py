"""
Picks Pipeline Models
=====================

Data layer for the v1 "Validated Picks" product. The picks pipeline ingests
unstructured signals (validator emails, X threads, system-generated
candidates) and lands a curated, attributable set of buy/sell/trim/add
recommendations the user can read or auto-execute.

Pipeline overview::

    EmailInbox ─┐
                ├─► EmailParse (LLM output, 1:N schemas) ─┐
    XThread ────┘                                         │
                                                          ▼
    Candidate (system-generated) ─────────► ValidatedPick ◄── Validator UI
                                                  │
                                                  ├─► PickEngagement (per-user)
                                                  └─► SourceAttribution (N:M provenance)

Two ancillary outputs of the same parser feed sibling tables so they can
be queried independently of any single pick:

* ``MacroOutlook`` — "I think we're in R3" from a validator email.
* ``PositionChange`` — "Trim 25% of XYZ", standalone from any pick.

Per ``engineering.mdc``:

* Sessions are passed in by callers; nothing here opens connections.
* All monetary values use ``Decimal`` (Numeric) — never ``float``.
* All datetime columns are timezone-aware.
* Multi-tenancy is enforced at the row level via ``user_id`` on tables
  that are user-specific (``PickEngagement``). Picks themselves are
  global (one curator publishes for all subscribers) but engagement is
  per-user.

Pseudonym discipline (validator-curator.mdc): the curator's real
identity lives only on the ``User`` row that owns the pick; everything
visible to other users uses ``ValidatedPick.validator_pseudonym``
(default "Twisted Slice"). The pseudonym mapping is enforced at the
service layer, not at the model layer, so an operator can run multiple
validators in the future.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    Column,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    TIMESTAMP,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import Base


# =============================================================================
# ENUMS
# =============================================================================


class PickAction(str, Enum):
    """User-visible action for a pick. ``TRIM``/``ADD`` are first-class so
    the rebalance + sizing engines can branch on them without parsing
    free-text rationale (per master plan)."""

    BUY = "buy"
    SELL = "sell"
    TRIM = "trim"
    ADD = "add"
    HOLD = "hold"
    EXIT = "exit"  # Sell the entire position; distinct from SELL of a slice


class PickStatus(str, Enum):
    """Lifecycle of a pick in the validator queue."""

    DRAFT = "draft"  # Validator has not published yet
    PUBLISHED = "published"  # Visible to subscribers
    EXPIRED = "expired"  # Past validity_window
    SUPERSEDED = "superseded"  # Newer pick replaces this one
    RETRACTED = "retracted"  # Validator pulled it back


class EmailParseStatus(str, Enum):
    PENDING = "pending"
    OK = "ok"
    FAILED = "failed"
    PARTIAL = "partial"  # Some schemas matched, some did not


class IngestionStatus(str, Enum):
    """Lifecycle for raw inbound email rows (``EmailInbox`` ingestion + parse)."""

    RECEIVED = "RECEIVED"
    PARSE_PENDING = "PARSE_PENDING"
    PARSED = "PARSED"
    PARSE_FAILED = "PARSE_FAILED"


class CandidateQueueState(str, Enum):
    """Validator queue lifecycle for a ``Candidate`` row."""

    DRAFT = "draft"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"


class EngagementType(str, Enum):
    """Per-user interaction with a pick. Drives relevance scoring and the
    "pick conversion" funnel metric in the dashboard."""

    VIEWED = "viewed"
    DISMISSED = "dismissed"
    SNOOZED = "snoozed"
    EXECUTED = "executed"
    PARTIAL_EXECUTED = "partial_executed"


class SourceType(str, Enum):
    """The provenance category for ``SourceAttribution``."""

    EMAIL = "email"
    X_POST = "x_post"
    NEWS_ARTICLE = "news_article"
    PDF_ATTACHMENT = "pdf_attachment"
    PDF_IMAGE = "pdf_image"
    SYSTEM_CANDIDATE = "system_candidate"
    MANUAL = "manual"


# =============================================================================
# INGESTION: EmailInbox + EmailParse
# =============================================================================


class EmailInbox(Base):
    """Raw incoming email from one of our trusted senders.

    The body is stored verbatim because:

    1. The LLM parser may need to be re-run with a new schema as we tune
       the prompt; we cannot re-fetch the email.
    2. Attribution links from a pick back to the source email must keep
       working even after the upstream mailbox prunes.

    PDFs and inline images are stored separately in object storage; this
    table only carries pointers (``attachments_meta``).
    """

    __tablename__ = "email_inbox"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(255), unique=True, nullable=False, index=True)
    source_label = Column(String(64), nullable=False, index=True)
    sender = Column(String(255), nullable=False, index=True)
    recipients = Column(JSON, nullable=True)
    subject = Column(Text, nullable=True)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    received_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    has_pdf = Column(
        Boolean, nullable=False, default=False, server_default=sa.text("false")
    )
    attachment_count = Column(
        Integer, nullable=False, default=0, server_default=sa.text("0")
    )
    attachments_meta = Column(JSON, nullable=True)
    raw_blob_url = Column(String(512), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    ingestion_status = Column(
        String(32),
        nullable=False,
        server_default="RECEIVED",
    )
    ingested_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    parses = relationship(
        "EmailParse",
        back_populates="email",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_email_inbox_source_received", "source_label", "received_at"),
        Index("ix_email_inbox_sender_received", "sender", "received_at"),
    )


class EmailParse(Base):
    """One LLM parsing attempt against an email under a specific schema.

    A single email may produce multiple parses (e.g. one against the
    ``picks_v1`` schema, another against the ``macro_outlook_v1``
    schema). This 1:N pattern lets us evolve schemas independently
    without invalidating prior runs.
    """

    __tablename__ = "email_parses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(
        Integer,
        ForeignKey("email_inbox.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schema_version = Column(String(64), nullable=False)
    parser_model = Column(String(64), nullable=False)
    parser_provider = Column(String(32), nullable=True)
    parser_cost_usd = Column(Numeric(10, 6), nullable=True)
    parser_tokens_in = Column(Integer, nullable=True)
    parser_tokens_out = Column(Integer, nullable=True)
    raw_response = Column(JSON, nullable=True)
    structured_output = Column(JSON, nullable=True)
    status = Column(
        SQLEnum(
            EmailParseStatus,
            values_callable=lambda x: [m.value for m in EmailParseStatus],
            native_enum=False,
            length=16,
            name="email_parse_status",
        ),
        nullable=False,
        server_default=EmailParseStatus.PENDING.value,
    )
    error_message = Column(Text, nullable=True)
    parsed_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    email = relationship("EmailInbox", back_populates="parses")
    picks = relationship("ValidatedPick", back_populates="source_parse")
    sourced_candidates = relationship(
        "Candidate",
        back_populates="source_email_parse",
        foreign_keys="Candidate.source_email_parse_id",
    )

    __table_args__ = (
        UniqueConstraint(
            "email_id",
            "schema_version",
            "parser_model",
            name="uq_email_parse_schema_model",
        ),
        Index("ix_email_parse_status_parsed", "status", "parsed_at"),
    )


# =============================================================================
# CANDIDATES (system-generated)
# =============================================================================


class Candidate(Base):
    """A system-generated trade candidate awaiting validator review.

    Generated by ``CandidateGenerator`` (e.g. "Stage 2A + RS Mansfield > 70
    + insider buying") and persisted so the validator's queue is
    deterministic and the funnel from candidate → published pick is
    measurable.
    """

    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    generator_name = Column(String(64), nullable=False, index=True)
    generator_version = Column(String(32), nullable=False)
    score = Column(Numeric(10, 4), nullable=True)
    action_suggestion = Column(
        SQLEnum(
            PickAction,
            values_callable=lambda x: [m.value for m in PickAction],
            native_enum=False,
            length=16,
            name="pick_action",
        ),
        nullable=False,
    )
    signals = Column(JSON, nullable=True)
    rationale_summary = Column(Text, nullable=True)
    status = Column(
        SQLEnum(
            CandidateQueueState,
            values_callable=lambda x: [m.value for m in CandidateQueueState],
            native_enum=False,
            length=24,
            name="candidate_status",
        ),
        nullable=False,
        server_default=CandidateQueueState.DRAFT.value,
        index=True,
    )
    promoted_to_pick_id = Column(
        Integer, ForeignKey("validated_picks.id", ondelete="SET NULL"), nullable=True
    )
    generated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    decided_at = Column(TIMESTAMP(timezone=True), nullable=True)
    state_transitioned_at = Column(TIMESTAMP(timezone=True), nullable=True)
    state_transitioned_by = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    source_email_parse_id = Column(
        Integer,
        ForeignKey("email_parses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    suggested_target = Column(Numeric(18, 6), nullable=True)
    suggested_stop = Column(Numeric(18, 6), nullable=True)
    published_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    promoted_pick = relationship(
        "ValidatedPick", foreign_keys=[promoted_to_pick_id]
    )
    source_email_parse = relationship(
        "EmailParse",
        foreign_keys=[source_email_parse_id],
        back_populates="sourced_candidates",
    )

    __table_args__ = (
        Index("ix_candidates_symbol_generated", "symbol", "generated_at"),
        Index("ix_candidates_status_score", "status", "score"),
    )


class PicksAuditLog(Base):
    """Append-only audit of ``Candidate`` queue state transitions."""

    __tablename__ = "picks_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(
        Integer,
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_state = Column(String(24), nullable=False)
    to_state = Column(String(24), nullable=False)
    actor_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reason = Column(Text, nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    candidate = relationship("Candidate", backref="audit_entries")

    __table_args__ = (
        Index("ix_picks_audit_log_candidate_created", "candidate_id", "created_at"),
    )


# =============================================================================
# VALIDATED PICKS (the published product)
# =============================================================================


class ValidatedPick(Base):
    """The published product. One row per (validator, symbol, action,
    publish moment).

    A pick can come from three sources:

    1. ``source_email_parse_id`` set — extracted from a validator email.
    2. ``promoted_from_candidate_id`` set — system-generated candidate
       that the validator approved.
    3. Both null — the validator wrote a free-form pick directly in the
       UI.

    ``superseded_by_id`` links to a newer pick that replaces this one
    (e.g. "TRIM 25%" supersedes a prior "ADD 5%"). The active pick set
    is always: ``status = published AND superseded_by_id IS NULL AND
    expires_at > now()``.
    """

    __tablename__ = "validated_picks"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Provenance (at least one is typically set; both null = manual UI entry)
    source_email_parse_id = Column(
        Integer,
        ForeignKey("email_parses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    promoted_from_candidate_id = Column(
        Integer,
        ForeignKey("candidates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Validator
    validator_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    validator_pseudonym = Column(
        String(64), nullable=False, server_default="Twisted Slice"
    )

    # Pick body
    symbol = Column(String(20), nullable=False, index=True)
    action = Column(
        SQLEnum(
            PickAction,
            values_callable=lambda x: [m.value for m in PickAction],
            native_enum=False,
            length=16,
            name="pick_action",
        ),
        nullable=False,
    )
    conviction = Column(Integer, nullable=False, default=3, server_default=sa.text("3"))
    reason_summary = Column(Text, nullable=False)
    full_rationale = Column(Text, nullable=True)

    # Sizing & risk hints (advisory; OrderManager + RiskGate are still
    # the authoritative path on execute)
    suggested_entry = Column(Numeric(18, 6), nullable=True)
    suggested_stop = Column(Numeric(18, 6), nullable=True)
    suggested_target = Column(Numeric(18, 6), nullable=True)
    suggested_size_pct = Column(Numeric(6, 4), nullable=True)
    validity_window_days = Column(Integer, nullable=False, default=10)

    # Lifecycle
    status = Column(
        SQLEnum(
            PickStatus,
            values_callable=lambda x: [m.value for m in PickStatus],
            native_enum=False,
            length=16,
            name="pick_status",
        ),
        nullable=False,
        server_default=PickStatus.DRAFT.value,
        index=True,
    )
    published_at = Column(TIMESTAMP(timezone=True), nullable=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    superseded_by_id = Column(
        Integer,
        ForeignKey("validated_picks.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    source_parse = relationship("EmailParse", back_populates="picks")
    engagements = relationship(
        "PickEngagement",
        back_populates="pick",
        cascade="all, delete-orphan",
    )
    superseded_by = relationship(
        "ValidatedPick",
        remote_side="ValidatedPick.id",
        foreign_keys=[superseded_by_id],
    )

    __table_args__ = (
        Index("ix_picks_symbol_status_published", "symbol", "status", "published_at"),
        Index("ix_picks_status_expires", "status", "expires_at"),
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_active(self, now: Optional[datetime] = None) -> bool:
        """A pick is active if published, not superseded, and not expired."""
        if self.status != PickStatus.PUBLISHED:
            return False
        if self.superseded_by_id is not None:
            return False
        if self.expires_at is None:
            return True
        if now is None:
            now = datetime.now(self.expires_at.tzinfo)
        return now < self.expires_at


class PickEngagement(Base):
    """Per-user interaction with a pick.

    One row per (user, pick, type) so you can see "user X viewed but did
    not execute" vs "user X executed". The unique constraint also lets us
    upsert idempotently when the frontend retries view tracking.
    """

    __tablename__ = "pick_engagements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pick_id = Column(
        Integer,
        ForeignKey("validated_picks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    engagement_type = Column(
        SQLEnum(
            EngagementType,
            values_callable=lambda x: [m.value for m in EngagementType],
            native_enum=False,
            length=24,
            name="engagement_type",
        ),
        nullable=False,
    )
    metadata_json = Column("metadata", JSON, nullable=True)
    occurred_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    pick = relationship("ValidatedPick", back_populates="engagements")

    __table_args__ = (
        UniqueConstraint(
            "pick_id", "user_id", "engagement_type",
            name="uq_pick_engagement_user_type",
        ),
        Index("ix_pick_engagement_user_occurred", "user_id", "occurred_at"),
    )


# =============================================================================
# ATTRIBUTION + SIBLING SIGNALS
# =============================================================================


class SourceAttribution(Base):
    """N:M provenance link between a published artifact (pick / outlook /
    position change) and one or more source documents.

    We use a single denormalized table rather than three pairwise join
    tables because attribution is dominated by the same query
    ("show me everything that contributed to pick X") and three small
    tables make that query painful.
    """

    __tablename__ = "source_attributions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_kind = Column(String(32), nullable=False, index=True)
    artifact_id = Column(Integer, nullable=False)
    source_type = Column(
        SQLEnum(
            SourceType,
            values_callable=lambda x: [m.value for m in SourceType],
            native_enum=False,
            length=24,
            name="source_type",
        ),
        nullable=False,
    )
    source_url = Column(String(1024), nullable=True)
    source_email_id = Column(
        Integer,
        ForeignKey("email_inbox.id", ondelete="SET NULL"),
        nullable=True,
    )
    excerpt = Column(Text, nullable=True)
    confidence = Column(Numeric(4, 3), nullable=True)
    metadata_json = Column("metadata", JSON, nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_attribution_artifact", "artifact_kind", "artifact_id"),
        Index("ix_attribution_source_email", "source_email_id"),
    )


class MacroOutlook(Base):
    """A "I think we're in regime R3" call extracted from a validator
    email or written manually in the UI."""

    __tablename__ = "macro_outlooks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_email_parse_id = Column(
        Integer,
        ForeignKey("email_parses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    validator_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    validator_pseudonym = Column(
        String(64), nullable=False, server_default="Twisted Slice"
    )
    regime_call = Column(String(8), nullable=True)
    thesis = Column(Text, nullable=False)
    time_horizon_days = Column(Integer, nullable=True)
    confidence = Column(Numeric(4, 3), nullable=True)
    status = Column(
        SQLEnum(
            PickStatus,
            values_callable=lambda x: [m.value for m in PickStatus],
            native_enum=False,
            length=16,
            name="pick_status",
        ),
        nullable=False,
        server_default=PickStatus.DRAFT.value,
        index=True,
    )
    published_at = Column(TIMESTAMP(timezone=True), nullable=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_macro_outlook_published", "published_at"),
    )


class PositionChange(Base):
    """Standalone "trim X by 25%" guidance extracted from an email when
    it does not warrant a full ``ValidatedPick`` row.

    Keeping these separate from ``ValidatedPick`` lets the frontend
    render a tight "actions on positions you already hold" widget
    without scanning every pick row."""

    __tablename__ = "position_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_email_parse_id = Column(
        Integer,
        ForeignKey("email_parses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    validator_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    validator_pseudonym = Column(
        String(64), nullable=False, server_default="Twisted Slice"
    )
    symbol = Column(String(20), nullable=False, index=True)
    action = Column(
        SQLEnum(
            PickAction,
            values_callable=lambda x: [m.value for m in PickAction],
            native_enum=False,
            length=16,
            name="pick_action",
        ),
        nullable=False,
    )
    size_change_pct = Column(Numeric(6, 4), nullable=True)
    reason = Column(Text, nullable=False)
    status = Column(
        SQLEnum(
            PickStatus,
            values_callable=lambda x: [m.value for m in PickStatus],
            native_enum=False,
            length=16,
            name="pick_status",
        ),
        nullable=False,
        server_default=PickStatus.DRAFT.value,
        index=True,
    )
    published_at = Column(TIMESTAMP(timezone=True), nullable=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "ix_position_change_symbol_published",
            "symbol",
            "published_at",
        ),
    )
