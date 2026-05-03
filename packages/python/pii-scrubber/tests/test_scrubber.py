"""End-to-end scrubber behavior and canonical corpus (no false negatives)."""

from __future__ import annotations

import pytest

from pii_scrubber import ScrubMode, scrub

from safe_str import ss


def _assert_scrubbed_once(mode: ScrubMode, sample: str) -> None:
    res = scrub(sample, modes=[mode])
    assert mode in res.replacements_by_mode
    assert res.replacements_by_mode[mode] >= 1
    assert f"[REDACTED:{mode.name}]" in res.text


@pytest.mark.parametrize(
    "sample",
    [
        "078-05-1120",
        "123-45-6789",
        "000-12-3456",
        "856-45-6789",
        "AAA 111-22-3333 BBB",
        "prefix 234-56-7890 suffix",
        "SSN: 321-54-9876 today",
        "edge 001-01-0001",
        "multi 111-11-1111 and 222-22-2222",
        "last 999-99-9999",
    ],
)
def test_ssn_positive_scrubs(sample: str) -> None:
    _assert_scrubbed_once(ScrubMode.SSN, sample)


@pytest.mark.parametrize(
    "sample",
    [
        "123456789",
        "12-34-5678",
        "1234-56-7890",
        "no-ssn-here",
        "123-45-678",  # too short
        "12345-678-90",
        "12-345-6789",
    ],
)
def test_ssn_negative_no_scrub(sample: str) -> None:
    res = scrub(sample, modes=[ScrubMode.SSN])
    assert res.replacements_by_mode.get(ScrubMode.SSN, 0) == 0
    assert res.text == sample


@pytest.mark.parametrize(
    "sample",
    [
        "10-1234567",
        "53-1234567",
        "12-3456788",
        "00-0000000",
        "EIN 12-3456788 ok",
        "prefix 99-9999999 suffix",
        "two 10-1234567 and 20-3034567",
        "33-4444444",
        "55-6666666",
        "77-8888888",
    ],
)
def test_ein_positive_scrubs(sample: str) -> None:
    _assert_scrubbed_once(ScrubMode.EIN, sample)


@pytest.mark.parametrize(
    "sample",
    [
        "12-3456789",
        "not-an-ein",
        "1-2345678",
        "123-456789",
    ],
)
def test_ein_negative_excludes_common_false_positive(sample: str) -> None:
    res = scrub(sample, modes=[ScrubMode.EIN])
    assert res.replacements_by_mode.get(ScrubMode.EIN, 0) == 0
    assert res.text == sample


@pytest.mark.parametrize(
    "sample",
    [
        "user@example.com",
        "first.last+tag@sub.example.co.uk",
        "a@b.co",
        "contact: support@company.io please",
            "many a@b.co and x@y.io",
        "underscore_name@domain_name.org",
        "digits123@digits456.net",
        "mixed.Case@Mixed.CASE",
        "long.subdomain@host.part1.part2.info",
        "edge.case@xn--example.com",
    ],
)
def test_email_positive_scrubs(sample: str) -> None:
    _assert_scrubbed_once(ScrubMode.EMAIL, sample)


@pytest.mark.parametrize(
    "sample",
    [
        "not@",
        "@nodomain",
        "spaces in @bad.com",
        "foo@@bar.com",
        "missingatsign.com",
    ],
)
def test_email_negative_no_scrub(sample: str) -> None:
    res = scrub(sample, modes=[ScrubMode.EMAIL])
    assert res.replacements_by_mode.get(ScrubMode.EMAIL, 0) == 0
    assert res.text == sample


@pytest.mark.parametrize(
    "sample",
    [
        "(212) 555-0199",
        "+1 415 555 2671",
        "+1-310-555-0112",
        "206.555.0199",
        "5035550113",
        "(503)555-0113",
        "+1(202)555-0173",
        "call 617-555-0148 now",
        "800-555-0199",
        "888.555.0199",
    ],
)
def test_phone_us_positive_scrubs(sample: str) -> None:
    _assert_scrubbed_once(ScrubMode.PHONE_US, sample)


@pytest.mark.parametrize(
    "sample",
    [
        "12345678901",
        "152-555-0199",
        "not-a-phone",
        "12345",
    ],
)
def test_phone_us_negative_no_scrub(sample: str) -> None:
    res = scrub(sample, modes=[ScrubMode.PHONE_US])
    assert res.replacements_by_mode.get(ScrubMode.PHONE_US, 0) == 0
    assert res.text == sample


