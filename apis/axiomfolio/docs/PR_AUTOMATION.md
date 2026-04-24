# PR automation

How this repo opens PRs, runs CI, merges **Dependabot** updates, and (for `agent/**` branches) auto-merge after approval. Use this as the operator playbook for “branch → PR → review → green → merge”.

## Table of contents

- [Goals](#goals)
- [Lanes: `agent/**` vs everything else](#lanes-agent-vs-everything-else)
- [CI (when checks run)](#ci-when-checks-run)
- [Scripts](#scripts)
- [GitHub workflows (inventory)](#github-workflows-inventory)
  - [Request Copilot review (automation)](#request-copilot-review-automation)
- [End-to-end operator loop](#end-to-end-operator-loop)
- [Dependabot: auto-merge and how to help](#dependabot-auto-merge-and-how-to-help)
- [Agent PRs: squash-merge after approval](#agent-prs-squash-merge-after-approval)
- [GitHub CLI (`gh`) recipes](#github-cli-gh-recipes)
- [Requirements](#requirements)
- [Branch protection (recommended)](#branch-protection-recommended)

---

## Goals

- **Dependabot** PRs should merge themselves after **minor/patch** updates pass **CI** (see [Dependabot](#dependabot-auto-merge-and-how-to-help)).
- **Human/feature work** should not land on `main` without a PR; prefer **feature branches** (`feat/`, `fix/`, …) or the **`agent/**` script lane** when you want the automation below.
- **Reviews**: eligible PRs **request Copilot automatically** (see [Request Copilot review](#request-copilot-review-automation)); add humans as needed; fix feedback in new commits until CI is green.

---

## Lanes: `agent/**` vs everything else

| Lane | Branch pattern | Who creates the PR | Auto-merge after approval? |
|------|----------------|-------------------|----------------------------|
| **Script lane** | `agent/<type>/...` | `scripts/open_pr.sh` or push (see [Agent auto-open PR](#agent-auto-open-pr-on-push)) | Yes — [Agent merge after CI](#agent-prs-squash-merge-after-approval) (requires **approval by `sankalp404`**, not Draft) |
| **Normal lane** | `feat/`, `fix/`, `chore/`, `docs/`, … | You (`gh pr create` or GitHub UI) | **No** — merge manually unless you enable repo auto-merge / merge queue yourself |

**Important:** `scripts/open_pr.sh` only creates **`agent/**`** branches. Work on a conventional branch (e.g. `feat/foo`) is **not** picked up by the agent merge workflow unless you rename/move the branch.

---

## CI (when checks run)

Workflow: `.github/workflows/ci.yml`

| Trigger | What runs |
|---------|-----------|
| **`pull_request`** (any branch targeting `main`) | `Backend (pytest in docker)` + `Frontend (lint/typecheck/test)` |
| **`push` to `main`** | Same jobs (post-merge verification) |
| **`workflow_dispatch`** | Same jobs (manual run) |

**Concurrency:** one CI run per PR or per ref; in-progress runs cancel when a new commit is pushed (`cancel-in-progress: true`).

**Required check names** (used by merge automation and branch protection):

- `CI / Backend (pytest in docker)`
- `CI / Frontend (lint/typecheck/test)`

---

## Scripts

### `scripts/open_pr.sh` — branch, commit, push, Draft PR

**Usage:**

```bash
scripts/open_pr.sh <feat|fix|chore|docs|refactor|test> "Short title in quotes"
```

**Behavior:**

1. If you are on `agent/**` with **uncommitted** changes → exits (you must commit/stash first).
2. If you are on `agent/**` with an **open PR** that is **not merged** → exits (finish or merge that PR first).
3. If you are on `agent/**` and the PR is **merged** → switches to `main`, `git pull --ff-only`.
4. Creates **`agent/<type>/<slug>-YYYYMMDD`**, commits all staged/untracked changes with `type: title`, pushes, opens a **Draft** PR to `main` (body from `.github/pull_request_template.md` plus a short auto header).

**Needs:** `gh` authenticated; scopes: `contents:write`, `pull_requests:write`.

### `scripts/close_dependabot_prs.sh` — bulk-close Dependabot PRs

**Usage:** `./scripts/close_dependabot_prs.sh "reason"` — closes **all** open PRs from `dependabot[bot]`. Use when resetting policy or cleaning up after config changes (see `dependabot.yml`).

---

## GitHub workflows (inventory)

### Dependabot auto-merge

**File:** `.github/workflows/dependabot-automerge.yml`  
**Runs on:** `pull_request` — `opened`, `synchronize`, `reopened`, `ready_for_review`  
**Actor:** `dependabot[bot]` only  

**Behavior:**

- Uses `dependabot/fetch-metadata` to read the update type.
- **Only** auto-merges **semver minor** and **semver patch** (not major).
- Tries **`gh pr merge --auto --squash --delete-branch`** first (merge queue / branch rules).
- If auto-merge is disabled, **polls** until checks pass and `mergeStateStatus` is mergeable, then squash-merges.
- If PR is **Draft**, the fallback loop skips.
- If branch is **BEHIND** `main`, updates the PR branch via GraphQL and waits.

### Agent auto-open PR (on push)

**File:** `.github/workflows/agent-auto-pr.yml`  
**Runs on:** `push` to **`agent/**`** only  

**Behavior:** If no PR exists for that head branch, creates a **Draft** PR to `main` (title derived from branch segments; body from `.github/pull_request_template.md` if present).  
**Does not** dispatch CI explicitly — CI is driven by **PR** events (see [CI](#ci-when-checks-run)).

### Agent merge after CI (when approved)

**File:** `.github/workflows/agent-merge-after-ci.yml`  
**Runs on:**

- `workflow_run` after **CI** completes successfully, or
- `pull_request_review` submitted  

**Branch filter:** `agent/**` only  

**Merge conditions:**

- PR is **not** Draft (must click **Ready for review**).
- At least one **APPROVED** review from **`sankalp404`**.
- For `workflow_run`: the CI run’s **head SHA** matches the PR **head SHA** (avoids merging stale commits).
- **Required checks** (by name) are **SUCCESS** — workflow polls `statusCheckRollup` for `Backend (pytest in docker)` and `Frontend (lint/typecheck/test)` (ignores its own job to avoid deadlock).
- If **BEHIND** `main`, updates the branch (and may dispatch CI on the branch ref).

Then: **`gh pr merge --auto --squash --delete-branch`**, or direct squash if auto-merge is unavailable.

### Update agent PR branch from main (when ready)

**File:** `.github/workflows/agent-update-branch.yml`  
**Runs on:** `pull_request` — `ready_for_review`, `reopened`, `synchronize`  

**Behavior:** For **`agent/**`** only, if PR is **not** Draft and `mergeStateStatus` is **BEHIND**, updates the branch from `main` via GraphQL.

### Request Copilot review (automation)

**File:** `.github/workflows/request-copilot-review.yml`  
**Runs on:** `pull_request` into **`main`** — `opened`, `reopened`, `ready_for_review`

**Skips:** PRs from **`dependabot[bot]`**, **Draft** PRs, **fork** PRs (head repo ≠ this repo).

**Behavior:** Runs `gh pr edit … --add-reviewer @copilot` using `GITHUB_TOKEN`. The step uses **`continue-on-error: true`** so missing Copilot entitlement, an older `gh` on the runner, or “already requested” does **not** fail the workflow run.

When you **mark a Draft PR ready for review**, `ready_for_review` fires and Copilot is requested.

**Dependabot config:** `.github/dependabot.yml` — weekly npm (frontend), pip (root), GitHub Actions; groups and limits as documented in that file.

---

## End-to-end operator loop

This is the intended “automation loop” for day-to-day work. Nothing here replaces **reading CI** and **fixing failures**; GitHub cannot fix code in your repo without a bot or Actions that you add yourself.

### 1. Before you open a PR

1. **Implement** on a branch (`agent/...` via `open_pr.sh`, or `feat/...` / `fix/...` manually).
2. **Run checks** from repo root (see [Makefile quick reference](README.md#makefile-quick-reference)):
   - `make test`
   - Frontend touched: `make frontend-check` or `make test-frontend`
   - Both: `make test-all`
3. **Fill the PR story** (title + body): use `.github/pull_request_template.md` checklist.

### 2. Open the PR

- **Script lane:** `scripts/open_pr.sh fix "short description"` → **Draft** PR.
- **Manual:** `gh pr create --base main --head <branch>` (add `--draft` if you want Draft).

### 3. After the PR exists

1. **Watch CI** on the PR — both Backend and Frontend jobs must pass.
2. **Reviews:** Copilot is requested automatically for eligible PRs (see [Request Copilot review](#request-copilot-review-automation)); add humans as needed — [gh recipes](#github-cli-gh-recipes).
3. **Resolve comments:** push commits; CI re-runs on PR sync. Repeat until green and reviewers are satisfied.
4. **Mark Ready for review** when you want merges (Draft PRs are **not** auto-merged by the agent workflow).

### 4. Merge

- **`agent/**`:** Approve as **`sankalp404`**; wait for merge workflow after CI (or merge manually if policy allows).
- **Other branches:** Merge from GitHub UI (squash-merge preferred per [git workflow](../.cursor/rules/git-workflow.mdc)), or `gh pr merge`.

---

## Dependabot: auto-merge and how to help

**What runs automatically**

- New Dependabot PRs get **minor/patch** auto-merge via **Dependabot auto-merge** workflow (after checks pass).
- **Major** updates are **not** merged by that workflow (metadata must be minor/patch).

**When you need to help**

| Situation | What to do |
|-----------|------------|
| **CI failed** | Check logs; fix **on a new branch** or push to the Dependabot branch if your policy allows; often re-run after lockfile or test fixes. |
| **Major bump** | Review manually, adjust code, merge when ready — or extend ignore rules in `dependabot.yml` if you want to skip. |
| **PR stuck “behind”** | Workflow tries to update; you can also `gh pr merge` after updating branch or use **Update branch** in GitHub UI. |
| **Too many open Dependabot PRs** | Lower `open-pull-requests-limit` in `dependabot.yml` or use `scripts/close_dependabot_prs.sh` with a clear reason after changing policy. |
| **Conflicts** | Resolve on the branch; re-run CI. |

**Labels:** Dependabot applies `deps` plus `frontend` / `backend` / `ci` per `dependabot.yml`.

---

## Agent PRs: squash-merge after approval

- **Who can trigger merge:** approval by **`sankalp404`** (see workflow).
- **Draft PRs** are never merged by automation — mark **Ready for review**.
- **Branch must stay mergeable** — `mergeStateStatus` should become mergeable after required checks; workflow handles BEHIND by updating the branch.

---

## GitHub CLI (`gh`) recipes

The **Request Copilot review** workflow also runs `gh pr edit … --add-reviewer @copilot` for eligible PRs; use the commands below when you want to adjust reviewers manually.

**Authentication:** `gh auth login` (or `GH_TOKEN` with `contents:write`, `pull_requests:write`).

**Open / edit PR**

```bash
gh pr create --base main --head <branch> --title "feat: …" --body-file .github/pull_request_template.md
gh pr view --web
gh pr edit <number> --title "feat: …" --body-file .github/pull_request_template.md
```

**Mark ready for review**

```bash
gh pr ready <number>
```

**Request Copilot review** (requires GitHub CLI **v2.88+** and a plan that includes Copilot code review; not supported on GitHub Enterprise Server):

```bash
gh pr edit <number> --add-reviewer @copilot
```

If the CLI rejects `@copilot`, use the PR **Reviewers** sidebar and add **GitHub Copilot** (or your org’s equivalent).

**Watch checks**

```bash
gh pr checks <number> --watch
```

**Merge (manual)**

```bash
gh pr merge <number> --squash --delete-branch
```

**List Dependabot PRs**

```bash
gh pr list --author "dependabot[bot]" --state open
```

---

## Requirements

- **GitHub CLI** (`gh`) installed.
- **Auth:** `gh auth login` or `GH_TOKEN` with at least `contents:write` and `pull_requests:write`.
- For **Dependabot** merge from Actions: default `GITHUB_TOKEN` permissions as in workflows (read/write as declared).

---

## Branch protection (recommended)

In GitHub repo Settings → **Branches** → protect `main`:

- Require a pull request before merging.
- Require status checks: **exact names** from CI:
  - `Backend (pytest in docker)`
  - `Frontend (lint/typecheck/test)`
- Optionally restrict who can push to `main`.

---

## What is *not* automated (today)

- **Creating branches** for arbitrary `feat/**` names — only `scripts/open_pr.sh` creates `agent/**` branches automatically.
- **Copilot on fork PRs** — the Request Copilot workflow only targets same-repo PRs (`head` repo = base repo).
- **Applying code fixes** from review comments — requires human or AI in the repo with push access; CI only validates.

---

## Related docs

- [Makefile quick reference](README.md#makefile-quick-reference)
- [PR template](../.github/pull_request_template.md)
- [Git workflow rules](../.cursor/rules/git-workflow.mdc)
