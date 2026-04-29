"""Conversation attachment storage helper (WS-69 PR E).

Stores uploaded images/files under:
    apis/brain/data/conversation_attachments/<conversation_id>/<uuid>.<ext>

Max 10 MB per file.  Allowed MIME types for images: image/png, image/jpeg,
image/webp, image/gif.  Other types stored as generic files.

Access is via a redirect endpoint with a short-lived HMAC token (signed URL).
v2 will promote to S3/R2.

medallion: ops
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)

_MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
_ALLOWED_IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
_TOKEN_TTL_SECONDS = 3600  # 1 h


# ---------------------------------------------------------------------------
# Data-directory helpers
# ---------------------------------------------------------------------------


def _data_dir() -> Path:
    repo_root = os.environ.get("REPO_ROOT", "").strip()
    if repo_root:
        return Path(repo_root) / "apis" / "brain" / "data"
    return Path(__file__).resolve().parents[2] / "data"


def _attachments_dir(conversation_id: str) -> Path:
    d = _data_dir() / "conversation_attachments" / conversation_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def store_attachment(
    conversation_id: str,
    filename: str,
    content: bytes,
    mime: str,
) -> dict[str, str | int | None]:
    """Persist *content* to disk and return metadata dict.

    Returns a dict with keys: id, path (relative), mime, size_bytes, kind.
    Raises ValueError if the file is too large or the MIME type is not allowed.
    """
    if len(content) > _MAX_SIZE_BYTES:
        msg = f"Attachment exceeds maximum size of {_MAX_SIZE_BYTES // (1024 * 1024)} MB"
        raise ValueError(msg)

    # Derive extension
    ext = _ext_for_mime(mime, filename)
    attachment_id = str(uuid4())
    dest_dir = _attachments_dir(conversation_id)
    dest_path = dest_dir / f"{attachment_id}{ext}"
    dest_path.write_bytes(content)

    kind = "image" if mime in _ALLOWED_IMAGE_MIMES else "file"
    return {
        "id": attachment_id,
        "kind": kind,
        "mime": mime,
        "size_bytes": len(content),
        "local_path": str(dest_path),
    }


def attachment_path(conversation_id: str, attachment_id: str) -> Path | None:
    """Resolve the on-disk path for a stored attachment.  Returns None if missing."""
    d = _attachments_dir(conversation_id)
    for candidate in d.iterdir():
        if candidate.stem == attachment_id:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Signed-URL token helpers (HMAC-SHA256, TTL-based)
# ---------------------------------------------------------------------------


def _signing_secret() -> str:
    return os.environ.get("BRAIN_API_SECRET", "dev-secret")


def generate_token(conversation_id: str, attachment_id: str) -> str:
    """Generate a time-limited HMAC token for a specific attachment."""
    expires = int(time.time()) + _TOKEN_TTL_SECONDS
    payload = f"{conversation_id}:{attachment_id}:{expires}"
    sig = hmac.new(
        _signing_secret().encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{expires}.{sig}"


def verify_token(conversation_id: str, attachment_id: str, token: str) -> bool:
    """Verify a signed token.  Returns False if expired or invalid."""
    try:
        expires_str, sig = token.split(".", 1)
        expires = int(expires_str)
    except (ValueError, AttributeError):
        return False
    if time.time() > expires:
        return False
    payload = f"{conversation_id}:{attachment_id}:{expires}"
    expected_sig = hmac.new(
        _signing_secret().encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(sig, expected_sig)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_MIME_TO_EXT: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "application/pdf": ".pdf",
}


def _ext_for_mime(mime: str, filename: str) -> str:
    if mime in _MIME_TO_EXT:
        return _MIME_TO_EXT[mime]
    suffix = Path(filename).suffix
    return suffix if suffix else ".bin"
