"""Receipt storage for Expense records (WS-69 PR N).

Stores uploaded files in apis/brain/data/expenses/receipts/<expense_id>/<filename>.
Max size: 10 MB. Allowed MIME: image/jpeg, image/png, image/webp, application/pdf.

medallion: ops
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
_ALLOWED_MIMES = frozenset({"image/jpeg", "image/png", "image/webp", "application/pdf"})
_ENV_REPO_ROOT = "REPO_ROOT"


def _receipts_base_dir() -> Path:
    env = os.environ.get(_ENV_REPO_ROOT, "").strip()
    if env:
        return Path(env) / "apis" / "brain" / "data" / "expenses" / "receipts"
    # services/ -> app/ -> brain/
    here = Path(__file__).resolve()
    brain_root = here.parent.parent.parent
    return brain_root / "data" / "expenses" / "receipts"


def validate_receipt(filename: str, mime_type: str, size_bytes: int) -> None:
    """Raise ValueError for invalid receipts."""
    if mime_type not in _ALLOWED_MIMES:
        raise ValueError(
            f"Receipt MIME type '{mime_type}' not allowed. Use: {', '.join(sorted(_ALLOWED_MIMES))}"
        )
    if size_bytes > _MAX_SIZE_BYTES:
        raise ValueError(
            f"Receipt file too large ({size_bytes} bytes). Max: {_MAX_SIZE_BYTES} bytes (10 MB)"
        )
    if not filename or "/" in filename or ".." in filename:
        raise ValueError("Invalid filename")


def store_receipt(expense_id: str, filename: str, content: bytes, mime_type: str) -> str:
    """Write receipt bytes to disk. Returns the stored_path relative to brain root."""
    validate_receipt(filename, mime_type, len(content))
    dest_dir = _receipts_base_dir() / expense_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(content)
    # Return path relative to brain data dir for storage in Expense record
    return f"expenses/receipts/{expense_id}/{filename}"


def get_receipt_path(stored_path: str) -> Path | None:
    """Resolve a stored_path to an absolute filesystem path. Returns None if missing."""
    env = os.environ.get(_ENV_REPO_ROOT, "").strip()
    if env:
        base = Path(env) / "apis" / "brain" / "data"
    else:
        here = Path(__file__).resolve()
        brain_root = here.parent.parent.parent
        base = brain_root / "data"
    full = base / stored_path
    return full if full.exists() else None


def delete_receipt(stored_path: str) -> bool:
    path = get_receipt_path(stored_path)
    if path and path.exists():
        path.unlink()
        return True
    return False
