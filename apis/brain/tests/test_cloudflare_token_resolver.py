"""Tests for app.services.cloudflare_token_resolver (WS-47)."""

from __future__ import annotations

import logging

# ---------------------------------------------------------------------------
# zone_to_slug
# ---------------------------------------------------------------------------


def test_zone_to_slug_simple_tld():
    from app.services.cloudflare_token_resolver import zone_to_slug

    assert zone_to_slug("axiomfolio.com") == "AXIOMFOLIO_COM"


def test_zone_to_slug_two_char_tld():
    from app.services.cloudflare_token_resolver import zone_to_slug

    assert zone_to_slug("filefree.ai") == "FILEFREE_AI"


def test_zone_to_slug_strips_and_lowercases():
    from app.services.cloudflare_token_resolver import zone_to_slug

    assert zone_to_slug("  PaperWorkLabs.COM  ") == "PAPERWORKLABS_COM"


def test_zone_to_slug_hyphen_in_name():
    from app.services.cloudflare_token_resolver import zone_to_slug

    assert zone_to_slug("distill.tax") == "DISTILL_TAX"


# ---------------------------------------------------------------------------
# resolve_write_token — per-zone token takes priority
# ---------------------------------------------------------------------------


def test_resolve_write_token_per_zone_preferred(monkeypatch):
    """Per-zone env var is returned when set, no fallback."""
    monkeypatch.setenv("CLOUDFLARE_TOKEN_AXIOMFOLIO_COM", "per-zone-tok-abc")
    # Account-wide also set — should NOT be returned
    monkeypatch.setattr(
        "app.services.cloudflare_token_resolver.settings",
        _mock_settings(api_token="account-wide-tok"),
    )

    from app.services import cloudflare_token_resolver

    result = cloudflare_token_resolver.resolve_write_token("axiomfolio.com")
    assert result == "per-zone-tok-abc"


def test_resolve_write_token_fallback_to_account_wide(monkeypatch, caplog):
    """Falls back to account-wide token when per-zone is absent; emits warning."""
    monkeypatch.delenv("CLOUDFLARE_TOKEN_AXIOMFOLIO_COM", raising=False)
    monkeypatch.setattr(
        "app.services.cloudflare_token_resolver.settings",
        _mock_settings(api_token="acct-fallback"),
    )

    from app.services import cloudflare_token_resolver

    with caplog.at_level(logging.WARNING, logger="app.services.cloudflare_token_resolver"):
        result = cloudflare_token_resolver.resolve_write_token("axiomfolio.com")

    assert result == "acct-fallback"
    assert "falling back to CLOUDFLARE_API_TOKEN" in caplog.text


def test_resolve_write_token_none_when_nothing_configured(monkeypatch, caplog):
    """Returns None and logs error when no token is available."""
    monkeypatch.delenv("CLOUDFLARE_TOKEN_AXIOMFOLIO_COM", raising=False)
    monkeypatch.setattr(
        "app.services.cloudflare_token_resolver.settings",
        _mock_settings(api_token=""),
    )

    from app.services import cloudflare_token_resolver

    with caplog.at_level(logging.ERROR, logger="app.services.cloudflare_token_resolver"):
        result = cloudflare_token_resolver.resolve_write_token("axiomfolio.com")

    assert result is None
    assert "neither" in caplog.text


def test_resolve_write_token_unknown_zone_falls_back(monkeypatch, caplog):
    """Unknown zones still fall back to account-wide and log a warning."""
    monkeypatch.delenv("CLOUDFLARE_TOKEN_UNKNOWN_ZONE_XYZ", raising=False)
    monkeypatch.setattr(
        "app.services.cloudflare_token_resolver.settings",
        _mock_settings(api_token="fallback-tok"),
    )

    from app.services import cloudflare_token_resolver

    with caplog.at_level(logging.WARNING, logger="app.services.cloudflare_token_resolver"):
        result = cloudflare_token_resolver.resolve_write_token("unknown.zone.xyz")

    assert result == "fallback-tok"
    assert "falling back to CLOUDFLARE_API_TOKEN" in caplog.text


