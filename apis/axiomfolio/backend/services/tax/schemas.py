"""
FileFree.ai export schema (v1)
==============================

Stable wire format that AxiomFolio guarantees to FileFree.ai (or any other
downstream tax-prep consumer). Bump :data:`SCHEMA_VERSION` whenever a
breaking change is made and document the migration in
``docs/KNOWLEDGE.md``.

Why a separate schema (instead of returning ORM rows)?

* ORM models change for many reasons unrelated to tax filing -- column
  renames, relationship tweaks, internal flags. We do not want to break
  external consumers every time we refactor internals.
* Tax filing is a contract that, once shipped, must remain stable for a
  full filing year. A separate Pydantic model makes the contract
  machine-readable and the schema diff reviewable.
* The same schema feeds both the JSON export and the CSV export, which
  guarantees the two formats stay in sync.

Conventions:

* All monetary values are :class:`Decimal`, serialized as strings in JSON
  to avoid IEEE-754 round-tripping problems on the consumer side.
* All timestamps are timezone-aware UTC, serialized as ISO-8601 with the
  trailing ``Z`` stripped (Pydantic default).
* Enum values are lower-case snake_case strings so consumers can pattern
  match without import-coupling.

medallion: silver
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"


class LotTerm(str, Enum):
    """Holding-period classification per IRS rules."""

    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    UNKNOWN = "unknown"


class DataQuality(str, Enum):
    """How confident we are in a lot's reported numbers.

    ``broker_official`` lots come from the broker's own tax engine
    (IBKR FlexQuery closed-lot rows, Schwab 1099-B feed when wired, etc.)
    and can be filed as-is. ``calculated`` lots are derived in-app from
    open positions and average-cost arithmetic; they are good enough for
    estimates and harvesting decisions but the user should reconcile
    against the broker's own 1099-B before filing. ``unknown`` is the
    safe fallback when the source can't be determined.
    """

    BROKER_OFFICIAL = "broker_official"
    CALCULATED = "calculated"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class InstrumentType(str, Enum):
    EQUITY = "equity"
    OPTION = "option"
    ETF = "etf"
    OTHER = "other"


class FileFreeAccount(BaseModel):
    """One broker account that contributed lots to this export."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    account_ref: str = Field(
        ..., description="Stable opaque ref, format: '<broker>:<account_number>'"
    )
    broker: str = Field(..., description="Broker slug (e.g. 'ibkr', 'tastytrade')")
    account_type: str = Field(
        ..., description="taxable | ira | roth_ira | hsa | trust | business"
    )
    is_tax_advantaged: bool = Field(
        ..., description="True for IRA/Roth/HSA. FileFree should normally exclude."
    )
    lot_count: int = Field(..., ge=0)
    has_calculated_lots: bool = Field(
        False, description="True if any lot in this account is data_quality=calculated"
    )


class FileFreeLot(BaseModel):
    """A single closed lot ready to slot into IRS Form 8949."""

    model_config = ConfigDict(extra="forbid")

    lot_id: str = Field(
        ..., description="Stable per-export id, derived from account+execution"
    )
    account_ref: str
    symbol: str
    description: str = Field(..., description="Human-readable, e.g. 'AAPL (100 sh)'")
    instrument_type: InstrumentType = InstrumentType.EQUITY

    quantity: Decimal
    proceeds: Decimal = Field(..., description="Gross proceeds from sale, USD")
    cost_basis: Decimal = Field(..., description="Adjusted cost basis, USD")
    realized_gain: Decimal = Field(..., description="proceeds - cost_basis - adjustments")

    date_acquired: Optional[date] = Field(
        None, description="Lot acquisition date; None means 'VARIOUS'"
    )
    date_sold: date

    term: LotTerm
    is_wash_sale: bool = False
    wash_sale_disallowed_loss: Optional[Decimal] = Field(
        None, description="Positive number; only set when is_wash_sale is True"
    )
    adjustment_code: Optional[str] = Field(
        None,
        description="IRS Form 8949 adjustment code letter(s), e.g. 'W' for wash sale",
    )

    data_quality: DataQuality = DataQuality.UNKNOWN
    source: str = Field(..., description="Slug describing origin, e.g. 'ibkr_flexquery'")


class FileFreeSummary(BaseModel):
    """Roll-up totals matching the lots the consumer just received."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lot_count: int = Field(..., ge=0)
    total_proceeds: Decimal
    total_cost_basis: Decimal
    total_realized_gain: Decimal
    total_short_term_gain: Decimal
    total_long_term_gain: Decimal
    wash_sale_disallowed_total: Decimal


class FileFreePackage(BaseModel):
    """The full export envelope written to JSON or rendered to CSV."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=SCHEMA_VERSION, description="Wire format")
    generated_at: datetime = Field(..., description="UTC, when the export ran")
    tax_year: int = Field(..., ge=1900)
    user_id: int = Field(..., ge=1)
    accounts: List[FileFreeAccount]
    lots: List[FileFreeLot]
    summary: FileFreeSummary
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal advisories the consumer should surface to the user",
    )
