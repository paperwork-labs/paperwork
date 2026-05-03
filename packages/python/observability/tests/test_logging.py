"""Tests for JSON logging and contextvars."""

from __future__ import annotations

import asyncio
import io
import json
import logging

import pytest

from observability.logging import (
    StructuredJsonFormatter,
    request_context,
    scrub_pii,
)


def _parse_last_json_line(stream: io.StringIO) -> dict[str, object]:
    raw = stream.getvalue().strip().splitlines()
    assert raw
    return json.loads(raw[-1])


def test_structured_log_fields() -> None:
    stream = io.StringIO()
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        StructuredJsonFormatter("unit-svc", json_ensure_ascii=False),
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    token_rid = request_context.set_request_id("req-abc")
    token_uid = request_context.set_user_id("user-xyz")
    logging.getLogger("demo").info(
        "processing",
        extra={"task": "ingest"},
    )
    request_context.reset_user_id(token_uid)
    request_context.reset_request_id(token_rid)

    row = _parse_last_json_line(stream)
    assert row["service_name"] == "unit-svc"
    assert row["message"] == "processing"
    assert row["request_id"] == "req-abc"
    assert row["user_id"] == "user-xyz"
    assert row["task"] == "ingest"
    assert "timestamp" in row
    assert row["level"] == "INFO"


@pytest.mark.asyncio
async def test_contextvars_isolate_across_tasks() -> None:
    stream = io.StringIO()
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        StructuredJsonFormatter("async-svc", json_ensure_ascii=False),
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    barrier = asyncio.Barrier(2)

    async def worker(rid: str, label: str) -> None:
        token = request_context.set_request_id(rid)
        await barrier.wait()
        logging.getLogger("w").info("tick %s", label)
        request_context.reset_request_id(token)

    await asyncio.gather(worker("r1", "a"), worker("r2", "b"))

    lines = [json.loads(line) for line in stream.getvalue().strip().splitlines()]
    by_rid = {str(row["request_id"]): row for row in lines}
    assert by_rid["r1"]["message"] == "tick a"
    assert by_rid["r2"]["message"] == "tick b"


def test_scrub_pii_in_message() -> None:
    stream = io.StringIO()
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredJsonFormatter("pii-svc", json_ensure_ascii=False))
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    logging.getLogger("x").info("Reach me at someone@example.com today")
    row = _parse_last_json_line(stream)
    assert "someone@example.com" not in json.dumps(row)
    assert row["message"] == "Reach me at [REDACTED_EMAIL] today"


def test_scrub_pii_helper_covers_ssn_phone() -> None:
    raw = "SSN 123-45-6789 and +1 (415) 555-2671"
    out = scrub_pii(raw)
    assert "123-45-6789" not in out
    assert "555-2671" not in out


def test_formatter_extra_fields() -> None:
    stream = io.StringIO()
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        StructuredJsonFormatter(
            "extra-svc",
            extra_fields={"deployment": "test"},
            json_ensure_ascii=False,
        ),
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    logging.getLogger("g").info("ping")
    row = _parse_last_json_line(stream)
    assert row["deployment"] == "test"
    assert row["message"] == "ping"
