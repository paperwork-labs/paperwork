"""
Provider Quorum & Drift Detection Models
========================================

Data quality layer for the market data pipeline. Sits BEFORE values land
in ``MarketSnapshot`` / ``PriceData`` and answers two questions:

1. **Quorum** -- when N providers return a value for the same field,
   do at least ``ceil(threshold * N)`` of them agree within tolerance?
   If yes, we have a trusted ``quorum_value``. If no, we log a
   ``DISAGREEMENT`` row and refuse to silently pick one (R32, R34, R38
   class of bugs: silent fallbacks make broken systems look healthy).
2. **Drift** -- does a single provider's value sit outside its own
   recent ``mean +/- 3 sigma`` range? That signals that the provider
   has changed its calculation, broken its feed, or is rate-limiting
   us into a stale cache. Per-provider, not per-field-of-truth.

Both tables are global infra (no ``user_id``). They are read by the
admin Data Quality dashboard and by the auto-ops health agent.

Decimal everywhere -- this is provider-vs-provider price/volume
comparison and float drift would invent disagreements that don't exist.
"""

from __future__ import annotations

import enum
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from . import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class QuorumStatus(str, enum.Enum):
    """Outcome of a single quorum check.

    * ``QUORUM_REACHED`` -- enough providers agreed within tolerance and
      ``quorum_value`` is set.
    * ``DISAGREEMENT`` -- providers diverged beyond tolerance; no
      trustworthy value. Caller MUST treat this as "no value
      available", never silently pick one.
    * ``INSUFFICIENT_PROVIDERS`` -- fewer than 2 providers returned a
      value. We can't compute a quorum from one source.
    * ``SINGLE_SOURCE`` -- exactly 1 provider configured / queried for
      this field. Logged so we can spot fields that need a second
      source added.
    """

    QUORUM_REACHED = "QUORUM_REACHED"
    DISAGREEMENT = "DISAGREEMENT"
    INSUFFICIENT_PROVIDERS = "INSUFFICIENT_PROVIDERS"
    SINGLE_SOURCE = "SINGLE_SOURCE"


class QuorumAction(str, enum.Enum):
    """What the caller did with the quorum result.

    Distinct from ``status`` so that we can tell, for example, that a
    ``DISAGREEMENT`` was ``FLAGGED_FOR_REVIEW`` rather than silently
    ``ACCEPTED``. If you ever see ``ACCEPTED`` paired with
    ``DISAGREEMENT``, that's a regression in the calling code -- fix
    the caller, don't paper over it here.
    """

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    FLAGGED_FOR_REVIEW = "FLAGGED_FOR_REVIEW"


# Postgres-side enum type names (must match the migration).
QUORUM_STATUS_ENUM_NAME = "provider_quorum_status_enum"
QUORUM_ACTION_ENUM_NAME = "provider_quorum_action_enum"


