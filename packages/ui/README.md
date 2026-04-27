# @paperwork-labs/ui

Shared design system primitives for Paperwork apps: Radix-based components, tokens, and utilities. It is **framework-agnostic** so the same package can be used from Next.js, Vite, Storybook, and other React surfaces without pulling in one host framework’s runtime.

## Hard rules (why)

| Ban | Rationale |
|-----|-----------|
| **`next/*`, `next`, `next-auth*`** | Routing, auth, and server APIs are host concerns; the design system must not depend on Next.js entrypoints. |
| **`vite`, `@vercel/*`, `node:*`, `fs`, `path`, `child_process`** | Tooling and Node built-ins are not browser-portable; keeps the package usable in SSR, static Storybook, and non-Node bundlers. |
| **`react-router*`, `@remix-run/*`** | Not all consumers use the same router; navigation primitives live in the app. |
| **Direct `process.env` reads** | Env is compile-time/host-specific; inject values via **props** or **React context** from the app (or a thin wrapper). |
| **Unguarded `window` / `window[...]`** | SSR and tests may not define `window`; guard with `typeof window !== "undefined"`, use `globalThis`, or pass browser-only values from the host. Optional: a typed `useIsomorphicLayoutEffect` in the app. |
| **`"use server"` and `export async function` exports** | Server Actions / RSC-style async exports do not belong in shared UI; keep this tree **client / pure React**. |

**Allowed:** `react`, `react-dom`, styling helpers (`clsx`, `tailwind-merge`, `class-variance-authority`), icons (`lucide-react`), motion (`framer-motion`), headless primitives (e.g. Radix), **`next-themes`** (peer; not the same as `next/*`), and other libraries that work across bundlers.

## How to add a feature that needs Next.js

1. **Define the contract in `@paperwork-labs/ui`** — props, context types, or headless behavior with no Next imports.
2. **Implement the Next-specific glue in the app** — e.g. a wrapper under `apps/<name>/src/components/` that imports `next/link`, `next/navigation`, or server helpers and passes URLs, router callbacks, or data into UI primitives.
3. **Do not** move Next-only logic into this package to “save a file”; that couples every consumer to Next.

Example: theme for toasts — the `Toaster` may read `useTheme()` from `next-themes` (peer); the app must still provide `ThemeProvider` from the host. For flags like analytics or base URLs, pass them in as props instead of reading `process.env` here.

## Enforcement

1. **ESLint** — [`eslint.config.mjs`](./eslint.config.mjs) (`pnpm --filter @paperwork-labs/ui lint`).
2. **CI** — [`scripts/check-ui-package-purity.mjs`](../../scripts/check-ui-package-purity.mjs) (line-based audit; no opt-out).
3. **Code review** — catch dynamic imports and patterns automations miss.

## Peer dependencies

`react` and `react-dom` are **peer** dependencies; the host provides them. `next-themes` is a **peer** for theme-aware components (e.g. toasts) and is not a `next/*` import.

## Known violations

None. If a legacy file must temporarily violate a rule, add a **file-scoped ESLint override** (`warn` only for that path), fix or track removal, and list the path here with a TODO/issue link.

