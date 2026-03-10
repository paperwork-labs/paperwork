"""Tests for OCR service: SSN isolation, dollar conversion, mock mode."""

import pytest

from app.services.ocr_service import (
    W2ExtractionResult,
    _dollars_to_cents,
    _extract_ssn,
    _mock_extraction,
    process_w2,
)


class TestSSNExtraction:
    def test_extracts_formatted_ssn(self):
        text = "Employee SSN: 123-45-6789 Employer EIN: 12-3456789"
        ssn, scrubbed = _extract_ssn(text)
        assert ssn == "123-45-6789"
        assert "123-45-6789" not in scrubbed
        assert "XXX-XX-XXXX" in scrubbed
        assert "12-3456789" in scrubbed  # EIN should not be removed

    def test_extracts_unformatted_ssn(self):
        text = "SSN 123456789 Wages 75000"
        ssn, scrubbed = _extract_ssn(text)
        assert ssn == "123-45-6789"
        assert "123456789" not in scrubbed

    def test_no_ssn_in_text(self):
        text = "Employer name: Acme Corp"
        ssn, scrubbed = _extract_ssn(text)
        assert ssn == ""
        assert scrubbed == text

    def test_multiple_ssns_returns_first(self):
        text = "Primary: 111-22-3333 Secondary: 444-55-6666"
        ssn, scrubbed = _extract_ssn(text)
        assert ssn == "111-22-3333"
        assert "111-22-3333" not in scrubbed
        assert "444-55-6666" not in scrubbed


class TestDollarsToCents:
    def test_string_with_dollar_sign(self):
        assert _dollars_to_cents("$75,000.00") == 7500000

    def test_string_plain(self):
        assert _dollars_to_cents("50000") == 5000000

    def test_float(self):
        assert _dollars_to_cents(75000.50) == 7500050

    def test_integer(self):
        assert _dollars_to_cents(100) == 100

    def test_empty_string(self):
        assert _dollars_to_cents("") == 0

    def test_zero(self):
        assert _dollars_to_cents(0) == 0

    def test_string_with_spaces(self):
        assert _dollars_to_cents(" 1,234.56 ") == 123456


class TestMockExtraction:
    def test_returns_valid_result(self):
        result = _mock_extraction()
        assert isinstance(result, W2ExtractionResult)
        assert result.tier_used == "mock"
        assert result.employer_name == "Acme Corporation"
        assert result.wages == 7500000
        assert result.confidence > 0
        assert result.employee_ssn == "123-45-6789"


@pytest.mark.asyncio
async def test_process_w2_mock_mode():
    """Without API keys, process_w2 should return mock data."""
    dummy_image = b"\xff\xd8\xff" + b"\x00" * 100
    result = await process_w2(dummy_image)
    assert result.tier_used == "mock"
    assert result.wages > 0
    assert result.employer_name != ""
