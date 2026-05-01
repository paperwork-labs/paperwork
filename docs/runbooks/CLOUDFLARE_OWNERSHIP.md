---
title: Cloudflare account ownership + migration
last_reviewed: 2026-04-28
owner: infra-ops
status: active
domain: infra
doc_kind: runbook
summary: "Completed 2026-04-28: all production zones on Paperwork Labs work Cloudflare account (former founder personal account migrated-from) + token rotation and ongoing DNS ops."
tags: [cloudflare, dns, secrets, migration, security]
---

# Cloudflare account ownership + migration

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

**Old zones on the former personal account** (`Sankalp404@gmail.com`, migrated-from): keep for 24h soak (until ~2026-04-29 21:00 UTC), then delete from that **former** Cloudflare account — they are not production DNS. **Runbook:** `docs/runbooks/CLOUDFLARE_ZONE_DECOMMISSION.md` (script: `scripts/cloudflare_decommission_zones.py`).

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

## Post-migration DNS verification checklist

After **any** future Cloudflare zone migration or bulk "import DNS" operation on a production apex:

1. Run **`python3 scripts/reconcile_clerk_dns.py --check-only`** with `CLERK_SECRET_KEY` + `CLOUDFLARE_API_TOKEN` (or `CF_TOKEN`) from a trusted machine. Exit **0** means Clerk's required `cname_targets` match Cloudflare. See [Clerk DNS incident (2026-04-28)](CLERK_DNS_INCIDENT_2026-04-28.md) for the failure mode Cloudflare's auto-scan can miss.
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
