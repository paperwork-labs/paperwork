"""Direct checks for Luhn helper edge cases (coverage + invariants)."""

from __future__ import annotations

from pii_scrubber.scrubber import _luhn_ok

from safe_str import ss


def test_luhn_rejects_wrong_length() -> None:
    assert not _luhn_ok("424242424242")
    assert not _luhn_ok("4" * 20)


def test_luhn_rejects_uniform_digit_run() -> None:
    assert not _luhn_ok("1" * 16)


def test_luhn_accepts_known_test_pan() -> None:
    assert _luhn_ok(ss("4242424242", "42424242"))
