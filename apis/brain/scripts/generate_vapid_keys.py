#!/usr/bin/env python3
"""Generate VAPID key pair for web push — WS-69 PR I.

Run once to generate the VAPID keys and print them for vault entry.

Usage:
    python3 apis/brain/scripts/generate_vapid_keys.py

Output:
    Prints VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, and VAPID_SUBJECT values
    ready to paste into your .env / vault.

Requires: pywebpush (pip install pywebpush)
"""

from __future__ import annotations

import sys


def _out(msg: str = "") -> None:
    sys.stdout.write(msg + "\n")


def main() -> None:
    try:
        from py_vapid import Vapid  # type: ignore[import-untyped]
    except ImportError:
        sys.stderr.write("ERROR: py_vapid not found. Install pywebpush: pip install pywebpush\n")
        sys.exit(1)

    v = Vapid()
    v.generate_keys()

    pub = v.public_key_urlsafe_base64
    priv = v.private_key_urlsafe_base64

    _out("VAPID key pair generated successfully.")
    _out()
    _out("Add the following to your .env / vault:")
    _out()
    _out(f"VAPID_PUBLIC_KEY={pub}")
    _out(f"VAPID_PRIVATE_KEY={priv}")
    _out("VAPID_SUBJECT=mailto:founder@paperworklabs.com")
    _out()
    _out("IMPORTANT: Store VAPID_PRIVATE_KEY securely — treat it like a private key.")
    _out("The public key is shared with the browser; keep the private key secret.")


if __name__ == "__main__":
    main()
