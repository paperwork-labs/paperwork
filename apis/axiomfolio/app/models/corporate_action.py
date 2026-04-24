"""Corporate-action ledger.

Two tables:

* ``corporate_actions`` -- one row per (symbol, action_type, ex_date) that
  the fetcher discovers from a market-data provider. Authoritative source
  of *what happened to the symbol*.
* ``applied_corporate_actions`` -- one row per ``(corporate_action, user,
  position|tax_lot)`` that records what the applier actually did to a
  user's holdings. Stores the **original** quantity / cost basis so that
  the apply step is fully reversible without consulting a separate
  audit log.

Iron laws this schema enforces (see ``.cursor/rules/no-silent-fallback``
and ``engineering.mdc``):

1. **No silent overwrites** -- every write to ``positions`` /
   ``tax_lots`` produced by the engine has a matching
   ``applied_corporate_actions`` row pointing back to the source
   ``corporate_actions`` row.
2. **Decimal precision** -- ratios, cash amounts, and adjusted /
   original cost-basis values use ``Numeric(20, 8)``; the application
   layer wraps everything in ``decimal.Decimal``. No floats touch the
   adjustment math.
3. **Multi-tenancy** -- ``applied_corporate_actions.user_id`` is
   non-nullable; the applier scopes every batch by user id and uses
   per-user savepoints so that one tenant's failure can't taint
   another's adjustments.

The companion ``feat/wc-symbol-master`` PR introduces a
``symbol_master`` table. To avoid a cross-PR ordering constraint we
keep ``symbol_master_id`` here as a plain nullable ``Integer``
(no FK); the symbol-master PR can add the constraint in a later
migration once both branches have merged.
"""

from __future__ import annotations

import enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import Base


class CorporateActionType(str, enum.Enum):
    """Catalog of supported corporate-action types.

    String-backed (per ``engineering.mdc``: prefer ``String(N)`` columns
    over native PG enums so that adding a new variant doesn't require a
    blocking ``ALTER TYPE`` migration in production).
    """

    SPLIT = "split"  # forward stock split, ratio_numerator > ratio_denominator
    REVERSE_SPLIT = "reverse_split"  # ratio_numerator < ratio_denominator
    STOCK_DIVIDEND = "stock_dividend"  # bonus shares; treat like a small split
    CASH_DIVIDEND = "cash_dividend"  # cash distribution (does NOT change qty)
    SPECIAL_CASH_DIVIDEND = "special_cash_dividend"  # one-off cash div
    MERGER_STOCK = "merger_stock"  # stock-for-stock merger; new symbol issued
    MERGER_CASH = "merger_cash"  # cash buyout; closes the position
    SPINOFF = "spinoff"  # NB: not auto-applied in v1
    NAME_CHANGE = "name_change"  # ticker rename only
    SYMBOL_CHANGE = "symbol_change"  # alias for NAME_CHANGE


class CorporateActionSource(str, enum.Enum):
    FMP = "fmp"
    POLYGON = "polygon"
    MANUAL = "manual"  # admin-created via API


class CorporateActionStatus(str, enum.Enum):
    """Lifecycle state of a corporate action.

    ``PENDING`` -- fetched, not yet applied.
    ``APPLIED`` -- every eligible holding adjusted successfully.
    ``PARTIAL`` -- at least one user adjusted, at least one failed.
        The ``error_message`` column captures the failure detail.
    ``FAILED`` -- no successful applications.
    ``SKIPPED`` -- no holders found at ex_date (still recorded so we
        don't re-fetch / re-process the same action).
    ``REVERSED`` -- applier ran, then admin reversed it. The original
        ``applied_corporate_actions`` rows are deleted on reverse.
    """

    PENDING = "pending"
    APPLIED = "applied"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    REVERSED = "reversed"


