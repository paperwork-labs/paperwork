---
owner: infra-ops
last_reviewed: 2026-04-24
doc_kind: runbook
domain: infra
status: active
severity_default: red
---
# Runbook: Encryption Key Rotation

> One-line summary: Broker credentials (Tastytrade OAuth tokens, IBKR FlexQuery tokens, Schwab OAuth tokens) are encrypted at rest using Fernet (symmetric encryption). Rotating the encryption key invalidates stored credentials; this runbook covers when that applies, how to triage, rotate intentionally, verify, roll back, and hand off. Referenced from [CONNECTIONS.md](CONNECTIONS.md) (credential storage) and [PRODUCTION.md](PRODUCTION.md) (env/security).

## When this fires

- [CONNECTIONS.md](CONNECTIONS.md) documents credential storage; [PRODUCTION.md](PRODUCTION.md) documents env/security for production.
- The encryption key is provided via `ENCRYPTION_KEY` or derived from `SECRET_KEY` in development (see [Configuration](#configuration) below).
- **Intentional rotation:** you are scheduling or executing a planned `ENCRYPTION_KEY` change (notify users, low-traffic window per existing procedure).
- **Post-change impact:** after rotation, **all users must reconnect their broker accounts** (Tastytrade, IBKR, Schwab). Existing `AccountCredentials` rows become unreadable; sync tasks will fail with decryption errors unless you use a separate migration strategy.
- _TODO: document alert names, dashboard tiles, and exact log line substrings for Fernet or decryption failures in production._

## Triage (≤5 min)

**Classify: intentional rotation vs. surprise key / env drift**

- **Key rotation invalidates all stored credentials.** Credentials encrypted with the previous key cannot be decrypted with the new key.
- If zero-downtime rotation is required, you need a migration strategy (e.g., dual-key decrypt during transition)—_TODO: document the approved pattern for this repo/services._
- If users report broken connections or sync after a deploy or config change, suspect key mismatch before other causes.

```bash
# _TODO: document copy-paste commands to confirm which env vars are set in the target deployment (names only; never log secret values)_
# _TODO: document one log query or error-rate check for AccountCredentials / Fernet decrypt failures_
```

## Verification

- After a successful **intentional** rotation and cutover, confirm the new `ENCRYPTION_KEY` is the one in environment/config and application servers have been restarted.
- **Users re-connect** via **Settings → Connections** for each affected account (Tastytrade, IBKR, Schwab).
- Confirm no ongoing decryption errors for stored credentials in application logs or metrics—_TODO: document the exact query or panel._
- (Optional) Clear or flag existing `AccountCredentials` rows to avoid confusing decryption errors, per your operational policy.

**Rotation procedure (when intentional)** — preserve full sequence from operations practice:

1. Notify users that a key rotation will occur; they will need to reconnect accounts.
2. Schedule maintenance or perform during low-traffic period.
3. Set the new `ENCRYPTION_KEY` in environment/config.
4. Restart application servers.
5. (Optional) Clear or flag existing `AccountCredentials` rows to avoid confusing decryption errors.
6. Users re-connect via **Settings → Connections** for each affected account.

## Rollback

- If the new key made things worse and you must restore service **without** a dual-key migration: **restore the previous `ENCRYPTION_KEY`** in environment/config (from secure storage / prior secret version—_TODO: document where previous keys are stored for this service_), then **restart application servers** so the app uses the prior key.
- Reverting the key return stored ciphertext to readability **only** if the rows were still encrypted with that key; if users or jobs wrote new data under the new key, restoring the old key alone may not be sufficient—_TODO: document data repair steps if both keys were used in sequence._
- If a **code** change (not just env) was part of the bad rollout: `git revert <sha>` and redeploy per your normal process; the primary rollback for a bad **key** change remains restoring the previous `ENCRYPTION_KEY` and restarting.

## Escalation

- Primary: _TODO: document Slack channel and owning role for AxiomFolio/infra-ops_ — include link or handle from [PRODUCTION.md](PRODUCTION.md) when documented there.
- _TODO: document when to page or open a vendor ticket (if any) for hosting/secrets—_

## Post-incident

- Add a row to `docs/KNOWLEDGE.md` under "Recent incidents" with the pattern and the runbook section that handled it.
- If a new guardrail emerged, file a `.cursor/rules/*.mdc` update PR.
- If the runbook itself was wrong/stale, update it before closing the ticket. Bump `last_reviewed`.
- _TODO: document whether a handoff to product/broker-success is required after mass reconnect._

## Appendix

### Configuration

- **ENCRYPTION_KEY:** 32-byte URL-safe base64-encoded key (e.g., `Fernet.generate_key()`).
- **Fallback:** If not set, dev mode derives from `SECRET_KEY` (not recommended for production).

### Reference

- [CONNECTIONS.md](CONNECTIONS.md) — credential storage
- [PRODUCTION.md](PRODUCTION.md) — env/security

```python
# Example: generate a Fernet-compatible key (32-byte URL-safe base64)
# Fernet.generate_key()
```
