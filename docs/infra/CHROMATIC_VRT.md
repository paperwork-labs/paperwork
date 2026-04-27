# Chromatic visual regression

Chromatic is wired into the `apps/design` Storybook canvas. It builds Storybook
on every PR that touches `apps/design/**`, `packages/**/src/**`, or this
workflow itself, publishes the static bundle to Chromatic's CDN, and snapshots
every non-motion story. Visual diffs surface as a GitHub check on the PR; the
founder/designer approves changes which become the new baseline on merge to
`main`.

This is the killer feature that justified migrating from Ladle to Storybook —
catching "did I just break the LaunchFree dark hero?" before brand work ships
across 6 products with theme variants × dark mode × reduced motion.

## Why a merged PR can still show a red Chromatic check

GitHub displays the **last commit** on the PR branch. If that commit’s Chromatic
(or Storybook **build**) run failed or was still pending, the PR row may show a
red **X** even **after squash-merge** to `main`. Confirm **`main`** is green in
Actions; treat the PR list icon as historical unless you are about to merge.

## Prerequisites

The monorepo must include the `apps/design` package with a working
`build-storybook` script (filter name `@paperwork-labs/design` in the root
workspace). **Do not set `CHROMATIC_PROJECT_TOKEN` until that package is on
`main`**, or the Chromatic job will fail at install/build when the secret
enables the workflow. While the token is unset, the job is skipped (no red
checks).

## Founder one-time setup

1. **Create the Chromatic project**
   - Visit <https://www.chromatic.com> → sign in with GitHub
   - Choose the `paperwork-labs/paperwork` repo
   - Project type: Storybook
   - Copy the project token Chromatic shows you on the welcome screen

2. **Add `CHROMATIC_PROJECT_TOKEN` to GitHub Actions secrets**
   - GitHub repo → **Settings** → **Secrets and variables** → **Actions**
   - Click **New repository secret**
   - Name: `CHROMATIC_PROJECT_TOKEN`
   - Value: the token from step 1
   - Save

3. **Update `apps/design/chromatic.config.json`**
   - Replace `Project:<filled-in-after-founder-creates-project>` with the
     actual `projectId` Chromatic shows in your project settings
   - Commit + push the change

4. **Capture the first baseline**
   - Push any change under `apps/design/**` or `packages/**/src/**` to trigger
     the workflow, OR run locally:

     ```bash
     pnpm --filter @paperwork-labs/design chromatic
     ```

   - The first run baselines all 22+ stories (~10 min on a cold runner).
     Subsequent PRs only snapshot stories that changed (TurboSnap).

Until step 2 lands, the workflow's `if: ${{ secrets.CHROMATIC_PROJECT_TOKEN != '' }}`
guard makes the job no-op gracefully — no red checks on PRs, no failed
workflow runs in the Actions tab.

## What's snapshotted

| Story type | Snapshotted? | Why |
| --- | --- | --- |
| Static brand marks (`Brand.stories`) | YES | Deterministic |
| Tokens (color swatches, spacing, typography) | YES | Deterministic |
| Reduced-motion variants | YES | Same as static end-state |
| Dark-surface variants | YES | Deterministic |
| Theme variants (×6 products) | YES | Deterministic |
| Animated entrance (e.g., `ClippedWordmark Animated`) | NO | Pause-at-end-of-animation captures one frame, but the timeline can shift across runs; we explicitly disable to avoid flake |
| Hover micro-interactions (e.g., `HoverWiggle`) | NO | No way to deterministically trigger hover in headless |
| Charts with live data | NO | Data-dependent |

To opt a story out of snapshotting, add the parameter:

```tsx
HoverWiggle.parameters = {
  ...HoverWiggle.parameters,
  chromatic: { disableSnapshot: true },
};
```

The global `chromatic.pauseAnimationAtEnd: true` in the design app’s
`.storybook/preview.tsx` (next to `main.ts` under `apps/design`) makes any
remaining animations land on their final frame deterministically, so most
reduced-motion + animated-end states still get good coverage.

## How to triage Chromatic diffs

When a PR's Chromatic check shows visual changes:

1. Open the Chromatic build URL from the GitHub check details
2. For each diff, click **Approve** or **Deny**
   - **Approve** = "this change is intentional; treat it as the new baseline"
   - **Deny** = "this is a regression; fix it before merging"
3. Approved diffs become the new baseline once the PR merges to `main`
   (`autoAcceptChanges: main` in the workflow config)
4. Denied diffs block the merge until the regression is fixed

A PR can carry both approved and denied diffs. The check is green only when
zero diffs are pending or denied.

## Local workflow

Run Chromatic against your branch from your laptop:

```bash
export CHROMATIC_PROJECT_TOKEN=<token-from-chromatic-dashboard>
pnpm --filter @paperwork-labs/design chromatic
```

This is useful for:

- Sanity-checking diffs before pushing
- Forcing a baseline refresh on a feature branch
- Triaging a flaky story in isolation

## Failure modes

- **`CHROMATIC_PROJECT_TOKEN` missing on a fork PR** — workflow no-ops via
  the `if` guard; not a CI failure.
- **Build OOM on the GitHub runner** — already mitigated by
  `NODE_OPTIONS: --max-old-space-size=4096` at the job level. Bump to `6144`
  if Storybook grows past ~50 stories with heavy MDX.
- **First-run timeout** — Chromatic's first baseline can take 10+ min on
  30+ stories; that's normal. The workflow has no explicit timeout so the
  GitHub default (6 hours) applies; never reached in practice.
- **Flaky animation snapshot** — add `chromatic: { disableSnapshot: true }`
  to the offending story (see [What's snapshotted](#whats-snapshotted)).
- **`Project ID does not match`** — `apps/design/chromatic.config.json` still
  has the placeholder `projectId`; complete founder setup step 3.

## Capacity planning (free tier limits)

Chromatic's free tier ceilings, last verified Apr 2026:

| Limit | Free tier | Headroom for `apps/design` today |
| --- | --- | --- |
| Snapshots per month | 5,000 | 22 stories × ~30 PRs/mo × 1 viewport ≈ 660. Comfortable. |
| Active stories | 250 | We have 22+; ~10× headroom. |
| Concurrent builds | 1 | Fine for a single canvas. |

When the team grows or we add multi-viewport snapshots:

- Each additional viewport multiplies snapshot consumption by ~1×.
- Adding `chromatic: { modes: { mobile: { viewport: 375 } } }` to a story
  doubles its snapshot cost.
- TurboSnap (`onlyChanged: true`) keeps consumption proportional to the
  surface area that actually changed in a PR — keep this on.

If we approach the free-tier ceiling, options are:

1. Tighten `paths:` in the workflow trigger to skip irrelevant package
   changes.
2. Mark more development-iteration stories with `disableSnapshot: true`.
3. Upgrade to Chromatic's paid plan (currently ~$149/mo for 35,000 snapshots).

## Related docs

- `.storybook/preview.tsx` in the `apps/design` package — global `chromatic` parameters
- `apps/design/chromatic.config.json` — project + build config
- `.github/workflows/chromatic.yaml` — CI integration
