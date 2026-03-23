from app.services.pii import scrub_pii


class TestPIIScrubbing:
    def test_scrubs_ssn_dashes(self):
        assert scrub_pii("SSN is 123-45-6789") == "SSN is ***-**-****"

    def test_scrubs_ssn_spaces(self):
        assert scrub_pii("SSN 123 45 6789") == "SSN ***-**-****"

    def test_scrubs_ein(self):
        assert scrub_pii("EIN: 12-3456789") == "EIN: **-*******"

    def test_scrubs_credit_card(self):
        assert "****" in scrub_pii("Card: 4111-1111-1111-1111")

    def test_preserves_clean_text(self):
        text = "The tax refund was $1,234. Filed on 2026-01-15."
        assert scrub_pii(text) == text

    def test_multiple_patterns(self):
        text = "SSN: 123-45-6789, EIN: 12-3456789"
        result = scrub_pii(text)
        assert "123-45-6789" not in result
        assert "12-3456789" not in result
