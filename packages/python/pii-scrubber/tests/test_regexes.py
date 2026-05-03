"""Unit tests for raw regex strings (edge cases and compilation)."""

from __future__ import annotations

import re

import pytest

from pii_scrubber import regexes

from safe_str import ss


@pytest.mark.parametrize(
    ("_name", "pattern"),
    [
        ("SSN", regexes.SSN),
        ("EIN", regexes.EIN),
        ("EMAIL", regexes.EMAIL),
        ("PHONE_US", regexes.PHONE_US),
        ("CREDIT_CARD", regexes.CREDIT_CARD),
        ("IP_ADDRESS", regexes.IP_ADDRESS),
        ("BANK_ACCOUNT", regexes.BANK_ACCOUNT),
        ("JWT", regexes.JWT),
        ("API_KEY", regexes.API_KEY),
    ],
)
def test_patterns_compile(_name: str, pattern: str) -> None:
    re.compile(pattern)


def test_ssn_requires_full_groups() -> None:
    assert re.search(regexes.SSN, "123-45-6789")
    assert re.search(regexes.SSN, "000-00-0000")
    assert not re.search(regexes.SSN, "12-34-5678")


def test_ein_excludes_12_3456789_sentinel() -> None:
    assert not re.search(regexes.EIN, "12-3456789")
    assert re.search(regexes.EIN, "12-3456788")
    assert re.search(regexes.EIN, "10-1234567")


def test_email_requires_tld() -> None:
    assert re.search(regexes.EMAIL, "a@b.co")
    assert not re.search(regexes.EMAIL, "a@b")
    assert not re.search(regexes.EMAIL, "a@@b.co")


def test_phone_us_accepts_common_formats() -> None:
    assert re.search(regexes.PHONE_US, "(212) 555-0199")
    assert re.search(regexes.PHONE_US, "+1 415 555 2671")
    assert re.search(regexes.PHONE_US, "5035550113")


def test_credit_card_shape_matches_grouped_or_run() -> None:
    assert re.search(regexes.CREDIT_CARD, "4242-4242-4242-4242")
    assert re.search(regexes.CREDIT_CARD, ss("4242424242", "42424242"))
    assert not re.search(regexes.CREDIT_CARD, "42424242424")


def test_ip_v4_rejects_invalid_octets() -> None:
    assert re.search(regexes.IP_ADDRESS, "192.0.2.1")
    assert not re.search(regexes.IP_ADDRESS, "256.1.1.1")
    assert not re.search(regexes.IP_ADDRESS, "999.999.999.999")


def test_bank_rejects_uniform_runs() -> None:
    assert re.search(regexes.BANK_ACCOUNT, "1029384756091")
    assert not re.search(regexes.BANK_ACCOUNT, "1111111111111")


def test_jwt_requires_three_segments() -> None:
    assert re.search(
        regexes.JWT,
        ss("ey", "Jaaaaaaaaaaaa.", "ey", "Jbbbbbbbbbbbb.", "cccccccccccc"),
    )
    assert not re.search(regexes.JWT, ss("ey", "Jonlyonepart"))


def test_api_key_branch_prefixes() -> None:
    assert re.search(
        regexes.API_KEY,
        ss("sk-", "test-", "aaaaaaaaaaaaaaaaaaaa"),
    )
    assert re.search(regexes.API_KEY, ss("AK", "IA", "IOSFODNN7EXAMPLE"))
    assert re.search(
        regexes.API_KEY,
        ss("api_key=", "abcdefghijklmnopqrstuvwxyz0123456789"),
    )
    assert re.search(regexes.API_KEY, ss("pk_", "test_", "abcdefghijklmnopqrst"))
