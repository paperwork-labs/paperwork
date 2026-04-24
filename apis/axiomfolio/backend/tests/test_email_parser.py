"""Unit tests for the polymorphic email parser scaffold.

No DB, no network, no real LLM. Provider is stubbed; PDF parsing degrades
to a warning when pypdf is not installed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.services.picks.email_parser import (
    EmailPreprocessor,
    LLMParseProvider,
    LLMRequest,
    ParserLimits,
    ParseResult,
    PolymorphicEmailParser,
    RawEmail,
    SourceFormat,
    StubLLMParseProvider,
)
from backend.services.picks.email_parser.preprocessor import (
    _extract_candidate_tickers,
    _html_to_text,
    _strip_forwarded_envelopes,
)
from backend.services.picks.email_parser.types import (
    PickActionHint,
    clamp_confidence,
    clamp_sentiment,
)

pytestmark = pytest.mark.no_db


# --------------------------------------------------------------------------- #
# clamp helpers                                                               #
# --------------------------------------------------------------------------- #


class TestClamp:
    def test_confidence_clamped_to_unit_interval(self):
        assert clamp_confidence(1.7) == Decimal("1")
        assert clamp_confidence(-0.2) == Decimal("0")
        assert clamp_confidence(0.5) == Decimal("0.5")
        assert clamp_confidence("0.42") == Decimal("0.42")

    def test_confidence_garbage_returns_zero(self):
        assert clamp_confidence(None) == Decimal("0")
        assert clamp_confidence("not a number") == Decimal("0")

    def test_sentiment_clamped_to_signed_unit_interval(self):
        assert clamp_sentiment(2) == Decimal("1")
        assert clamp_sentiment(-3) == Decimal("-1")
        assert clamp_sentiment(0.0) == Decimal("0")


# --------------------------------------------------------------------------- #
# Preprocessor                                                                #
# --------------------------------------------------------------------------- #


class TestPreprocessorInline:
    def test_plain_text_passes_through(self):
        pp = EmailPreprocessor()
        out = pp.normalize(
            RawEmail(
                sender="A N <a@example.com>",
                subject="watchlist",
                received_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                body_text="Buy AAPL on the dip; trim NVDA.",
            )
        )
        assert out.source_format == SourceFormat.PLAIN_TEXT
        assert "AAPL" in out.candidate_tickers
        assert "NVDA" in out.candidate_tickers
        assert out.received_at.tzinfo is timezone.utc

    def test_html_is_stripped(self):
        pp = EmailPreprocessor()
        out = pp.normalize(
            RawEmail(
                sender="x@y.com",
                subject="s",
                received_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                body_html="<html><body><p>Buy <b>MSFT</b></p>"
                "<script>alert(1)</script></body></html>",
            )
        )
        assert out.source_format == SourceFormat.HTML
        assert "MSFT" in out.body
        assert "alert" not in out.body  # script tag dropped

    def test_default_received_at_is_utc(self):
        pp = EmailPreprocessor()
        out = pp.normalize(RawEmail(body_text="hi"))
        assert out.received_at.tzinfo is timezone.utc

    def test_image_attachments_become_data_urls(self):
        pp = EmailPreprocessor()
        out = pp.normalize(
            RawEmail(
                body_text="see chart",
                image_attachments=[("image/png", b"\x89PNG\r\n\x1a\nfake")],
            )
        )
        assert len(out.image_b64_blocks) == 1
        assert out.image_b64_blocks[0].startswith("data:image/png;base64,")

    def test_pdf_without_pypdf_emits_warning(self, monkeypatch):
        # Force the lazy import in _pdf_to_text to fail.
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *a, **kw):
            if name == "pypdf":
                raise ImportError("forced for test")
            return real_import(name, *a, **kw)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        pp = EmailPreprocessor()
        out = pp.normalize(
            RawEmail(body_text="see attached", pdf_attachments=[b"%PDF-1.4 fake"])
        )
        assert out.extracted_pdf_text == ""
        assert any("pypdf not installed" in w for w in out.parse_warnings)


class TestPreprocessorRfc822:
    def test_parses_rfc822_with_text_body(self):
        raw = (
            b"From: A N <a@example.com>\r\n"
            b"Subject: Test signal\r\n"
            b"Date: Wed, 25 Mar 2026 15:33:00 -0700\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"\r\n"
            b"Buy NVDA. Avoid TSLA.\r\n"
        )
        pp = EmailPreprocessor()
        out = pp.normalize(RawEmail(raw_bytes=raw))
        assert out.sender == "A N <a@example.com>"
        assert out.subject == "Test signal"
        assert "NVDA" in out.candidate_tickers
        assert out.received_at.year == 2026

    def test_forwarded_message_marker_sets_format(self):
        raw = (
            b"From: a@example.com\r\n"
            b"Subject: Fwd\r\n"
            b"Content-Type: text/plain\r\n"
            b"\r\n"
            b"---------- Forwarded message ----------\r\n"
            b"From: analyst@firm.com\r\n"
            b"Real content here. Buy AAPL.\r\n"
        )
        pp = EmailPreprocessor()
        out = pp.normalize(RawEmail(raw_bytes=raw))
        assert out.source_format == SourceFormat.FORWARDED_EMAIL
        # The marker text was stripped from the body.
        assert "Forwarded message" not in out.body
        assert "AAPL" in out.candidate_tickers


class TestPreprocessorHelpers:
    def test_html_to_text_collapses_whitespace(self):
        out = _html_to_text("<p>a</p>\n\n\n<p>b</p>")
        assert "a" in out and "b" in out
        assert "\n\n\n" not in out

    def test_extract_candidate_tickers_drops_stopwords(self):
        out = _extract_candidate_tickers("THE AND USA AAPL MSFT")
        assert "THE" not in out and "USA" not in out
        assert "AAPL" in out and "MSFT" in out

    def test_extract_candidate_tickers_dedupes(self):
        out = _extract_candidate_tickers("AAPL aapl AAPL MSFT")
        assert out == ("AAPL", "MSFT")

    def test_strip_forwarded_envelopes_keeps_body(self):
        text = (
            "---------- Forwarded message ----------\n"
            "From: x@y.com\n"
            "Real content here.\n"
        )
        out = _strip_forwarded_envelopes(text)
        assert "Forwarded message" not in out
        assert "Real content" in out


# --------------------------------------------------------------------------- #
# Provider protocol                                                           #
# --------------------------------------------------------------------------- #


class TestStubProvider:
    def test_satisfies_protocol(self):
        stub = StubLLMParseProvider(["{}"])
        assert isinstance(stub, LLMParseProvider)

    def test_records_calls_in_order(self):
        stub = StubLLMParseProvider(["a", "b"])
        r1 = stub.parse(LLMRequest(system_prompt="s", user_prompt="u1"))
        r2 = stub.parse(LLMRequest(system_prompt="s", user_prompt="u2"))
        assert (r1.raw_text, r2.raw_text) == ("a", "b")
        assert [c.user_prompt for c in stub.calls] == ["u1", "u2"]

    def test_exhaustion_raises(self):
        stub = StubLLMParseProvider([])
        with pytest.raises(RuntimeError, match="exhausted"):
            stub.parse(LLMRequest(system_prompt="s", user_prompt="u"))


# --------------------------------------------------------------------------- #
# Parser orchestrator                                                         #
# --------------------------------------------------------------------------- #


def _good_payload(picks=None, macro=None, changes=None, conf=0.8):
    return json.dumps(
        {
            "picks": picks or [],
            "macro": macro or [],
            "position_changes": changes or [],
            "overall_confidence": conf,
            "parser_notes": "",
        }
    )


def _norm(body="Buy AAPL.", subject="watchlist") -> "object":
    pp = EmailPreprocessor()
    return pp.normalize(
        RawEmail(
            sender="a@example.com",
            subject=subject,
            received_at=datetime(2026, 4, 9, tzinfo=timezone.utc),
            body_text=body,
        )
    )


class TestParserHappyPath:
    def test_extracts_pick(self):
        provider = StubLLMParseProvider(
            [
                _good_payload(
                    picks=[
                        {
                            "symbol": "AAPL",
                            "action": "buy",
                            "confidence": 0.9,
                            "rationale": "Stage 2A breakout",
                            "target_price": "200.00",
                            "stop_loss": "180.00",
                            "horizon_days": 60,
                            "source_excerpt": "buy AAPL on the dip",
                        }
                    ]
                )
            ]
        )
        parser = PolymorphicEmailParser(provider)
        result = parser.parse(_norm())
        assert isinstance(result, ParseResult)
        assert len(result.picks) == 1
        pick = result.picks[0]
        assert pick.symbol == "AAPL"
        assert pick.action == PickActionHint.BUY
        assert pick.confidence == Decimal("0.9")
        assert pick.target_price == Decimal("200.00")
        assert pick.horizon_days == 60
        assert result.parse_errors == ()

    def test_extracts_macro_and_position_change(self):
        provider = StubLLMParseProvider(
            [
                _good_payload(
                    macro=[
                        {
                            "headline": "Tech rotation",
                            "body": "Mega-caps rolling over",
                            "sentiment": "-0.3",
                            "confidence": 0.7,
                            "sectors": ["XLK", "XLY"],
                            "horizon_days": 30,
                            "source_excerpt": "tech rolling",
                        }
                    ],
                    changes=[
                        {
                            "symbol": "TSLA",
                            "action": "trim",
                            "quantity_hint": 50,
                            "occurred_at_hint": "2026-04-08T20:00:00Z",
                            "confidence": 0.6,
                            "source_excerpt": "trimmed TSLA yesterday",
                        }
                    ],
                )
            ]
        )
        parser = PolymorphicEmailParser(provider)
        result = parser.parse(_norm())
        assert len(result.macro) == 1
        assert result.macro[0].sentiment == Decimal("-0.3")
        assert result.macro[0].sectors == ("XLK", "XLY")
        assert len(result.position_changes) == 1
        pc = result.position_changes[0]
        assert pc.symbol == "TSLA"
        assert pc.action == PickActionHint.TRIM
        assert pc.occurred_at_hint == datetime(2026, 4, 8, 20, 0, tzinfo=timezone.utc)


class TestParserErrorPaths:
    def test_provider_exception_returns_empty_result(self):
        class _Boom:
            def parse(self, request):
                raise RuntimeError("connection reset")

        parser = PolymorphicEmailParser(_Boom())
        result = parser.parse(_norm())
        assert result.is_empty()
        assert any("provider_failed" in e for e in result.parse_errors)

    def test_invalid_json_returns_empty_result(self):
        provider = StubLLMParseProvider(["not json at all"])
        parser = PolymorphicEmailParser(provider)
        result = parser.parse(_norm())
        assert result.is_empty()
        assert any("schema_invalid" in e for e in result.parse_errors)

    def test_missing_required_field_caught(self):
        provider = StubLLMParseProvider([json.dumps({"picks": []})])  # no overall_conf
        parser = PolymorphicEmailParser(provider)
        result = parser.parse(_norm())
        assert any("missing required field" in e for e in result.parse_errors)

    def test_per_record_errors_skip_only_that_record(self):
        provider = StubLLMParseProvider(
            [
                _good_payload(
                    picks=[
                        # invalid ticker (too long; >10 chars)
                        {
                            "symbol": "TOOLONGTICKER",
                            "action": "buy",
                            "confidence": 0.5,
                            "rationale": "x",
                        },
                        # invalid ticker (number prefix)
                        {
                            "symbol": "9X",
                            "action": "buy",
                            "confidence": 0.5,
                            "rationale": "y",
                        },
                        # good ticker
                        {
                            "symbol": "AAPL",
                            "action": "buy",
                            "confidence": 0.9,
                            "rationale": "z",
                        },
                    ]
                )
            ]
        )
        parser = PolymorphicEmailParser(provider)
        result = parser.parse(_norm())
        assert len(result.picks) == 1
        assert result.picks[0].symbol == "AAPL"
        invalid_errors = [e for e in result.parse_errors if "invalid ticker" in e]
        assert len(invalid_errors) == 2

    def test_unknown_action_skipped(self):
        provider = StubLLMParseProvider(
            [
                _good_payload(
                    picks=[
                        {
                            "symbol": "AAPL",
                            "action": "yolo",
                            "confidence": 0.5,
                            "rationale": "x",
                        }
                    ]
                )
            ]
        )
        result = PolymorphicEmailParser(provider).parse(_norm())
        assert result.picks == ()
        assert any("unknown action" in e for e in result.parse_errors)


class TestParserClamping:
    def test_confidence_above_one_is_clamped(self):
        provider = StubLLMParseProvider(
            [
                _good_payload(
                    picks=[
                        {
                            "symbol": "AAPL",
                            "action": "buy",
                            "confidence": 1.7,
                            "rationale": "x",
                        }
                    ]
                )
            ]
        )
        result = PolymorphicEmailParser(provider).parse(_norm())
        assert result.picks[0].confidence == Decimal("1")

    def test_negative_horizon_days_skipped(self):
        provider = StubLLMParseProvider(
            [
                _good_payload(
                    picks=[
                        {
                            "symbol": "AAPL",
                            "action": "buy",
                            "confidence": 0.5,
                            "rationale": "x",
                            "horizon_days": -5,
                        }
                    ]
                )
            ]
        )
        result = PolymorphicEmailParser(provider).parse(_norm())
        assert result.picks == ()
        assert any("negative horizon" in e for e in result.parse_errors)

    def test_excerpt_truncated_to_limit(self):
        provider = StubLLMParseProvider(
            [
                _good_payload(
                    picks=[
                        {
                            "symbol": "AAPL",
                            "action": "buy",
                            "confidence": 0.5,
                            "rationale": "r",
                            "source_excerpt": "x" * 500,
                        }
                    ]
                )
            ]
        )
        limits = ParserLimits(max_excerpt_chars=100)
        result = PolymorphicEmailParser(provider, limits=limits).parse(_norm())
        assert len(result.picks[0].source_excerpt) <= 100


class TestParserLimits:
    def test_max_picks_enforced(self):
        items = [
            {"symbol": f"AAA{i}"[:5] if i < 100 else "AAPL",
             "action": "buy", "confidence": 0.5, "rationale": "x"}
            for i in range(50)
        ]
        # Replace symbols with valid uppercase tickers
        for idx, item in enumerate(items):
            item["symbol"] = chr(ord("A") + (idx % 26)) + chr(ord("A") + ((idx // 26) % 26))
        provider = StubLLMParseProvider([_good_payload(picks=items)])
        limits = ParserLimits(max_picks=5)
        result = PolymorphicEmailParser(provider, limits=limits).parse(_norm())
        assert len(result.picks) == 5

    def test_invalid_provider_raises_at_construction(self):
        with pytest.raises(TypeError):
            PolymorphicEmailParser(provider="not a provider")  # type: ignore[arg-type]

    def test_long_body_is_truncated_in_prompt(self):
        provider = StubLLMParseProvider([_good_payload()])
        limits = ParserLimits(max_body_chars=200)
        big_body = "Buy AAPL. " + ("filler " * 1000)
        norm = EmailPreprocessor().normalize(
            RawEmail(
                sender="a@b.com",
                subject="s",
                received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                body_text=big_body,
            )
        )
        PolymorphicEmailParser(provider, limits=limits).parse(norm)
        # The provider received a request whose user_prompt contains the
        # truncation marker.
        assert any("truncated" in c.user_prompt for c in provider.calls)


class TestParseResultShape:
    def test_telemetry_propagates(self):
        provider = StubLLMParseProvider([_good_payload()])
        result = PolymorphicEmailParser(provider).parse(_norm())
        assert result.llm_provider == "stub"
        assert result.llm_model == "stub-model"
        assert result.prompt_tokens > 0
        assert result.completion_tokens > 0
        assert result.elapsed_ms >= 0

    def test_request_id_unique_per_call(self):
        provider = StubLLMParseProvider([_good_payload(), _good_payload()])
        parser = PolymorphicEmailParser(provider)
        r1 = parser.parse(_norm())
        r2 = parser.parse(_norm())
        assert r1.request_id != r2.request_id

    def test_warnings_passed_through(self):
        # Build a NormalizedEmail with a warning baked in.
        from backend.services.picks.email_parser.preprocessor import NormalizedEmail

        norm = NormalizedEmail(
            sender="a@b.com",
            subject="s",
            received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            body="hi",
            source_format=SourceFormat.PLAIN_TEXT,
            extracted_pdf_text="",
            image_b64_blocks=(),
            candidate_tickers=(),
            parse_warnings=("warn-from-preprocessor",),
        )
        provider = StubLLMParseProvider([_good_payload()])
        result = PolymorphicEmailParser(provider).parse(norm)
        assert "warn-from-preprocessor" in result.parse_warnings
