---
title: Cloudflare account ownership + migration
last_reviewed: 2026-05-02
owner: infra-ops
status: active
domain: infra
doc_kind: runbook
summary: "Completed 2026-04-28: all production zones on Paperwork Labs work Cloudflare account (former founder personal account migrated-from) + token rotation and ongoing DNS ops."
tags: [cloudflare, dns, secrets, migration, security]
---

# Cloudflare account ownership + migration

> **Category**: ops
> **Owner**: @infra-ops
> **Last verified**: 2026-05-02
> **Status**: active

**TL;DR:** How production zones moved from the founder’s personal Cloudflare account to the work account (done 2026-04-28), plus token rotation and day-to-day DNS ops.

> **As of 2026-04-28, all 5 production zones are migrated** to the Paperwork Labs work Cloudflare account (`7e8976a674c66193992c04d61d5a6747`). This runbook is **historical reference** (how we cut over) **plus ongoing operational procedures** (tokens, new zones, team access).

This runbook captures the **founder migration** (completed 2026-04-28) from the **former** personal Cloudflare account (`Sankalp404@gmail.com` — migrated-from, not current production ownership) to the **work** account, and the **ongoing operational procedures** (token rotation, zone admission, team access) now that the work account is canonical.

## Migration status (live)

| Zone | State | Account ID | Zone ID | Notes |
|---|---|---|---|---|
| `paperworklabs.com` | ✅ migrated 2026-04-28 | `7e8976a674c66193992c04d61d5a6747` | `6efe0c9f87c80a21617ff040fa2e55dd` | NS=`janet+noel.ns.cloudflare.com`. Spaceship registrar updated. Status=active. |
| `axiomfolio.com` | ✅ migrated 2026-04-28 | `7e8976a674c66193992c04d61d5a6747` | `e06277688d45265fb6e1240ca17e796e` | NS=`janet+noel.ns.cloudflare.com`. All A/CNAME records auto-imported. Status=active. Production 200 OK across `axiomfolio.com / www / api`. |
| `filefree.ai` | ✅ migrated 2026-04-28 | `7e8976a674c66193992c04d61d5a6747` | `0ec8bf3e6992c73725c2a0b6cf549cfa` | NS=`janet+noel.ns.cloudflare.com`. Spaceship registrar updated. Zone activated work account **~20:11 UTC**. Status=active. |
| `launchfree.ai` | ✅ migrated 2026-04-28 | `7e8976a674c66193992c04d61d5a6747` | `38e6ea06b1380246082b83399826ac22` | NS=`janet+noel.ns.cloudflare.com`. Spaceship registrar updated. Zone activated **~20:12 UTC**. Status=active. |
| `distill.tax` | ✅ migrated 2026-04-28 | `7e8976a674c66193992c04d61d5a6747` | `0497b4c7e9c65e62bd016f940d62e8e8` | NS=`janet+noel.ns.cloudflare.com`. Spaceship registrar updated. Zone activated **~20:24 UTC**. Status=active. |

**Phase 2 (paperworklabs.com)** and **Phase 3 (axiomfolio.com)** below are
historical playbooks — both completed 2026-04-28. Use them as reference if a
similar migration is needed in the future, or for emergency rollback.

**Old zones on the former personal account** (`Sankalp404@gmail.com`, migrated-from): keep for 24h soak (until ~2026-04-29 21:00 UTC), then delete from that **former** Cloudflare account — they are not production DNS. **Runbook:** `docs/runbooks/cloudflare-zone-decommission.md` (script: `scripts/cloudflare_decommission_zones.py`).

## Why migrate

| Reason | Risk if we don't |
|---|---|
| Personal Gmail owns business-critical DNS | Bus factor; acquisition diligence flag; SOC 2 control gap |
| Tax / SSN / PII handling | Auditors require business-account ownership of production infrastructure |
| Team access + role separation | Personal account can't grant scoped DNS access to Founder 2, contractors, or Brain MCP |
| Single billing record | Cleaner books for tax / cap table / acquisition |
| Audit log clarity | Personal account commingles personal-domain history with business |

## Inventory (canonical end state — achieved 2026-04-28)

All paperwork-labs production zones **now** live on the **work account** (`7e8976a674c66193992c04d61d5a6747`):

| Zone | Before (migration source) | After (canonical) | Outcome |
|---|---|---|---|
| `paperworklabs.com` | Former personal account ("Finish setup" — never served production from personal NS) | Work | Cutover completed; NS + registrar aligned |
| `axiomfolio.com` | Former personal account (live proxied traffic) | Work | Cutover completed; records preserved via import |
| `filefree.ai` | Former personal / prior delegation | Work | Cutover completed 2026-04-28 (~20:11 UTC) |
| `launchfree.ai` | Former personal / prior delegation | Work | Cutover completed 2026-04-28 (~20:12 UTC) |
| `distill.tax` | Former personal / prior delegation | Work | Cutover completed 2026-04-28 (~20:24 UTC) |
| `tools.filefree.ai` | Subdomain of `filefree.ai` | Inherits `filefree.ai` zone | n/a |

