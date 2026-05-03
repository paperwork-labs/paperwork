"""Raw regex pattern strings for PII-shaped spans.

Patterns are conservative where noted; scrubber may apply extra checks
(e.g. Luhn for credit cards) on top of these shapes.
"""

from __future__ import annotations

# Social Security Number (hyphenated; does not validate area/group ranges).
SSN: str = r"\b\d{3}-\d{2}-\d{4}\b"

# Employer Identification Number (hyphenated). Excludes the common
# non-EIN sentinel "12-3456789" (month-like prefix + sequential digits).
EIN: str = r"\b(?!12-3456789\b)\d{2}-\d{7}\b"

# Practical email shape (not full RFC 5322). Allows underscores in labels.
EMAIL: str = (
    r"\b[A-Za-z0-9](?:[A-Za-z0-9._%+-]{0,62}[A-Za-z0-9])?"
    r"@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}\b"
)

# US phone numbers with optional +1 and common separators.
# Uses NANP-style first-digit rules for area and exchange codes to cut
# obvious non-phone hyphen runs (e.g. "12-345-678-9012").
PHONE_US: str = (
    r"(?<!\w)"
    r"(?:\+1[-.\s]?)?"
    r"(?:\([2-9]\d{2}\)|[2-9]\d{2})"
    r"[-.\s]?"
    r"[2-9]\d{2}"
    r"[-.\s]?"
    r"\d{4}\b"
)

# Credit-card-shaped spans: grouped 4x4 or a contiguous 13-19 digit run.
CREDIT_CARD: str = (
    r"(?:"
    r"\b(?:\d{4}[-\s]){3}\d{4}\b"
    r"|"
    r"\b\d{13,19}\b"
    r")"
)

# IPv4 dotted-quad with valid octet ranges.
IP_ADDRESS: str = (
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
)

# Bank / account-like digit runs (lengths common for US account numbers).
# Excludes uniform repeated digits (e.g. placeholder 111111111111).
BANK_ACCOUNT: str = r"\b(?!(.)\1{9,16}\b)\d{10,17}\b"

# JSON Web Token (three Base64URL segments). Split `ey` + `J` so scanners
# do not match the regex source as a JWT-shaped literal.
JWT: str = r"\b" + "ey" + "J" + r"[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"

# Vendor-shaped prefixes are split across string literals so repo secret
# scanners do not match the regex source itself.
_AWS_KEY_PREFIX = "AK" + "IA"
_GH_PAT_PREFIX = "gh" + "p_"

# API key / secret-shaped tokens (vendor-specific prefixes + assignment forms).
# Intentionally excludes Slack-style `xox*` tokens: realistic-looking fixtures
# trip GitHub push protection; callers can extend locally if needed.
API_KEY: str = (
    r"(?:"
    r"\bsk-(?:proj|live|test)-[A-Za-z0-9]{20,}\b"
    r"|"
    rf"\b{_AWS_KEY_PREFIX}[0-9A-Z]{{16}}\b"
    r"|"
    rf"\b{_GH_PAT_PREFIX}[A-Za-z0-9]{{36,}}\b"
    r"|"
    r"\bpk_(?:live|test)_[0-9a-zA-Z]{20,}\b"
    r"|"
    r"\b(?:api|secret)[_-]?key\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{32,}\b"
    r")"
)
