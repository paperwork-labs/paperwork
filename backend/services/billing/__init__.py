"""Billing services: Stripe integration, price catalog, webhook processing.

This package is the *only* sanctioned path for translating Stripe events into
internal subscription state. Everything that wants to know "is this user a
Pro+ subscriber?" must go through the entitlements service (added in PR #326),
which in turn is mutated only by:

    - manual operator grants (EntitlementService.manual_set_tier)
    - this package's StripeWebhookProcessor (which calls
      EntitlementService.apply_subscription_state)

Never call `stripe.*` from a route, task, or model. Always go through
``stripe_client.get_stripe()`` so the lazy import / test-mode guard rails
hold.
"""
