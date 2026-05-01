# Runbook: FileFree — Clerk Auth Env Vars for All Vercel Environments

**TL;DR:** Set `NEXT_PUBLIC_CLERK_*` URLs in Vercel for Preview and Production so middleware uses your sign-in shell instead of the hosted Clerk page.

## Problem

Without `NEXT_PUBLIC_CLERK_SIGN_IN_URL` / `NEXT_PUBLIC_CLERK_SIGN_UP_URL` set in the Vercel
environment, Clerk's server-side middleware does not know where the embedded auth pages live.
It falls back to the hosted Account Portal at `accounts.clerk.dev`, producing the bare "Sign in
to Paperwork Labs / Secured by Clerk" screen instead of the custom `SignInShell`.

This affects **Preview** deployments (PR previews) and any **Production** deployment that has
not had these vars set in the Vercel dashboard.

## Root cause

`apps/filefree/.env.production` now commits the values for the production environment.
Vercel **Preview** deployments do not load `.env.production`; they load `.env` and
dashboard env vars scoped to "Preview". Those vars must be set explicitly.

## Fix: set vars via Vercel CLI

Run the following once per environment. Requires `vercel` CLI and being linked to the project:

```bash
# Link to the filefree project if not already
vercel link --project filefree

# Production
vercel env add NEXT_PUBLIC_CLERK_SIGN_IN_URL production <<< "/sign-in"
vercel env add NEXT_PUBLIC_CLERK_SIGN_UP_URL production <<< "/sign-up"
vercel env add NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL production <<< "/file"
vercel env add NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL production <<< "/file"

# Preview (PR deployments)
vercel env add NEXT_PUBLIC_CLERK_SIGN_IN_URL preview <<< "/sign-in"
vercel env add NEXT_PUBLIC_CLERK_SIGN_UP_URL preview <<< "/sign-up"
vercel env add NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL preview <<< "/file"
vercel env add NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL preview <<< "/file"

# Development (optional — .env.local overrides, but good to have as fallback)
vercel env add NEXT_PUBLIC_CLERK_SIGN_IN_URL development <<< "/sign-in"
vercel env add NEXT_PUBLIC_CLERK_SIGN_UP_URL development <<< "/sign-up"
vercel env add NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL development <<< "/file"
vercel env add NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL development <<< "/file"
```

After adding, redeploy the current production deployment:

```bash
vercel --prod --force
```

And re-trigger any open PR preview deployments by pushing a no-op commit or via the Vercel
dashboard "Redeploy" button.

## Verify

1. Open `https://filefree.ai/sign-in` — should show the dark FileFree `SignInShell`, NOT the
   bare Clerk portal ("Secured by Clerk" footer must be absent).
2. Open a PR preview URL + `/sign-in` — same custom shell.
3. Check browser Network tab: the page URL must stay on `filefree.ai` or the preview domain,
   not redirect to `accounts.clerk.dev`.

## Reference: AxiomFolio (working reference)

AxiomFolio uses the identical pattern and its auth flow is correct. Its Vercel project has
`NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in` and `NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up` set
for all three environments (production, preview, development) in the Vercel dashboard.

The `ClerkProvider` props (`signInUrl` / `signUpUrl`) in `apps/filefree/src/app/layout.tsx`
configure the **client-side** React component. The env vars configure **server-side middleware**
and the hosted Account Portal redirect target — both are required.

## Also required (secret — never commit)

| Var | Scope | Where to get |
|-----|-------|-------------|
| `CLERK_SECRET_KEY` | server-only | Clerk dashboard → API Keys |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | public | Clerk dashboard → API Keys |

These must also be set in Vercel for each environment. They are intentionally omitted from
all committed `.env.*` files.
