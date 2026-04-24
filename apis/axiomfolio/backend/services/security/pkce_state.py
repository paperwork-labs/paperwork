"""medallion: ops"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
import time
from typing import Optional, Dict, Tuple

import redis

from backend.config import settings

logger = logging.getLogger(__name__)


def _get_redis() -> redis.Redis:
    # Default to docker service hostname for local dev
    url = getattr(settings, "REDIS_URL", None) or "redis://redis:6379/0"
    return redis.from_url(url, decode_responses=True)

# In-memory fallback store if Redis is unavailable
_MEM_STORE: Dict[str, Tuple[str, float]] = {}


def generate_code_verifier(length: int = 64) -> str:
    """
    Generate an RFC 7636 code_verifier (43-128 chars).
    """
    length = max(43, min(length, 128))
    # urlsafe base64 from random bytes; strip padding
    verifier = base64.urlsafe_b64encode(os.urandom(length)).decode("utf-8").rstrip("=")
    # Ensure within limits
    if len(verifier) < 43:
        verifier = verifier + ("A" * (43 - len(verifier)))
    return verifier[:128]


def compute_code_challenge(code_verifier: str) -> str:
    """
    Compute S256 code_challenge from verifier (base64url without padding).
    """
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def save_verifier_for_state(state: str, code_verifier: str, ttl_seconds: int = 600) -> None:
    """
    Save code_verifier keyed by OAuth 'state' with TTL.
    """
    try:
        r = _get_redis()
        r.setex(f"pkce:{state}", ttl_seconds, code_verifier)
        return
    except Exception as e:
        logger.warning("PKCE save_verifier Redis setex failed, using in-memory: %s", e)
        # Fallback to in-memory with expiration
        _MEM_STORE[f"pkce:{state}"] = (code_verifier, time.time() + ttl_seconds)


def pop_verifier_for_state(state: str) -> Optional[str]:
    """
    Atomically retrieve and delete the verifier for a given state.
    """
    key = f"pkce:{state}"
    try:
        r = _get_redis()
        pipe = r.pipeline()
        pipe.get(key)
        pipe.delete(key)
        val, _ = pipe.execute()
        if val is not None:
            return val
    except Exception as e:
        logger.warning("PKCE pop_verifier Redis pipeline failed, trying in-memory: %s", e)
    # Fallback to in-memory
    try:
        val, exp = _MEM_STORE.pop(key)
        if time.time() <= exp:
            return val
    except KeyError:
        return None
    return None


