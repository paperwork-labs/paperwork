"""
TOTP Utilities for IBKR 2FA
===========================

Generate TOTP codes for automated IBKR Gateway login.
Used with IBC (Interactive Brokers Controller) for unattended 2FA.

medallion: ops
"""

import base64
import hmac
import struct
import time


def generate_totp(secret: str, digits: int = 6, interval: int = 30) -> str | None:
    """Generate a TOTP code from a Base32 secret.

    Args:
        secret: Base32-encoded TOTP secret (from IBKR Authenticator setup)
        digits: Number of digits in the code (IBKR uses 6)
        interval: Time step in seconds (IBKR uses 30)

    Returns:
        6-digit TOTP code as string, or None if generation fails
    """
    if not secret:
        return None

    try:
        # Decode Base32 secret
        secret_bytes = base64.b32decode(secret.upper().replace(" ", ""))

        # Get current time step
        counter = int(time.time() // interval)

        # Pack counter as big-endian 64-bit integer
        counter_bytes = struct.pack(">Q", counter)

        # Generate HMAC-SHA1
        hmac_digest = hmac.new(secret_bytes, counter_bytes, "sha1").digest()

        # Dynamic truncation
        offset = hmac_digest[-1] & 0x0F
        truncated = struct.unpack(">I", hmac_digest[offset : offset + 4])[0]
        truncated &= 0x7FFFFFFF

        # Generate code
        code = truncated % (10**digits)

        return str(code).zfill(digits)

    except Exception:
        return None


def get_totp_remaining_seconds(interval: int = 30) -> int:
    """Get seconds remaining until current TOTP expires.

    Useful for timing automation to avoid using a code near expiration.
    """
    return interval - (int(time.time()) % interval)


def validate_totp_secret(secret: str) -> bool:
    """Check if a TOTP secret is valid Base32.

    Args:
        secret: The secret to validate

    Returns:
        True if valid, False otherwise
    """
    if not secret:
        return False

    try:
        # Try to decode
        base64.b32decode(secret.upper().replace(" ", ""))
        return True
    except Exception:
        return False
