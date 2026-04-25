---
owner: legal
last_reviewed: 2026-04-24
doc_kind: reference
domain: company
status: active
---
# Privacy & Sub-Processors

AxiomFolio processes sensitive financial data on behalf of end users.
This document lists the third-party sub-processors that may receive
user data in the course of normal operation, and the safeguards applied
to each.

## Sub-processors

- **Plaid Inc.** — Used to connect investment accounts at institutions
  without direct OAuth integration (e.g., Fidelity, Vanguard). Users
  explicitly authorize each connection via Plaid Link. Plaid receives
  the user's institution credentials; AxiomFolio never sees or stores
  them. See the
  [Plaid DPA](https://plaid.com/legal/data-processing-agreement/).
  Tokens are stored encrypted at rest (Fernet) and revoked on user
  request.

- **Interactive Brokers (IBKR)** — User-authenticated FlexQuery and IB
  Gateway sessions. AxiomFolio stores read-only FlexQuery tokens and
  gateway credentials encrypted at rest; credentials are never logged.

- **Charles Schwab / E*TRADE / Tastytrade / Tradier / Coinbase** —
  OAuth 2.0 access tokens stored encrypted at rest; refresh tokens are
  used for offline sync and revoked on user-initiated disconnect.

- **Render** — Application + worker hosting. Encrypts data at rest and
  in transit; access limited to operator accounts with MFA.

- **Cloudflare** — DNS / CDN / edge TLS termination. Does not inspect
  application payloads beyond what's required for TLS + WAF.

- **Stripe** — Subscription billing (test mode by default). Stripe is
  the card-data processor of record; AxiomFolio never handles raw PAN.

## Data retention

Plaid access tokens, broker credentials, and portfolio data are
retained until the user disconnects the integration or deletes their
account, whichever is earlier. Webhook delivery audit logs are
retained for 30 days for incident response.

## Security posture

- All secrets at rest are Fernet-encrypted with a key rotated per
  `docs/ENCRYPTION_KEY_ROTATION.md`.
- No third-party ever receives a user's AxiomFolio password. Broker
  and Plaid authentication happens entirely on the provider's domain.
- Webhook endpoints (Plaid, Stripe) require a cryptographically-verified
  signature on every request and reject unsigned or mismatched bodies.

## Contact

Privacy or data-deletion requests: founder@axiomfolio.dev.
