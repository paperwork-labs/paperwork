# Paperwork ID (`apps/accounts`)

Next.js app for **`accounts.paperworklabs.com`** — the **primary Clerk Frontend API host** in the multi-domain satellite topology. Product apps (FileFree, LaunchFree, AxiomFolio, Distill, Trinkets, Studio) are **satellites** that sync auth with this domain.

## Runbook

- **[Clerk satellite topology](../../docs/infra/CLERK_SATELLITE_TOPOLOGY.md)** — authoritative steps for Dashboard, DNS, and per-app env.

## Before production

1. **DNS** — Add Clerk-verified records for `accounts.paperworklabs.com` in the `paperworklabs.com` zone (see runbook).
2. **Clerk Dashboard** — Add the domain, primary Frontend API, and satellite domains per runbook.
3. **Vercel** — Create a project rooted at `apps/accounts`, link the repo, set env vars from `.env.example`, and add the real `project_id` to `vercel-projects.json` + [`.github/workflows/vercel-promote-on-merge.yaml`](../../.github/workflows/vercel-promote-on-merge.yaml) (set `skip_promote: false` and paste `project_id` for `accounts` when ready).
4. **Env** — Copy `.env.example` to Vercel / local; use the same Clerk keys as other linked apps.

## Local dev

```bash
pnpm install
cp .env.example .env.local
# fill Clerk keys
pnpm dev
```

Open [http://localhost:3010](http://localhost:3010).

## Branding

Parent palette only: slate ink `#0F172A` and amber `#F59E0B`. User-facing **“Paperwork ID”** copy is limited to this app (home + sign-in/up). Other products keep **“Sign in to &lt;Product&gt;”**.
