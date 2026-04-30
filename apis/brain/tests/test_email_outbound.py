"""Tests for the Gmail SMTP email fallback service (WS-69 PR J)."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from app.services.email_outbound import (
    EmailConfigError,
    _build_attachment_lines,
    _build_deep_link,
    send_conversation_email,
)

# ---------------------------------------------------------------------------
# _build_deep_link
# ---------------------------------------------------------------------------


def test_build_deep_link_includes_id() -> None:
    link = _build_deep_link("abc-123")
    assert "abc-123" in link
    assert link.startswith("https://studio.paperworklabs.com/admin/brain/conversations/")


# ---------------------------------------------------------------------------
# _build_attachment_lines
# ---------------------------------------------------------------------------


def test_build_attachment_lines_empty() -> None:
    assert _build_attachment_lines([]) == ""


def test_build_attachment_lines_renders_name_and_url() -> None:
    att = [{"id": "receipt.pdf", "url": "https://storage.example.com/receipt.pdf"}]
    out = _build_attachment_lines(att)
    assert "receipt.pdf" in out
    assert "https://storage.example.com/receipt.pdf" in out


def test_build_attachment_lines_falls_back_to_url_when_no_id() -> None:
    att = [{"url": "https://storage.example.com/file.png"}]
    out = _build_attachment_lines(att)
    assert "https://storage.example.com/file.png" in out


# ---------------------------------------------------------------------------
# send_conversation_email — missing config raises EmailConfigError
# ---------------------------------------------------------------------------


def test_send_raises_email_config_error_when_all_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.email_outbound.settings",
        MagicMock(
            GMAIL_USERNAME="",
            GMAIL_APP_PASSWORD="",
            FOUNDER_FALLBACK_EMAIL="",
        ),
    )
    with pytest.raises(EmailConfigError, match="missing env vars"):
        send_conversation_email(
            conversation_id="conv-1",
            title="Test",
            body_md="body",
        )


def test_send_raises_email_config_error_missing_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.email_outbound.settings",
        MagicMock(
            GMAIL_USERNAME="brain@example.com",
            GMAIL_APP_PASSWORD="",
            FOUNDER_FALLBACK_EMAIL="founder@example.com",
        ),
    )
    with pytest.raises(EmailConfigError, match="GMAIL_APP_PASSWORD"):
        send_conversation_email(
            conversation_id="conv-1",
            title="Critical Alert",
            body_md="Something went wrong",
        )


def test_send_raises_email_config_error_names_all_missing_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.email_outbound.settings",
        MagicMock(
            GMAIL_USERNAME="",
            GMAIL_APP_PASSWORD="",
            FOUNDER_FALLBACK_EMAIL="",
        ),
    )
    with pytest.raises(EmailConfigError) as exc_info:
        send_conversation_email(conversation_id="conv-1", title="T", body_md="B")
    msg = str(exc_info.value)
    assert "GMAIL_USERNAME" in msg
    assert "GMAIL_APP_PASSWORD" in msg
    assert "FOUNDER_FALLBACK_EMAIL" in msg


# ---------------------------------------------------------------------------
# send_conversation_email — subject + body formatting
# ---------------------------------------------------------------------------


def _make_mock_settings() -> MagicMock:
    return MagicMock(
        GMAIL_USERNAME="brain@paperworklabs.com",
        GMAIL_APP_PASSWORD="app-password-123",
        FOUNDER_FALLBACK_EMAIL="founder@paperworklabs.com",
    )


def test_send_calls_smtp_send_message_with_correct_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.email_outbound.settings", _make_mock_settings())

    mock_smtp = MagicMock()
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)

    with patch("app.services.email_outbound.smtplib.SMTP", return_value=mock_smtp):
        send_conversation_email(
            conversation_id="conv-42",
            title="Infra Down",
            body_md="**All services offline.**",
        )

    mock_smtp.send_message.assert_called_once()
    msg: EmailMessage = mock_smtp.send_message.call_args[0][0]
    assert msg["Subject"] == "[Brain] Infra Down"
    assert msg["To"] == "founder@paperworklabs.com"
    assert msg["From"] == "brain@paperworklabs.com"


def test_send_body_contains_deep_link(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.email_outbound.settings", _make_mock_settings())

    mock_smtp = MagicMock()
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)

    with patch("app.services.email_outbound.smtplib.SMTP", return_value=mock_smtp):
        send_conversation_email(
            conversation_id="conv-99",
            title="Alert",
            body_md="body text",
        )

    msg: EmailMessage = mock_smtp.send_message.call_args[0][0]
    payload = msg.get_body()
    assert payload is not None
    content = payload.get_payload()
    assert "conv-99" in content


def test_send_body_includes_attachment_links(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.email_outbound.settings", _make_mock_settings())

    mock_smtp = MagicMock()
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)

    with patch("app.services.email_outbound.smtplib.SMTP", return_value=mock_smtp):
        send_conversation_email(
            conversation_id="conv-5",
            title="Doc Ready",
            body_md="Your doc is ready.",
            attachments=[{"id": "report.pdf", "url": "https://storage.example.com/r.pdf"}],
        )

    msg: EmailMessage = mock_smtp.send_message.call_args[0][0]
    payload = msg.get_body()
    assert payload is not None
    content = payload.get_payload()
    assert "report.pdf" in content
    assert "https://storage.example.com/r.pdf" in content


# ---------------------------------------------------------------------------
# send_conversation_email — SMTP send failure → RuntimeError
# ---------------------------------------------------------------------------


def test_send_raises_runtime_error_on_smtp_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.email_outbound.settings", _make_mock_settings())

    mock_smtp = MagicMock()
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)
    mock_smtp.send_message.side_effect = smtplib.SMTPException("Connection refused")

    with (
        patch("app.services.email_outbound.smtplib.SMTP", return_value=mock_smtp),
        pytest.raises(RuntimeError, match="SMTP send failed"),
    ):
        send_conversation_email(
            conversation_id="conv-fail",
            title="Failed Alert",
            body_md="This won't be delivered.",
        )
