# Cloudflare Per-Zone Write Tokens

**Status:** Active — WS-47 (Phase C Wallet)  
**Owner:** ops-engineer  
**Last updated:** 2026-04-28

---

## Why per-zone tokens?

The account-wide `CLOUDFLARE_API_TOKEN` can mutate **every** zone (DNS, SSL,
cache, WAF rules, Workers) across the entire Paperwork Labs Cloudflare account.
A single leaked token puts all domains at risk simultaneously.

Per-zone tokens are scoped to **one apex zone** with only the permissions required
for write operations:

| Permission | Why |
|---|---|
| Zone: Read | Required to list/verify zone membership |
| Zone DNS: Edit | Create/update/delete DNS records |
| Zone Cache Purge: Edit | Purge cached assets after deployments |

If a per-zone token is leaked, the blast radius is limited to that one zone.
The remaining zones are unaffected.

---

## Zones managed

| Zone | Env var name | Status |
|---|---|---|
| `paperworklabs.com` | `CLOUDFLARE_TOKEN_PAPERWORKLABS_COM` | Migrate |
| `axiomfolio.com` | `CLOUDFLARE_TOKEN_AXIOMFOLIO_COM` | Migrate |
| `filefree.ai` | `CLOUDFLARE_TOKEN_FILEFREE_AI` | Migrate |
| `launchfree.ai` | `CLOUDFLARE_TOKEN_LAUNCHFREE_AI` | Migrate |
| `distill.tax` | `CLOUDFLARE_TOKEN_DISTILL_TAX` | Migrate |

---

## Creating a per-zone token in the Cloudflare dashboard

**Token naming pattern:** `paperwork-brain-write-<zone-slug>`  
Examples: `paperwork-brain-write-paperworklabs-com`, `paperwork-brain-write-axiomfolio-com`

### Steps (repeat for each zone)

1. Go to [Cloudflare Dashboard → My Profile → API Tokens](https://dash.cloudflare.com/profile/api-tokens)
2. Click **Create Token**
3. Select **Create Custom Token**
4. Token name: `paperwork-brain-write-<zone-slug>` (e.g. `paperwork-brain-write-axiomfolio-com`)
5. Under **Permissions**, add exactly three rows:

   | Resource | Permission |
   |---|---|
   | Zone | Read |
   | Zone → DNS | Edit |
   | Zone → Cache Purge | Edit |

   **Do NOT add account-level permissions.**

6. Under **Zone Resources**, select **Specific zone** → choose the target zone (e.g. `axiomfolio.com`)
7. Under **IP Address Filtering** (optional): restrict to Render egress IPs if known
8. Under **TTL**: set an expiry (recommend 1 year; Brain rotation monitor will alert at 30 days)
9. Click **Continue to summary** → **Create Token**
10. **Copy the token immediately** — it is shown only once

---

## Registering the token

### Vault (canonical)

```bash
# Store in the Paperwork secrets vault first (authoritative copy)
curl -s -X POST https://paperworklabs.com/api/secrets \
  -H "Authorization: Bearer $SECRETS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "CLOUDFLARE_TOKEN_AXIOMFOLIO_COM",
    "value": "<token>",
    "service": "cloudflare",
    "location": "vault",
    "description": "Per-zone write token for axiomfolio.com (DNS:Edit, Cache Purge:Edit)"
  }'
```

### Vercel (runtime)

```bash
# Brain API (Render) — add to the brain-api service
# Via Vercel CLI (Studio if deployed on Vercel):
vercel env add CLOUDFLARE_TOKEN_AXIOMFOLIO_COM production
# Paste the token value when prompted

# Repeat for each zone:
vercel env add CLOUDFLARE_TOKEN_PAPERWORKLABS_COM production
vercel env add CLOUDFLARE_TOKEN_FILEFREE_AI production
vercel env add CLOUDFLARE_TOKEN_LAUNCHFREE_AI production
vercel env add CLOUDFLARE_TOKEN_DISTILL_TAX production
```

### Render (Brain API)

Set each env var in the **brain-api** Render service dashboard:
`Settings → Environment → Add Environment Variable`

Or via Render API:
```bash
curl -s -X POST "https://api.render.com/v1/services/$BRAIN_RENDER_SERVICE_ID/env-vars" \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '[{"key":"CLOUDFLARE_TOKEN_AXIOMFOLIO_COM","value":"<token>"}]'
```

---

## Code integration

The resolver lives at `apis/brain/app/services/cloudflare_token_resolver.py`.

```python
from app.services.cloudflare_token_resolver import resolve_write_token, write_auth_headers

# Get the token for a zone
token = resolve_write_token("axiomfolio.com")

# Get ready-to-use headers dict
headers = write_auth_headers("axiomfolio.com")
# → {"Authorization": "Bearer <token>", "Content-Type": "application/json"}
```

The resolver:
1. Looks up `CLOUDFLARE_TOKEN_AXIOMFOLIO_COM` in `os.environ`
2. If unset, falls back to `CLOUDFLARE_API_TOKEN` and logs a `WARNING`
3. If neither is set, logs an `ERROR` and returns `None`

`cloudflare_client.cloudflare_auth_headers(hostname_or_apex=..., write=True)` also
routes through the resolver automatically.

---

## Migration plan (dual-token cutover)

The system supports **both** `CLOUDFLARE_API_TOKEN` (account-wide) and per-zone
tokens simultaneously during migration.  No code changes are required between
steps; resolution is transparent.

| Phase | Description |
|---|---|
| **Before migration** | Only `CLOUDFLARE_API_TOKEN` set → all writes use it (warning logged) |
| **During migration** | Set `CLOUDFLARE_TOKEN_<ZONE>` for each zone one at a time → resolver picks per-zone; account-wide unused for that zone |
| **After migration** | All per-zone tokens set → remove `CLOUDFLARE_API_TOKEN` from vault and all environments |
| **Verification** | Watch Brain logs for `cloudflare_token_resolver: using per-zone token` lines; absence of `falling back to CLOUDFLARE_API_TOKEN` confirms migration complete |

### Cleanup after full migration

```bash
# Remove account-wide token from vault
curl -s -X DELETE "https://paperworklabs.com/api/secrets/CLOUDFLARE_API_TOKEN" \
  -H "Authorization: Bearer $SECRETS_API_KEY"

# Remove from Vercel
vercel env rm CLOUDFLARE_API_TOKEN production

# Revoke the account-wide token in Cloudflare dashboard
# Dashboard → My Profile → API Tokens → paperwork-brain-write (account-wide) → Revoke
```

---

## Rotation schedule

Brain's secrets rotation monitor (`app/schedulers/secrets_rotation_monitor.py`)
alerts in Slack when any `CLOUDFLARE_TOKEN_*` key expires within 30 days.

Recommended TTL: **1 year**.  Rotate proactively every 11 months.

Rotation steps:
1. Create a new per-zone token in the Cloudflare dashboard (same permissions)
2. Update in vault → propagate to Render + Vercel
3. Verify Brain logs show the new token resolving correctly
4. Revoke the old token in the Cloudflare dashboard

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `CLOUDFLARE_API_TOKEN` warning in Brain logs | Per-zone token not set | Set `CLOUDFLARE_TOKEN_<ZONE>` |
| 401 from Cloudflare API | Wrong token / expired | Rotate token, verify vault |
| `neither ... nor CLOUDFLARE_API_TOKEN is configured` error | Both vars absent | Set at least one token |
| DNS mutations affecting wrong zone | Token scoped incorrectly | Verify token zone restriction in CF dashboard |
