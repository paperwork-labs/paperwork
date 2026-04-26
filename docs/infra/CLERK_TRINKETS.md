# Clerk SSO — Trinkets (Next.js)

Runbook for the Trinkets app (`apps/trinkets`) identity layer: **Clerk** for interactive SSO (`/sign-in`, `/sign-up`) and global `ClerkProvider` appearance. The app is a **public** utility surface (home and future tool routes stay ungated in middleware); there is **no** legacy session cookie, **no** Basic Auth escape hatch, and **no** admin gate in this app—match LaunchFree/Studio only when you add protected routes later.

## Environment variables (standard names)

| Variable | Where used | Source |
| -------- | ------------ | ------ |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Client + server bootstrap | [Vercel Marketplace — Clerk](https://vercel.com/integrations) on the linked Trinkets Vercel project; copy locally from the vault for dev |
| `CLERK_SECRET_KEY` | Server (session verification, middleware) | Same as above |

**No custom prefix** — use these exact names on the Trinkets project, not a `TRINKETS_` prefix.

## Embedded `<SignIn />` on first-party routes (required)

Trinkets uses embedded auth on `/sign-in` and `/sign-up`, not the hosted Account Portal—no `accounts.*` DNS; avoids non-removable Clerk portal branding on Hobby.

| Variable | Value |
| -------- | ----- |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` |
| `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL` | `/` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL` | `/` |

Aligns with `<ClerkProvider signInUrl` / `signUpUrl` in `apps/trinkets/src/app/layout.tsx`. Do not set `NEXT_PUBLIC_CLERK_DOMAIN` or change Clerk keys for this.

**Branding:** `trinkets-clerk-appearance.ts` hides Clerk footer chrome; auth pages show **Paperwork Labs** / **Single Sign-On** above the form.

## How Clerk fits Trinkets

- **Clerk** handles interactive SSO (email/OAuth, session cookies) once keys are set; `/sign-in` and `/sign-up` are public.
- **`clerkMiddleware`** runs for session state; **public routes** include `/`, `/sign-in`, `/sign-up`, and `/api/health` (mirrors Studio/LaunchFree static-asset matcher). No `auth().protect()` on other paths yet—future protected areas can follow `CLERK_LAUNCHFREE.md` / `CLERK_STUDIO.md` composition patterns.
- **Development** and **production** use the same public-route list for Trinkets (no env-specific admin short-circuit).

## Test sign-in locally

1. Add `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` to `apps/trinkets/.env.local` (do not commit).
2. Run: `pnpm --filter @paperwork-labs/trinkets dev` (port **3003** by default).
3. Open `http://localhost:3003/sign-in` and complete the Clerk dev flow. Confirm `/` still loads without signing in.

## Theming

Clerk UI uses the **Appearance** API ([Clerk docs: `appearance` prop](https://clerk.com/docs/customization/overview#appearance-prop)). Precedent: LaunchFree (`launchfree-clerk-appearance` + `ClerkAuthPageShell`).

### Where configuration lives

| Piece | Path |
| ----- | ---- |
| Global `appearance` (SignIn, SignUp, `UserButton`, modals) | `apps/trinkets/src/lib/trinkets-clerk-appearance.ts`, passed to `<ClerkProvider>` in `apps/trinkets/src/app/layout.tsx` |
| Auth route shell (full-viewport gradient, centers the form) | `apps/trinkets/src/components/clerk/ClerkAuthPageShell.tsx`, used by `sign-in` / `sign-up` catch-all pages |

`baseTheme` is `@clerk/themes`’s `dark` theme. **`colorPrimary`** is the locked **indigo** `#6366F1`; **sky cyan** `#38BDF8` appears in focus rings, secondary glows, and `ClerkAuthPageShell` gradients (Trinkets brand table: indigo + sky cyan).

### Trinkets palette → Clerk variables

| Clerk `appearance.variables` | Notes |
| ---------------------------- | ----- |
| `colorPrimary` | `#6366F1` (indigo; not the amber `--primary` from `[data-theme="trinkets"]` in `packages/ui`) |
| `colorBackground` | `hsl(var(--background))` from `[data-theme="trinkets"]` |
| `colorInputBackground` / input text / text / secondary / danger | Same HSL bridge pattern as LaunchFree |
| `borderRadius` | `0.5rem` |
| `fontFamily` | `var(--font-inter)` from `next/font` in `layout.tsx` |

`appearance.elements` adds Tailwind classes (indigo/sky borders, card chrome)—see `trinkets-clerk-appearance.ts`.

### Per-route overrides (future)

Import `trinketsClerkAppearance` and pass `appearance={{ ...trinketsClerkAppearance, ... }}` to a page-level `<SignIn />` / `<SignUp />` if a route needs a one-off. Keep the **provider** default in `layout.tsx` unless intentionally overridden.

### Escape hatches

- None in-app (no Basic Auth on Trinkets). Operators use the Vercel/Clerk dashboards and standard env rotation per `secrets-ops` / `infra-ops` rules.

## Troubleshooting

- **Middleware / sign-in loops**: Ensure `"/"`, `"/sign-in(.*)"`, and `"/sign-up(.*)"` stay in the public route matcher in `apps/trinkets/src/middleware.ts` if you add `auth().protect()` elsewhere.
- **Missing keys**: Without `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` / `CLERK_SECRET_KEY`, Clerk components error at runtime—confirm Marketplace install and `vercel env pull` for the Trinkets project.
- **Theme mismatch**: If `hsl(var(--background))` looks wrong, confirm `data-theme="trinkets"` on `<body>` and `globals.css` imports `@paperwork-labs/ui/themes.css`.

## Related

- LaunchFree runbook: `docs/infra/CLERK_LAUNCHFREE.md`
- Studio runbook: `docs/infra/CLERK_STUDIO.md`
- Sprint: `docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md`
