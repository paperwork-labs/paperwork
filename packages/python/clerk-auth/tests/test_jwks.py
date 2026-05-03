"""Tests for :class:`clerk_auth.jwks.JWKSClient`."""

from __future__ import annotations

from typing import Any

import pytest

from clerk_auth.errors import ClerkUnreachableError
from clerk_auth.jwks import JWKSClient
from tests.support import ISSUER, RSA_KID


def test_jwks_cache_respects_ttl(
    monkeypatch: pytest.MonkeyPatch,
    rsa_public_jwk: dict[str, Any],
) -> None:
    calls = {"n": 0}
    doc = {"keys": [rsa_public_jwk]}

    def fetch(_self: JWKSClient) -> dict[str, Any]:
        calls["n"] += 1
        return doc

    monkeypatch.setattr(JWKSClient, "_fetch_jwks_document", fetch)

    clock = {"t": 0.0}

    client = JWKSClient(
        ISSUER,
        cache_ttl_s=60,
        monotonic=lambda: clock["t"],
    )

    client.get_signing_key(RSA_KID)
    client.get_signing_key(RSA_KID)
    assert calls["n"] == 1

    clock["t"] = 70.0
    client.get_signing_key(RSA_KID)
    assert calls["n"] == 2


def test_fail_open_uses_snapshot_after_outage(
    monkeypatch: pytest.MonkeyPatch,
    rsa_public_jwk: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    doc = {"keys": [rsa_public_jwk]}
    state = {"phase": "ok"}

    def fetch(_self: JWKSClient) -> dict[str, Any]:
        if state["phase"] != "ok":
            raise ClerkUnreachableError("jwks down")
        return doc

    monkeypatch.setattr(JWKSClient, "_fetch_jwks_document", fetch)

    clock = {"t": 0.0}
    client = JWKSClient(
        ISSUER,
        cache_ttl_s=30,
        monotonic=lambda: clock["t"],
    )

    first = client.get_signing_key(RSA_KID)
    state["phase"] = "down"
    clock["t"] = 100.0

    with caplog.at_level("WARNING"):
        second = client.get_signing_key(RSA_KID)

    assert second == first
    assert any("snapshot" in r.message for r in caplog.records)
    snap = client.degradation_snapshot()
    assert snap["count"] >= 1


def test_unreachable_without_snapshot_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fetch(_self: JWKSClient) -> dict[str, Any]:
        raise ClerkUnreachableError("jwks down")

    monkeypatch.setattr(JWKSClient, "_fetch_jwks_document", fetch)

    client = JWKSClient(ISSUER, cache_ttl_s=30, monotonic=lambda: 0.0)

    with pytest.raises(ClerkUnreachableError):
        client.get_signing_key(RSA_KID)


def test_jwks_url_normalizes_trailing_slash(
    rsa_public_jwk: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        JWKSClient,
        "_fetch_jwks_document",
        lambda _self: {"keys": [rsa_public_jwk]},
    )
    issuer = "https://clerk.example/"
    client = JWKSClient(issuer, cache_ttl_s=10, monotonic=lambda: 0.0)

    assert client.jwks_url() == "https://clerk.example/.well-known/jwks.json"


def test_clear_cache_forces_refresh(
    rsa_public_jwk: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}
    doc = {"keys": [rsa_public_jwk]}

    def fetch(_self: JWKSClient) -> dict[str, Any]:
        calls["n"] += 1
        return doc

    monkeypatch.setattr(JWKSClient, "_fetch_jwks_document", fetch)

    clock = {"t": 0.0}
    client = JWKSClient(ISSUER, cache_ttl_s=60, monotonic=lambda: clock["t"])

    client.get_signing_key(RSA_KID)
    client.clear_cache()
    clock["t"] = 10.0
    client.get_signing_key(RSA_KID)

    assert calls["n"] == 2


def test_unknown_kid_without_cache_raises(
    monkeypatch: pytest.MonkeyPatch,
    rsa_public_jwk: dict[str, Any],
) -> None:
    doc = {"keys": [rsa_public_jwk]}

    monkeypatch.setattr(
        JWKSClient,
        "_fetch_jwks_document",
        lambda _self: doc,
    )

    client = JWKSClient(ISSUER, cache_ttl_s=60, monotonic=lambda: 0.0)

    with pytest.raises(ClerkUnreachableError):
        client.get_signing_key("missing-kid")
