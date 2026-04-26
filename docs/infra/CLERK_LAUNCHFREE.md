# Clerk SSO — LaunchFree (Next.js)

Runbook for the LaunchFree app (`apps/launchfree`) identity stack: Clerk (primary SSO) with the legacy `session` cookie on `/dashboard`, plus Basic Auth as an operator escape hatch on `/admin` and `/api/admin` in production until removed by an explicit follow-up.

## Environment variables (standard names)

| Variable | Where used | Source |
| -------- | ------------ | ------ |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Client + server bootstrap | [Vercel Marketplace — Clerk](https://vercel.com/integrations) on the linked LaunchFree project; copy locally from the vault for dev |
| `CLERK_SECRET_KEY` | Server (session verification, middleware) | Same as above |

**Custom prefix** is not used — do not add an `LAUNCHFREE_` or other prefix to these names in Vercel or `.env`.

## Embedded `<SignIn />` on first-party routes (required)

LaunchFree uses embedded auth on `/sign-in` and `/sign-up`, not the hosted Account Portal—no `accounts.*` DNS; avoids non-removable Clerk portal branding on Hobby.

| Variable | Value |
| -------- | ----- |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` |
| `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL` | `/dashboard` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL` | `/dashboard` |

Aligns with `<ClerkProvider signInUrl` / `signUpUrl` in `apps/launchfree/src/app/layout.tsx`. Do not set `NEXT_PUBLIC_CLERK_DOMAIN` or change Clerk keys for this.

**Branding:** `launchfree-clerk-appearance.ts` hides Clerk footer chrome; auth pages show **Paperwork Labs** / **Single Sign-On** above the form.

**Basic Auth** (admin surfaces only, production) uses:

- `ADMIN_EMAILS` — comma-separated allowlist
- `ADMIN_ACCESS_PASSWORD` — shared password (rotate via ops)

## How Clerk, cookie, and Basic Auth coexist

- **Clerk** handles interactive SSO (email/OAuth, session cookies) once keys are set; `/sign-in` and `/sign-up` are public.
- **`/dashboard`** accepts either a **Clerk session** (`auth().userId`) or the existing **`session` cookie** (legacy).
- **Basic Auth** remains available on **`/admin`** and **`/api/admin`** in **production** for operators without a Clerk browser session. Either a valid **Clerk session** or valid **Basic** credentials suffice — both are not required.

**Development:** the wall on `/admin` and `/api/admin` is not enforced. **`/dashboard`** still requires Clerk or the legacy cookie (same as pre-Clerk local behavior).

**Precedence** for `/admin` and `/api/admin` in production (`apps/launchfree/src/middleware.ts`):

1. Public routes: no LaunchFree admin gate.
2. If `auth().userId` → allow.
3. Else if valid Basic Auth → allow.
4. Else → sign-in redirect (pages) or `401` with `WWW-Authenticate` (API).

## Test sign-in locally

1. Copy `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` into `apps/launchfree/.env.local` (never commit).
2. Run: `cd apps/launchfree && pnpm dev` (port **3002** by default).
3. Open `http://localhost:3002/sign-in` and complete the Clerk dev flow. Confirm `/dashboard` is reachable with Clerk or with the legacy cookie flow as before.

## Theming

Clerk UI is aligned with LaunchFree’s dark slate + teal palette via the **Appearance** API ([Clerk docs: `appearance` prop](https://clerk.com/docs/customization/overview#appearance-prop)). Precedent: Studio in PR #152 (`studio-clerk-appearance` + `ClerkAuthPageShell`).

### Where configuration lives

| Piece | Path |
| ----- | ---- |
| Global `appearance` (all Clerk surfaces: SignIn, SignUp, `UserButton`, modals) | `apps/launchfree/src/lib/launchfree-clerk-appearance.ts`, passed to `<ClerkProvider>` in `apps/launchfree/src/app/layout.tsx` |
| Auth route layout (full-viewport gradient shell, centers the form) | `apps/launchfree/src/components/clerk/ClerkAuthPageShell.tsx`, used by `apps/launchfree/src/app/sign-in/[[...sign-in]]/page.tsx` and `apps/launchfree/src/app/sign-up/[[...sign-up]]/page.tsx` |

`baseTheme` is `@clerk/themes`’s `dark` theme; CSS variables and `elements` extend it. Colors resolve at runtime from `[data-theme="launchfree"]` in `packages/ui/src/themes.css` (reinforced in `apps/launchfree/src/app/globals.css`).

### LaunchFree palette → Clerk variables

| Clerk `appearance.variables` | Theme source (HSL custom property) |
| ---------------------------- | ----------------------------------- |
| `colorPrimary` | `--primary` |
| `colorBackground` | `--background` |
| `colorInputBackground` | `--input` |
| `colorInputText` / `colorText` | `--foreground` |
| `colorTextSecondary` | `--muted-foreground` |
| `colorDanger` | `--destructive` |
| `borderRadius` | `0.5rem` (matches shared UI radius) |
| `fontFamily` | `var(--font-inter)` from `next/font` in `layout.tsx` |

`appearance.elements` adds Tailwind classes (slate borders, card chrome) where variables are not enough — see `launchfree-clerk-appearance.ts`.

### Per-route overrides (future)

Import `launchFreeClerkAppearance` and pass `appearance={{ ...launchFreeClerkAppearance, ... }}` to a page-level `<SignIn />` / `<SignUp />` if a route needs a one-off. Keep the **provider** default in `layout.tsx` so `UserButton` and modals stay consistent unless intentionally overridden.

## Related

- Studio runbook: `docs/infra/CLERK_STUDIO.md`
- Sprint: `docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md`
