"""JSON structured logging with request-scoped context (async-safe)."""

from __future__ import annotations

import contextvars
import logging
import re
from datetime import UTC, datetime
from typing import Any

from pythonjsonlogger.json import JsonFormatter

# ---------------------------------------------------------------------------
# Context (async-safe)
# ---------------------------------------------------------------------------

_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "observability_request_id",
    default=None,
)
_user_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "observability_user_id",
    default=None,
)


class request_context:
    """Helpers for binding contextvars used by the JSON log formatter."""

    @staticmethod
    def set_request_id(rid: str) -> contextvars.Token[str | None]:
        return _request_id_var.set(rid)

    @staticmethod
    def set_user_id(uid: str | None) -> contextvars.Token[str | None]:
        return _user_id_var.set(uid)

    @staticmethod
    def reset_request_id(token: contextvars.Token[str | None]) -> None:
        _request_id_var.reset(token)

    @staticmethod
    def reset_user_id(token: contextvars.Token[str | None]) -> None:
        _user_id_var.reset(token)


# ---------------------------------------------------------------------------
# PII scrubbing (log message field)
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
)
# Loose US SSN pattern; tuned to reduce false positives vs 9-digit IDs alone.
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# US phone-like sequences
_PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")


def scrub_pii(text: str) -> str:
    """Redact common PII patterns from free-text log messages."""
    redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    redacted = _SSN_RE.sub("[REDACTED_SSN]", redacted)
    redacted = _PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    return redacted


class StructuredJsonFormatter(JsonFormatter):
    """python-json-logger formatter with fixed schema fields + contextvars."""

    def __init__(
        self,
        service_name: str,
        extra_fields: dict[str, Any] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._service_name = service_name
        self._extra_fields = dict(extra_fields or {})

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        ts = datetime.fromtimestamp(record.created, tz=UTC)
        log_record["timestamp"] = ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        log_record["level"] = record.levelname
        log_record["service_name"] = self._service_name
        log_record["request_id"] = _request_id_var.get()
        log_record["user_id"] = _user_id_var.get()
        for key, value in self._extra_fields.items():
            log_record[key] = value
        msg = log_record.get("message")
        if isinstance(msg, str):
            log_record["message"] = scrub_pii(msg)


def configure_structured_logging(
    service_name: str,
    log_level: str = "INFO",
    *,
    extra_fields: dict[str, Any] | None = None,
) -> None:
    """Attach a single JSON :class:`logging.StreamHandler` on the root logger.

    Uses :class:`StructuredJsonFormatter` (not :func:`logging.basicConfig`).
    """
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    formatter = StructuredJsonFormatter(
        service_name,
        extra_fields=extra_fields,
        json_ensure_ascii=False,
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    level = getattr(logging, log_level.upper(), logging.INFO)
    root.setLevel(level)


__all__ = [
    "StructuredJsonFormatter",
    "configure_structured_logging",
    "request_context",
    "scrub_pii",
]
