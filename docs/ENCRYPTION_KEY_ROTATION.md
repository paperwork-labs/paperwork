# Encryption Key Rotation

## Overview

Broker credentials (Tastytrade OAuth tokens, IBKR FlexQuery tokens, Schwab OAuth tokens) are encrypted at rest using Fernet (symmetric encryption). The encryption key is provided via `ENCRYPTION_KEY` or derived from `SECRET_KEY` in development.

## Important: Key Rotation Invalidates Stored Credentials

**Rotating `ENCRYPTION_KEY` invalidates all stored credentials.** Credentials encrypted with the previous key cannot be decrypted with the new key. After rotation:

- All users must **reconnect their broker accounts** (Tastytrade, IBKR, Schwab)
- Existing `AccountCredentials` rows become unreadable; sync tasks will fail with decryption errors
- Consider a migration strategy if zero-downtime rotation is required (e.g., dual-key decrypt during transition)

## Rotation Procedure (when intentional)

1. Notify users that a key rotation will occur; they will need to reconnect accounts
2. Schedule maintenance or perform during low-traffic period
3. Set the new `ENCRYPTION_KEY` in environment/config
4. Restart application servers
5. (Optional) Clear or flag existing `AccountCredentials` rows to avoid confusing decryption errors
6. Users re-connect via Settings > Brokerages for each affected account

## Configuration

- **ENCRYPTION_KEY**: 32-byte URL-safe base64-encoded key (e.g., `Fernet.generate_key()`)
- **Fallback**: If not set, dev mode derives from `SECRET_KEY` (not recommended for production)
