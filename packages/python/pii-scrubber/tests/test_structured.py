"""Tests for structured JSON-like scrubbing."""

from __future__ import annotations

from pii_scrubber import scrub_dict


def test_scrub_dict_nested_strings() -> None:
    payload = {
        "user": {"email": "user@example.com", "note": "ok"},
        "ssn": "078-05-1120",
        "items": ["call (212) 555-0199", "safe"],
    }
    out = scrub_dict(payload)
    assert out["user"]["email"] == "[REDACTED:EMAIL]"
    assert out["user"]["note"] == "ok"
    assert out["ssn"] == "[REDACTED:SSN]"
    assert out["items"][0] == "call [REDACTED:PHONE_US]"
    assert out["items"][1] == "safe"


def test_scrub_dict_preserves_mixed_types() -> None:
    payload = {
        "n": 42,
        "z": None,
        "b": True,
        "f": 3.14,
        "s": "user@example.com",
    }
    out = scrub_dict(payload)
    assert out["n"] == 42
    assert out["z"] is None
    assert out["b"] is True
    assert out["f"] == 3.14
    assert out["s"] == "[REDACTED:EMAIL]"


def test_scrub_dict_recursive_false_leaves_nested_dicts() -> None:
    inner = {"email": "user@example.com"}
    payload = {"outer": inner}
    out = scrub_dict(payload, recursive=False)
    assert out["outer"] is inner
    assert out["outer"]["email"] == "user@example.com"


def test_scrub_dict_tuple_values() -> None:
    payload = {"t": ("user@example.com", "plain")}
    out = scrub_dict(payload)
    assert out["t"] == ("[REDACTED:EMAIL]", "plain")


def test_scrub_dict_does_not_mutate_input() -> None:
    payload = {"s": "user@example.com"}
    scrub_dict(payload)
    assert payload["s"] == "user@example.com"
