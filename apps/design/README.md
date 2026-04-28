# `@paperwork-labs/design`

Storybook 10 home for the Paperwork Labs design canvas. Hosts:

- **Brand canon** — the parent Paperwork Labs wordmark stories live next to the
  component (`packages/ui/src/components/brand/`) and are auto-collected by the
  `packages/**/src/**/*.stories.*` glob in `.storybook/main.ts`.
- **AxiomFolio design system** — tokens, typography, motion, microinteractions,
  charts, tables, layout, etc. Sourced from `apps/axiomfolio/src/stories` via
  the `@axiomfolio/*` Vite alias until each set of stories migrates into its
  owning package.

This workspace is independent of any one product app. Vercel deploys it to
`design.paperworklabs.com` so designers, contractors, and Chromatic visual
regression all hit one URL.

## Hosted

https://design.paperworklabs.com — auto-deployed on every merge to `main` that touches `apps/design/**` or `packages/**`.

## Scripts

```bash
# Local dev server on http://localhost:6006
pnpm --filter @paperwork-labs/design storybook

# Static build for Vercel / Chromatic
pnpm --filter @paperwork-labs/design build-storybook

# Typecheck
pnpm --filter @paperwork-labs/design type-check

# Lint
pnpm --filter @paperwork-labs/design lint
```

## How stories are discovered

`.storybook/main.ts` globs:

- `apps/design/src/**/*.stories.@(js|jsx|mjs|ts|tsx)` — workspace-local stories
  (helpers + cross-app stories that have moved here permanently).
- `apps/design/src/**/*.mdx` — long-form design docs.
- `packages/**/src/**/*.stories.*` — every shared package can ship its own
  stories alongside its components, no central registry needed.

## Migrating a story into its owning package

1. Move `*.stories.tsx` next to the component inside its package.
2. Update the import paths to be package-relative.
3. Drop the `@axiomfolio/*` alias dependency.

The canvas glob picks the file up automatically on next reload.

## Migration history

Migrated from Ladle on 2026-04-26 (founder-approved). Ladle config + axiomfolio
copies of the stories are temporarily kept under `apps/axiomfolio/.ladle/` and
`apps/axiomfolio/src/stories/` while Agent D decommissions them in a follow-up
PR.

## Contributing

- See `docs/brand/CANON.md` and `docs/brand/README.md` for brand canon.
- See `docs/infra/DESIGN_CANVAS_DEPLOY.md` for the deployment runbook (founder one-time Vercel setup, DNS record, GitHub Action behavior).
