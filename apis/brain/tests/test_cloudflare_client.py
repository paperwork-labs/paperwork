from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import cloudflare_client as cf


def _settings(
    *,
    api: str = "",
    ro_pp: str = "",
    ro_ax: str = "",
    ro_ff: str = "",
    ro_lf: str = "",
    ro_dt: str = "",
) -> SimpleNamespace:
    return SimpleNamespace(
        CLOUDFLARE_API_TOKEN=api,
        CLOUDFLARE_READONLY_TOKEN_PAPERWORKLABS=ro_pp,
        CLOUDFLARE_READONLY_TOKEN_AXIOMFOLIO=ro_ax,
        CLOUDFLARE_READONLY_TOKEN_FILEFREE=ro_ff,
        CLOUDFLARE_READONLY_TOKEN_LAUNCHFREE=ro_lf,
        CLOUDFLARE_READONLY_TOKEN_DISTILL_TAX=ro_dt,
    )


def test_apex_for_hostname() -> None:
    assert cf.apex_for_hostname("accounts.paperworklabs.com") == "paperworklabs.com"
    assert cf.apex_for_hostname("paperworklabs.com") == "paperworklabs.com"
    assert cf.apex_for_hostname("api.axiomfolio.com") == "axiomfolio.com"
    assert cf.apex_for_hostname("unknown.example") is None


def test_bearer_read_prefers_per_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cf,
        "settings",
        _settings(api="write-wide", ro_pp="ro-pp"),
    )
    assert cf.bearer_for_cloudflare_dns_read("www.paperworklabs.com") == "ro-pp"


def test_bearer_read_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cf,
        "settings",
        _settings(api="write-wide", ro_pp=""),
    )
    assert cf.bearer_for_cloudflare_dns_read("paperworklabs.com") == "write-wide"


def test_cloudflare_auth_headers_write_ignores_readonly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cf,
        "settings",
        _settings(api="write-wide", ro_pp="ro-pp"),
    )
    h = cf.cloudflare_auth_headers(hostname_or_apex="paperworklabs.com", write=True)
    assert h["Authorization"] == "Bearer write-wide"