@pytest.mark.parametrize(
    "sample",
    [
        ss("4242424242", "42424242"),
        "4242-4242-4242-4242",
        "5555 5555 5555 4444",
        ss("3782822463", "10005"),
        ss("6011111111111", "117"),
        ss("3056930902", "5904"),
        ss("3566111111111", "113"),
        ss("6200000000000", "005"),
        ss("6011000991300", "009"),
        ss("card 4000000000000", "002 today"),
    ],
)
def test_credit_card_positive_luhn_valid_scrubs(sample: str) -> None:
    _assert_scrubbed_once(ScrubMode.CREDIT_CARD, sample)


@pytest.mark.parametrize(
    "sample",
    [
        ss("1234567890123", "456"),
        ss("4242424242", "424241"),
        "0000000000000000",
        "4242-4242-4242-4241",
    ],
)
def test_credit_card_negative_invalid_luhn(sample: str) -> None:
    res = scrub(sample, modes=[ScrubMode.CREDIT_CARD])
    assert res.replacements_by_mode.get(ScrubMode.CREDIT_CARD, 0) == 0
    assert res.text == sample


@pytest.mark.parametrize(
    "sample",
    [
        "192.0.2.1",
        "198.51.100.10",
        "203.0.113.5",
        "10.0.0.1",
        "172.16.0.1",
        "127.0.0.1",
        "8.8.8.8",
        "1.2.3.4",
        "255.255.255.255",
        "0.0.0.0",
    ],
)
def test_ip_positive_scrubs(sample: str) -> None:
    _assert_scrubbed_once(ScrubMode.IP_ADDRESS, sample)


@pytest.mark.parametrize(
    "sample",
    [
        "999.999.999.999",
        "256.1.1.1",
        "1.2.3",
        "not.an.ip",
    ],
)
def test_ip_negative_invalid_octets(sample: str) -> None:
    res = scrub(sample, modes=[ScrubMode.IP_ADDRESS])
    assert res.replacements_by_mode.get(ScrubMode.IP_ADDRESS, 0) == 0
    assert res.text == sample


@pytest.mark.parametrize(
    "sample",
    [
        "1029384756",
        "1221051557123",
        "123456789012",
        "987654321098765",
        "1000000000000000",
        "acct 1221051557123456",
        "routing 0210000219999",
        "1234567890123",
        "23456789012345",
        "345678901234567",
    ],
)
def test_bank_account_positive_scrubs(sample: str) -> None:
    _assert_scrubbed_once(ScrubMode.BANK_ACCOUNT, sample)


@pytest.mark.parametrize(
    "sample",
    [
        "1111111111111",
        "9999999999",
        "123456789",
        "order-id-12345",
    ],
)
def test_bank_account_negative_uniform_or_short(sample: str) -> None:
    res = scrub(sample, modes=[ScrubMode.BANK_ACCOUNT])
    assert res.replacements_by_mode.get(ScrubMode.BANK_ACCOUNT, 0) == 0
    assert res.text == sample


_JWT_1 = ss(
    "ey",
    "JhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
    ".",
    "ey",
    "JzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0",
    ".",
    "dozjgNryP4J3jVmNHl0w5N_",
    "Xzg50QPWRwGuCDE-JwlE",
)
_JWT_2 = ss(
    "ey",
    "JhbGciOiJIUzI1NiJ9",
    ".",
    "ey",
    "JzdWIiOiIxMjM0NTY3ODkwIn0",
    ".",
    "dozjgNryP4J3jVmNHl0w5N_",
    "Xzg50QPWRwGuCDE-JwlE",
)
_JWT_3 = ss(
    "ey",
    "JhbGciOiJIUzI1NiJ9",
    ".",
    "ey",
    "JzdWIiOiIxMjM0NTY3ODkwIn0",
    ".",
    "abcdefghijklmnopqrstuvwxyz0123456789-_",
    "ABCDEF",
)


