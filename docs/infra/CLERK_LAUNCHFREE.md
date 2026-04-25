# Clerk SSO — LaunchFree (Next.js)

Runbook for the LaunchFree app (`apps/launchfree`) identity stack: Clerk (primary SSO) with the legacy `session` cookie on `/dashboard`, plus Basic Auth as an operator escape hatch on `/admin` and `/api/admin` in production until removed by an explicit follow-up.

## Environment variables (standard names)

| Variable | Where used | Source |
| -------- | ------------ | ------ |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Client + server bootstrap | [Vercel Marketplace — Clerk](https://vercel.com/integrations) on the linked LaunchFree project; copy locally from the vault for dev |
| `CLERK_SECRET_KEY` | Server (session verification, middleware) | Same as above |

**Custom prefix** is not used — do not add an `LAUNCHFREE_` or other prefix to these names in Vercel or `.env`.

Optional Clerk URLs (redirects) follow [Clerk environment variable docs](https://clerk.com/docs/guides/development/clerk-environment-variables) if dashboard defaults are insufficient.

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

## Related

- Studio runbook: `docs/infra/CLERK_STUDIO.md`
- Sprint: `docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md`
