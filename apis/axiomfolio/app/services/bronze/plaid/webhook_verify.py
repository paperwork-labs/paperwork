"""Plaid webhook JWT verification.

Plaid signs webhook bodies with ES256-JWTs and exposes the public keys via
``/webhook_verification_key/get`` keyed by ``kid``. The JWT's
``request_body_sha256`` claim must match ``sha256(raw_body)`` to bind the
signature to the specific payload.

This module is the only place that performs the verification; the route
layer does NOT roll its own hash comparison, because the most common
implementation bug is hashing the already-parsed dict (which changes the
byte sequence) instead of the raw request body.

See plan ``docs/plans/PLAID_FIDELITY_401K.md`` §6 and the
`Plaid webhook verification docs
<https://plaid.com/docs/api/webhooks/webhook-verification/>`_.

medallion: bronze
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

import jwt  # PyJWT
from jwt import PyJWTError
from jwt.algorithms import ECAlgorithm
from plaid.api import plaid_api
from plaid.exceptions import ApiException
from plaid.model.webhook_verification_key_get_request import (
    WebhookVerificationKeyGetRequest,
)

logger = logging.getLogger(__name__)


class WebhookVerificationError(RuntimeError):
    """Raised when a Plaid webhook signature / body hash does not verify.

    Routes should translate this to HTTP 401. The error message is
    intentionally low-detail (``invalid signature``) so attackers can't
    distinguish "wrong key" from "wrong body" from side channels; the
    full context is logged server-side.
    """


# kid -> (jwk_dict, fetched_at_epoch_seconds). Cache for 24 hours per
# Plaid's recommendation, with a shorter TTL on failure so transient
# outages don't pin a stale key forever.
_KEY_CACHE: Dict[str, Tuple[Dict[str, Any], float]] = {}
_KEY_CACHE_TTL_SECONDS = 24 * 60 * 60
_KEY_CACHE_LOCK = threading.Lock()


def _cache_get(kid: str) -> Optional[Dict[str, Any]]:
    with _KEY_CACHE_LOCK:
        entry = _KEY_CACHE.get(kid)
        if not entry:
            return None
        jwk, fetched_at = entry
        if time.time() - fetched_at > _KEY_CACHE_TTL_SECONDS:
            # Expired — evict and force a refetch to pick up rotations.
            _KEY_CACHE.pop(kid, None)
            return None
        return jwk


def _cache_put(kid: str, jwk: Dict[str, Any]) -> None:
    with _KEY_CACHE_LOCK:
        _KEY_CACHE[kid] = (jwk, time.time())


def reset_cache() -> None:
    """Clear the verification-key cache (used by tests)."""
    with _KEY_CACHE_LOCK:
        _KEY_CACHE.clear()


def _fetch_key(plaid_api_client: plaid_api.PlaidApi, kid: str) -> Dict[str, Any]:
    """Fetch a verification key from Plaid by ``kid``.

    Plaid returns a JWK in the ``key`` field; the "is_live" field on the
    key corresponds to ``PLAID_ENV`` and is NOT enforced here — we rely
    on the ``sandbox`` / ``production`` ``PLAID_SECRET`` being correct,
    so mixing envs would fail at the ``accounts_get`` level before we
    ever process a webhook.
    """
    try:
        response = plaid_api_client.webhook_verification_key_get(
            WebhookVerificationKeyGetRequest(key_id=kid)
        )
    except ApiException as exc:
        logger.warning(
            "plaid webhook_verification_key_get failed for kid=%s: %s",
            kid,
            exc,
        )
        raise WebhookVerificationError("invalid signature") from exc

    key = response["key"].to_dict() if "key" in response else {}
    if not key:
        raise WebhookVerificationError("invalid signature")
    return key


def _jwk_to_pem(jwk: Dict[str, Any]) -> bytes:
    """Convert a Plaid JWK (EC P-256) to PEM format accepted by PyJWT."""
    import json as _json

    return ECAlgorithm.from_jwk(_json.dumps(jwk))


def verify_webhook(
    *,
    body: bytes,
    plaid_verification_header: str,
    plaid_api_client: plaid_api.PlaidApi,
) -> Dict[str, Any]:
    """Verify a Plaid webhook and return the decoded JSON payload.

    Args:
        body: raw request body bytes; MUST be the exact bytes received.
            Hashing a re-serialized ``json.dumps(...)`` silently breaks
            this because JSON re-encoding is non-canonical.
        plaid_verification_header: the ``Plaid-Verification`` header value.
        plaid_api_client: a live Plaid SDK client for JWKS lookup.

    Returns:
        The parsed JSON body (as a dict). Returning the parsed payload
        after verification guarantees callers never accidentally use a
        locally-reparsed version that diverges from the signed bytes.

    Raises:
        WebhookVerificationError: when any verification step fails.
    """
    if not plaid_verification_header:
        raise WebhookVerificationError("invalid signature")

    try:
        headers = jwt.get_unverified_header(plaid_verification_header)
    except PyJWTError as exc:
        raise WebhookVerificationError("invalid signature") from exc

    alg = headers.get("alg")
    kid = headers.get("kid")
    if alg != "ES256" or not kid:
        # Strict mode: anything other than ES256 must fail. Plaid has
        # signalled no intent to rotate to a different alg, and a "None"
        # alg downgrade is the classic JWT exploit.
        raise WebhookVerificationError("invalid signature")

    jwk = _cache_get(kid)
    if jwk is None:
        jwk = _fetch_key(plaid_api_client, kid)
        _cache_put(kid, jwk)

    try:
        pem = _jwk_to_pem(jwk)
        claims = jwt.decode(
            plaid_verification_header,
            key=pem,
            algorithms=["ES256"],
        )
    except PyJWTError as exc:
        logger.warning(
            "plaid webhook JWT decode failed (kid=%s): %s", kid, exc
        )
        raise WebhookVerificationError("invalid signature") from exc

    expected_sha = claims.get("request_body_sha256")
    if not isinstance(expected_sha, str):
        raise WebhookVerificationError("invalid signature")

    actual_sha = hashlib.sha256(body).hexdigest()
    # Constant-time comparison to defuse timing-side channels on the hash.
    if not hmac.compare_digest(expected_sha, actual_sha):
        raise WebhookVerificationError("invalid signature")

    # Parse JSON only AFTER verification succeeds; prior to that we must
    # not trust the body enough to route off its contents.
    import json as _json

    try:
        payload = _json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise WebhookVerificationError("invalid signature") from exc

    if not isinstance(payload, dict):
        raise WebhookVerificationError("invalid signature")
    return payload


__all__ = [
    "WebhookVerificationError",
    "verify_webhook",
    "reset_cache",
]
