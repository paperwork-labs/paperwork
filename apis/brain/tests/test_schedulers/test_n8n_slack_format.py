"""Unit tests for n8n-ported Slack formatting helpers."""

from app.schedulers._n8n_slack_format import format_structured_json_for_slack, sanitize_slack_mrkdwn


def test_sanitize_strips_code_fence_language() -> None:
    out = sanitize_slack_mrkdwn("```py\nhi\n```")
    assert out.startswith("```")
    assert "py" not in out[:6]


def test_format_structured_json_for_slack_parses_object() -> None:
    raw = '{"title":"A","body":"B"}'
    out = format_structured_json_for_slack(raw, header_prefix="Growth Content")
    assert "Growth Content" in out
    assert "Title" in out and "Body" in out
    assert "A" in out and "B" in out
