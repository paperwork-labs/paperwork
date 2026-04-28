"""Cloudflare DNS credentials — split **read** vs **write** tokens.

**Reads** (DNS health checks, read-only CLIs, future infra dashboard) should
prefer per-zone vault keys issued by ``scripts/cloudflare_issue_readonly_tokens.py``:

* ``CLOUDFLARE_READONLY_TOKEN_PAPERWORKLABS`` → ``paperworklabs.com``
* ``CLOUDFLARE_READONLY_TOKEN_AXIOMFOLIO`` → ``axiomfolio.com``
* ``CLOUDFLARE_READONLY_TOKEN_FILEFREE`` → ``filefree.ai``
* ``CLOUDFLARE_READONLY_TOKEN_LAUNCHFREE`` → ``launchfree.ai``
* ``CLOUDFLARE_READONLY_TOKEN_DISTILL_TAX`` → ``distill.tax``

When the matching per-zone key is **unset or empty**, read paths **fall back**
to ``CLOUDFLARE_API_TOKEN`` (the account-wide token used for writes).

**Writes** (record create/update/delete) must use ``CLOUDFLARE_API_TOKEN`` only;
per-zone read tokens must not be used for mutations.

See ``docs/runbooks/CLOUDFLARE_OWNERSHIP.md``.

medallion: ops
"""

from __future__ import annotations

from app.config import settings

_KNOWN_APEXES: tuple[str, ...] = (
    "paperworklabs.com",
    "axiomfolio.com",
    "filefree.ai",
    "launchfree.ai",
    "distill.tax",
)


def apex_for_hostname(hostname: str) -> str | None:
    """Return the production apex zone for ``hostname``, or ``None`` if unknown.

    Accepts either a bare apex (``paperworklabs.com``) or a subdomain
    (``accounts.paperworklabs.com``).
    """
    host = hostname.strip().lower().rstrip(".")
    if not host:
        return None
    for apex in _KNOWN_APEXES:
        if host == apex or host.endswith(f".{apex}"):
            return apex
    return None


def _readonly_token_for_apex(apex: str) -> str | None:
    raw: str
    if apex == "paperworklabs.com":
        raw = settings.CLOUDFLARE_READONLY_TOKEN_PAPERWORKLABS
    elif apex == "axiomfolio.com":
        raw = settings.CLOUDFLARE_READONLY_TOKEN_AXIOMFOLIO
    elif apex == "filefree.ai":
        raw = settings.CLOUDFLARE_READONLY_TOKEN_FILEFREE
    elif apex == "launchfree.ai":
        raw = settings.CLOUDFLARE_READONLY_TOKEN_LAUNCHFREE
    elif apex == "distill.tax":
        raw = settings.CLOUDFLARE_READONLY_TOKEN_DISTILL_TAX
    else:
        return None
    token = raw.strip()
    return token or None


def bearer_for_cloudflare_dns_read(hostname_or_apex: str) -> str | None:
    """Bearer token for **read** calls (DNS GET), preferring per-zone read tokens."""
    apex = apex_for_hostname(hostname_or_apex)
    if apex:
        ro = _readonly_token_for_apex(apex)
        if ro:
            return ro
    write = (settings.CLOUDFLARE_API_TOKEN or "").strip()
    return write or None


def bearer_for_cloudflare_dns_write() -> str | None:
    """Bearer token for **write** calls (DNS mutations)."""
    tok = (settings.CLOUDFLARE_API_TOKEN or "").strip()
    return tok or None


def cloudflare_auth_headers(*, hostname_or_apex: str, write: bool) -> dict[str, str]:
    """Return ``Authorization`` headers for Cloudflare v4 JSON APIs."""
    if write:
        bearer = bearer_for_cloudflare_dns_write()
    else:
        bearer = bearer_for_cloudflare_dns_read(hostname_or_apex)
    if not bearer:
        return {}
    return {"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"}
