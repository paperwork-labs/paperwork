# PR Automation

## Table of contents

- [Goals](#goals)
- [Dependabot](#dependabot)
- [Agent / Human PR flow](#agent--human-pr-flow)
  - [End-to-end automated loop](#end-to-end-automated-loop)
- [Automatic PR opening](#automatic-pr-opening-on-push)
- [Automatic squash-merge](#automatic-squash-merge-after-approval-agent-branches-only)

---

## Goals
- Dependabot PRs should auto-merge after required checks pass (non-major updates).
- Human/agent changes should *never* be pushed directly to `main`; they should land via PRs.

## Dependabot

- Config: `.github/dependabot.yml`
- Auto-merge workflow: `.github/workflows/dependabot-automerge.yml`
  - Only runs for `dependabot[bot]`
  - Skips semver-major updates by default
  - Merges semver minor/patch updates after required checks are green (does not rely on repo auto-merge being enabled)

## Agent / Human PR flow

### End-to-end automated loop

Aim for a **fully automated loop** so that by the time you open the PR, tests have already passed locally, and after opening you verify CI, fix any failures, address review (e.g. Copilot) comments, and only then wait for approval.

1. **Before opening the PR**
   - Make changes locally.
   - **Run all checks** from repo root using the **Makefile** (see [docs/README.md](README.md)#makefile-quick-reference) and fix until they pass:
     - Backend: `make test`
     - Frontend (if touched): `make test-frontend` (or `make frontend-check` for lint + type-check + test)
     - Both: `make test-all`
   - **Update PR description** (title + body) so the template is filled and the change is clear. If using `scripts/open_pr.sh`, the script creates a Draft PR with the standard template; you can then edit the description in the UI or via `gh pr edit`.
   - Create the PR (e.g. `scripts/open_pr.sh fix "short description"`), which creates an `agent/<type>/...` branch, commits, pushes, and opens a **Draft** PR.
   - **Guardrail**: The script refuses to start a new PR if you are already on an `agent/**` branch whose PR is not merged.

2. **After opening the PR**
   - **Check that CI actually passes** on the PR (Backend + Frontend jobs). If anything fails:
     - Fix the code or tests locally.
     - Re-run the same checks (`make test`, `make test-frontend`, or `make test-all`) until they pass.
     - Push another commit; CI will re-run.
   - **Read review comments** (e.g. GitHub Copilot, or human reviewers). Reply where needed and **fix code** (and tests) for any requested changes.
   - Re-run tests locally after each fix, then push. Repeat until **tests pass and you’re happy with the diff**.

3. **Ready for review**
   - Mark the PR as **Ready for review** (remove Draft).
   - **Wait for approval.** Once approved and CI is green, the merge-after-approval workflow can squash-merge (see [Automatic squash-merge](#automatic-squash-merge-after-approval-agent-branches-only)).

In short: **run tests → fix until green → open PR → confirm CI passes → fix tests if needed → address Copilot/review comments → fix code & tests → tests pass → wait for approval.**

## Automatic PR opening (on push)
- Workflow: `.github/workflows/agent-auto-pr.yml`
  - Any push to a branch named `agent/**` will auto-open a **Draft** PR to `main` (if one doesn’t already exist).
  - Useful as a safety net if a branch is pushed without using `scripts/open_pr.sh`.
  - CI should appear reliably because `CI` runs on push for `agent/**` branches; we avoid auto-dispatching `workflow_dispatch` runs that can cancel push runs due to concurrency.

## Automatic squash-merge after approval (agent branches only)
- Workflow: `.github/workflows/agent-merge-after-ci.yml`
  - Triggers after `CI` completes successfully **or** when an approval review is submitted
  - Only considers `agent/**` branches
  - Requires:
    - PR is **not** Draft (must be marked Ready for review)
    - PR is approved by **sankalp404**
    - The successful CI run corresponds to the current PR head SHA
  - Action: squash merge + delete branch
  - Note: this workflow merges only when GitHub reports the PR is mergeable (`mergeStateStatus=CLEAN`);
    it does **not** rely on GitHub's repository-level "auto-merge" feature being enabled.

### Dependabot (merge behavior)

- Workflow: `.github/workflows/dependabot-automerge.yml`
  - Prefer repo auto-merge (merge-queue friendly) when enabled.
  - If repo auto-merge is disabled, fallback to polling required checks + direct merge.

## Requirements for automation

- GitHub CLI (`gh`) must be available
- The environment must be authenticated to GitHub:
  - either via `gh auth login`
  - or by providing `GH_TOKEN` (fine-grained PAT or GitHub App token) with:
    - `contents:write`
    - `pull_requests:write`

## Branch protection (recommended)

In GitHub repo settings:
- Protect `main`
- Require PRs for merges
- Require status checks:
  - `CI / Backend (pytest in docker)`
  - `CI / Frontend (lint/typecheck/test)`
- Restrict who can push to `main` (ideally: nobody)


