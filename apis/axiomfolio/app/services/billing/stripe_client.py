"""Thin lazy wrapper around the official `stripe` SDK.

We do not import `stripe` at module load time. Reasons:

1. The `stripe` package adds ~10MB to the worker image; not every entry point
   (Celery worker, alembic) needs it.
2. CI must pass even if the dep isn't installed yet (the dep is added in
   ``requirements.txt`` in this same PR, but we want the test layer to be
   resilient if a future contributor strips it).
3. It lets us mark "Stripe not configured" as a *runtime* condition rather
   than an import-time crash.

Usage:

    from app.services.billing.stripe_client import get_stripe

    stripe = get_stripe()  # raises StripeNotConfigured if STRIPE_API_KEY unset
    customer = stripe.Customer.create(email=user.email)

For tests, prefer ``StripeClientFactory`` (below) so you can inject a stub
module without monkey-patching ``sys.modules``.

medallion: ops
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


class StripeNotConfigured(RuntimeError):
    """Raised when Stripe is required but no API key has been configured.

    Routes that depend on Stripe should catch this and return a structured
    error body so the operator can see "Stripe is intentionally off in this
    environment" instead of a 500. The webhook route maps it to HTTP 402
    (Payment Required) so Stripe stops retrying delivery; user-facing
    routes that rely on Stripe should map to HTTP 503 (Service Unavailable).
    """


class _StripeLike(Protocol):
    """Minimal surface we use from the `stripe` SDK.

    Defined as a Protocol so test stubs can satisfy it without importing
    `stripe`. The real `stripe` module satisfies this implicitly.
    """

    api_key: Optional[str]
    api_version: Optional[str]

    Webhook: Any  # stripe.Webhook namespace
    Customer: Any
    Subscription: Any
    Checkout: Any
    Event: Any


class StripeClientFactory:
    """Test-friendly factory for the Stripe SDK module.

    Production code calls ``get_stripe()`` (the module-level singleton). Tests
    instantiate their own factory with an injected stub:

        factory = StripeClientFactory(loader=lambda: my_stub_module)
        stripe = factory.get(api_key="sk_test_xyz", api_version="2024-06-20")
    """

    def __init__(self, loader=None):
        self._loader = loader or self._default_loader
        self._cached: Optional[_StripeLike] = None

    @staticmethod
    def _default_loader() -> _StripeLike:
        try:
            import stripe  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercised by tests via stub
            raise StripeNotConfigured(
                "The `stripe` package is not installed. Add it to requirements.txt "
                "and rebuild the image."
            ) from exc
        return stripe  # type: ignore[return-value]

    def get(self, api_key: Optional[str], api_version: Optional[str] = None) -> _StripeLike:
        if not api_key:
            raise StripeNotConfigured(
                "STRIPE_API_KEY is not set. Set it in the environment to enable "
                "Stripe integration. Use a `sk_test_*` key for non-prod."
            )
        if self._cached is None:
            self._cached = self._loader()
        # Always re-set: api_key may rotate at runtime via secrets reload.
        self._cached.api_key = api_key
        if api_version:
            self._cached.api_version = api_version
        return self._cached

    def reset(self) -> None:
        """Drop cached SDK reference (test isolation)."""
        self._cached = None


_default_factory = StripeClientFactory()


def get_stripe(
    api_key: Optional[str] = None,
    api_version: Optional[str] = None,
) -> _StripeLike:
    """Return a configured `stripe` SDK module.

    If ``api_key`` is not passed, falls back to ``settings.STRIPE_API_KEY``.
    Raises ``StripeNotConfigured`` if no key is available.
    """
    if api_key is None:
        # Local import to avoid a hard dependency on `backend.config` at module
        # load (keeps this file unit-testable in isolation).
        from app.config import settings

        api_key = getattr(settings, "STRIPE_API_KEY", None)
        api_version = api_version or getattr(settings, "STRIPE_API_VERSION", None)
    return _default_factory.get(api_key=api_key, api_version=api_version)


def reset_default_factory() -> None:
    """Drop the module-level cached client (test isolation only)."""
    _default_factory.reset()
