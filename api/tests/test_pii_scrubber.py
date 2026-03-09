from app.utils.pii_scrubber import SSN_PATTERN, SSN_REPLACEMENT


def test_scrub_ssn_with_dashes() -> None:
    text = "SSN is 123-45-6789 for the user"
    result = SSN_PATTERN.sub(SSN_REPLACEMENT, text)
    assert "123-45-6789" not in result
    assert SSN_REPLACEMENT in result


def test_scrub_ssn_without_dashes() -> None:
    text = "SSN: 123456789"
    result = SSN_PATTERN.sub(SSN_REPLACEMENT, text)
    assert "123456789" not in result
    assert SSN_REPLACEMENT in result


def test_scrub_ssn_with_spaces() -> None:
    text = "SSN is 123 45 6789"
    result = SSN_PATTERN.sub(SSN_REPLACEMENT, text)
    assert "123 45 6789" not in result
    assert SSN_REPLACEMENT in result


def test_no_false_positive_on_short_numbers() -> None:
    text = "Phone: 555-1234"
    result = SSN_PATTERN.sub(SSN_REPLACEMENT, text)
    assert result == text


def test_scrub_multiple_ssns() -> None:
    text = "User A: 111-22-3333, User B: 444-55-6666"
    result = SSN_PATTERN.sub(SSN_REPLACEMENT, text)
    assert "111-22-3333" not in result
    assert "444-55-6666" not in result
    assert result.count(SSN_REPLACEMENT) == 2
