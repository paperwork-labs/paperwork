# @paperwork-labs/design

The Paperwork Labs design system canvas — all stories from `packages/ui` and the brand component library, rendered in Storybook 8.

## Hosted

https://design.paperworklabs.com — auto-deployed on every merge to `main` that touches `apps/design/**` or `packages/**`.

## Local dev

```bash
pnpm --filter @paperwork-labs/design storybook
# opens http://localhost:6006
```

## Build

```bash
pnpm --filter @paperwork-labs/design build-storybook
# outputs apps/design/storybook-static/
```

## Adding stories

Stories live in two places:

- `apps/design/src/stories/**/*.stories.tsx` — design-system-only stories (tokens, motion, microinteractions, etc.).
- `packages/*/src/**/*.stories.tsx` — co-located with components.

Both globs are auto-picked-up by `apps/design/.storybook/main.ts`.

## Contributing

- See `docs/brand/PROMPTS.md` and `docs/brand/README.md` for brand canon.
- See `docs/infra/DESIGN_CANVAS_DEPLOY.md` for the deployment runbook (founder one-time Vercel setup, DNS record, GitHub Action behavior).
