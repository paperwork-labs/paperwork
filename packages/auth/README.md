# `@paperwork-labs/auth-clerk`

Shared Clerk UI and identity helpers for the Paperwork Labs monorepo: **SignInShell** and **SignUpShell** (app-name–primary wordmark, “by Paperwork Labs” attribution), **createClerkAppearance** and appearance presets, session/admin utilities, and JWT verification for backends.

## Quickstart

```tsx
import { SignIn } from "@clerk/nextjs";
import { SignInShell } from "@paperwork-labs/auth-clerk/components/sign-in-shell";
import { fileFreeAppearance } from "@paperwork-labs/auth-clerk/appearance/presets";

export default function SignInPage() {
  return (
    <SignInShell
      appName="FileFree"
      appWordmark={<YourLockupOrWordmark />}
      appTagline="Free tax filing"
      appearance={fileFreeAppearance}
    >
      <SignIn />
    </SignInShell>
  );
}
```

Use **SignUpShell** the same way for `/sign-up` routes. Pass `appSlug` when it differs from `appName` normalization (e.g. AxiomFolio → `axiomfolio`). For the accounts host, set `isPrimaryHost` so the headline reads “Paperwork ID.” Use `variant="admin"` for Studio (hides the cross-product explainer).

## Exports

| Subpath | Purpose |
| --- | --- |
| `@paperwork-labs/auth-clerk` | Shells, RequireAuth, hooks, `PAPERWORK_PRODUCTS`, `verifyClerkJwt`, appearance types |
| `@paperwork-labs/auth-clerk/products` | Sibling-product registry + explainer helpers |
| `@paperwork-labs/auth-clerk/components/sign-in-shell` | `SignInShell` |
| `@paperwork-labs/auth-clerk/components/sign-up-shell` | `SignUpShell` |
| `@paperwork-labs/auth-clerk/appearance` | `createClerkAppearance` |
| `@paperwork-labs/auth-clerk/appearance/presets` | Per-app appearance presets |
| `@paperwork-labs/auth-clerk/server/verify-clerk-jwt` | Node JWT verification |

See `package.json` `exports` for the full list.

## Brand

Use the **canonical product tagline** from [brand.mdc](../../.cursor/rules/brand.mdc) (and shorter sign-in lines where noted) for each app’s `appTagline` — do not ship placeholder or wrong-vertical copy on Clerk sign-in pages.

## Related docs

- [Clerk satellite topology](../../docs/infra/CLERK_SATELLITE_TOPOLOGY.md) — custom domains, primary vs satellite apps
- SSO / customer unification (Q2): `sso_customer_unification_2026q2_3d1a572e.plan.md` in your local Cursor plans directory, e.g. `/Users/paperworklabs/.cursor/plans/sso_customer_unification_2026q2_3d1a572e.plan.md`
