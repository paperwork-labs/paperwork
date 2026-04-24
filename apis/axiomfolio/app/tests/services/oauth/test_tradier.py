"""Tests for :mod:`app.services.oauth.tradier`."""

from __future__ import annotations

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from app.services.oauth.base import OAuthCallbackContext
from app.services.oauth.tradier import TradierOAuth2Adapter


@patch("app.services.oauth.tradier.settings")
def test_initiate_url_includes_code_grant_and_callback(mock_settings: object) -> None:
    mock_settings.TRADIER_CLIENT_ID = "cid"
    mock_settings.TRADIER_CLIENT_SECRET = "csecret"
    mock_settings.TRADIER_OAUTH_REQUEST_TIMEOUT_S = 15.0
    ad = TradierOAuth2Adapter()
    res = ad.initiate_url(
        user_id=1,
        callback_url="https://app.example.com/settings/connections?cb=1",
    )
    parsed = urlparse(res.authorize_url)
    assert parsed.scheme == "https"
    assert "tradier.com" in parsed.netloc
    q = parse_qs(parsed.query)
    assert q.get("response_type") == ["code"]
    assert q.get("client_id") == ["cid"]
    assert "redirect_uri" in q
    assert q["redirect_uri"] == [
        "https://app.example.com/settings/connections?cb=1"
    ]
    assert "state" in q
    assert "scope" in q
    assert res.extra.get("callback_url") == (
        "https://app.example.com/settings/connections?cb=1"
    )


@patch("app.services.oauth.tradier.settings")
@patch("app.services.oauth.tradier.TradierOAuth2Adapter._post_token")
def test_exchange_code_sends_redirect_uri(mock_post, mock_settings) -> None:
    mock_settings.TRADIER_CLIENT_ID = "cid"
    mock_settings.TRADIER_CLIENT_SECRET = "csecret"
    mock_settings.TRADIER_OAUTH_REQUEST_TIMEOUT_S = 15.0
    mock_post.return_value = {
        "access_token": "atok",
        "refresh_token": "rtok",
        "expires_in": 3600,
    }
    ad = TradierOAuth2Adapter()
    ctx = OAuthCallbackContext(
        code="c0d3",
        state="st",
        extra={
            "callback_url": "https://app.example.com/oauth/cb",
            "user_id": 1,
        },
    )
    ad.exchange_code(ctx)
    assert mock_post.called
    call_payload = mock_post.call_args[0][0]
    assert call_payload.get("redirect_uri") == "https://app.example.com/oauth/cb"
    assert call_payload.get("grant_type") == "authorization_code"
    assert call_payload.get("code") == "c0d3"
