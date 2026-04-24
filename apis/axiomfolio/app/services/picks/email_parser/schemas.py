"""JSON schemas the LLM must return.

These dictionaries guide the model and provider ``response_format`` wiring.
Authoritative validation happens in ``PolymorphicEmailParser._validate_payload``
and the coercion helpers (not via Pydantic at the LLM boundary). Anything
that fails validation is recorded in ``parse_errors`` and discarded.

We intentionally use a *small* schema (no nested $ref, no oneOf) so the
schema can be passed verbatim to OpenAI's ``response_format={'type':
'json_schema'}`` and the equivalent Anthropic tool definition.

medallion: gold
"""

from __future__ import annotations

from typing import Any

# A Decimal is sent over the wire as a JSON number or string. The parser
# normalizes via ``Decimal(str(value))`` so either is acceptable.

PARSE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "picks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["symbol", "action", "confidence", "rationale"],
                "properties": {
                    "symbol": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": [
                            "buy",
                            "sell",
                            "trim",
                            "add",
                            "hold",
                            "avoid",
                            "unknown",
                        ],
                    },
                    "confidence": {"type": ["number", "string"]},
                    "rationale": {"type": "string"},
                    "target_price": {"type": ["number", "string", "null"]},
                    "stop_loss": {"type": ["number", "string", "null"]},
                    "horizon_days": {"type": ["integer", "null"]},
                    "source_excerpt": {"type": "string"},
                },
            },
        },
        "macro": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["headline", "body", "sentiment", "confidence"],
                "properties": {
                    "headline": {"type": "string"},
                    "body": {"type": "string"},
                    "sentiment": {"type": ["number", "string"]},
                    "confidence": {"type": ["number", "string"]},
                    "sectors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "horizon_days": {"type": ["integer", "null"]},
                    "source_excerpt": {"type": "string"},
                },
            },
        },
        "position_changes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["symbol", "action", "confidence"],
                "properties": {
                    "symbol": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": [
                            "buy",
                            "sell",
                            "trim",
                            "add",
                            "hold",
                            "avoid",
                            "unknown",
                        ],
                    },
                    "quantity_hint": {"type": ["number", "string", "null"]},
                    "occurred_at_hint": {"type": ["string", "null"]},  # ISO8601
                    "confidence": {"type": ["number", "string"]},
                    "source_excerpt": {"type": "string"},
                },
            },
        },
        "overall_confidence": {"type": ["number", "string"]},
        "parser_notes": {"type": "string"},
    },
    "required": ["picks", "macro", "position_changes", "overall_confidence"],
}


SYSTEM_PROMPT_DEFAULT = """\
You are AxiomFolio's email parser. You read one analyst/validator email and
extract structured trade signals.

HARD RULES:

1. Only extract signals that are EXPLICITLY stated. Do not infer ambiguous
   recommendations.
2. Use ONLY US-listed equity tickers (AAPL, MSFT, BRK.B, etc.). Reject ticker
   tokens that are obviously English words (THE, AND, USA).
3. Distinguish FORWARD-LOOKING recommendations (-> picks) from HISTORICAL
   "I bought X yesterday" statements (-> position_changes).
4. Macro statements ("market looks toppy", "tech leadership rotating") go to
   macro, not picks.
5. Confidence is YOUR confidence in your extraction (not the analyst's
   conviction). 0.0 = unsure / hedged, 1.0 = unambiguous explicit call.
6. Cite a source_excerpt for EVERY extraction (verbatim quote from the
   email body, max 240 chars).
7. Return ONLY valid JSON conforming to the schema. No prose outside the
   JSON object.
8. If the email contains zero signals, return empty arrays — never fabricate.
"""