# ---------------------------------------------------------------------------
# write_auth_headers
# ---------------------------------------------------------------------------


def test_write_auth_headers_returns_dict_with_bearer(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_TOKEN_PAPERWORKLABS_COM", "pz-tok-xyz")
    monkeypatch.setattr(
        "app.services.cloudflare_token_resolver.settings",
        _mock_settings(api_token=""),
    )

    from app.services import cloudflare_token_resolver

    headers = cloudflare_token_resolver.write_auth_headers("paperworklabs.com")
    assert headers == {
        "Authorization": "Bearer pz-tok-xyz",
        "Content-Type": "application/json",
    }


def test_write_auth_headers_empty_when_no_token(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_TOKEN_PAPERWORKLABS_COM", raising=False)
    monkeypatch.setattr(
        "app.services.cloudflare_token_resolver.settings",
        _mock_settings(api_token=""),
    )

    from app.services import cloudflare_token_resolver

    headers = cloudflare_token_resolver.write_auth_headers("paperworklabs.com")
    assert headers == {}


# ---------------------------------------------------------------------------
# cloudflare_client integration
# ---------------------------------------------------------------------------


def test_cloudflare_client_write_uses_resolver(monkeypatch):
    """cloudflare_auth_headers(write=True) delegates to resolver."""
    monkeypatch.setenv("CLOUDFLARE_TOKEN_AXIOMFOLIO_COM", "zone-write-tok")
    monkeypatch.setattr(
        "app.services.cloudflare_token_resolver.settings",
        _mock_settings(api_token="should-not-be-used"),
    )

    from app.services.cloudflare_client import cloudflare_auth_headers

    headers = cloudflare_auth_headers(hostname_or_apex="axiomfolio.com", write=True)
    assert headers["Authorization"] == "Bearer zone-write-tok"


def test_cloudflare_client_read_uses_readonly_token(monkeypatch):
    """cloudflare_auth_headers(write=False) returns the read-only token."""
    monkeypatch.setattr(
        "app.services.cloudflare_client.settings",
        _mock_settings_with_readonly(
            readonly_axiomfolio="ro-tok-axiom",
            api_token="should-not-be-used",
        ),
    )

    from app.services.cloudflare_client import cloudflare_auth_headers

    headers = cloudflare_auth_headers(hostname_or_apex="axiomfolio.com", write=False)
    assert headers["Authorization"] == "Bearer ro-tok-axiom"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockSettings:
    def __init__(
        self,
        api_token: str = "",
        readonly_paperworklabs: str = "",
        readonly_axiomfolio: str = "",
        readonly_filefree: str = "",
        readonly_launchfree: str = "",
        readonly_distill_tax: str = "",
    ) -> None:
        self.CLOUDFLARE_API_TOKEN = api_token
        self.CLOUDFLARE_READONLY_TOKEN_PAPERWORKLABS = readonly_paperworklabs
        self.CLOUDFLARE_READONLY_TOKEN_AXIOMFOLIO = readonly_axiomfolio
        self.CLOUDFLARE_READONLY_TOKEN_FILEFREE = readonly_filefree
        self.CLOUDFLARE_READONLY_TOKEN_LAUNCHFREE = readonly_launchfree
        self.CLOUDFLARE_READONLY_TOKEN_DISTILL_TAX = readonly_distill_tax


def _mock_settings(api_token: str = "") -> _MockSettings:
    return _MockSettings(api_token=api_token)


def _mock_settings_with_readonly(
    readonly_axiomfolio: str = "",
    api_token: str = "",
) -> _MockSettings:
    return _MockSettings(api_token=api_token, readonly_axiomfolio=readonly_axiomfolio)
