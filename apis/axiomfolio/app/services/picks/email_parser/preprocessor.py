"""Normalize raw RFC822 / forwarded / PDF emails into one shape for the LLM.

The LLM sees only `NormalizedEmail` — never raw HTML, never raw PDF bytes.
This module's job is to:

    1. Collapse forwarded threads ("---------- Forwarded message ---------")
       into the most recent author's body where possible.
    2. Strip HTML to text (best-effort; no JS execution, no external CSS).
    3. Extract attachments and route by mime type (PDF -> text, image -> b64).
    4. Surface a list of (symbol-like-token, source_excerpt) hints so the
       LLM has anchors even on long emails.

We keep this dependency-light: stdlib `email`, `html.parser`, and an
*optional* lazy import of `pypdf` for PDF text extraction. If `pypdf` is
not installed we record a `parse_warning` and pass the empty extracted text
to the LLM; the LLM can still reason about the email body.

medallion: gold
"""
from __future__ import annotations

import base64
import email
import email.policy
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from html.parser import HTMLParser
from typing import List, Optional, Tuple

from .types import SourceFormat

logger = logging.getLogger(__name__)


# Loose ticker matcher; intentionally NOT authoritative. A real ticker check
# happens in the candidate generator against the symbol universe.
_TICKER_RE = re.compile(r"\b\$?([A-Z][A-Z0-9.\-]{0,9})\b")
# Strip classic forwarded-message delimiters *or* RFC822-style forward
# blocks where ``From:`` is immediately followed by another header line.
# This is intentionally stricter than a bare ``^From:`` match to avoid
# false positives on prose lines like "From: weekly recap".
_FORWARD_BREAK = re.compile(
    r"(?m)(?:^[ >\-]*-{3,}\s*Forwarded message\s*-{3,}\s*\r?\n"
    r"(?=^(?:From|Subject|Date|To):)"
    r"|^From:\s+[^\r\n]+\r?\n(?=^(?:Subject|Date|To):))",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- #
# Input / output                                                              #
# --------------------------------------------------------------------------- #


@dataclass
class RawEmail:
    """Inputs to the preprocessor.

    `raw_bytes` is preferred (full RFC822); the convenience fields let
    callers test without producing a real RFC822 envelope.
    """

    raw_bytes: Optional[bytes] = None
    sender: Optional[str] = None
    subject: Optional[str] = None
    received_at: Optional[datetime] = None  # timezone-aware UTC
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    pdf_attachments: List[bytes] = field(default_factory=list)  # raw PDF bytes
    image_attachments: List[Tuple[str, bytes]] = field(
        default_factory=list
    )  # (mime, bytes)


@dataclass(frozen=True)
class NormalizedEmail:
    """The LLM-ready shape."""

    sender: str
    subject: str
    received_at: datetime
    body: str  # plain text, forwarded blocks collapsed
    source_format: SourceFormat
    extracted_pdf_text: str  # concatenated; "" if none
    image_b64_blocks: Tuple[str, ...]  # base64 strings ready for vision LLM
    candidate_tickers: Tuple[str, ...]  # rough hint set, deduped + capped
    parse_warnings: Tuple[str, ...]


# --------------------------------------------------------------------------- #
# HTML stripping                                                              #
# --------------------------------------------------------------------------- #


class _TextExtractor(HTMLParser):
    """Tiny stdlib HTML -> text. Drops <script>/<style>, preserves whitespace."""

    _DROP_TAGS = {"script", "style", "head"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: List[str] = []
        self._suppress_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._DROP_TAGS:
            self._suppress_depth += 1
        elif tag in {"br"}:
            self._chunks.append("\n")
        elif tag in {"p", "div", "tr", "li"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in self._DROP_TAGS and self._suppress_depth > 0:
            self._suppress_depth -= 1

    def handle_data(self, data):
        if self._suppress_depth == 0:
            self._chunks.append(data)

    def text(self) -> str:
        raw = "".join(self._chunks)
        # Collapse runs of >2 newlines.
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        # Collapse trailing whitespace per line.
        raw = "\n".join(line.rstrip() for line in raw.splitlines())
        return raw.strip()


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception as exc:  # malformed HTML; bail with a marker
        logger.warning("preprocessor: HTML parse failed: %s", exc)
        return html  # pass-through; the LLM can still read it
    return parser.text()


# --------------------------------------------------------------------------- #
# PDF extraction (lazy)                                                       #
# --------------------------------------------------------------------------- #


def _pdf_to_text(pdf_bytes: bytes) -> Tuple[str, Optional[str]]:
    """Return (text, warning).

    Tries pypdf first (lightweight). Returns ("", warning) if no PDF lib is
    available or the PDF is unparseable. Never raises.
    """
    if not pdf_bytes:
        return "", None
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        return (
            "",
            "pypdf not installed; PDF attachment skipped (install `pypdf` for text extraction)",
        )

    try:
        from io import BytesIO

        reader = PdfReader(BytesIO(pdf_bytes))
        pages: List[str] = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception as exc:
                logger.warning("preprocessor: pdf page extract failed: %s", exc)
        return "\n\n".join(p.strip() for p in pages if p.strip()), None
    except Exception as exc:
        return "", f"pdf parse failed: {exc!s}"


# --------------------------------------------------------------------------- #
# Forwarding collapse + ticker hints                                          #
# --------------------------------------------------------------------------- #


def _strip_forwarded_envelopes(text: str) -> str:
    """Drop "---------- Forwarded message ----------" headers (keep the body).

    We do NOT drop the entire forwarded block — analysts often forward the
    only useful content. We just remove the metadata noise so the LLM
    doesn't treat it as part of the rationale.
    """
    cleaned = _FORWARD_BREAK.sub("", text)
    return cleaned.strip()


def _extract_candidate_tickers(text: str, max_count: int = 24) -> Tuple[str, ...]:
    """Return uppercased ticker-like tokens, deduped, capped, with stopwords removed."""
    seen: List[str] = []
    stop = {
        "I", "A", "AN", "THE", "AT", "ON", "IN", "OF", "TO", "IS",
        "OR", "AND", "FOR", "BUT", "BY", "AS", "IT", "BE", "WE",
        "OUR", "ME", "MY", "YOU", "YOUR", "RE", "FW", "FWD", "PS",
        "USD", "USA", "US", "EU", "UK", "EOD", "NYSE", "NASDAQ",
        "ETF", "IPO", "CEO", "CFO", "AI", "ML",
    }
    for match in _TICKER_RE.finditer(text):
        tok = match.group(1).upper()
        if tok in stop:
            continue
        if tok in seen:
            continue
        seen.append(tok)
        if len(seen) >= max_count:
            break
    return tuple(seen)


# --------------------------------------------------------------------------- #
# Preprocessor                                                                #
# --------------------------------------------------------------------------- #


class EmailPreprocessor:
    """Stateless. Construct once and call `.normalize()` per email."""

    def normalize(self, raw: RawEmail) -> NormalizedEmail:
        warnings: List[str] = []

        if raw.raw_bytes:
            return self._normalize_rfc822(raw.raw_bytes, warnings)

        # Convenience path: caller assembled fields directly.
        body, source_format = self._normalize_inline(raw)
        # Promote to FORWARDED_EMAIL if the body shows the classic marker;
        # do this BEFORE stripping the markers so detection remains accurate.
        if _FORWARD_BREAK.search(body):
            source_format = SourceFormat.FORWARDED_EMAIL
        body = _strip_forwarded_envelopes(body)
        pdf_text, pdf_warns = self._extract_pdfs(raw.pdf_attachments)
        warnings.extend(pdf_warns)
        images = self._encode_images(raw.image_attachments)
        return NormalizedEmail(
            sender=(raw.sender or "").strip(),
            subject=(raw.subject or "").strip(),
            received_at=raw.received_at or datetime.now(timezone.utc),
            body=body,
            source_format=source_format,
            extracted_pdf_text=pdf_text,
            image_b64_blocks=images,
            candidate_tickers=_extract_candidate_tickers(
                "\n".join([raw.subject or "", body, pdf_text])
            ),
            parse_warnings=tuple(warnings),
        )

    # ------------------------------------------------------------------ #

    def _normalize_inline(self, raw: RawEmail) -> Tuple[str, SourceFormat]:
        if raw.body_text:
            return raw.body_text, SourceFormat.PLAIN_TEXT
        if raw.body_html:
            return _html_to_text(raw.body_html), SourceFormat.HTML
        return "", SourceFormat.PLAIN_TEXT

    def _normalize_rfc822(self, raw_bytes: bytes, warnings: List[str]) -> NormalizedEmail:
        msg: EmailMessage = email.message_from_bytes(  # type: ignore[assignment]
            raw_bytes, policy=email.policy.default
        )
        sender = (msg.get("From") or "").strip()
        subject = (msg.get("Subject") or "").strip()
        received_at = self._parse_date(msg.get("Date"))

        body_text = ""
        body_html = ""
        pdf_blobs: List[bytes] = []
        images: List[Tuple[str, bytes]] = []

        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = (part.get("Content-Disposition") or "").lower()
                if "attachment" in disp:
                    payload = part.get_payload(decode=True)
                    if not payload:
                        continue
                    if ctype == "application/pdf":
                        pdf_blobs.append(payload)
                    elif ctype.startswith("image/"):
                        images.append((ctype, payload))
                    continue
                if ctype == "text/plain" and not body_text:
                    body_text = self._safe_get_text(part)
                elif ctype == "text/html" and not body_html:
                    body_html = self._safe_get_text(part)
        else:
            ctype = msg.get_content_type()
            text = self._safe_get_text(msg)
            if ctype == "text/html":
                body_html = text
            else:
                body_text = text

        if body_text:
            body, source_format = body_text, SourceFormat.PLAIN_TEXT
        elif body_html:
            body, source_format = _html_to_text(body_html), SourceFormat.HTML
        else:
            body, source_format = "", SourceFormat.PLAIN_TEXT

        # If the body shows the classic "Forwarded message" marker, mark it.
        if _FORWARD_BREAK.search(body):
            source_format = SourceFormat.FORWARDED_EMAIL
        body = _strip_forwarded_envelopes(body)

        pdf_text, pdf_warns = self._extract_pdfs(pdf_blobs)
        warnings.extend(pdf_warns)
        return NormalizedEmail(
            sender=sender,
            subject=subject,
            received_at=received_at,
            body=body,
            source_format=source_format,
            extracted_pdf_text=pdf_text,
            image_b64_blocks=self._encode_images(images),
            candidate_tickers=_extract_candidate_tickers(
                "\n".join([subject, body, pdf_text])
            ),
            parse_warnings=tuple(warnings),
        )

    @staticmethod
    def _safe_get_text(part) -> str:
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                # Already-decoded string payload (multipart/alternative wrappers).
                value = part.get_content()
                if isinstance(value, str):
                    return value
                return ""
            charset = part.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
        except Exception as exc:
            logger.warning("preprocessor: part decode failed: %s", exc)
            return ""

    @staticmethod
    def _parse_date(date_header: Optional[str]) -> datetime:
        if not date_header:
            return datetime.now(timezone.utc)
        try:
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(date_header)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

    @staticmethod
    def _extract_pdfs(blobs: List[bytes]) -> Tuple[str, List[str]]:
        if not blobs:
            return "", []
        chunks: List[str] = []
        warns: List[str] = []
        for idx, blob in enumerate(blobs):
            text, warn = _pdf_to_text(blob)
            if warn:
                warns.append(f"pdf[{idx}]: {warn}")
            if text:
                chunks.append(text)
        return "\n\n--- pdf attachment ---\n\n".join(chunks), warns

    @staticmethod
    def _encode_images(images: List[Tuple[str, bytes]]) -> Tuple[str, ...]:
        out: List[str] = []
        for mime, blob in images:
            try:
                b64 = base64.b64encode(blob).decode("ascii")
            except Exception as exc:
                logger.warning("preprocessor: image encode failed: %s", exc)
                continue
            out.append(f"data:{mime};base64,{b64}")
        return tuple(out)
