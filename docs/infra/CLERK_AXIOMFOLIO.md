# Clerk SSO — AxiomFolio (Next.js)

Runbook for the AxiomFolio Next.js app (`apps/axiomfolio`, package `@paperwork-labs/axiomfolio`) identity stack: Clerk SDK foundation (T6c) alongside the existing **`qm_token`** session in `localStorage`. Per-app Clerk theming (T3.4) uses the Appearance API; see [Theming](#theming) below.

## Environment variables (standard names)

| Variable | Where used | Source |
| -------- | ------------ | ------ |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Client + server bootstrap | Vercel Marketplace — Clerk on the linked AxiomFolio Vercel project (dashboard name may still be `axiomfolio-next`); copy locally from the vault for dev |
| `CLERK_SECRET_KEY` | Server (proxy / session verification) | Same as above |

**Custom prefix** is not used — do not add an `AXIOMFOLIO_` or other prefix to these names in Vercel or `.env`.

## Embedded `<SignIn />` on first-party routes (required)

AxiomFolio uses embedded auth on `/sign-in` and `/sign-up`, not the hosted Account Portal—no `accounts.*` DNS; avoids non-removable Clerk portal branding on Hobby.

| Variable | Value |
| -------- | ----- |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` |
| `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL` | `/` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL` | `/` |

Aligns with `<ClerkProvider signInUrl` / `signUpUrl` in `apps/axiomfolio/src/app/layout.tsx`. Do not set `NEXT_PUBLIC_CLERK_DOMAIN` or change Clerk keys for this.

**Branding:** shared preset `axiomfolioAppearance` (see below) hides Clerk footer chrome; auth pages show **Paperwork Labs** / **Single Sign-On** above the form.

## Theming

- **Appearance object** — `packages/auth/src/appearance/presets.ts` exports `axiomfolioAppearance` (`createClerkAppearance` for AxiomFolio). It uses `baseTheme: dark` from `@clerk/themes` and maps Clerk `variables` to the app’s CSS tokens from `apps/axiomfolio/src/app/axiomfolio.css` and `apps/axiomfolio/src/app/globals.css` (oklch `--primary`, `--background`, `--foreground`, `--input`, etc.). The `elements` block applies Tailwind classes for the card, primary button, social buttons, and `UserButton` so sign-in, sign-up, and account controls match the dark blue canvas + gold primary accent.
- **Provider** — `RootLayout` imports `axiomfolioAppearance` from `@paperwork-labs/auth-clerk/appearance` and passes `appearance={axiomfolioAppearance}` to `<ClerkProvider>` so `UserButton` and any other top-level Clerk UI inherits the theme.
- **Auth routes** — `/sign-in` and `/sign-up` wrap `<SignIn />` / `<SignUp />` in `ClerkAuthPageShell` (gradient + AxiomFolio logo and tagline, aligned with `AuthLayout` for legacy auth).
- **Tweaking** — Adjust colors by editing the CSS variables in `axiomfolio.css` (`.dark` and `@theme`); for Clerk-only polish, edit the `elements` map in the appearance file. Keep `@clerk/themes` in lockstep with other Paperwork apps (`^2.4.x` range in `package.json`).

## How Clerk and `qm_token` coexist

- **Legacy auth** — `qm_token` in `localStorage`, `AuthContext`, `/auth/callback`, `/login`, `/register`, and **`RequireAuthClient`** on protected pages remain the **source of truth** for who can use the app today.
- **Clerk** — `/sign-in` and `/sign-up` (catch-all routes) render **embedded** `<SignIn />` / `<SignUp />` on this origin (not the Account Portal). Keys must be present for those routes to work in dev/prod.
- **Proxy** (`apps/axiomfolio/src/proxy.ts`) — Next.js 16 uses `proxy.ts` instead of `middleware.ts`. Clerk is composed there and is **non-blocking**: it does not call `auth().protect()` and does not redirect unauthenticated users. It only wires Clerk’s request context for gradual adoption. Server-side protection for Clerk-only flows is future work.

Public paths are explicitly listed in `proxy.ts` (home, legacy auth, Clerk auth, pricing, health). This list may be tightened when server-side gates are introduced.

## Admin routes

There is **no `/admin` surface** at the root path yet (admin lives under `/settings/admin/*` and `/system-status`). When new operator routes are added, mirror the Basic Auth + Clerk pattern from LaunchFree/FileFree runbooks if required.

## Test sign-in locally

1. Copy `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` into `apps/axiomfolio/.env.local` (never commit).
2. Run: `pnpm --filter @paperwork-labs/axiomfolio dev` (port **3005** by default).
3. Open `http://localhost:3005/sign-in` and complete the Clerk dev flow. Confirm legacy flows: `/login`, `/auth/callback`, and `RequireAuthClient`-wrapped pages still work with `qm_token` as before.
4. Public health: `GET /api/health` → `{"status":"ok"}`.

## Related

- LaunchFree: `docs/infra/CLERK_LAUNCHFREE.md`
- Sprint: `docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md`
