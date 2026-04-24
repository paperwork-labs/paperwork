"""OAuth broker adapter registry.

Adapters are registered by ``broker_id`` (matching the ``OAuthBrokerType``
enum value persisted in ``broker_oauth_connections.broker``). The route layer
calls ``get_adapter("etrade_sandbox")`` rather than knowing about concrete
classes — this is the seam future brokers (Schwab, Fidelity, …) plug into.

medallion: ops
"""

from __future__ import annotations

from typing import Dict, Type

from .base import (
    OAuthBrokerAdapter,
    OAuthCallbackContext,
    OAuthError,
    OAuthInitiateResult,
    OAuthTokens,
)
from .coinbase import CoinbaseOAuthAdapter
from .etrade import ETradeSandboxAdapter
from .tradier import TradierOAuth2Adapter, TradierSandboxOAuth2Adapter

_REGISTRY: dict[str, type[OAuthBrokerAdapter]] = {
    ETradeSandboxAdapter.broker_id: ETradeSandboxAdapter,
    TradierOAuth2Adapter.broker_id: TradierOAuth2Adapter,
    TradierSandboxOAuth2Adapter.broker_id: TradierSandboxOAuth2Adapter,
    CoinbaseOAuthAdapter.broker_id: CoinbaseOAuthAdapter,
}


def get_adapter(broker: str) -> OAuthBrokerAdapter:
    """Return a fresh adapter instance for ``broker`` or raise ``OAuthError``."""

    cls = _REGISTRY.get(broker)
    if cls is None:
        raise OAuthError(
            f"unsupported OAuth broker: {broker!r}",
            permanent=True,
            broker=broker,
        )
    return cls()


def supported_brokers() -> list[str]:
    """Return all registered broker ids — used for `/api/v1/oauth/brokers`."""

    return sorted(_REGISTRY.keys())


def register_adapter(cls: type[OAuthBrokerAdapter]) -> None:
    """Register a new adapter class. Test/extension hook."""

    if not cls.broker_id:
        raise ValueError("adapter class must set broker_id")
    _REGISTRY[cls.broker_id] = cls


__all__ = [
    "OAuthBrokerAdapter",
    "OAuthCallbackContext",
    "OAuthError",
    "OAuthInitiateResult",
    "OAuthTokens",
    "get_adapter",
    "register_adapter",
    "supported_brokers",
]
