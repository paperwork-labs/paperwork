# Clerk SSO — FileFree (Next.js)

Runbook for the FileFree app (`apps/filefree`) identity layer: **Clerk** (primary SSO) for admin surfaces, with **Basic Auth** as an operator escape hatch until removed in a follow-up. **Legacy session cookies** for `/file` and `/auth/*` are unchanged.

## Environment variables (standard names)

| Variable | Where used | Source |
| -------- | ------------ | ------ |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Client + server bootstrap | [Vercel Marketplace — Clerk](https://vercel.com/integrations) for the **FileFree** Vercel project; copy to local from your secrets vault for dev |
| `CLERK_SECRET_KEY` | Server (session verification, middleware) | Same as above |

**No custom prefix** — use these exact names on the FileFree project, not a `FILEFREE_` prefix.

## Embedded `<SignIn />` on first-party routes (required)

FileFree uses embedded auth on `/sign-in` and `/sign-up`, not Clerk’s hosted Account Portal—no `accounts.*` DNS dependency; Clerk portal “Powered by” footer is avoided on Hobby.

| Variable | Value |
| -------- | ----- |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` |
| `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL` | `/dashboard` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL` | `/dashboard` |

Match `<ClerkProvider signInUrl` / `signUpUrl` in `apps/filefree/src/app/layout.tsx`. Do not set `NEXT_PUBLIC_CLERK_DOMAIN` or change Clerk keys for this.

**Branding:** `filefree-clerk-appearance.ts` hides Clerk footer chrome; auth pages show **Paperwork Labs** / **Single Sign-On** above the form.

**Basic Auth** (admin escape hatch) uses the same variable names as Studio when present:

- `ADMIN_EMAILS` — comma-separated allowlist
- `ADMIN_ACCESS_PASSWORD` — shared password (rotate per ops)

## How Clerk, Basic, and the legacy session coexist

- **Clerk** handles interactive SSO for `/admin` and `/api/admin` when keys are set.
- **Basic Auth** still works in **production** on those paths for scripts or emergency access. Either a valid **Clerk session** or valid **Basic** credentials is enough.
- **Session cookie** gating for `/file`, `/dashboard`, and `/auth/*` is the same as before this layer (no Clerk required for the core filing flow).

**Development:** the admin wall is not enforced on `/admin` and `/api/admin` (local DX). **Production:** the dual gate applies.

**Precedence** (enforced in `apps/filefree/src/middleware.ts` for admin routes in production): legacy session redirects run first, then: public routes pass through, then (for `/admin*`) 1) `auth().userId` → allow, 2) else valid Basic → allow, 3) else sign-in redirect or 401 for APIs.

## Test sign-in locally

1. Add `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` to `apps/filefree/.env.local` (do not commit).
2. `pnpm --filter @paperwork-labs/filefree dev` (port **3001** by default).
3. Open `http://localhost:3001/sign-in` and complete the Clerk dev flow.

## Theming

Clerk UI is aligned with FileFree’s violet / dark theme via the **Appearance** API ([Clerk docs: `appearance` prop](https://clerk.com/docs/customization/overview#appearance-prop)). Precedent: Studio in PR #152 (`studio-clerk-appearance` + `ClerkAuthPageShell`).

### Where configuration lives

| Piece | Path |
| ----- | ---- |
| Global `appearance` (all Clerk surfaces: SignIn, SignUp, `UserButton`, modals) | `apps/filefree/src/lib/filefree-clerk-appearance.ts`, passed to `<ClerkProvider>` in `apps/filefree/src/app/layout.tsx` |
| Auth route layout (gradient shell, centers the form; height fits below fixed `Nav` + `pt-14`) | `apps/filefree/src/components/clerk/ClerkAuthPageShell.tsx`, used by `apps/filefree/src/app/sign-in/[[...sign-in]]/page.tsx` and `apps/filefree/src/app/sign-up/[[...sign-up]]/page.tsx` |

`baseTheme` is `@clerk/themes`’s `dark` theme; CSS variables and `elements` extend it. Colors resolve at runtime from `[data-theme="filefree"]` in `packages/ui/src/themes.css` (imported by `apps/filefree/src/app/globals.css`).

### FileFree palette → Clerk variables

| Clerk `appearance.variables` | Theme source (HSL custom property) |
| ---------------------------- | ----------------------------------- |
| `colorPrimary` | `--primary` |
| `colorBackground` | `--background` |
| `colorInputBackground` | `--input` |
| `colorInputText` / `colorText` | `--foreground` |
| `colorTextSecondary` | `--muted-foreground` |
| `colorDanger` | `--destructive` |
| `borderRadius` | `0.5rem` (from `globals.css` `@theme` `--radius`) |
| `fontFamily` | `var(--font-inter)` from `next/font` in `layout.tsx` |

`appearance.elements` adds Tailwind classes (violet-tinted card and inputs) — see `filefree-clerk-appearance.ts`.

### Per-route overrides (future)

Import `fileFreeClerkAppearance` and pass a spread override to `<SignIn />` / `<SignUp />` on a specific route if needed. Keep the **provider** in `layout.tsx` as the default for modals and `UserButton` unless you intentionally override at the component.

## Related

- Studio runbook: `docs/infra/CLERK_STUDIO.md`
- Sprint: `docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md`
