---
title: Design Canvas (Storybook) deploy
last_reviewed: 2026-04-26
owner: infra-ops
status: draft
domain: infra
doc_kind: runbook
summary: "Founder + engineering runbook for shipping apps/design (Storybook 10) to design.paperworklabs.com via the existing Vercel auto-promote workflow."
tags: [vercel, dns, storybook, design, brand]
---

# Design Canvas (Storybook) deploy

This runbook covers the **one-time founder actions** needed to wire
`apps/design` (the Paperwork Labs Storybook canvas) to its production
host `design.paperworklabs.com`, plus the engineering pieces that ship
with this PR.

The actual auto-promotion logic is shared with every other Paperwork
Labs Vercel app — see `docs/infra/VERCEL_AUTO_PROMOTE.md`. This doc only
covers the **design-canvas-specific** founder steps.

## What ships in code (already merged with this PR)

1. Matrix entry `project: design` in
   `.github/workflows/vercel-promote-on-merge.yaml` with placeholder
   `project_id: TBD_CREATE_BEFORE_MERGE`. The job **skips cleanly**
   while the placeholder is in place — no failed runs, no production
   impact.
2. `apps/design/vercel.json` — Storybook 10 build config (corepack +
   pnpm filter install, `pnpm --filter @paperwork-labs/design
   build-storybook`, `outputDirectory: storybook-static`).
3. `apps/design/README.md` — local dev + story-glob reference.
4. Tracked-apps row added to `docs/infra/VERCEL_AUTO_PROMOTE.md`.

## Founder one-time setup

### 1. Create the Vercel project

1. Vercel Dashboard → **Add New** → **Project**.
2. Import the `paperwork-labs/paperwork` repo (already linked at the
   team level — `team_RwfzJ9ySyLuVcoWdKJfXC7h5`).
3. **Project name:** `design` (matches the matrix `project` slug, so
   the auto-promote URL `https://vercel.com/paperwork-labs/design/...`
   resolves correctly).
4. **Root directory:** `apps/design`.
5. **Framework preset:** **Other**. Build command, install command,
   and output directory are all auto-detected from `apps/design/vercel.json`
   — leave the dashboard fields blank so the file is the source of
   truth.
6. **Production branch:** `main`.

### 2. Replace the workflow placeholder with the real project ID

Once Vercel issues the project ID:

1. Vercel Dashboard → Project → **Settings** → **General** → copy
   `Project ID` (format: `prj_…`).
2. Open `.github/workflows/vercel-promote-on-merge.yaml`, find:

   ```yaml
   - project: design
     project_id: TBD_CREATE_BEFORE_MERGE
   ```

   Replace `TBD_CREATE_BEFORE_MERGE` with the real `prj_…` id and merge
   that change. The matrix follows the same convention as every other
   app (no GitHub secret — IDs are not sensitive, only the
   `VERCEL_API_TOKEN` is).
3. Update the same row in `docs/infra/VERCEL_AUTO_PROMOTE.md`.

### 3. Add the custom domain

1. Vercel project → **Domains** → **Add** → `design.paperworklabs.com`.
2. Vercel will display the **exact** DNS record to add (target host
   may vary — copy it from the dashboard, do **not** copy from this
   doc).
3. Add the record at the registrar (Cloudflare for
   `paperworklabs.com`):

   | Type | Name | Value | TTL | Proxy |
   | --- | --- | --- | --- | --- |
   | `CNAME` | `design` | *(value Vercel shows — typically `cname.vercel-dns.com`)* | Auto | **DNS only** (orange cloud OFF) |

   Cloudflare proxy must be **off** for Vercel to issue a TLS cert.
4. Wait for Vercel to mark the domain **Verified** + the cert to
   issue (usually < 5 minutes).

### 4. (Optional) Enable PR preview deploys

The `vercel-promote-on-merge.yaml` workflow only handles **production
promotion on merge to `main`**. For per-PR preview URLs (every brand
PR gets a preview link), Vercel’s **GitHub integration** must be
enabled on the project.

