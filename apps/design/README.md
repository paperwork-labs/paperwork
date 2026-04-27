# @paperwork-labs/design

Storybook 8 design canvas for shared UI (`@paperwork-labs/ui`) and brand components.

## Commands

| Script | Description |
| --- | --- |
| `pnpm storybook` | Dev server on port 6006 |
| `pnpm build-storybook` | Static build to `storybook-static/` |
| `pnpm chromatic` | Publish to Chromatic (requires `CHROMATIC_PROJECT_TOKEN`) |

## Stories

Stories live next to components under `packages/ui/src` (and optional MDX under `apps/design/src`). This package only hosts Storybook configuration and the intro canvas — not the components themselves.

## Deploy

Vercel and custom domain `design.paperworklabs.com` are documented in `docs/infra/DESIGN_CANVAS_DEPLOY.md` (founder setup; not automated in a single PR).
