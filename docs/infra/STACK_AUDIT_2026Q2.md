# Stack audit — 2026 Q2 (WS-73 Batch B)

Snapshot date: **2026-04-30**. Sources: root `package.json` engines, workspace `package.json` files, `pnpm-lock.yaml` resolution hints (`pnpm outdated -r`), `npm view` / registry metadata, `apis/brain/requirements.txt` + `uv pip compile`, PyPI JSON for `openai`, `render.yaml` + `apis/brain/Dockerfile` for runtime Python.

## Executive summary

The monorepo is on **Node ≥20.9**, **Next.js 16.2.x**, **React 19.2.x**, and **pnpm 10.33.x**. TypeScript is mostly **5.9.x resolved** from `^5.6.0` pins; **`apps/design`** intentionally pins **TypeScript ^6.0.3** for Storybook/Vite. **Zod** is split: several apps/packages use **v4** (`@paperwork-labs/data`, filing-engine, launchfree); **studio** and **filefree** stay on **v3** (latest v3 line is **3.25.76**). **Sentry** is only wired in **filefree** (`@sentry/nextjs`). **Brain** ships on **Python 3.11.9** in Docker; `openai` resolves to **2.33.0** under current lower bounds (already latest on PyPI).

**This PR (WS-76 PR-12)** applies **patch/minor** JS bumps only (Clerk, TanStack Query, lucide-react, PostHog, AI SDK, Storybook addons, typescript-eslint, Sentry, zod v4 apps). **Deferred:** TypeScript 6 monorepo rollout, Zod v3→v4 migration for remaining apps, `jose` 5→6, major Storybook/Vite stack jumps where outdated shows major gaps.

## Current vs latest (key dependencies)

| Dependency | Where / how pinned | Current (typical) | Registry “latest” (check date) | Risk if jumping | Recommendation |
|------------|-------------------|-------------------|-------------------------------|-----------------|----------------|
| **Node.js** | Root `engines.node` `>=20.9.0`; per-app engines match; **no `.nvmrc`** | ≥20.9 | 22.x LTS / 24.x current | Low for patch; CI/runtime must match | **Keep** floor; add `.nvmrc` optional follow-up for local DX |
| **pnpm** | Root `packageManager` | 10.33.2 | 10.x evolves | Low patch | **Keep**; bump with toolchain PRs |
| **TypeScript** | Most packages `^5.6.0` → lock **5.9.3**; design `^6.0.3` | 5.9.3 / 6.0.x | **6.0.3** | **High** for 5→6 (compiler + `@types` ripple) | **Defer** repo-wide TS 6; design already on 6 |
| **Next.js** | Apps `^16.2.4` | 16.2.4 | 16.2.4 | Low at patch | **Safe** patch bumps when released |
| **React / react-dom** | `^19.2.5` | 19.2.5 | 19.2.5 | Low patch | **Safe** patches |
| **@sentry/nextjs** | filefree only `^10.50.0` | 10.50.0 | 10.51.0 | Low minor | **Upgrade** minor (this PR) |
| **zod** | v4: data/filing-engine/launchfree `^4.3.6`; v3: studio `^3.25.76`, filefree `^3.24.2` | 4.3.6 / 3.24.x | 4.4.1 / 3.25.76 | v4 minor: low–medium; v3→v4: **major** migration | **Bump** v4 to **4.4.x**; align filefree v3 to **3.25.76** (this PR) |
| **OpenAI (Python)** | `apis/brain/requirements.txt` `openai>=1.57.0` | Resolved **2.33.0** | **2.33.0** | Lower bound already satisfied | **No change**; optional doc-only tighten to `>=2.33.0` later |
| **Python** | Brain Dockerfile `python:3.11.9-slim`; filefree Render `PYTHON_VERSION` **3.11.0** | 3.11.x | 3.13+ | Medium (deps + images) | **Defer** 3.12+ until scheduled infra pass; note mypy `python_version = "3.13"` is check-only |

## Risk assessment (upgrade themes)

1. **TypeScript 5 → 6** — Breaking typing changes and stricter defaults possible; must be coordinated with ESLint flat config, Storybook, and all `tsc` pipelines. **Effort:** high. **Defer.**

2. **Zod v3 vs v4** — Two major lines coexist; unifying requires code changes in studio/filefree consumers. **Effort:** medium–high. **Defer** unification; minor bumps within each line are fine.

3. **@clerk/nextjs** — Patch/minor releases are usually safe; watch release notes for middleware and `auth()` signatures. **Effort:** low. **Safe now.**

4. **lucide-react** — Minor releases add/rename icons occasionally; rare breaks. **Effort:** low. **Safe now** (CI build validates imports).

5. **AI SDK (`ai`, `@ai-sdk/*`)** — Minor bumps can change streaming/types; filefree is the consumer. **Effort:** low–medium. **Safe** with full `turbo build`.

6. **`jose` 5 → 6** (auth-clerk) — Major; JWT API shifts. **Defer.**

7. **Python Brain** — `requirements.txt` uses wide `>=`; production resolves current stack. Bumping floors without lockfile can surprise deploys; prefer dedicated PR with `pip-compile` + pytest. **No change this PR.**

## Recommended upgrade order (future quarters)

1. Patch/minor npm bumps with full `pnpm install` + `turbo run build` (this PR pattern).
2. Optional `.nvmrc` pinned to CI Node (e.g. 22.x) + docs.
3. Scheduled **TypeScript 6** migration starting with shared packages, then Next apps, design already aligned.
4. **Zod v4** migration for studio/filefree behind a single initiative + tests.
5. **Python 3.12+** for Brain/filefree with image + Render matrix update + pytest/mypy pass.

## Safe now vs defer

| Action | Verdict |
|--------|---------|
| Clerk, TanStack Query, PostHog-js, Sentry, typescript-eslint, Storybook 10.3.x patches | **Safe now** |
| zod **4.3.x → 4.4.x** on v4 consumers | **Safe now** |
| zod **3.24.x → 3.25.76** on filefree | **Safe now** |
| AI SDK patch bumps (filefree) | **Safe now** with CI |
| TypeScript 6 everywhere | **Defer** |
| Next/React major | **Defer** (not applicable — already latest minors) |
| `jose` 6 | **Defer** |
| Python runtime / openai floor tighten | **Defer** (document only) |

## Changes applied in WS-76 PR-12

- Minor/patch version range bumps as committed in workspace `package.json` files and refreshed `pnpm-lock.yaml`.
- No Python source or `requirements.txt` edits (Brain tests unchanged).

## Verification commands

```bash
pnpm install
npx turbo run build
cd apis/brain && uv run pytest --tb=short -q   # when Python deps change
```
