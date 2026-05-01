---
last_reviewed: 2026-05-01
---

# Secret intake (Studio)

## Why this exists

Agents and automation sometimes need new or rotated secrets (for example Clerk `sk_live_*` / `sk_test_*`). Pasting those into chat, terminal history, or ad-hoc files is risky. **Secret intake** gives the founder a single-use browser link: they paste the value once; Studio encrypts it into the existing `secrets` vault; the agent polls status and continues without ever seeing the plaintext.

## Architecture

```mermaid
sequenceDiagram
  participant Agent as Agent / script
  participant API as Studio API
  participant DB as Postgres
  participant Founder as Founder browser

  Agent->>API: POST /api/secrets/intake (Bearer / Basic)
  API->>DB: INSERT secret_intakes (token, metadata, expires_at)
  API-->>Agent: intake_url

  Founder->>API: GET /admin/secrets/intake/:token (Clerk + ADMIN_EMAILS)
  API-->>Founder: HTML + metadata

  Founder->>API: GET /api/secrets/intake/:token (metadata JSON)
  Founder->>API: POST .../submit (Clerk session, value)
  API->>DB: encrypt + upsert secrets; mark intake received

  Agent->>API: GET .../status (Bearer / Basic)
  API-->>Agent: status=received
```

ASCII overview:

```
Agent (API key)          Founder (Clerk admin)           Vault
    |                              |                      |
    | POST /api/secrets/intake     |                      |
    |--------------------------->  |                      |
    |<---------------------------  |                      |
    |  { intake_url }              |                      |
    |                              | open URL            |
    |                              | POST /submit        |
    |                              |-------------------->| encrypt + upsert
    | GET .../status (poll)        |                      |
    |--------------------------------------------------->|
    |  { status: received }        |                      |
```

## How an agent uses it

From the repo root (same env loading pattern as `scripts/vault-get.sh`):

```bash
# Print the one-time URL for the founder
scripts/request-secret.sh CLERK_SECRET_KEY clerk --description "Rotate production secret" --prefix "sk_live_" --expires-in 60

# Block until the founder submits (or intake expires)
scripts/request-secret.sh CLERK_SECRET_KEY clerk --prefix "sk_live_" --expires-in 60 --poll
```

Requirements:

- `STUDIO_URL` (optional; defaults to `https://paperworklabs.com`)
- `SECRETS_API_KEY` **or** `ADMIN_EMAILS` + `ADMIN_ACCESS_PASSWORD` for API auth

The founder receives the HTTPS link out-of-band (Slack, etc.) — **not** the secret value.

## How the founder experiences it

1. Sign in to Studio with a Clerk account whose email is listed in `ADMIN_EMAILS`.
2. Open the intake URL (`/admin/secrets/intake/<token>`).
3. Review name, service, description, and expected prefix (if any).
4. Paste the secret in the masked field once and submit.
5. After success, the page redirects back to **Secrets** after a few seconds.

If the account is not in `ADMIN_EMAILS`, the UI shows **Not authorized** with a sign-out action.

## Security properties

| Property | Behavior |
|----------|----------|
| Admin-only UI | Clerk session + server-side `ADMIN_EMAILS` check on submit. |
| Agent API | Create intake and poll status: `authenticateSecretsRequest` (Bearer or admin Basic). |
| No Bearer on submit | Submit intentionally requires a founder browser session so API keys alone cannot push plaintext into the vault. |
| One-time use | Intake is single-use: status moves to `received`; a second submit returns **409**. |
| Expiry | Rows expire by time; polling and metadata treat past `expires_at` as **expired**. |
| Entropy | Intake token: 128-bit random, base32 (~26 chars), URL-safe. |
| Audit | `received_by_email`, `received_from_ip`, `received_at`, `upserted_secret_id` on `secret_intakes`. |
| Logging | No full secret values in logs or API error bodies; prefix mismatches only show a short masked hint. |

## Inaugural use case: Clerk key rotation

1. Agent runs `scripts/request-secret.sh CLERK_SECRET_KEY clerk --prefix "sk_live_" --poll` (adjust name/service to match your vault entries).
2. Founder opens the printed URL, confirms the metadata matches Clerk Dashboard → API keys, pastes the new **Secret key** once.
3. Agent sees `✓ secret received` and proceeds to deploy or document rotation; optional follow-up: update Clerk Dashboard / Vercel env references per your runbook.

## Related code

- `apps/studio/src/lib/db.ts` — `ensureSecretIntakesTable()`
- `apps/studio/src/app/api/secrets/intake/*` — create, metadata, submit, status
- `apps/studio/src/app/admin/secrets/intake/[token]/` — founder UI
- `scripts/request-secret.sh` — agent helper
