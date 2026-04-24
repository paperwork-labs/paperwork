"""Polymorphic LLM-based parser for analyst/validator emails.

The "Validated Picks" pipeline (see app/models/picks.py in PR #327)
ingests three very different shapes of input from one inbox:

    1. Plain markdown writeups composed by the validator.
    2. Verbatim forwards of analyst emails (HTML, often deeply nested).
    3. PDF attachments with charts/tables/images.

A template-based parser cannot survive that variety. Instead we use a
two-stage pipeline:

    raw RFC822 -> EmailPreprocessor -> NormalizedEmail
                                            |
                                            v
                              PolymorphicEmailParser (LLMProvider)
                                            |
                                            v
                              ParseResult
                                  - extracted_picks: list[ExtractedPick]
                                  - extracted_macro: list[ExtractedMacro]
                                  - extracted_position_changes: list[...]
                                  - confidence: float
                                  - parse_errors: list[str]

The LLM call is gated by deterministic JSON-shape validation in
``PolymorphicEmailParser._validate_payload`` (plus per-record coercion);
nothing that fails validation becomes a candidate. The output is *extracted
candidate* state — it is the candidate generator's job (see PR #328) to
validate each pick against current MarketSnapshot before promoting it to a
``ValidatedPick`` row.

Hard rules (enforced by tests):

- Never call any provider/network at module-import time.
- All money / scores are Decimal at the boundary.
- Datetimes are timezone-aware UTC.
- LLM access is per-parse via the injected ``LLMParseProvider`` (constructor
  parameter); there is no global env flag that enables/disables the model.
- LLM provider is a Protocol; a deterministic stub ships with the package.
- PDF parsing is lazy-imported in the preprocessor; if ``pypdf`` is missing,
  PDF bytes are skipped and a ``parse_warning`` is attached to
  ``NormalizedEmail`` (the parser surfaces those warnings on ``ParseResult``).

medallion: gold
"""

from .llm_provider import (
    LLMParseProvider,
    LLMRequest,
    LLMResponse,
    StubLLMParseProvider,
)
from .parser import (
    ParseResult,
    ParserLimits,
    PolymorphicEmailParser,
)
from .preprocessor import EmailPreprocessor, NormalizedEmail, RawEmail
from .types import (
    ExtractedMacro,
    ExtractedPick,
    ExtractedPositionChange,
    PickActionHint,
    SourceFormat,
)

__all__ = [
    "EmailPreprocessor",
    "ExtractedMacro",
    "ExtractedPick",
    "ExtractedPositionChange",
    "LLMParseProvider",
    "LLMRequest",
    "LLMResponse",
    "NormalizedEmail",
    "ParseResult",
    "ParserLimits",
    "PickActionHint",
    "PolymorphicEmailParser",
    "RawEmail",
    "SourceFormat",
    "StubLLMParseProvider",
]
