"""Postmark webhook request signature verification.

Postmark signs webhook HTTP bodies with HMAC-SHA256 using a per-server
signing secret you configure for the server or inbound stream. The digest
is sent in the ``X-Postmark-Signature`` request header.

**Algorithm (aligned with Postmark's common SDK / integration examples):**

1. Compute ``digest = HMAC_SHA256(secret_utf8, raw_request_body_bytes)``.
2. Encode ``digest`` as **Base64** (standard alphabet, no newlines) and
   compare to the header value using ``hmac.compare_digest`` (constant-time).

Some snippets use lowercase **hex** encoding of the same digest; we also
accept hex for compatibility.

References:

* Postmark — Webhooks overview (securing endpoints)
* Postmark — Inbound webhook (JSON body; HTTP 403 stops retries)

medallion: gold
"""

from __future__ import annotations

import base64
import hashlib
import hmac


def validate_postmark_signature(
    raw_body: bytes, signature_header: str | None, secret: str
) -> bool:
    """Return True if ``signature_header`` matches the HMAC-SHA256 of ``raw_body``.

    ``secret`` is the Postmark signing secret (UTF-8 string). Empty
    ``signature_header`` or ``secret`` yields False.
    """
    if not secret or not signature_header:
        return False
    sig = signature_header.strip()
    mac = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256)
    digest = mac.digest()
    expected_b64 = base64.b64encode(digest).decode("ascii")
    if hmac.compare_digest(sig, expected_b64):
        return True
    expected_hex = digest.hex()
    return hmac.compare_digest(sig.lower(), expected_hex.lower())
