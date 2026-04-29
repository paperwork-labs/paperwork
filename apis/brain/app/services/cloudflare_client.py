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

**Writes** (record create/update/delete, cache purge) must use the resolver
from :mod:`app.services.cloudflare_token_resolver`.  The resolver prefers
per-zone ``CLOUDFLARE_TOKEN_<ZONE_SLUG_UPPERCASE>`` tokens and falls back to
``CLOUDFLARE_API_TOKEN`` with a deprecation warning.  Callers must pass the
zone apex so the resolver can pick the narrowest-scoped token.

See ``docs/runbooks/cloudflare-per-zone-tokens.md``.

medallion: ops
"""

from __future__ import annotations

from app.config import settings
from app.services.cloudflare_token_resolver import write_auth_headers as _write_auth_headers

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


def bearer_for_cloudflare_dns_write(apex: str) -> str | None:
    """Bearer token for **write** calls (DNS mutations, cache purge) for *apex*.

    Delegates to :func:`~app.services.cloudflare_token_resolver.resolve_write_token`
    which prefers per-zone ``CLOUDFLARE_TOKEN_<SLUG>`` and falls back to
    ``CLOUDFLARE_API_TOKEN`` with a warning.

    Parameters
    ----------
    apex:
        Zone apex, e.g. ``"paperworklabs.com"``.  Must be supplied so the
        resolver can select the narrowest-scoped token.
    """
    from app.services.cloudflare_token_resolver import resolve_write_token

    return resolve_write_token(apex)


def cloudflare_auth_headers(*, hostname_or_apex: str, write: bool) -> dict[str, str]:
    """Return ``Authorization`` headers for Cloudflare v4 JSON APIs.

    Parameters
    ----------
    hostname_or_apex:
        The zone or hostname to look up.  Used for both read *and* write paths.
    write:
        When ``True``, use the per-zone write token (via the resolver).
        When ``False``, prefer the per-zone read-only token.
    """
    if write:
        apex = apex_for_hostname(hostname_or_apex) or hostname_or_apex.strip().lower()
        return _write_auth_headers(apex)
    else:
        bearer = bearer_for_cloudflare_dns_read(hostname_or_apex)
        if not bearer:
            return {}
        return {"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"}