# Default quorum threshold: 2 of 3 providers. Must be exactly two
# thirds -- ``Decimal("0.667")`` is slightly *above* 2/3, so comparing
# ``agreeing_count / R >= threshold`` would reject a valid 2-of-3
# quorum. Numeric(4,3) still rounds stored values for display; runtime
# comparisons use this exact fraction. Centralised so the migration's
# server_default, the model default, and the QuorumService default stay
# aligned on intent.
DEFAULT_QUORUM_THRESHOLD = Decimal("2") / Decimal("3")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ProviderQuorumLog(Base):
    """One row per quorum check.

    Sampled (not on every read) -- writing one row per market-data fetch
    would dominate insert volume. The hourly scheduled task samples ~5%
    of recent ``MarketSnapshot`` writes for cross-provider validation.
    Ad-hoc callers (e.g., an operator-driven re-check) may also write
    here.
    """

    __tablename__ = "provider_quorum_log"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    # e.g., "LAST_PRICE", "VOLUME", "MARKET_CAP", "EPS". Stored as text
    # rather than an enum so adding a new field doesn't require an
    # Alembic migration.
    field_name = Column(String(64), nullable=False, index=True)
    check_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    # JSONB so we can index/filter on ``providers_queried->>'fmp'`` if
    # a provider drifts catastrophically. Shape: {provider_name:
    # decimal_string_or_null}.
    providers_queried = Column(JSONB, nullable=False)
    quorum_value = Column(Numeric(precision=24, scale=10), nullable=True)
    quorum_threshold = Column(
        Numeric(precision=4, scale=3),
        nullable=False,
        default=DEFAULT_QUORUM_THRESHOLD,
        server_default="0.667",
    )
    status = Column(
        PgEnum(
            QuorumStatus,
            name=QUORUM_STATUS_ENUM_NAME,
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        index=True,
    )
    # Largest pairwise spread across providers, expressed as a fraction
    # of the median (e.g., 0.012 = 1.2%). NULL when only one provider
    # responded.
    max_disagreement_pct = Column(Numeric(precision=10, scale=6), nullable=True)
    action_taken = Column(
        PgEnum(
            QuorumAction,
            name=QUORUM_ACTION_ENUM_NAME,
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_provider_quorum_status_check_at", "status", "check_at"),
        Index(
            "uq_provider_quorum_symbol_field_check_at",
            "symbol",
            "field_name",
            "check_at",
            unique=True,
        ),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Wire-shape used by the admin Data Quality endpoints."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "field_name": self.field_name,
            "check_at": self.check_at.isoformat() if self.check_at else None,
            "providers_queried": self.providers_queried,
            "quorum_value": (
                str(self.quorum_value) if self.quorum_value is not None else None
            ),
            "quorum_threshold": str(self.quorum_threshold),
            "status": self.status.value if self.status else None,
            "max_disagreement_pct": (
                str(self.max_disagreement_pct)
                if self.max_disagreement_pct is not None
                else None
            ),
            "action_taken": self.action_taken.value if self.action_taken else None,
        }


class ProviderDriftAlert(Base):
    """One row per detected per-provider drift event.

    A drift event means *one* provider's value is outside its own
    recent statistical envelope. That's narrower than a quorum
    DISAGREEMENT (which says "providers don't agree with each other")
    -- a drift alert says "this one provider has changed". We use it to
    rotate priority in ``ProviderRouter`` and to surface "needs human
    review" cards in the admin dashboard.

    Resolution is operator-driven (``POST .../resolve``). We store the
    note so future audits can answer "why was provider X flagged on
    2026-04-12 and what did we do about it?".
    """

    __tablename__ = "provider_drift_alerts"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    field_name = Column(String(64), nullable=False)
    provider = Column(String(64), nullable=False, index=True)
    # Shape: {"mean": "...", "stddev": "...", "lower": "...",
    # "upper": "...", "n_samples": int, "window_days": int}. JSONB so we
    # can evolve the envelope (e.g., add MAD-based bounds) without a
    # migration.
    expected_range = Column(JSONB, nullable=False)
    actual_value = Column(Numeric(precision=24, scale=10), nullable=False)
    # Signed: positive means "above the expected band", negative means
    # "below". (actual - mean) / mean. NULL is impossible by
    # construction (we only insert when |z| >= threshold).
    deviation_pct = Column(Numeric(precision=10, scale=6), nullable=False)
    alert_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True, index=True)
    resolution_note = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_provider_drift_open", "resolved_at", "alert_at"),
    )

    def is_open(self) -> bool:
        return self.resolved_at is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "field_name": self.field_name,
            "provider": self.provider,
            "expected_range": self.expected_range,
            "actual_value": str(self.actual_value),
            "deviation_pct": str(self.deviation_pct),
            "alert_at": self.alert_at.isoformat() if self.alert_at else None,
            "resolved_at": (
                self.resolved_at.isoformat() if self.resolved_at else None
            ),
            "resolution_note": self.resolution_note,
            "is_open": self.is_open(),
        }
