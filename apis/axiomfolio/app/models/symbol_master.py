"""
Symbol Master
=============

Single source of truth for symbol identity across the platform.

The platform has historically resolved tickers ad-hoc — every service
that touches market data has its own symbol-string handling. That
falls apart the moment a real-world corporate action happens:

* FB renamed to META on 2022-06-09. Backtests, snapshot history,
  brokerage statements, and news feeds all need to know that
  "FB on 2022-06-08" and "META on 2022-06-10" are the *same*
  underlying entity.
* TWTR was acquired and rebranded to X. Tax lots from 2021 still
  reference TWTR; live quotes don't.
* GOOG -> GOOGL split. Two share classes for one issuer.

This module models that domain explicitly:

* ``SymbolMaster`` is the canonical row for an entity (Meta Platforms,
  Inc.). Its ``primary_ticker`` is whatever string the entity trades
  under *today*.
* ``SymbolAlias`` rows link historical or alternate tickers to the
  master. ``valid_from`` / ``valid_to`` form a half-open interval
  ``[valid_from, valid_to)`` so point-in-time resolution is
  unambiguous.
* ``SymbolHistory`` is an append-only audit ledger of changes
  (ticker rename, exchange migration, status flip, merger). Old and
  new values are JSON blobs so the schema does not have to enumerate
  every kind of change up-front.

Design notes
------------

* Enums are persisted as VARCHAR rather than as Postgres ENUM
  types. We've been bitten by PG ENUMs before — adding a value
  requires either ``ALTER TYPE`` (which can't run inside a
  transaction in some Postgres versions) or a fragile rebuild
  migration. Strings round-trip through Alembic without ceremony
  and are equally indexable.
* This table is *global* (no ``user_id``). Every downstream
  query that joins through it must remain user-scoped at the
  outer layer; see ``no-silent-fallback.mdc`` and the
  multi-tenancy section in ``engineering.mdc``.
* No FK migration on existing tables in this PR. Per the master
  plan, downstream callers move to the master in a follow-up.
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import Base


# =============================================================================
# ENUMS (persisted as VARCHAR — see module docstring)
# =============================================================================


class AssetClass(str, Enum):
    EQUITY = "EQUITY"
    ETF = "ETF"
    ADR = "ADR"
    MLP = "MLP"
    OPTION = "OPTION"
    FUTURE = "FUTURE"
    CRYPTO = "CRYPTO"
    INDEX = "INDEX"
    FOREX = "FOREX"
    BOND = "BOND"


class SymbolStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DELISTED = "DELISTED"
    MERGED = "MERGED"
    SUSPENDED = "SUSPENDED"


class AliasSource(str, Enum):
    TICKER_CHANGE = "TICKER_CHANGE"
    MERGER = "MERGER"
    SPINOFF = "SPINOFF"
    EXCHANGE_MIGRATION = "EXCHANGE_MIGRATION"
    MANUAL = "MANUAL"


class SymbolChangeType(str, Enum):
    TICKER_CHANGE = "TICKER_CHANGE"
    EXCHANGE_CHANGE = "EXCHANGE_CHANGE"
    NAME_CHANGE = "NAME_CHANGE"
    STATUS_CHANGE = "STATUS_CHANGE"
    MERGER = "MERGER"
    SPINOFF = "SPINOFF"
    SPLIT_RATIO_UPDATE = "SPLIT_RATIO_UPDATE"


# =============================================================================
# MODELS
# =============================================================================


class SymbolMaster(Base):
    """Canonical identity row for a tradeable entity.

    ``primary_ticker`` is the string the entity trades under today.
    All historical or alternate strings live in ``SymbolAlias``.
    """

    __tablename__ = "symbol_master"

    id = Column(Integer, primary_key=True, autoincrement=True)

    primary_ticker = Column(String(20), nullable=False, unique=True, index=True)

    # Stable cross-system identifiers. All optional because we'll often
    # bootstrap from a brokerage feed that only knows the ticker.
    cik = Column(String(20), nullable=True, index=True)
    isin = Column(String(20), nullable=True, index=True)
    figi = Column(String(20), nullable=True, index=True)

    asset_class = Column(String(20), nullable=False)  # AssetClass
    exchange = Column(String(20), nullable=True)
    country = Column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    currency = Column(String(3), nullable=True)  # ISO 4217

    name = Column(String(200), nullable=True)
    sector = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)
    gics_code = Column(String(20), nullable=True)

    status = Column(
        String(20),
        nullable=False,
        default=SymbolStatus.ACTIVE.value,
    )

    first_seen_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    delisted_at = Column(DateTime(timezone=True), nullable=True)

    # When this row was rolled up into another (e.g. acquired). Self-FK.
    merged_into_symbol_master_id = Column(
        Integer,
        ForeignKey("symbol_master.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    aliases = relationship(
        "SymbolAlias",
        back_populates="master",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    history = relationship(
        "SymbolHistory",
        back_populates="master",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    merged_into = relationship(
        "SymbolMaster",
        remote_side="SymbolMaster.id",
        foreign_keys=[merged_into_symbol_master_id],
    )

    __table_args__ = (
        Index("idx_symbol_master_asset_class_status", "asset_class", "status"),
        Index("idx_symbol_master_status", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return (
            f"<SymbolMaster id={self.id} ticker={self.primary_ticker!r} "
            f"asset_class={self.asset_class} status={self.status}>"
        )


class SymbolAlias(Base):
    """Historical or alternate ticker for a SymbolMaster row.

    ``[valid_from, valid_to)`` is a half-open interval. ``valid_to``
    NULL means "still valid / sticky" (used for legacy strings we
    want to keep resolving forever, e.g. references in old user
    notes or tax lots).
    """

    __tablename__ = "symbol_alias"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol_master_id = Column(
        Integer,
        ForeignKey("symbol_master.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias_ticker = Column(String(20), nullable=False, index=True)
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date, nullable=True)
    source = Column(String(30), nullable=False)  # AliasSource
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    master = relationship("SymbolMaster", back_populates="aliases")

    __table_args__ = (
        # Allow the same alias_ticker to be reused across masters
        # provided each (master, alias, valid_from) triple is unique.
        # This blocks accidental dup-inserts during reruns of the
        # initial-load script.
        UniqueConstraint(
            "symbol_master_id",
            "alias_ticker",
            "valid_from",
            name="uq_alias_master_ticker_from",
        ),
        Index("idx_symbol_alias_ticker_from", "alias_ticker", "valid_from"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return (
            f"<SymbolAlias id={self.id} ticker={self.alias_ticker!r} "
            f"valid_from={self.valid_from} valid_to={self.valid_to} "
            f"master_id={self.symbol_master_id}>"
        )


class SymbolHistory(Base):
    """Append-only audit ledger of changes to a SymbolMaster.

    ``old_value`` and ``new_value`` are JSON so the schema does not
    have to enumerate every change kind up-front. The ``change_type``
    enum is the discriminator.
    """

    __tablename__ = "symbol_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol_master_id = Column(
        Integer,
        ForeignKey("symbol_master.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    change_type = Column(String(30), nullable=False)  # SymbolChangeType
    # JSONB rather than JSON so equality comparisons (used by the
    # idempotency dedupe in `record_ticker_change`) work natively.
    # Postgres has no `=` operator for `json`, only `jsonb`.
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    effective_date = Column(Date, nullable=False, index=True)
    recorded_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # Free-form provenance label (e.g. "ticker_change_seed",
    # "ibkr_corporate_action", "manual_admin"). Keeping it free-form
    # avoids a second enum we'd have to evolve in lock-step with the
    # data sources.
    source = Column(String(30), nullable=False)

    master = relationship("SymbolMaster", back_populates="history")

    __table_args__ = (
        Index(
            "idx_symbol_history_master_effective",
            "symbol_master_id",
            "effective_date",
        ),
        Index("idx_symbol_history_change_type", "change_type"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return (
            f"<SymbolHistory id={self.id} master_id={self.symbol_master_id} "
            f"change_type={self.change_type} effective_date={self.effective_date}>"
        )