class CorporateAction(Base):
    __tablename__ = "corporate_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    symbol = Column(String(20), nullable=False, index=True)
    # Forward-compatible link to the upcoming `symbol_master` table.
    # Intentionally no FK -- see module docstring.
    symbol_master_id = Column(Integer, nullable=True, index=True)

    action_type = Column(String(32), nullable=False)

    # The ex-date is the canonical "as of" date for adjustments:
    # any holding owned at the *close* of (ex_date - 1) is eligible.
    ex_date = Column(Date, nullable=False, index=True)
    record_date = Column(Date, nullable=True)
    payment_date = Column(Date, nullable=True)
    declaration_date = Column(Date, nullable=True)

    # Ratio is stored as numerator / denominator. For a 3-for-1 split:
    # numerator=3, denominator=1, qty multiplied by 3, cost-per-share / 3.
    # For a 1-for-10 reverse split: numerator=1, denominator=10.
    # For a stock dividend of 5%: numerator=21, denominator=20 (1.05x).
    ratio_numerator = Column(Numeric(20, 8), nullable=True)
    ratio_denominator = Column(Numeric(20, 8), nullable=True)

    # For cash dividends (per share) and cash mergers (per share).
    cash_amount = Column(Numeric(20, 8), nullable=True)
    cash_currency = Column(String(8), nullable=True, default="USD")

    # For mergers / spinoffs.
    target_symbol = Column(String(20), nullable=True)

    source = Column(String(16), nullable=False)
    source_ref = Column(String(128), nullable=True)  # provider's record id

    status = Column(
        String(16),
        nullable=False,
        default=CorporateActionStatus.PENDING.value,
        server_default=CorporateActionStatus.PENDING.value,
        index=True,
    )

    # True once HistoricalOhlcvAdjuster has back-adjusted price_data for
    # this action. Tracked separately from `status` because OHLCV
    # adjustment is gated by FEATURE_BACK_ADJUST_OHLCV and may run
    # later (or never) without affecting holding-level adjustments.
    ohlcv_adjusted = Column(Boolean, nullable=False, default=False)

    error_message = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    applied_at = Column(DateTime, nullable=True)

    applications = relationship(
        "AppliedCorporateAction",
        back_populates="corporate_action",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        # Idempotency anchor for the fetcher: re-fetching the same source
        # must not produce a duplicate row.
        UniqueConstraint(
            "symbol",
            "action_type",
            "ex_date",
            name="uq_corp_action_symbol_type_exdate",
        ),
        Index(
            "ix_corp_action_status_exdate",
            "status",
            "ex_date",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (
            f"<CorporateAction(id={self.id} {self.symbol} {self.action_type} "
            f"ex_date={self.ex_date} status={self.status})>"
        )


class AppliedCorporateAction(Base):
    __tablename__ = "applied_corporate_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    corporate_action_id = Column(
        Integer,
        ForeignKey("corporate_actions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # SET NULL on delete: if a user closes / deletes a position after
    # the adjustment, we keep the audit row so the action history is
    # complete. (Reversibility relies on `original_qty` /
    # `original_cost_basis` columns, not on the live position row.)
    position_id = Column(
        Integer,
        ForeignKey("positions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tax_lot_id = Column(
        Integer,
        ForeignKey("tax_lots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    symbol = Column(String(20), nullable=False)

    # Snapshots taken BEFORE the engine modified the row.
    original_qty = Column(Numeric(20, 8), nullable=False)
    original_cost_basis = Column(Numeric(20, 8), nullable=False)
    original_avg_cost = Column(Numeric(20, 8), nullable=True)

    adjusted_qty = Column(Numeric(20, 8), nullable=False)
    adjusted_cost_basis = Column(Numeric(20, 8), nullable=False)
    adjusted_avg_cost = Column(Numeric(20, 8), nullable=True)

    # For cash dividends / cash mergers: the gross cash credited to the
    # user (qty * cash_amount). Recorded for downstream accounting; the
    # applier itself does not write to AccountBalance.
    cash_credited = Column(Numeric(20, 8), nullable=True)

    applied_at = Column(DateTime, default=func.now(), nullable=False)

    corporate_action = relationship("CorporateAction", back_populates="applications")

    __table_args__ = (
        # Per-action, per-user, per-(position|lot) uniqueness. We want
        # to be able to apply once and only once per row so the applier
        # never double-counts on retry.
        UniqueConstraint(
            "corporate_action_id",
            "user_id",
            "position_id",
            "tax_lot_id",
            name="uq_applied_action_user_position_lot",
        ),
        Index(
            "ix_applied_action_user_symbol",
            "user_id",
            "symbol",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (
            f"<AppliedCorporateAction(id={self.id} action={self.corporate_action_id} "
            f"user={self.user_id} symbol={self.symbol})>"
        )
