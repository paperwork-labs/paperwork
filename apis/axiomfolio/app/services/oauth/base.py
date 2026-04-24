"""Abstract OAuth broker adapter contract.

Every concrete broker (E*TRADE, Schwab, Fidelity, …) implements
``OAuthBrokerAdapter``. The route + Celery layers only ever see this
interface, which lets us add new brokers without touching the API or DB
plumbing.

Design notes
------------
* OAuth 1.0a vs 2.0 are unified at the adapter boundary by treating
  ``code`` + optional ``state`` opaquely. For OAuth 1.0a the "code" is the
  user verifier and the "extra" payload (request_token + secret) is
  retrieved by the route from a Redis state store.
* Tokens returned by the adapter are **plaintext** dataclasses; the calling
  service is responsible for encrypting before persistence.
* Failures distinguish between transient (network, 5xx) and permanent
  (revoked, invalid_grant, 4xx). Permanent errors carry
  ``permanent=True`` so the refresh task knows to mark
  ``REFRESH_FAILED`` instead of retrying.

medallion: ops
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


class OAuthError(Exception):
    """OAuth provider/transport error.

    ``permanent`` distinguishes "needs human reauth" from "retry safe".
    """

    def __init__(
        self,
        message: str,
        *,
        permanent: bool = False,
        broker: Optional[str] = None,
        provider_status: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.permanent = permanent
        self.broker = broker
        self.provider_status = provider_status

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"OAuthError(message={str(self)!r}, permanent={self.permanent}, "
            f"broker={self.broker!r}, status={self.provider_status})"
        )


@dataclass
class OAuthInitiateResult:
    """Result of starting an OAuth flow.

    ``state`` is the CSRF nonce we issue. The route persists ``extra`` in
    Redis keyed by ``(broker, state)`` and replays it on callback so the
    adapter can finish OAuth 1.0a (which needs the original
    ``request_token_secret``) without holding state in memory.
    """

    authorize_url: str
    state: str
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OAuthTokens:
    """Plaintext token bundle returned by an adapter."""

    access_token: str
    refresh_token: Optional[str] = None  # OAuth 1.0a: token secret; OAuth 2.0: refresh token
    expires_at: Optional[datetime] = None
    scope: Optional[str] = None
    provider_account_id: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OAuthCallbackContext:
    """Inputs available to ``exchange_code``.

    * ``code`` is the OAuth 2.0 code or OAuth 1.0a verifier
    * ``state`` is the CSRF nonce we issued during ``initiate_url``
    * ``extra`` is whatever ``OAuthInitiateResult.extra`` we stashed in Redis
    """

    code: str
    state: str
    extra: Dict[str, Any] = field(default_factory=dict)


class OAuthBrokerAdapter(abc.ABC):
    """Contract every OAuth broker adapter must implement."""

    #: Stable broker identifier matching ``OAuthBrokerType`` enum values.
    broker_id: str = ""

    #: ``"sandbox"`` or ``"live"`` — surfaced into the DB row + UI.
    environment: str = "sandbox"

    @abc.abstractmethod
    def initiate_url(self, *, user_id: int, callback_url: str) -> OAuthInitiateResult:
        """Begin an OAuth flow; return the URL to redirect the user to."""

    @abc.abstractmethod
    def exchange_code(self, ctx: OAuthCallbackContext) -> OAuthTokens:
        """Trade the callback ``code`` for a usable access token."""

    @abc.abstractmethod
    def refresh(
        self,
        *,
        access_token: str,
        refresh_token: Optional[str],
    ) -> OAuthTokens:
        """Refresh / renew the access token.

        For OAuth 2.0 brokers ``refresh_token`` is the refresh grant.
        For OAuth 1.0a brokers (E*TRADE) ``refresh_token`` is actually the
        access_token_secret used to sign the renew request.
        """

    @abc.abstractmethod
    def revoke(
        self,
        *,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> None:
        """Revoke the token at the provider. Best-effort; errors are logged."""

    def fetch_account_summary(
        self,
        *,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Optional: small "is the token actually live?" probe.

        Return ``None`` if the adapter doesn't implement a summary endpoint.
        """

        return None


__all__ = [
    "OAuthBrokerAdapter",
    "OAuthCallbackContext",
    "OAuthError",
    "OAuthInitiateResult",
    "OAuthTokens",
]
