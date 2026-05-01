---
last_reviewed: 2026-05-01
---

# Studio vault — read / write helpers

The Studio app exposes a Postgres-backed encrypted secrets store. These shell helpers call the Studio HTTP API so you do not need to hand-craft `curl` and JSON.

## When to use which script

| Script | Purpose |
|--------|---------|
| `scripts/vault-get.sh` | **Read** one secret by name; prints the decrypted value on stdout (pipe-friendly). |
| `scripts/vault-set.sh` | **Write / upsert** one or many secrets by name; idempotent `POST /api/secrets`. |

Use **vault-get** in automation that only needs to read (e.g. pulling a key into a local env). Use **vault-set** when rotating keys, onboarding envs, or bulk-importing values (e.g. Clerk keys from a local `.env`-style file).

## Auth (same for both scripts)

Load creds from repo root `.env.local` and/or `apps/studio/.env.local` (both are sourced if present), or export in the shell:

- **Preferred:** `SECRETS_API_KEY` — `Authorization: Bearer …` to `STUDIO_URL` (default `https://paperworklabs.com`).
- **Fallback:** first email in `ADMIN_EMAILS` plus `ADMIN_ACCESS_PASSWORD` — HTTP Basic when the bearer key is missing or returns 401.

`STUDIO_URL` defaults to `https://paperworklabs.com` if unset.

## Examples

Single secret (silent prompt on a TTY if you omit value flags and do not pipe):

```bash
./scripts/vault-set.sh MY_API_KEY --service uncategorized
```

Explicit value:

```bash
./scripts/vault-set.sh CLERK_SECRET_KEY --value 'sk_live_...' --service clerk
```

Dry run (prints the JSON that would be sent; no network write):

```bash
./scripts/vault-set.sh MY_KEY --value 'x' --dry-run
```

Batch import from a `.env`-style file (`KEY=VALUE` per line; lines starting with `#` are comments):

```bash
./scripts/vault-set.sh --batch ./keys.env --service clerk
```

Read a secret:

```bash
./scripts/vault-get.sh MY_API_KEY
```

## Downstream propagation

The vault is the **canonical** store for secret *metadata and values* in Studio. After writing here, sync to deployment targets as needed (Vercel env, Render env, etc.); that propagation is a separate step and is not performed by these scripts.
