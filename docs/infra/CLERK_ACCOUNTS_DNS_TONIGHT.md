---
owner: infra-ops
last_reviewed: 2026-04-27
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

**DNS for `paperworklabs.com`:** hosted on **[Spaceship](https://www.spaceship.com)** — not Cloudflare. Use the Spaceship steps below.

## 0. Pick the correct Clerk instance (production only)

1. Open **[Clerk Dashboard](https://dashboard.clerk.com)** and sign in.
2. If you see **multiple applications/instances** (e.g. dev `clerk-paperwork-labs` vs production), select the one that matches **production** — the same instance whose `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` / `CLERK_SECRET_KEY` your live apps use. **Do not** add `accounts.paperworklabs.com` on a dev or staging instance.
3. If the instance list is confusing: in each candidate instance, open **API Keys** and compare the **publishable key prefix** to a production app’s env (Vercel / Render). Only configure DNS on the **production** instance.

## 1. Add the custom domain in Clerk (get the CNAME target)

On the **production** instance:

1. **Settings** → **Domains** (or **Configure** → **Domains**).
2. **Custom domain** → **Add domain** / **Add custom domain** → enter **`accounts.paperworklabs.com`**.
3. Clerk displays the **DNS records** to create. Copy the **CNAME target** value for the primary Frontend API record (Clerk’s UI is authoritative — hostname may look like `clerk.frontend-api.*.lcl.dev` or similar).

**Also add** any extra records Clerk lists for the same domain (e.g. `clerk.accounts`, DKIM `clk._domainkey.accounts`) — only if the Dashboard shows them.

## 2. Add the CNAME in Spaceship

1. Log in: **[https://www.spaceship.com/application/login/](https://www.spaceship.com/application/login/)**
2. **Manage** domain **`paperworklabs.com`** → **Advanced DNS** → **DNS Records**.
3. **Add Record** (or equivalent):
   - **Type:** `CNAME`
   - **Host:** `accounts` (Spaceship expects the subdomain label; this creates `accounts.paperworklabs.com`)
   - **Value:** paste the **target from Clerk Dashboard** (the full hostname Clerk gave you)
   - **TTL:** `3600` (Spaceship default; aligns with ~5–10 min effective propagation for verification)
4. **Save**. Repeat for any **additional** CNAMEs Clerk required (same Advanced DNS flow, Host/Value per Clerk’s table).

## 3. Verify DNS

After **5–10 minutes** (TTL-dependent):

```bash
dig +short CNAME accounts.paperworklabs.com
```

You should see Clerk’s target hostname. Then in **[dashboard.clerk.com](https://dashboard.clerk.com)** → **Domains** → **Verify** on `accounts.paperworklabs.com` until the Dashboard shows **Verified** / **Active**.

## 4. Mark product domains as satellites (after primary is verified)

In the **same** Clerk **production** instance:

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
