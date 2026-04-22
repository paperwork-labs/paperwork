"""Tests for :mod:`backend.services.oauth.coinbase`."""

from __future__ import annotations

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

from backend.services.oauth.base import OAuthCallbackContext, OAuthError
from backend.services.oauth.coinbase import CoinbaseOAuthAdapter


@patch("backend.services.oauth.coinbase.settings")
def test_initiate_url_code_grant_and_redirect(mock_settings: object) -> None:
    mock_settings.COINBASE_CLIENT_ID = "cid"
    mock_settings.COINBASE_CLIENT_SECRET = "sec"
    mock_settings.COINBASE_OAUTH_REQUEST_TIMEOUT_S = 15.0
    ad = CoinbaseOAuthAdapter()
    res = ad.initiate_url(
        user_id=901,
        callback_url="https://app.example.com/settings/connections?cb=1",
    )
    parsed = urlparse(res.authorize_url)
    assert parsed.scheme == "https"
    assert "coinbase.com" in parsed.netloc
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


@patch("backend.services.oauth.coinbase.settings")
@patch.object(CoinbaseOAuthAdapter, "_post_token")
def test_exchange_code_posts_redirect_uri(mock_post, mock_settings) -> None:
    mock_settings.COINBASE_CLIENT_ID = "cid"
    mock_settings.COINBASE_CLIENT_SECRET = "sec"
    mock_settings.COINBASE_OAUTH_REQUEST_TIMEOUT_S = 15.0
    mock_post.return_value = {
        "access_token": "at",
        "refresh_token": "rt",
        "expires_in": 7200,
    }
    ad = CoinbaseOAuthAdapter()
    ctx = OAuthCallbackContext(
        code="c0d3",
        state="st",
        extra={
            "callback_url": "https://app.example.com/oauth/cb",
            "user_id": 902,
        },
    )
    ad.exchange_code(ctx)
    assert mock_post.called
    call_payload = mock_post.call_args[0][0]
    assert call_payload.get("redirect_uri") == "https://app.example.com/oauth/cb"
    assert call_payload.get("grant_type") == "authorization_code"
    assert call_payload.get("code") == "c0d3"


@patch("backend.services.oauth.coinbase.settings")
@patch.object(CoinbaseOAuthAdapter, "_post_token")
def test_refresh_sends_refresh_token(mock_post, mock_settings) -> None:
    mock_settings.COINBASE_CLIENT_ID = "cid"
    mock_settings.COINBASE_CLIENT_SECRET = "sec"
    mock_settings.COINBASE_OAUTH_REQUEST_TIMEOUT_S = 15.0
    mock_post.return_value = {
        "access_token": "new_at",
        "refresh_token": "new_rt",
        "expires_in": 7200,
    }
    ad = CoinbaseOAuthAdapter()
    out = ad.refresh(access_token="old", refresh_token="rt_old")
    assert out.access_token == "new_at"
    assert out.refresh_token == "new_rt"
    body = mock_post.call_args[0][0]
    assert body.get("grant_type") == "refresh_token"
    assert body.get("refresh_token") == "rt_old"


@patch("backend.services.oauth.coinbase.settings")
@patch.object(CoinbaseOAuthAdapter, "_post_token")
def test_refresh_fails_without_refresh(mock_post, mock_settings) -> None:
    mock_settings.COINBASE_CLIENT_ID = "cid"
    mock_settings.COINBASE_CLIENT_SECRET = "sec"
    mock_settings.COINBASE_OAUTH_REQUEST_TIMEOUT_S = 15.0
    ad = CoinbaseOAuthAdapter()
    with pytest.raises(OAuthError) as ei:
        ad.refresh(access_token="x", refresh_token=None)
    assert ei.value.permanent is True
    assert mock_post.call_count == 0


@patch("backend.services.oauth.coinbase.requests.Session.post")
@patch("backend.services.oauth.coinbase.settings")
def test_post_token_classifies_400_permanent(mock_settings, mock_post) -> None:
    mock_settings.COINBASE_CLIENT_ID = "c"
    mock_settings.COINBASE_CLIENT_SECRET = "s"
    mock_settings.COINBASE_OAUTH_REQUEST_TIMEOUT_S = 15.0
    resp = mock_post.return_value
    resp.status_code = 400
    resp.text = "bad"
    resp.content = b"bad"
    ad = CoinbaseOAuthAdapter()
    with pytest.raises(OAuthError) as ei:
        ad._post_token({"grant_type": "authorization_code", "code": "x"})
    assert ei.value.permanent is True
    assert ei.value.provider_status == 400
