"""Clerk JWKS client with TTL cache and fail-open degradation snapshots."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from clerk_auth.errors import ClerkUnreachableError

logger = logging.getLogger(__name__)

JWKDict = dict[str, Any]


def _utc_wall_iso_now() -> str:
    return datetime.now(UTC).isoformat()


class JWKSClient:
    """Fetch and cache Clerk signing keys from ``{issuer}/.well-known/jwks.json``.

    JWKS payloads are refreshed on a TTL. When Clerk is unreachable, the client
    logs a warning and returns the **last merged** JWK snapshot for ``kid``
    after recording degradation telemetry (similar in spirit to
    :pyclass:`mcp_server.quota.DailyCallQuota` fail-open bookkeeping).
    """

    def __init__(
        self,
        clerk_issuer: str,
        cache_ttl_s: int = 3600,
        *,
        http_timeout_s: float = 5.0,
        monotonic: Callable[[], float] | None = None,
        wall_iso_now: Callable[[], str] | None = None,
    ) -> None:
        wall_resolver = wall_iso_now or _utc_wall_iso_now

        normalized = clerk_issuer.rstrip("/")
        self._jwks_url = f"{normalized}/.well-known/jwks.json"
        self._cache_ttl_s = cache_ttl_s
        self._http_timeout_s = http_timeout_s
        self._monotonic = monotonic if monotonic is not None else time.monotonic
        self._wall_iso_now = wall_resolver
        self._lock = threading.Lock()
        self._keys_by_kid: dict[str, JWKDict] = {}
        self._cache_expires_mono: float | None = None
        self._degradation: dict[str, Any] = {
            "count": 0,
            "last_error": None,
            "last_at_wall": None,
        }

    def jwks_url(self) -> str:
        """Resolved JWKS URL for tests and instrumentation."""
        return self._jwks_url

    def degradation_snapshot(self) -> dict[str, Any]:
        """Copy of JWKS outage counters for health endpoints."""
        with self._lock:
            return dict(self._degradation)

    def clear_cache(self) -> None:
        """Reset cached keys and JWKS TTL. Primarily for tests."""
        with self._lock:
            self._keys_by_kid.clear()
            self._cache_expires_mono = None

    def get_signing_key(self, kid: str) -> JWKDict:
        """Resolve the Clerk JWK matching ``kid``.

        Raises :pyexc:`ClerkUnreachableError` when JWKS retrieval fails **and**
        there is no degraded snapshot stored for ``kid``.
        """
        mono = self._monotonic()

        if self._cache_is_fresh(mono) and (key := self._lookup_no_lock(kid)):
            return key

        try:
            self._refresh_blocking(mono)
        except ClerkUnreachableError as exc:
            return self._degraded_return_or_raise(kid, exc)

        resolved = self._lookup_no_lock(kid)
        if resolved is None:
            # Primary refresh succeeded but Clerk rotated keys — force one refresh.
            self._invalidate_cache_ttl()
            try:
                mono2 = self._monotonic()
                self._refresh_blocking(mono2)
            except ClerkUnreachableError as exc:
                return self._degraded_return_or_raise(kid, exc)

            resolved = self._lookup_no_lock(kid)

        if resolved is None:
            return self._degraded_return_or_raise(
                kid,
                ClerkUnreachableError(f"unknown signing key id: {kid!r}"),
            )

        return resolved

    def _lookup_no_lock(self, kid: str) -> JWKDict | None:
        with self._lock:
            jwk = self._keys_by_kid.get(kid)
        return dict(jwk) if jwk is not None else None

    def _cache_is_fresh(self, mono: float) -> bool:
        with self._lock:
            return (
                self._cache_expires_mono is not None and mono < self._cache_expires_mono
            )

    def _invalidate_cache_ttl(self) -> None:
        with self._lock:
            self._cache_expires_mono = None

    def _refresh_blocking(self, mono_now: float) -> None:
        payload = self._fetch_jwks_document()
        if not isinstance(payload, Mapping):
            raise ClerkUnreachableError("jwks response is not an object")

        raw_keys = payload.get("keys", [])
        if not isinstance(raw_keys, list):
            raise ClerkUnreachableError("jwks keys payload invalid")

        merged: dict[str, JWKDict] = {}
        with self._lock:
            merged = dict(self._keys_by_kid)

        for raw in raw_keys:
            if not isinstance(raw, Mapping):
                continue
            key_id = raw.get("kid")
            if not isinstance(key_id, str) or not key_id:
                continue
            merged[key_id] = dict(raw)

        with self._lock:
            self._keys_by_kid = merged
            self._cache_expires_mono = mono_now + float(self._cache_ttl_s)

    def _fetch_jwks_document(self) -> Mapping[str, Any]:
        try:
            with httpx.Client(timeout=self._http_timeout_s) as client:
                resp = client.get(self._jwks_url)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise ClerkUnreachableError(
                f"jwks http {exc.response.status_code}: {exc!s}"
            ) from exc
        except httpx.RequestError as exc:
            raise ClerkUnreachableError(f"jwks request error: {exc!s}") from exc

        if not isinstance(data, Mapping):
            raise ClerkUnreachableError("jwks payload is not a JSON object")
        return data

    def _degraded_return_or_raise(
        self,
        kid: str,
        reason: BaseException,
    ) -> JWKDict:
        degraded = self._lookup_no_lock(kid)
        if degraded is not None:
            logger.warning(
                "clerk JWKS unavailable — using last-known key snapshot",
                extra={"kid": kid, "reason": str(reason)},
            )
            self._record_degradation(reason)
            return degraded
        self._record_degradation(reason)
        raise ClerkUnreachableError(str(reason)) from reason

    def _record_degradation(self, exc: BaseException) -> None:
        try:
            with self._lock:
                self._degradation["count"] += 1
                self._degradation["last_error"] = str(exc)
                self._degradation["last_at_wall"] = self._wall_iso_now()
        except Exception:
            pass