@pytest.mark.parametrize(
    "sample",
    [
        _JWT_1,
        _JWT_2,
        _JWT_3,
        ss("ey", "Jaaaaaaaaaaaa.", "ey", "Jbbbbbbbbbbbb.", "cccccccccccc"),
        ss("ey", "Jaaaaaaaaaaaaa.", "ey", "Jbbbbbbbbbbbbb.", "ccccccccccccc"),
        ss("ey", "Jaaaaaaaaaaaaaa.", "ey", "Jbbbbbbbbbbbbbb.", "cccccccccccccc"),
        ss("ey", "Jaaaaaaaaaaaaaaa.", "ey", "Jbbbbbbbbbbbbbbb.", "ccccccccccccccc"),
        ss("ey", "Jaaaaaaaaaaaaaaaa.", "ey", "Jbbbbbbbbbbbbbbbb.", "cccccccccccccccc"),
        ss("ey", "Jaaaaaaaaaaaaaaaaa.", "ey", "Jbbbbbbbbbbbbbbbbb.", "ccccccccccccccccc"),
        ss("ey", "Jaaaaaaaaaaaaaaaaaa.", "ey", "Jbbbbbbbbbbbbbbbbbb.", "cccccccccccccccccc"),
        ss("ey", "Jaaaaaaaaaaaaaaaaaaa.", "ey", "Jbbbbbbbbbbbbbbbbbbb.", "ccccccccccccccccccc"),
    ],
)
def test_jwt_positive_scrubs(sample: str) -> None:
    _assert_scrubbed_once(ScrubMode.JWT, sample)


@pytest.mark.parametrize(
    "sample",
    [
        ss("ey", "Jshort.bad.token"),
        "not.a.jwt",
        ss("ey", "Jnodots"),
    ],
)
def test_jwt_negative_no_scrub(sample: str) -> None:
    res = scrub(sample, modes=[ScrubMode.JWT])
    assert res.replacements_by_mode.get(ScrubMode.JWT, 0) == 0
    assert res.text == sample


@pytest.mark.parametrize(
    "sample",
    [
        ss("sk-", "test-", "aaaaaaaaaaaaaaaaaaaa"),
        ss("sk-", "live-", "bbbbbbbbbbbbbbbbbbbb"),
        ss("sk-", "proj-", "cccccccccccccccccccc"),
        ss("sk-", "test-", "dddddddddddddddddddd"),
        ss("AK", "IA", "IOSFODNN7EXAMPLE"),
        ss("gh", "p_", "abcdefghijklmnopqrstuvwxyz0123456789ABCD"),
        ss("pk_", "test_", "abcdefghijklmnopqrst"),
        ss("pk_", "live_", "abcdefghijklmnopqrst"),
        ss("api_key=", "abcdefghijklmnopqrstuvwxyz0123456789"),
        ss("secret_key: ", "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
        ss('api-key="', "abcdefghijklmnopqrstuvwxyz0123456789", '"'),
        ss("sk-", "live-", "eeeeeeeeeeeeeeeeeeee"),
    ],
)
def test_api_key_positive_scrubs(sample: str) -> None:
    _assert_scrubbed_once(ScrubMode.API_KEY, sample)


@pytest.mark.parametrize(
    "sample",
    [
        ss("sk-", "test-", "short"),
        ss("AK", "IA123"),
        ss("gh", "p_short"),
        "api_key=tooshort",
        "not-an-api-key-here",
    ],
)
def test_api_key_negative_no_scrub(sample: str) -> None:
    res = scrub(sample, modes=[ScrubMode.API_KEY])
    assert res.replacements_by_mode.get(ScrubMode.API_KEY, 0) == 0
    assert res.text == sample


def test_scrub_default_modes_covers_all() -> None:
    blob = (
        "078-05-1120 10-1234567 user@example.com (212) 555-0199 "
        + ss("4242424242", "42424242")
        + " 192.0.2.1 "
        + ss("1029384756", "123")
        + " "
        + ss(
            "ey",
            "JhbGciOiJIUzI1NiJ9",
            ".",
            "ey",
            "JzdWIiOiIxMjM0NTY3ODkwIn0",
            ".",
            "abcdefghijklmnopqrstuvwxyz0123456789-_",
            "ABCDEF ",
        )
        + ss("sk-", "test-", "aaaaaaaaaaaaaaaaaaaa")
    )
    res = scrub(blob)
    for mode in ScrubMode:
        assert res.replacements_by_mode.get(mode, 0) >= 1, mode


def test_scrub_idempotent() -> None:
    first = scrub("078-05-1120 and user@example.com")
    second = scrub(first.text)
    assert second.text == first.text
    assert second.total_replacements == 0
    assert all(v == 0 for v in second.replacements_by_mode.values())
