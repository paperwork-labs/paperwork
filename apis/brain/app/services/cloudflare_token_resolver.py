"""Per-zone Cloudflare write-token resolver.

Given an apex zone (e.g. ``paperworklabs.com``), returns the narrowest-scoped
token available for *write* operations (DNS record mutations, cache purge).

Resolution order
----------------
1. ``CLOUDFLARE_TOKEN_<ZONE_SLUG_UPPERCASE>``  (per-zone write token)
   e.g. ``CLOUDFLARE_TOKEN_AXIOMFOLIO_COM`` for ``axiomfolio.com``
2. ``CLOUDFLARE_API_TOKEN``  (account-wide fallback — logged as a warning)
3. ``None``  (not configured — callers must treat this as an error)

Zone slug derivation
--------------------
Replace every non-alphanumeric character with ``_`` and upper-case:
``axiomfolio.com``  → ``AXIOMFOLIO_COM``
``filefree.ai``     → ``FILEFREE_AI``
``launchfree.com``  → ``LAUNCHFREE_COM``
``paperworklabs.com`` → ``PAPERWORKLABS_COM``
``distill.tax``     → ``DISTILL_TAX``

Security rationale
------------------
An account-wide ``CLOUDFLARE_API_TOKEN`` can modify *all* zones (DNS, cache,
SSL) across the entire account.  A leaked or over-privileged token therefore
has blast radius spanning every property.  Per-zone tokens are scoped to
exactly one zone with only the permissions required (Zone:Read, DNS:Edit,
Cache Purge:Edit).  If leaked, the damage is limited to that zone.

See ``docs/runbooks/cloudflare-ownership.md`` (**Per-zone write tokens**).

medallion: ops
"""

from __future__ import annotations

import logging
import re

from app.config import settings

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")


def zone_to_slug(apex: str) -> str:
    """Convert an apex zone name to the env-var slug component.

    Examples::

        >>> zone_to_slug("axiomfolio.com")
        'AXIOMFOLIO_COM'
        >>> zone_to_slug("filefree.ai")
        'FILEFREE_AI'
    """
    return _SLUG_RE.sub("_", apex.strip().lower()).upper()


def resolve_write_token(apex: str) -> str | None:
    """Return the best-available Cloudflare write token for *apex*.

    Prefers the per-zone ``CLOUDFLARE_TOKEN_<SLUG>`` env var.  Falls back
    to the account-wide ``CLOUDFLARE_API_TOKEN`` with a warning so operators
    know that a migration is incomplete.

    Parameters
    ----------
    apex:
        The zone apex, e.g. ``"paperworklabs.com"``.

    Returns
    -------
    str | None
        Bearer token string, or ``None`` if nothing is configured.
    """
    slug = zone_to_slug(apex)
    env_name = f"CLOUDFLARE_TOKEN_{slug}"

    # Per-zone token is stored in the settings object's extra-ignore dict
    # OR read directly from os.environ for forward-compatibility.
    import os

    per_zone = os.environ.get(env_name, "").strip()
    if per_zone:
        logger.debug("cloudflare_token_resolver: using per-zone token for %s (%s)", apex, env_name)
        return per_zone

    # Fall back to account-wide token
    account_wide = (settings.CLOUDFLARE_API_TOKEN or "").strip()
    if account_wide:
        logger.warning(
            "cloudflare_token_resolver: %s is not set; falling back to CLOUDFLARE_API_TOKEN "
            "(account-wide) for zone %s — migrate to per-zone token to reduce blast radius",
            env_name,
            apex,
        )
        return account_wide

    logger.error(
        "cloudflare_token_resolver: neither %s nor CLOUDFLARE_API_TOKEN is configured; "
        "write calls to zone %s will fail",
        env_name,
        apex,
    )
    return None


def write_auth_headers(apex: str) -> dict[str, str]:
    """Return ``Authorization`` + ``Content-Type`` headers for write calls to *apex*.

    Returns an empty dict if no token is available (callers should treat this
    as a configuration error and raise an appropriate exception).
    """
    token = resolve_write_token(apex)
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
