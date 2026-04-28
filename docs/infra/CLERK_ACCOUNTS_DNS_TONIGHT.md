---
owner: infra-ops
last_reviewed: 2026-04-28
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

**DNS for `paperworklabs.com`:** **Cloudflare** (Paperwork Labs work account — zone ID `6efe0c9f87c80a21617ff040fa2e55dd`; see `docs/runbooks/CLOUDFLARE_OWNERSHIP.md`). **Spaceship** is the registrar (NS delegation to Cloudflare). Use the Cloudflare steps below — do **not** add apex-zone records only in Spaceship unless you intentionally bypass Cloudflare (we do not).

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

## 2. Add the CNAME in Cloudflare (`paperworklabs.com` zone)

1. Log in to **[Cloudflare](https://dash.cloudflare.com)** on the **Paperwork Labs work** account and open the **`paperworklabs.com`** zone.
2. **DNS** → **Records** → **Add record**:
   - **Type:** `CNAME`
   - **Name:** `accounts` (creates `accounts.paperworklabs.com`)
   - **Target:** paste the **hostname from Clerk Dashboard** (the CNAME target Clerk shows for the primary Frontend API record)
   - **Proxy status:** **DNS only** (grey cloud) — same pattern as other Vercel/Clerk apex records so TLS issuance stays predictable
   - **TTL:** Auto or `300` / `3600` per your norm
3. **Save**. Repeat for any **additional** records Clerk listed for this hostname (e.g. `clerk.accounts`, DKIM) — same zone, **DNS only** unless Clerk docs explicitly require proxy (rare).

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

Each satellite will get **its own** DNS instructions (often `clerk.<apex>` in **that** zone). As of **2026-04-28**, all five brand apex zones live on the **same** work Cloudflare account — complete those records in the matching zone when you cut over app-by-app (`docs/runbooks/CLOUDFLARE_OWNERSHIP.md`).

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
