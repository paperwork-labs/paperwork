"""Typed shapes for the polymorphic email parser.

These are *transport* types — they live between the preprocessor, the LLM
provider, and the parser orchestrator. They are NOT ORM rows. The candidate
generator (PR #328) is responsible for upserting these into the picks
database tables defined in PR #327 (`Candidate`, `EmailParse`,
`MacroOutlook`, `PositionChange`).

Conventions (enforced by tests):

- Decimal for all money / scores / percentages.
- timezone-aware UTC datetimes everywhere.
- Frozen dataclasses (immutable extracted records).
- Explicit `confidence` per item (0.0 - 1.0).
- `source_excerpt` on every record so audit trail is intact.

medallion: gold
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

# --------------------------------------------------------------------------- #
# Enums                                                                       #
# --------------------------------------------------------------------------- #


class PickActionHint(str, Enum):
    """Direction the LLM thinks the email is suggesting.

    Mirrors `app.models.picks.PickAction` (PR #327) but redeclared
    locally so this package is import-safe before that PR merges.
    """

    BUY = "buy"
    SELL = "sell"
    TRIM = "trim"
    ADD = "add"
    HOLD = "hold"
    AVOID = "avoid"
    UNKNOWN = "unknown"


class SourceFormat(str, Enum):
    """Which preprocessing path produced the parsed text."""

    PLAIN_TEXT = "plain_text"
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    FORWARDED_EMAIL = "forwarded_email"


# --------------------------------------------------------------------------- #
# Extracted records                                                           #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ExtractedPick:
    """One ticker-level recommendation extracted from the email."""

    symbol: str  # uppercased, validated against /^[A-Z][A-Z0-9.\-]{0,9}$/
    action: PickActionHint
    confidence: Decimal  # 0.0 - 1.0; LLM self-rating clamped server-side
    rationale: str  # short, <500 chars
    target_price: Decimal | None = None
    stop_loss: Decimal | None = None
    horizon_days: int | None = None  # holding period suggestion
    source_excerpt: str = ""  # verbatim quote anchoring the extraction
    source_format: SourceFormat = SourceFormat.PLAIN_TEXT


@dataclass(frozen=True)
class ExtractedMacro:
    """Macro/market-wide outlook (regime call, sector tilt, risk-off, etc.)."""

    headline: str  # one-line summary
    body: str  # supporting text from the email
    sentiment: Decimal  # -1.0 (bearish) .. +1.0 (bullish)
    confidence: Decimal
    sectors: tuple[str, ...] = field(default_factory=tuple)  # ETF symbols / GICS names
    horizon_days: int | None = None
    source_excerpt: str = ""
    source_format: SourceFormat = SourceFormat.PLAIN_TEXT


@dataclass(frozen=True)
class ExtractedPositionChange:
    """The validator says they personally changed a position.

    Used to log validator behavior for the engagement tracker (see PR #327
    `PickEngagement`). Distinct from `ExtractedPick` because this is
    *historical* (already done) vs *forward-looking* (suggesting).
    """

    symbol: str
    action: PickActionHint
    quantity_hint: Decimal | None = None  # rough size if mentioned
    occurred_at_hint: datetime | None = None  # timezone-aware UTC
    confidence: Decimal = Decimal("0.5")
    source_excerpt: str = ""
    source_format: SourceFormat = SourceFormat.PLAIN_TEXT


# --------------------------------------------------------------------------- #
# Validation / clamp helpers                                                  #
# --------------------------------------------------------------------------- #


_VALID_SYMBOL_PATTERN = "^[A-Z][A-Z0-9.\\-]{0,9}$"  # documented; checked in preprocessor


def clamp_confidence(value) -> Decimal:
    """Clamp confidence to [0, 1] as Decimal.

    LLMs sometimes emit 1.5 or 0.05 erroneously; we hard-clamp before
    persisting so downstream queries can rely on the invariant.
    """
    try:
        d = Decimal(str(value))
    except Exception:
        return Decimal("0")
    if d < Decimal("0"):
        return Decimal("0")
    if d > Decimal("1"):
        return Decimal("1")
    return d


def clamp_sentiment(value) -> Decimal:
    """Clamp sentiment to [-1, 1] as Decimal."""
    try:
        d = Decimal(str(value))
    except Exception:
        return Decimal("0")
    if d < Decimal("-1"):
        return Decimal("-1")
    if d > Decimal("1"):
        return Decimal("1")
    return d


# Whitelist of common forwarded-from addresses we treat as analyst sources;
# the parser records the actual sender for audit but uses this to bias the
# system prompt selection. Real list lives in DB once PR #327 lands.
KNOWN_ANALYST_DOMAINS: frozenset[str] = frozenset(
    {
        # placeholder, intentionally empty — populated via env / DB at deploy.
    }
)
