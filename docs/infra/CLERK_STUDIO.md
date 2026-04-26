# Clerk SSO — Paperwork Studio (Next.js)

Runbook for the Studio app (`apps/studio`) identity stack: Clerk (primary SSO) with Basic Auth as a documented operator escape hatch until that path is removed by an explicit follow-up.

## Environment variables (standard names)

| Variable | Where used | Source |
| -------- | ------------ | ------ |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Client + server bootstrap | [Vercel Marketplace — Clerk](https://vercel.com/integrations) auto-provision on the linked Studio project; copy to local from **Studio Secrets Vault** for dev |
| `CLERK_SECRET_KEY` | Server (session verification, middleware) | Same as above |
| `BRAIN_API_URL` | Server (`/api/admin/*` routes that call Brain, e.g. n8n mirror status) | Same value as Render `brain-api` public URL; include `/api/v1` or base host — `command-center` normalizes |
| `BRAIN_API_SECRET` | Server (sent as `X-Brain-Secret` to Brain `/admin/*`) | Must match Brain’s `BRAIN_API_SECRET` |

**Custom prefix** is not used (empty) — do not add a `STUDIO_` or other prefix to these variable names in Vercel or `.env`.

## Embedded `<SignIn />` on first-party routes (required)

Paperwork Studio does **not** rely on Clerk’s hosted Account Portal (`accounts.*`). Auth uses embedded `<SignIn />` / `<SignUp />` on `/sign-in` and `/sign-up`. That removes the need to maintain `accounts.paperworklabs.com` DNS for login and avoids Clerk’s non-removable “Powered by Clerk” footer on the portal (non–Clerk Pro).

| Variable | Value | Purpose |
| -------- | ----- | ------- |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` | Aligns with `<ClerkProvider signInUrl="/sign-in">` in `apps/studio/src/app/layout.tsx` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` | Same for sign-up |
| `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL` | `/admin` | Fallback after sign-in when no `redirect_url` is present |
| `NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL` | `/admin` | Same for sign-up |

Set these on the **Studio** Vercel project. Do **not** add `NEXT_PUBLIC_CLERK_DOMAIN` or alter Marketplace-provisioned publishable/secret keys for this.

### Branding

`studio-clerk-appearance.ts` suppresses Clerk’s residual footer wordmark (“Secured by Clerk”) via `appearance.elements` (`footer`, `footerAction*`, `badge`, `internal` → Tailwind `hidden`). Sign-in and sign-up pages add a **Paperwork Labs** / **Single Sign-On** wordmark above the form.

**Basic Auth** (unchanged) still uses:

- `ADMIN_EMAILS` — comma-separated allowlist
- `ADMIN_ACCESS_PASSWORD` — shared password (rotate via ops process)

## How Clerk and Basic Auth coexist

- **Clerk** handles interactive SSO (email/OAuth, session cookies, `UserButton` in `/admin` UI) once keys are set.
- **Basic Auth** remains available on `/admin` and `/api/admin` in **production** so operators can use tools that do not have a browser session to Clerk (e.g. scripts, or emergency access). Either a valid **Clerk session** or a valid **Basic** credential is sufficient — both are not required.
- The **`/api/secrets*`** routes are **not** gated by this layer; they use `src/lib/secrets-auth.ts` (Basic + machine tokens) as before.

**Development:** the Studio wall on `/admin` and `/api/admin` is not enforced (so local work does not require Basic or Clerk in `.env` unless you are testing them). **Production:** the dual gate above applies.

**Precedence** (enforced in `apps/studio/src/middleware.ts`):

1. Public routes and secrets API: no Studio Clerk/Basic wall.
2. If `auth().userId` is set → allow.
3. Else if valid Basic Auth → allow.
4. Else → sign-in redirect (pages) or `401` with `WWW-Authenticate` (API).

## Test sign-in locally

1. Copy `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` from the Studio vault into `apps/studio/.env.local` (never commit these files).
2. Run: `cd apps/studio && pnpm dev` (port **3004** by default).
3. Open `http://localhost:3004/sign-in` and complete the Clerk dev flow. After success, open `/admin` and confirm the **User** menu appears; use sign-out to verify session clears.
4. **Production-like Basic Auth (optional):** on Vercel Preview, use Basic credentials from the vault and hit `/api/admin/...` with an `Authorization: Basic` header, or use the browser with Basic when not signed in to Clerk.

## When Basic Auth is ready to be removed

1. Confirm all operators use Clerk for day-to-day access and on-call is comfortable without Basic.
2. Remove `ADMIN_EMAILS` / `ADMIN_ACCESS_PASSWORD` from the Studio project environment (and vault references).
3. Simplify `middleware.ts`: delete Basic parsing and the second branch; keep `clerkMiddleware` with `auth.protect()`-style gating (or keep custom redirect only) for `/admin` and `/api/admin`.
4. Update this doc and the sprint/infra inventory to mark Basic Auth as retired.

## Theming

Clerk UI is aligned with Studio’s dark zinc palette via the **Appearance** API ([Clerk docs: `appearance` prop](https://clerk.com/docs/customization/overview#appearance-prop)).

### Where configuration lives

| Piece | Path |
| ----- | ---- |
| Global `appearance` (all Clerk surfaces: SignIn, SignUp, `UserButton`, modals) | `apps/studio/src/lib/studio-clerk-appearance.ts`, passed to `<ClerkProvider>` in `apps/studio/src/app/layout.tsx` |
| Auth route layout (full-viewport gradient shell, centers the form) | `apps/studio/src/components/clerk/ClerkAuthPageShell.tsx`, used by `apps/studio/src/app/sign-in/[[...sign-in]]/page.tsx` and `apps/studio/src/app/sign-up/[[...sign-up]]/page.tsx` |

`baseTheme` is `@clerk/themes`’s `dark` theme; CSS variables and `elements` extend it for Paperwork Studio.

### Studio palette → Clerk variables

Colors resolve at runtime from `[data-theme="studio"]` in `packages/ui/src/themes.css` (also mirrored in `:root` in `apps/studio/src/app/globals.css`). Use the same HSL tokens when adjusting the table below.

| Clerk `appearance.variables` | Studio source (HSL custom property) |
| ---------------------------- | ----------------------------------- |
| `colorPrimary` | `--primary` |
| `colorBackground` | `--background` |
| `colorInputBackground` | `--input` |
| `colorInputText` | `--foreground` |
| `colorText` | `--foreground` |
| `colorTextSecondary` | `--muted-foreground` |
| `colorDanger` | `--destructive` |
| `borderRadius` | `globals.css` `@theme` `--radius` (`0.5rem`) |
| `fontFamily` | `var(--font-inter)` from `next/font` in `layout.tsx` |

Additional card, button, header, and `userButton*` tweaks use `appearance.elements` (Tailwind classes) where variables are not enough — see `studio-clerk-appearance.ts`.

### Per-route overrides (future)

Some products may need a different sign-in shell or extra `appearance` props on `<SignIn />` (e.g. FileFree on its own host). In that case import `studioClerkAppearance` and pass `appearance={{ ...studioClerkAppearance, elements: { ... } }}` to the page-level Clerk component, or build a product-specific object — keep the **provider** in `layout.tsx` as the default so modals and `UserButton` stay consistent unless you intentionally override at the component. Not implemented in Studio today; this is the intended extension point.

## Related

- Sprint: `docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md` (T3)
- Decision log: `docs/KNOWLEDGE.md` (Clerk via Vercel Marketplace)
