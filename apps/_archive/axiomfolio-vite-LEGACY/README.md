# AxiomFolio Vite — LEGACY ARCHIVE

**Status**: archived 2026-04-27. Do not modify.

## What this is

The original Vite + React build of AxiomFolio, frozen at the moment of cutover to the Next.js App Router port. The active app now lives at `../../axiomfolio/` (which was previously `apps/axiomfolio-next/`).

## Why we kept it

1. **Migration safety net** — the Next.js port passes all tests, but archive lets us spot-check feature parity if a regression is reported.
2. **Git history** — preserved without `git filter-repo` or destructive rewrites.
3. **Decommission delay** — Render legacy static site for the Vite app may still be running; archive lets us reproduce a build if needed.

## When to delete

- **Earliest**: after 1 production cycle (~30 days) on the Next.js port with no regressions reported.
- **Trigger**: founder approval + Render Vite static service decommissioned.
- **Tracking**: see `docs/axiomfolio/plans/PORT_INVENTORY_2026Q2.md`.

## Build/run instructions (legacy)

Original `package.json` scripts work in isolation but are **not** wired into the monorepo turbo pipeline; `pnpm` workspace globs in root `pnpm-workspace.yaml` exclude `apps/_archive/**`. From this directory, install dependencies per the monorepo root (or a standalone copy) and run the Vite scripts defined in `package.json`.
