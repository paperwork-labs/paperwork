"""Gmail SMTP fallback for high/critical Brain conversations (WS-69 PR J).

Sends a plain-text + HTML email to ``FOUNDER_FALLBACK_EMAIL`` whenever a
Conversation is created with urgency in {high, critical} and
``needs_founder_action=True``.

Env vars required (all three must be set; Brain surfaces a structured error
if any are missing — no silent skip per no-silent-fallback.mdc):

- ``GMAIL_USERNAME``: the Gmail address used for SMTP auth (e.g. ``brain@paperworklabs.com``)
- ``GMAIL_APP_PASSWORD``: Google app password (16-char, generated per Google Account → Security)
- ``FOUNDER_FALLBACK_EMAIL``: delivery address (e.g. ``founder@paperworklabs.com``)

Optional:

- ``STUDIO_BASE_URL``: base URL for Studio deep links (default ``https://studio.paperworklabs.com``).

medallion: ops
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from html import escape

from app.config import settings

logger = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


class EmailConfigError(RuntimeError):
    """Raised when required Gmail SMTP env vars are missing."""


def _require_smtp_config() -> tuple[str, str, str]:
    """Return (username, app_password, to_address) or raise EmailConfigError.

    Never returns partial config — all three must be present.
    """
    username = (getattr(settings, "GMAIL_USERNAME", "") or "").strip()
    app_password = (getattr(settings, "GMAIL_APP_PASSWORD", "") or "").strip()
    to_address = (getattr(settings, "FOUNDER_FALLBACK_EMAIL", "") or "").strip()

    missing = [
        name
        for name, val in [
            ("GMAIL_USERNAME", username),
            ("GMAIL_APP_PASSWORD", app_password),
            ("FOUNDER_FALLBACK_EMAIL", to_address),
        ]
        if not val
    ]
    if missing:
        raise EmailConfigError(
            f"Gmail SMTP fallback is not configured — missing env vars: {', '.join(missing)}. "
            "Set GMAIL_USERNAME, GMAIL_APP_PASSWORD, and FOUNDER_FALLBACK_EMAIL in Brain env "
            "(Render dashboard). Until then high/critical conversations will NOT deliver email."
        )
    return username, app_password, to_address


def _studio_base() -> str:
    return (getattr(settings, "STUDIO_BASE_URL", "") or "").strip().rstrip("/")


def _build_deep_link(conversation_id: str) -> str:
    base = _studio_base() or "https://studio.paperworklabs.com"
    return f"{base}/admin/brain/conversations/{conversation_id}"


def _build_attachment_lines(attachments: list[dict[str, str]]) -> str:
    if not attachments:
        return ""
    lines = ["\n\nAttachments:"]
    for att in attachments:
        url = att.get("url", "")
        name = att.get("id", url)
        lines.append(f"  - {name}: {url}")
    return "\n".join(lines)


def send_conversation_email(
    *,
    conversation_id: str,
    title: str,
    body_md: str,
    attachments: list[dict[str, str]] | None = None,
) -> None:
    """Send a Gmail SMTP email for a high/critical conversation.

    Plain-text parts use the raw title and body (human-readable markdown).
    The HTML alternative escapes dynamic strings so injected markup cannot
    execute in HTML-capable clients.

    Raises:
        EmailConfigError: if any of the three required env vars are missing.
        RuntimeError: if the SMTP connection or send fails.

    Never silently skips — callers must handle or log the exception.
    """
    username, app_password, to_address = _require_smtp_config()

    deep_link = _build_deep_link(conversation_id)
    att_lines = _build_attachment_lines(attachments or [])

    subject_title = " ".join(title.splitlines()).strip()
    subject = f"[Brain] {subject_title}"
    text_body = f"{title}\n\n{body_md}\n\nOpen in Brain: {deep_link}{att_lines}"

    title_html = escape(title)
    body_html = escape(body_md).replace("\n", "<br>\n")
    deep_esc = escape(deep_link, quote=True)
    att_html = ""
    if attachments:
        parts: list[str] = []
        for a in attachments:
            url = a.get("url", "") or ""
            label = a.get("id", url) or url
            parts.append(f'<li><a href="{escape(url, quote=True)}">{escape(label)}</a></li>')
        att_html = "<ul>" + "".join(parts) + "</ul>"

    html_body = (
        f"<h2>{title_html}</h2>"
        f"<p>{body_html}</p>"
        f'<p><a href="{deep_esc}">Open in Brain →</a></p>'
        f"{att_html}"
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = username
    msg["To"] = to_address
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(username, app_password)
            smtp.send_message(msg)
        logger.info("email_outbound: Brain notification email sent (conv=%s)", conversation_id)
    except smtplib.SMTPException as exc:
        raise RuntimeError(
            f"email_outbound: SMTP send failed for conversation {conversation_id!r}: {exc}"
        ) from exc