## Phase 1 — Set up work account (founder UI, ~15 min)

1. Sign up at [cloudflare.com](https://cloudflare.com) with a workspace email — `ops@paperworklabs.com` or `founders@paperworklabs.com`. Use a Google Workspace alias if a dedicated mailbox doesn't exist yet.
2. **Enable 2FA on day 1**: Settings → Authentication → Two-Factor Authentication → TOTP (not SMS). Save recovery codes to 1Password / Bitwarden.
3. Create a backup-recovery email (any trusted personal inbox the founder controls — e.g. the **former** personal account used pre-migration — belt + suspenders for solo-founder lockout).
4. Add Founder 2 (when they have a Paperwork Labs email) as `Domain Admin` member.

## Phase 2 — `paperworklabs.com` (zero-risk switch)

> ✅ Completed 2026-04-28.

This zone never finished setup on the personal account, so cutover is trivial.

```bash
# (founder UI)
# 1. Personal account → paperworklabs.com → Settings → Remove Site
# 2. Work account → Add a Site → paperworklabs.com → Free plan
# 3. Work account gives you 2 nameservers (e.g. ns1-work.cloudflare.com)
# 4. Update nameservers at the registrar (Spaceship dashboard for paperworklabs.com)
# 5. Wait 5-30 min, verify:
dig +trace ns paperworklabs.com
# Expected: returns the 2 work-account nameservers
```

**No DNS records existed yet** so there's nothing to import. After nameserver propagation, configure DNS records as `apps/accounts/`, `apps/design/`, etc come online (CNAMEs to Vercel).

## Phase 3 — `axiomfolio.com` (live traffic — careful)

> ✅ Completed 2026-04-28.

```bash
# (founder UI on personal account)
# 1. axiomfolio.com → DNS → Records → Import and Export → Export
#    Save the BIND file as: docs/runbooks/_artifacts/axiomfolio-zone-2026-04-28.bind
#    (Do not commit the file — it can include sensitive TXT records.
#     Keep it local for rollback.)

# (founder UI on work account)
# 2. Add a Site → axiomfolio.com → Free plan
# 3. DNS → Records → Import and Export → Import → upload BIND file
# 4. Visually compare records side-by-side with personal account
#    until 100% match (proxy flags, TTLs, all records present)

# 5. Switch nameservers at the registrar
# 6. Within 5-15 min the work-account zone goes "Active";
#    SSL re-provisions in 2-5 min on top.
# 7. Verify:
curl -sS -o /dev/null -w '%{http_code}\n' https://axiomfolio.com
curl -sS -o /dev/null -w '%{http_code}\n' https://api.axiomfolio.com
# Both should return 200 / their normal app responses.

# 8. Wait 24h before deleting the zone from the former personal account.
```

**Rollback**: revert nameservers at the registrar to the **former** personal-account values. Within 5-15 min traffic resumes against the old zone (which is still active until you delete it).

## Phase 4 — Token rotation (founder + agent)

### Brain automation token (`paperwork-brain`)

| Field | Value |
|---|---|
| Name | `paperwork-brain` |
| Scope | Entire Account |
| Expiration | 1 year (auto-rotate via WS-26 secrets-rotation track) |
| Client IP filter | **EMPTY** (Brain on Render has dynamic egress IPs — IP-locking will break automation) |
| Permissions | `DNS & Zones → Zone:Read,Edit`, `DNS:Read,Edit`, `Zone Settings:Edit`, `App Security → SSL and Certificates:Edit`, `Cache & Performance → Cache Purge:Purge` |

After issuing:

```bash
# 1. Add to repo vault
./scripts/vault-set.sh CLOUDFLARE_API_TOKEN "<new-token>"

# 2. Update Render env var on brain-api
# (Render dashboard → brain-api → Environment → CLOUDFLARE_API_TOKEN)

# 3. Update GitHub Actions secret
gh secret set CLOUDFLARE_API_TOKEN --body "<new-token>"

# 4. Update CLOUDFLARE_ZONE_ID values per-zone in vault
#    (one zone per axiomfolio.com, paperworklabs.com, etc.)
```

### Founder click-ops token (`paperwork-founder-laptop`)

For when you want to run scripts from your laptop without trusting a shared Brain token.

| Field | Value |
|---|---|
| Name | `paperwork-founder-laptop` |
| Scope | Entire Account |
| Expiration | 90 days |
| Client IP filter | Your home IP (good security hygiene for personal-machine tokens) |
| Permissions | Same as Brain token |

Store in 1Password / Bitwarden — never commit.

### Per-environment ephemeral tokens

For one-off operations (e.g. a bulk cutover script), generate a 7-day token scoped to the single zone, with the minimum permissions needed. Delete after use.

## Phase 5 — Verify Brain + GitHub Actions

After Phase 4 token swap:

```bash
# Verify the new token works for the cutover script
./scripts/cutover/axiomfolio-finish-phase-3.sh --dry-run

# Re-trigger any workflows that use CLOUDFLARE_API_TOKEN
gh workflow run vercel-cutover-axiomfolio.yml -f dry_run=true
```

## Operational procedures

### Adding a new zone

1. Founder adds in Cloudflare UI under work account → records imported / configured.
2. Update nameservers at the registrar.
3. Verify `dig +trace ns <zone>` returns work-account nameservers.
4. The Brain token (account-scoped) automatically has access — no token re-issue needed.

### Rotating tokens

- **Brain token**: WS-26 secrets-rotation track — quarterly, via the workflow that pulls a new token from a sealed secret store and updates Render + GH Actions atomically.
- **Founder laptop token**: every 90 days, manual; just regenerate in Cloudflare UI and replace local env file.

### Granting team access

Settings → Members → Invite. Roles:

- **Super Admin**: only the founder (1-2 max).
- **Domain Admin**: per-zone DNS edit. Use for engineers who need to ship.
- **Read-only**: for Brain MCP read tools, contractors, auditors.

---

## Per-zone write tokens

> **Merged from:** the former standalone `cloudflare-per-zone-tokens.md` runbook — use zone-scoped write tokens to limit blast radius (WS-47).

**TL;DR:** Prefer per-zone Cloudflare API tokens instead of one account-wide write token when rotating secrets or finishing the WS-47 migration.

### Why per-zone tokens?

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

### Zones managed

| Zone | Env var name | Status |
|---|---|---|
| `paperworklabs.com` | `CLOUDFLARE_TOKEN_PAPERWORKLABS_COM` | Migrate |
| `axiomfolio.com` | `CLOUDFLARE_TOKEN_AXIOMFOLIO_COM` | Migrate |
| `filefree.ai` | `CLOUDFLARE_TOKEN_FILEFREE_AI` | Migrate |
| `launchfree.ai` | `CLOUDFLARE_TOKEN_LAUNCHFREE_AI` | Migrate |
| `distill.tax` | `CLOUDFLARE_TOKEN_DISTILL_TAX` | Migrate |

### Creating a per-zone token in the Cloudflare dashboard

**Token naming pattern:** `paperwork-brain-write-<zone-slug>`
Examples: `paperwork-brain-write-paperworklabs-com`, `paperwork-brain-write-axiomfolio-com`

**Steps** (repeat for each zone):

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

### Registering the token

**Vault** (canonical):

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

**Vercel** (runtime):

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

**Render** (Brain API):

Set each env var in the **brain-api** Render service dashboard:
`Settings → Environment → Add Environment Variable`

Or via Render API:

```bash
curl -s -X POST "https://api.render.com/v1/services/$BRAIN_RENDER_SERVICE_ID/env-vars" \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '[{"key":"CLOUDFLARE_TOKEN_AXIOMFOLIO_COM","value":"<token>"}]'
```

### Code integration

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

### Migration plan (dual-token cutover)

The system supports **both** `CLOUDFLARE_API_TOKEN` (account-wide) and per-zone
tokens simultaneously during migration.  No code changes are required between
steps; resolution is transparent.

| Phase | Description |
|---|---|
| **Before migration** | Only `CLOUDFLARE_API_TOKEN` set → all writes use it (warning logged) |
| **During migration** | Set `CLOUDFLARE_TOKEN_<ZONE>` for each zone one at a time → resolver picks per-zone; account-wide unused for that zone |
| **After migration** | All per-zone tokens set → remove `CLOUDFLARE_API_TOKEN` from vault and all environments |
| **Verification** | Watch Brain logs for `cloudflare_token_resolver: using per-zone token` lines; absence of `falling back to CLOUDFLARE_API_TOKEN` confirms migration complete |

**Cleanup after full migration:**

```bash
# Remove account-wide token from vault
curl -s -X DELETE "https://paperworklabs.com/api/secrets/CLOUDFLARE_API_TOKEN" \
  -H "Authorization: Bearer $SECRETS_API_KEY"

# Remove from Vercel
vercel env rm CLOUDFLARE_API_TOKEN production

# Revoke the account-wide token in Cloudflare dashboard
# Dashboard → My Profile → API Tokens → paperwork-brain-write (account-wide) → Revoke
```

### Rotation schedule

Brain's secrets rotation monitor (`app/schedulers/secrets_rotation_monitor.py`)
alerts in Slack when any `CLOUDFLARE_TOKEN_*` key expires within 30 days.

Recommended TTL: **1 year**.  Rotate proactively every 11 months.

Rotation steps:

1. Create a new per-zone token in the Cloudflare dashboard (same permissions)
2. Update in vault → propagate to Render + Vercel
3. Verify Brain logs show the new token resolving correctly
4. Revoke the old token in the Cloudflare dashboard

### Per-zone troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `CLOUDFLARE_API_TOKEN` warning in Brain logs | Per-zone token not set | Set `CLOUDFLARE_TOKEN_<ZONE>` |
| 401 from Cloudflare API | Wrong token / expired | Rotate token, verify vault |
| `neither ... nor CLOUDFLARE_API_TOKEN is configured` error | Both vars absent | Set at least one token |
| DNS mutations affecting wrong zone | Token scoped incorrectly | Verify token zone restriction in CF dashboard |

---

## Post-migration DNS verification checklist

After **any** future Cloudflare zone migration or bulk "import DNS" operation on a production apex:

1. Run **`python3 scripts/reconcile_clerk_dns.py --check-only`** with `CLERK_SECRET_KEY` + `CLOUDFLARE_API_TOKEN` (or `CF_TOKEN`) from a trusted machine. Exit **0** means Clerk's required `cname_targets` match Cloudflare. See [Clerk DNS incident (2026-04-28)](clerk-dns-incident-2026-04-28.md) for the failure mode Cloudflare's auto-scan can miss.
2. Manually diff **SaaS CNAMEs** that flatten or proxy oddly — **`*.clerk.services`**, **`*.onrender.com`**, **`cname.vercel-dns.com`**, third-party mail (`mail.*.clerk.services`, DKIM `dkim*`), and any **non-Clerk** ops rows (e.g. Brain on Render) against a **pre-migration export** or registrar snapshot. Do not assume "import succeeded" means "all rows present".
3. Re-check **Clerk Dashboard → Domains** for **custom hostname / satellite** status after the zone moves accounts; Cloudflare-for-SaaS registration is **per zone** and may need re-validation.
4. For Vercel-linked hostnames, confirm the intended **CNAME target** still matches the active architecture (Clerk-hosted Account Portal vs self-hosted).

## Cloudflare UX patterns we adopt for our own products

The Cloudflare token-issuance flow is a clean model for any future API-key UX we ship in FileFree / LaunchFree / Distill. Patterns worth standardizing on:

| Pattern | Why it works | Where to apply |
|---|---|---|
| **Token name forced before generation** | Operator labels the token with intent | Distill API key issuance |
| **Permissions grouped by resource (DNS, App Security, etc.)** | Maps to mental model not DB tables | All admin UIs |
| **Mandatory expiration with a "No expiration" footgun behind a confirmation** | Forces hygiene by default | Future API tokens |
| **Optional client IP allowlist on the same screen** | Defense-in-depth without extra workflow | High-trust tokens |
| **"Review token" preview step before generation** | Last-chance confirmation, prevents misconfigured tokens | Any sensitive write op |
| **Token shown ONCE after generation, then never again** | Forces rotation / re-provision instead of silent capture | All API key flows |
| **Account-scoped vs Zone-scoped vs Per-environment ephemeral** | Three-tier blast radius | Internal tooling |

These map naturally to our own forthcoming patterns — e.g. when we eventually
ship customer-facing API keys for Distill, copy this UX exactly. (We already
borrow from this in the existing `apps/studio/` admin secrets surface.)

## Rollback

If anything goes sideways during Phase 3:

1. **Revert nameservers** at the registrar (use the original **former** personal-account values).
2. Wait 5-15 min for DNS to propagate back.
3. The **former** personal-account zone is still configured and "Active" until you explicitly delete it — **do not delete that zone for at least 24h after the work zone goes live**.

## Deliverables (migration complete)

| Action | Code / docs | Founder UI |
|---|---|---|
| This runbook | ✓ | — |
| Token in vault + Render + GH Actions | ✓ (account-scoped `paperwork-brain`) | — |
| Cloudflare work account | — | ✓ |
| 2FA enrollment | — | ✓ |
| Zone migration (all 5 prod zones) | — | ✓ |
| Nameserver switch at registrar (Spaceship) | — | ✓ |

## What we learned

For **every** production zone (`paperworklabs.com`, `axiomfolio.com`, `filefree.ai`, `launchfree.ai`, `distill.tax`), Cloudflare’s **Import** flow accepted **BIND-style zone exports** from the source account (or equivalent) without a manual record-by-record rebuild. After import, we verified proxy flags and critical hostnames, switched registrar nameservers to the work-account pair (`janet.ns.cloudflare.com` + `noel.ns.cloudflare.com`), and confirmed HTTP 200 on apex + key subdomains. **No zone required a fully manual DNS rewrite** — plan for import + diff + NS cutover, not spreadsheet-driven copy-paste.
