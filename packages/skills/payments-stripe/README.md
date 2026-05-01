# @paperwork/skills-payments-stripe

Stripe webhook verification (signed payloads) and subscription MRR aggregation for Paperwork skills. Apps own routing, persistence, and auth; this package provides a typed client and pure helpers.

## API

- **`PaymentsStripeClient`** — constructed with `StripeConfig` (`secretKey`, `webhookSecret`).
  - `verifyWebhook(rawBody, signature)` — verifies the Stripe signature and returns a normalized `SubscriptionEvent`.
  - `snapshotMrr(asOf?)` — fetches all subscriptions from Stripe, normalizes monthly recurring amounts (minor units, single currency), and returns an `MRRSnapshot`. Movement buckets (`newMrr`, `expansionMrr`, etc.) are zero in this list-based snapshot; future event-driven reporting can fill them.
  - `listSubscriptions()` — returns `CustomerSubscription[]` with monthly-equivalent amounts (annual prices ÷ 12).

- **`verifyWebhook` / `handleEvent`** — lower-level helpers for custom wiring; `handleEvent` maps a `Stripe.Event` after you verify the signature.

- **`snapshotMrrFromSubscriptions`**, **`monthlyMinorFromStripeItems`** — pure functions for tests and offline fixtures.

## Conventions

- Amounts are **minor units** (e.g. cents).
- **Single currency** for MRR aggregation; mixed currencies throw a clear error.
- **Trialing** subscriptions are excluded from `totalMrr`; **cancelled** excluded; **past_due** included.

## Future consumer

Admin **Products** cockpit MRR card can call `snapshotMrr` or consume normalized webhook events for live updates.
