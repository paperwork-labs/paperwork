# Design canvas — Vercel + Chromatic

This document is the **founder runbook** for shipping the shared Storybook at `design.paperworklabs.com`. Code for the canvas lives in `apps/design/`; component stories live under `packages/ui/src/**` next to components.

## 1. Vercel project

1. In the Vercel dashboard, **Add New Project** and import the GitHub repo.
2. **Root directory:** leave as monorepo root (repo root), not `apps/design`, so `pnpm` can resolve `workspace:*` and `packages/ui`.
3. Configure from `apps/design/vercel.json` (or paste equivalent in the UI):
   - **Install command:** `pnpm install --filter @paperwork-labs/design...`
   - **Build command:** `pnpm --filter @paperwork-labs/design build-storybook`
   - **Output directory:** `apps/design/storybook-static` (or `storybook-static` if the UI is relative to an overridden root — match where the static build is emitted; default is `apps/design/storybook-static` when project root is the repo).
4. **Environment variables:** none required for a static Storybook build unless you add runtime env later.

If Vercel’s project root is set to **`apps/design`** instead of the repo root, adjust paths: run install from the monorepo root via a root `vercel.json` or use Vercel’s monorepo settings so dependencies still install correctly. The reliable pattern for this repo is **project root = repository root** and commands that use `pnpm --filter @paperwork-labs/design`.

## 2. Custom domain (`design.paperworklabs.com`)

1. In the Vercel project → **Settings → Domains**, add `design.paperworklabs.com`.
2. Add the DNS records Vercel shows (typically `CNAME` to `cname.vercel-dns.com` or A records for apex, depending on DNS host).
3. Wait for verification and HTTPS provisioning.

## 3. Chromatic (`CHROMATIC_PROJECT_TOKEN`)

1. Create a project at [chromatic.com](https://www.chromatic.com/) linked to this GitHub repo (or link the repo from Chromatic’s UI).
2. Copy the **project token** (used by the CLI and GitHub Action).
3. In GitHub: **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `CHROMATIC_PROJECT_TOKEN`
   - Value: paste the token from Chromatic.
4. Optional: copy **Project ID** into `apps/design/chromatic.config.json` (`projectId` field) for local `pnpm chromatic` runs; CI primarily uses the token.

Workflow: `.github/workflows/chromatic.yaml` builds Storybook from `apps/design` and runs `chromaui/action@v11` on pushes to `main` and on pull requests (path-filtered).

## 4. First deploy checklist

- [ ] Vercel project builds successfully from `main` (preview).
- [ ] Domain `design.paperworklabs.com` resolves and serves the Storybook static build.
- [ ] `CHROMATIC_PROJECT_TOKEN` is set; Chromatic workflow run on `main` completes (or fails clearly if paths change).
- [ ] Auto-promote: after the Vercel **project id** exists, add it to `.github/workflows/vercel-promote-on-merge.yaml` under `matrix.include` for `project: design` (replace `TBD_CREATE_BEFORE_MERGE`).

## 5. Mapping file

`scripts/vercel-projects.json` lists the design app path and intended domain for tooling and agents (see file for current values).
