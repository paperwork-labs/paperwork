PR Automation
=============

Goals
-----
- Dependabot PRs should auto-merge after required checks pass (non-major updates).
- Human/agent changes should *never* be pushed directly to `main`; they should land via PRs.

Dependabot
----------
- Config: `.github/dependabot.yml`
- Auto-merge workflow: `.github/workflows/dependabot-automerge.yml`
  - Only runs for `dependabot[bot]`
  - Skips semver-major updates by default
  - Merges semver minor/patch updates after required checks are green (does not rely on repo auto-merge being enabled)

Agent / Human PR flow
---------------------

Recommended workflow for an agent change-set:
- Make changes locally
- Run checks:
  - `./run.sh test`
  - `cd frontend && npm test` (if frontend changed)
- Create a PR automatically:
  - `scripts/open_pr.sh fix "short description"`
    - Creates an `agent/<type>/...` branch
    - Commits and pushes
    - Opens a **Draft** PR with the standard PR template
    - Guardrail: refuses to start a new PR if you are currently on an `agent/**` branch whose PR is not merged

Automatic PR opening (on push)
------------------------------
- Workflow: `.github/workflows/agent-auto-pr.yml`
  - Any push to a branch named `agent/**` will auto-open a **Draft** PR to `main` (if one doesn’t already exist).
  - Useful as a safety net if a branch is pushed without using `scripts/open_pr.sh`.
  - CI should appear reliably because `CI` runs on push for `agent/**` branches; we avoid auto-dispatching `workflow_dispatch` runs that can cancel push runs due to concurrency.

Automatic squash-merge after approval (agent branches only)
----------------------------------------------------------
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

Dependabot
----------
- Workflow: `.github/workflows/dependabot-automerge.yml`
  - Prefer repo auto-merge (merge-queue friendly) when enabled.
  - If repo auto-merge is disabled, fallback to polling required checks + direct merge.

Requirements for automation
---------------------------
- GitHub CLI (`gh`) must be available
- The environment must be authenticated to GitHub:
  - either via `gh auth login`
  - or by providing `GH_TOKEN` (fine-grained PAT or GitHub App token) with:
    - `contents:write`
    - `pull_requests:write`

Branch protection (recommended)
-------------------------------
In GitHub repo settings:
- Protect `main`
- Require PRs for merges
- Require status checks:
  - `CI / Backend (pytest in docker)`
  - `CI / Frontend (lint/typecheck/test)`
- Restrict who can push to `main` (ideally: nobody)


