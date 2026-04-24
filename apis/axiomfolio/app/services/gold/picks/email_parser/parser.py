"""Polymorphic email parser orchestrator.

Pipeline:

    NormalizedEmail -> build LLMRequest -> provider.parse() -> validate JSON
        -> coerce to ExtractedPick / ExtractedMacro / ExtractedPositionChange
        -> ParseResult

Bounded by ``ParserLimits``:
    - max_picks (default 25)
    - max_macros (default 10)
    - max_position_changes (default 25)
    - max_body_chars sent to LLM (default 32_000; truncated head + tail)
    - max_pdf_chars (default 20_000)
    - max_image_blocks (default 6)

Error policy:
    - LLM provider exceptions are CAUGHT and recorded as parse_errors.
      The parser returns an empty ParseResult so callers can persist a
      failed-parse row and move on (Stripe-webhook style: never crash).
    - Schema-invalid LLM output -> parse_errors, empty extraction lists.
    - Per-record validation failures (e.g., bad ticker) are skipped with a
      parse_error appended for that single record.

medallion: gold
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, List, Mapping, Optional, Tuple

from app.observability import traced

from .llm_provider import LLMParseProvider, LLMRequest, LLMResponse
from .preprocessor import NormalizedEmail
from .schemas import PARSE_OUTPUT_SCHEMA, SYSTEM_PROMPT_DEFAULT
from .types import (
    ExtractedMacro,
    ExtractedPick,
    ExtractedPositionChange,
    PickActionHint,
    SourceFormat,
    clamp_confidence,
    clamp_sentiment,
)

logger = logging.getLogger(__name__)


_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


# --------------------------------------------------------------------------- #
# Limits + result                                                             #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ParserLimits:
    max_picks: int = 25
    max_macros: int = 10
    max_position_changes: int = 25
    max_body_chars: int = 32_000
    max_pdf_chars: int = 20_000
    max_image_blocks: int = 6
    max_excerpt_chars: int = 240


@dataclass(frozen=True)
class ParseResult:
    request_id: str
    received_at: datetime
    sender: str
    subject: str
    source_format: SourceFormat
    picks: Tuple[ExtractedPick, ...]
    macro: Tuple[ExtractedMacro, ...]
    position_changes: Tuple[ExtractedPositionChange, ...]
    overall_confidence: Decimal
    parser_notes: str
    parse_errors: Tuple[str, ...]
    parse_warnings: Tuple[str, ...]
    llm_provider: str
    llm_model: str
    prompt_tokens: int
    completion_tokens: int
    elapsed_ms: int

    def is_empty(self) -> bool:
        return not (self.picks or self.macro or self.position_changes)


# --------------------------------------------------------------------------- #
# Parser                                                                      #
# --------------------------------------------------------------------------- #


class PolymorphicEmailParser:
    """Construct once with a provider; call ``.parse()`` per email.

    Stateless apart from the provider reference. Safe to share across
    threads provided the provider is.
    """

    def __init__(
        self,
        provider: LLMParseProvider,
        limits: Optional[ParserLimits] = None,
        system_prompt: str = SYSTEM_PROMPT_DEFAULT,
    ) -> None:
        if not isinstance(provider, LLMParseProvider):
            raise TypeError(
                "provider must satisfy LLMParseProvider Protocol "
                "(must have a .parse(LLMRequest) -> LLMResponse method)"
            )
        self._provider = provider
        self._limits = limits or ParserLimits()
        self._system_prompt = system_prompt

    # ------------------------------------------------------------------ #
    # Entry point                                                        #
    # ------------------------------------------------------------------ #

    @traced(
        "picks_email_parser_parse",
        attrs={"component": "picks", "subsystem": "email_parser"},
    )
    def parse(self, email: NormalizedEmail) -> ParseResult:
        request_id = uuid.uuid4().hex[:16]
        started = time.monotonic()
        errors: List[str] = []

        try:
            request = self._build_request(email, request_id)
        except Exception as exc:  # never crash on prompt construction
            logger.exception("email_parser: prompt build failed: %s", exc)
            return self._empty_result(
                email,
                request_id,
                started,
                errors=[f"prompt_build_failed:{exc!s}"],
            )

        try:
            response = self._provider.parse(request)
        except Exception as exc:
            logger.exception("email_parser: provider failed: %s", exc)
            return self._empty_result(
                email,
                request_id,
                started,
                errors=[f"provider_failed:{exc!s}"],
            )

        try:
            payload = self._validate_payload(response.raw_text)
        except _SchemaError as exc:
            errors.append(f"schema_invalid:{exc!s}")
            return self._empty_result(
                email,
                request_id,
                started,
                errors=errors,
                provider=response.provider,
                model=response.model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
            )

        picks, pick_errs = self._coerce_picks(
            payload.get("picks", []), email.source_format
        )
        macros, macro_errs = self._coerce_macros(
            payload.get("macro", []), email.source_format
        )
        changes, change_errs = self._coerce_position_changes(
            payload.get("position_changes", []), email.source_format
        )
        errors.extend(pick_errs)
        errors.extend(macro_errs)
        errors.extend(change_errs)

        elapsed = int((time.monotonic() - started) * 1000)
        return ParseResult(
            request_id=request_id,
            received_at=email.received_at,
            sender=email.sender,
            subject=email.subject,
            source_format=email.source_format,
            picks=picks,
            macro=macros,
            position_changes=changes,
            overall_confidence=clamp_confidence(payload.get("overall_confidence", 0)),
            parser_notes=str(payload.get("parser_notes", ""))[:1000],
            parse_errors=tuple(errors),
            parse_warnings=email.parse_warnings,
            llm_provider=response.provider,
            llm_model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            elapsed_ms=elapsed,
        )

    # ------------------------------------------------------------------ #
    # Prompt construction                                                #
    # ------------------------------------------------------------------ #

    def _build_request(self, email: NormalizedEmail, request_id: str) -> LLMRequest:
        body = self._truncate(email.body, self._limits.max_body_chars)
        pdf = self._truncate(email.extracted_pdf_text, self._limits.max_pdf_chars)

        ticker_hints = ", ".join(email.candidate_tickers) or "(none)"
        user_prompt_parts = [
            f"# Email metadata\n",
            f"From: {email.sender or '(unknown)'}\n",
            f"Subject: {email.subject or '(no subject)'}\n",
            f"Source format: {email.source_format.value}\n",
            f"Received at (UTC): {email.received_at.isoformat()}\n",
            f"Candidate ticker hints: {ticker_hints}\n\n",
            "# Email body\n",
            body or "(empty)\n",
        ]
        if pdf:
            user_prompt_parts.extend(
                [
                    "\n\n# PDF attachment(s) extracted text\n",
                    pdf,
                ]
            )
        user_prompt = "".join(user_prompt_parts)

        images = email.image_b64_blocks[: self._limits.max_image_blocks]

        return LLMRequest(
            system_prompt=self._system_prompt,
            user_prompt=user_prompt,
            image_data_urls=images,
            json_schema=PARSE_OUTPUT_SCHEMA,
            request_id=request_id,
        )

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        if not text or len(text) <= max_chars:
            return text or ""
        head = text[: max_chars // 2]
        tail = text[-max_chars // 2 :]
        return f"{head}\n\n[... {len(text) - max_chars} chars truncated ...]\n\n{tail}"

    # ------------------------------------------------------------------ #
    # JSON validation                                                    #
    # ------------------------------------------------------------------ #

    def _validate_payload(self, raw_text: str) -> Mapping[str, Any]:
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise _SchemaError(f"not valid JSON: {exc.msg}")

        if not isinstance(payload, dict):
            raise _SchemaError("top-level payload must be an object")

        # Cheap field-level shape check (we don't bring in jsonschema as a dep).
        # Wire format follows ``PARSE_OUTPUT_SCHEMA``: ``macro`` holds macro
        # outlook rows; ``position_changes`` may be JSON ``null`` when absent.
        required = ("picks", "macro", "position_changes", "overall_confidence")
        for key in required:
            if key not in payload:
                raise _SchemaError(f"missing required field: {key}")

        if not isinstance(payload["picks"], list):
            raise _SchemaError("picks must be an array")

        for list_field in ("macro", "position_changes"):
            value = payload[list_field]
            if value is None:
                payload[list_field] = []
                continue
            if not isinstance(value, list):
                raise _SchemaError(f"{list_field} must be an array or null")

        oc = payload["overall_confidence"]
        if not isinstance(oc, (int, float, str)):
            raise _SchemaError("overall_confidence must be a number or numeric string")

        return payload

    # ------------------------------------------------------------------ #
    # Coercion helpers                                                   #
    # ------------------------------------------------------------------ #

    def _coerce_picks(
        self, raw: Iterable[Mapping[str, Any]], source_format: SourceFormat
    ) -> Tuple[Tuple[ExtractedPick, ...], List[str]]:
        out: List[ExtractedPick] = []
        errs: List[str] = []
        for idx, item in enumerate(raw):
            if not isinstance(item, Mapping):
                errs.append(f"picks[{idx}]: not an object")
                continue
            act_in = item.get("action_hint", item.get("action"))
            if not isinstance(item.get("symbol"), str) or not item.get("symbol", "").strip():
                errs.append(f"picks[{idx}]: symbol must be a non-empty string")
                continue
            if not isinstance(act_in, str) or not act_in.strip():
                errs.append(
                    f"picks[{idx}]: action_hint/action must be a non-empty string"
                )
                continue
            try:
                symbol = self._coerce_symbol(item.get("symbol"))
                action = _coerce_action(act_in)
                conf = clamp_confidence(item.get("confidence"))
                rationale = self._truncate_str(item.get("rationale"), 500)
                target = _maybe_decimal(item.get("target_price"))
                stop = _maybe_decimal(item.get("stop_loss"))
                horizon = _maybe_int(item.get("horizon_days"))
                excerpt = self._truncate_str(
                    item.get("source_excerpt"), self._limits.max_excerpt_chars
                )
            except _CoerceError as exc:
                errs.append(f"picks[{idx}]: {exc!s}")
                continue
            out.append(
                ExtractedPick(
                    symbol=symbol,
                    action=action,
                    confidence=conf,
                    rationale=rationale,
                    target_price=target,
                    stop_loss=stop,
                    horizon_days=horizon,
                    source_excerpt=excerpt,
                    source_format=source_format,
                )
            )
            if len(out) >= self._limits.max_picks:
                break
        return tuple(out), errs

    def _coerce_macros(
        self, raw: Iterable[Mapping[str, Any]], source_format: SourceFormat
    ) -> Tuple[Tuple[ExtractedMacro, ...], List[str]]:
        out: List[ExtractedMacro] = []
        errs: List[str] = []
        for idx, item in enumerate(raw):
            if not isinstance(item, Mapping):
                errs.append(f"macro[{idx}]: not an object")
                continue
            try:
                headline = self._truncate_str(item.get("headline"), 200)
                body = self._truncate_str(item.get("body"), 1000)
                sentiment = clamp_sentiment(item.get("sentiment"))
                conf = clamp_confidence(item.get("confidence"))
                sectors = tuple(
                    str(s).strip()
                    for s in (item.get("sectors") or [])
                    if isinstance(s, (str, int))
                    and str(s).strip()
                )
                horizon = _maybe_int(item.get("horizon_days"))
                excerpt = self._truncate_str(
                    item.get("source_excerpt"), self._limits.max_excerpt_chars
                )
            except _CoerceError as exc:
                errs.append(f"macro[{idx}]: {exc!s}")
                continue
            if not headline:
                errs.append(f"macro[{idx}]: empty headline")
                continue
            out.append(
                ExtractedMacro(
                    headline=headline,
                    body=body,
                    sentiment=sentiment,
                    confidence=conf,
                    sectors=sectors,
                    horizon_days=horizon,
                    source_excerpt=excerpt,
                    source_format=source_format,
                )
            )
            if len(out) >= self._limits.max_macros:
                break
        return tuple(out), errs

    def _coerce_position_changes(
        self, raw: Iterable[Mapping[str, Any]], source_format: SourceFormat
    ) -> Tuple[Tuple[ExtractedPositionChange, ...], List[str]]:
        out: List[ExtractedPositionChange] = []
        errs: List[str] = []
        for idx, item in enumerate(raw):
            if not isinstance(item, Mapping):
                errs.append(f"position_changes[{idx}]: not an object")
                continue
            try:
                symbol = self._coerce_symbol(item.get("symbol"))
                action = _coerce_action(item.get("action"))
                qty = _maybe_decimal(item.get("quantity_hint"))
                occurred = _maybe_iso_dt(item.get("occurred_at_hint"))
                conf = clamp_confidence(item.get("confidence"))
                excerpt = self._truncate_str(
                    item.get("source_excerpt"), self._limits.max_excerpt_chars
                )
            except _CoerceError as exc:
                errs.append(f"position_changes[{idx}]: {exc!s}")
                continue
            out.append(
                ExtractedPositionChange(
                    symbol=symbol,
                    action=action,
                    quantity_hint=qty,
                    occurred_at_hint=occurred,
                    confidence=conf,
                    source_excerpt=excerpt,
                    source_format=source_format,
                )
            )
            if len(out) >= self._limits.max_position_changes:
                break
        return tuple(out), errs

    @staticmethod
    def _coerce_symbol(value: Any) -> str:
        if not isinstance(value, str):
            raise _CoerceError("symbol must be string")
        norm = value.strip().upper().lstrip("$")
        if not _TICKER_RE.match(norm):
            raise _CoerceError(f"invalid ticker: {value!r}")
        return norm

    @staticmethod
    def _truncate_str(value: Any, max_chars: int) -> str:
        if value is None:
            return ""
        s = str(value)
        if len(s) <= max_chars:
            return s
        return s[: max_chars - 1] + "\u2026"

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #

    def _empty_result(
        self,
        email: NormalizedEmail,
        request_id: str,
        started: float,
        *,
        errors: List[str],
        provider: str = "unknown",
        model: str = "unknown",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> ParseResult:
        return ParseResult(
            request_id=request_id,
            received_at=email.received_at,
            sender=email.sender,
            subject=email.subject,
            source_format=email.source_format,
            picks=(),
            macro=(),
            position_changes=(),
            overall_confidence=Decimal("0"),
            parser_notes="",
            parse_errors=tuple(errors),
            parse_warnings=email.parse_warnings,
            llm_provider=provider,
            llm_model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )


# --------------------------------------------------------------------------- #
# Internal exceptions                                                         #
# --------------------------------------------------------------------------- #


class _SchemaError(Exception):
    pass


class _CoerceError(Exception):
    pass


# --------------------------------------------------------------------------- #
# Module-level coercion helpers (kept outside the class so tests can use them)#
# --------------------------------------------------------------------------- #


def _coerce_action(value: Any) -> PickActionHint:
    if isinstance(value, PickActionHint):
        return value
    if not isinstance(value, str):
        raise _CoerceError("action must be string")
    try:
        return PickActionHint(value.strip().lower())
    except ValueError:
        raise _CoerceError(f"unknown action: {value!r}")


def _maybe_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        raise _CoerceError(f"not a decimal: {value!r}")


def _maybe_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        out = int(value)
    except (TypeError, ValueError):
        raise _CoerceError(f"not an int: {value!r}")
    if out < 0:
        raise _CoerceError(f"negative horizon: {out}")
    return out


def _maybe_iso_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if not isinstance(value, str):
        raise _CoerceError("datetime must be ISO8601 string")
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise _CoerceError(f"not ISO8601: {value!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
