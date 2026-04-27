---
owner: infra-ops
last_reviewed: 2026-04-26
doc_kind: runbook
domain: infra
status: active
severity_default: yellow
related_runbooks:
  - CLERK_SATELLITE_TOPOLOGY.md
---

# Tonight: `accounts.paperworklabs.com` — Clerk primary + DNS (H1)

**Time budget:** ~10 minutes for DNS + Dashboard clicks (propagation may add minutes).

**Goal:** Add the **primary** Clerk production domain `accounts.paperworklabs.com` and prove DNS so Clerk can issue TLS. Satellites (`filefree.ai`, etc.) come **after** verify — and **application code** must stay on the current Clerk integration until Track H4 ships `apps/accounts/` (see ordering below).

## 1. Get CNAME targets from Clerk (exact values)

1. Clerk Dashboard → **Settings** (or **Configure**) → **Domains** (or **DNS & domains**).
2. **Add domain** / **Add custom domain** → enter **`accounts.paperworklabs.com`**.
3. Clerk shows **DNS records** (names + targets). **Copy only into your DNS provider** — do not paste secrets or verification tokens into the repo.

Typical shapes (Clerk’s UI is authoritative — yours may differ):

- **`accounts`** (or `@` / `accounts.paperworklabs.com`) → CNAME → `clerk.frontend-api.<instance>.lcl.dev` or a Workers-style target Clerk displays.
- **`clerk.accounts`** (satellite helper on the primary zone) → only if the Dashboard lists it.
- **`clk._domainkey.accounts`** (or similar DKIM) → only if Clerk lists it for email.

## 2. Add records at your DNS provider

**Authoritative NS for `paperworklabs.com`:** run `dig +short NS paperworklabs.com` — use **that** registrar/DNS UI (today this may be Spaceship or another host; it is **not** assumed to be Cloudflare).

Create the records **exactly** as Clerk’s panel shows (type, name/host, value, TTL **DNS only** / no orange-cloud proxy if Clerk says verification fails behind a proxy).

Example pattern (replace placeholders with Dashboard values):

```text
CNAME  accounts.paperworklabs.com  →  <Clerk Frontend API target from Dashboard>
CNAME  clerk.accounts.paperworklabs.com  →  <only if Dashboard requires it>
CNAME  clk._domainkey.accounts.paperworklabs.com  →  <only if Dashboard requires DKIM>
```

## 3. Verify DNS

Within a few minutes (TTL-dependent):

```bash
dig +short CNAME accounts.paperworklabs.com
```

You should see Clerk’s target hostname. Then in Clerk → **Verify** on the domain until the Dashboard shows **Verified** / **Active**.

## 4. Mark product domains as satellites (after primary is verified)

In the **same** Clerk production instance:

1. **Domains** → **Satellite domains** (wording may vary).
2. For each production app host, add as satellite, e.g. `filefree.ai`, `launchfree.ai`, `distill.tax`, `paperworklabs.com` (Studio), `tools.filefree.ai`, and the public AxiomFolio hostname — **exact hostnames users type**.

Each satellite will get **its own** DNS instructions (often `clerk.<apex>` in **that** zone). Complete those in the respective DNS providers when you cut over app-by-app.

## 5. Code / deploy ordering (critical)

- **Do not** flip Next.js apps to Clerk **satellite mode** in code (`isSatellite`, `domain={...}`, `signInUrl="https://accounts.paperworklabs.com/sign-in"`) until **Track H4** deploys the **`apps/accounts/`** app on `accounts.paperworklabs.com`. Early deploy would send users to a **404** on the primary host.
- When H4 is live: update each app’s `<ClerkProvider>` per [Clerk satellite docs](https://clerk.com/docs/guides/dashboard/dns-domains/satellite-domains) and your [`CLERK_SATELLITE_TOPOLOGY.md`](CLERK_SATELLITE_TOPOLOGY.md).

## 6. End-to-end test (after H4 + satellite code deploy)

1. Open a **satellite** app in an incognito window (e.g. `https://filefree.ai`).
2. Start sign-in → expect redirect to **`https://accounts.paperworklabs.com/sign-in`** (or Clerk’s flow URL).
3. Complete sign-in → expect return to the satellite, **session recognized** (multi-domain SSO path).

## Reference

- Architecture: [`docs/infra/CLERK_SATELLITE_TOPOLOGY.md`](CLERK_SATELLITE_TOPOLOGY.md)
- Product map: [`docs/INFRA.md`](../INFRA.md)