1. Vercel project → **Settings** → **Git** → **Connected Git
   Repository**: confirm the repo is linked.
2. **Settings** → **Git** → **Deploy Hooks** / **Ignored Build Step**:
   leave defaults; the `ignoreCommand` in `apps/design/vercel.json`
   skips Dependabot-only commits.
3. **Settings** → **Environments** → confirm Preview environment is
   on.

After this, every PR that touches `apps/design/**` or `packages/**`
will get an automatic preview comment from the Vercel GitHub App with
a hosted Storybook URL.

### 5. Trigger the first production deploy

Push any change that touches `apps/design/**` or `packages/**` to
`main`. The auto-promote workflow will run, find the READY preview,
and flip production. Manual fallback:

```bash
gh workflow run vercel-promote-on-merge.yaml -f pr_number=<pr>
```

(Manual dispatch runs every matrix job; the design row is the only one
that will act on a `apps/design`-only PR.)

## What gets deployed

- Storybook 10 static build of every story under
  - `apps/design/src/stories/**/*.stories.tsx`
  - `packages/**/src/**/*.stories.tsx`
- Re-deploy triggers on every merge to `main` that touches
  `apps/design/**`, `packages/**`, `pnpm-lock.yaml`, or root
  `package.json` (path filter shared with the rest of the Vercel
  matrix — see `VERCEL_AUTO_PROMOTE.md` § Monorepo path filters).

## Failure modes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Workflow logs `Vercel project for design not yet created. Skipping promote.` | `project_id: TBD_CREATE_BEFORE_MERGE` placeholder still in the matrix. | Founder step 2 above — replace with real `prj_…` and merge. |
| Workflow logs `VERCEL_API_TOKEN secret is not set — skipping promote.` | Repo-wide `VERCEL_API_TOKEN` missing. | `gh secret set VERCEL_API_TOKEN` (one secret covers all matrix rows; see `VERCEL_AUTO_PROMOTE.md` §1-time setup). |
| `No preview found for design — Vercel skipped this build` | Vercel did not start a build for the merge commit (path filter, ignoreCommand, Hobby rate limit, or Vercel project not yet created). | Check Vercel dashboard for the SHA. If missing, run `vercel deploy --prod` from `apps/design` or merge a change under paths the design Vercel project includes (see `VERCEL_AUTO_PROMOTE.md` § Monorepo path filters). |
| Storybook build fails after dependency bump | Transitive breakage or Vite/Storybook mismatch. | Pin versions in `apps/design/package.json`; confirm `pnpm --filter @paperwork-labs/design build-storybook` locally; see Chromatic + CI logs. |
| DNS still pending after 1h | Cloudflare proxy still on, or TLD slow to propagate. | Confirm orange cloud is **off**; wait up to 24h on rare TLDs (this one is `.com`, should be < 30 min). |
| Vercel Hobby `Deployment rate limited — retry in 24 hours` on commit | Multiple matrix projects all building from the same merge commit. | Wait. The promote workflow is idempotent and will pick up the build when it lands. See `VERCEL_AUTO_PROMOTE.md` § Cost. |

## Why this lives outside the brand stack

The design canvas is **infrastructure for engineers and brand
contributors**, not a customer surface. It is therefore:

- **Not** a Clerk satellite (no auth — see
  `docs/infra/CLERK_SATELLITE_TOPOLOGY.md` for the apps that are).
- **Not** part of the apex `paperworklabs.com` cookie group; it lives
  on its own subdomain so a Storybook crash or asset 404 cannot bleed
  into Studio.
- **Not** in the Vercel project path filter for monorepo rebuilds of
  the customer apps — `apps/design/**` only triggers `design`.

## See also

- `.github/workflows/vercel-promote-on-merge.yaml` — the workflow.
- `docs/infra/VERCEL_AUTO_PROMOTE.md` — shared auto-promote runbook.
- `apps/design/vercel.json` — Storybook 10 build config.
- `apps/design/README.md` — local dev + story-glob reference.
- `docs/brand/PROMPTS.md` — brand prompt canon (rendered in stories).
