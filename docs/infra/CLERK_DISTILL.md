# Clerk SSO — Distill (Next.js)

Runbook for the Distill app (`apps/distill`) identity stack: **Clerk** (SSO) for interactive sign-in. There is **no** legacy session cookie or Basic Auth layer in this app — `clerkMiddleware` only enforces a Clerk session on `/dashboard`; the home page and auth routes stay public.

## Environment variables (standard names)

| Variable | Where used | Source |
| -------- | ------------ | ------ |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Client + server bootstrap | [Vercel Marketplace — Clerk](https://vercel.com/integrations) on the linked Distill project; copy locally from the vault for dev |
| `CLERK_SECRET_KEY` | Server (session verification, middleware) | Same as above |

**Custom prefix** is not used — do not add a `DISTILL_` or other prefix to these names in Vercel or `.env`.

**Dashboard feature gate** (unchanged, page-level): `DISTILL_DASHBOARD_ENABLED` may still redirect signed-in users from `/dashboard` to `/` when not in development. That is separate from Clerk — see `apps/distill/src/app/dashboard/page.tsx`.

## Embedded `<SignIn />` on first-party routes (required)

Distill uses embedded auth on `/sign-in` and `/sign-up`, not the hosted Account Portal—no `accounts.*` DNS; avoids non-removable Clerk portal branding on Hobby.

| Variable | Value |
| -------- | ----- |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` |
| `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL` | `/dashboard` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL` | `/dashboard` |

Aligns with `<ClerkProvider signInUrl` / `signUpUrl` in `apps/distill/src/app/layout.tsx`. Do not set `NEXT_PUBLIC_CLERK_DOMAIN` or change Clerk keys for this.

**Branding:** `clerk-appearance.ts` hides Clerk footer chrome; auth pages show **Paperwork Labs** / **Single Sign-On** above the form.

## How Clerk is applied

- **Clerk** handles email/OAuth and session cookies. `/sign-in` and `/sign-up` are public.
- **`/dashboard`** requires a **Clerk session** in middleware (`userId`); unauthenticated users are redirected to sign-in. The legacy LaunchFree/FileFree “escape hatches” (session cookie, Basic Auth) are **not** used here.
- **Development** vs **production**: same middleware behavior for Distill; only the `DISTILL_DASHBOARD_ENABLED` check differs inside the page.

**Precedence** (`apps/distill/src/middleware.ts`):

1. Non-dashboard routes: no Clerk gate in middleware.
2. `/dashboard`: if no `auth().userId` → redirect to sign-in; otherwise allow (page may still `redirect("/")` per env).

## Test sign-in locally

1. Copy `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` into `apps/distill/.env.local` (never commit).
2. Run: `pnpm --filter @paperwork-labs/distill dev` (port **3005** by default).
3. Open `http://localhost:3005/sign-in` and complete the Clerk dev flow. Confirm `/dashboard` is reachable when signed in and `DISTILL_DASHBOARD_ENABLED` / dev mode allows it.

## Theming

Clerk UI uses Distill’s **teal** (`#0F766E`) and **burnt orange** (`#C2410C`) accents on a dark base via the **Appearance** API ([Clerk docs: `appearance` prop](https://clerk.com/docs/customization/overview#appearance-prop)). Precedent: LaunchFree (`launchfree-clerk-appearance` + `ClerkAuthPageShell`); Distill uses a dedicated palette file instead of the shared `themes.css` primary for this product.

### Where configuration lives

| Piece | Path |
| ----- | ---- |
| Global `appearance` (SignIn, SignUp, `UserButton`, modals) | `packages/auth-clerk/src/appearance/presets.ts` (`distillAppearance`), passed to `<ClerkProvider>` in `apps/distill/src/app/layout.tsx` |
| Auth route shell (full-viewport gradient, centers the form) | `apps/distill/src/components/clerk/ClerkAuthPageShell.tsx`, used by `apps/distill/src/app/sign-in/[[...sign-in]]/page.tsx` and `apps/distill/src/app/sign-up/[[...sign-up]]/page.tsx` |

`baseTheme` is `@clerk/themes`’s `dark` theme; `variables` and `elements` extend it with the locked teal + orange palette.

### Distill palette → Clerk variables

| Clerk `appearance.variables` | Notes |
| ---------------------------- | ----- |
| `colorPrimary` | Teal `#0F766E` |
| `colorBackground` / inputs / text | Dark slate HSLs aligned with `[data-theme="distill"]` in `packages/ui` |
| `borderRadius` | `0.5rem` (matches shared UI radius) |
| `fontFamily` | `var(--font-inter)` from `next/font` in `layout.tsx` |

`appearance.elements` adds Tailwind classes (teal/orange border and card chrome) where variables are not enough — see `clerk-appearance.ts`.

### Per-route overrides (future)

Import `distillClerkAppearance` and pass `appearance={{ ...distillClerkAppearance, ... }}` to a page-level `<SignIn />` / `<SignUp />` if a route needs a one-off. Keep the **provider** default in `layout.tsx` so `UserButton` and modals stay consistent unless intentionally overridden.

### Next.js 16 note

`next build` may log that the `middleware` file convention is deprecated in favor of `proxy`. The Distill app follows the same `src/middleware.ts` layout as LaunchFree until the monorepo standardizes on `proxy.ts`; behavior is correct today.

## Related

- LaunchFree runbook: [CLERK_LAUNCHFREE.md](./CLERK_LAUNCHFREE.md)
- FileFree runbook: [CLERK_FILEFREE.md](./CLERK_FILEFREE.md)
- Studio runbook: [CLERK_STUDIO.md](./CLERK_STUDIO.md)
- Sprint: [docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md](../sprints/STREAMLINE_SSO_DAGS_2026Q2.md)
