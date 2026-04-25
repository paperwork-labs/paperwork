---
name: repo-move-sankalp404-to-paperwork-labs
overview: Phase 0 of the agent-PR-automation Path 2 rollout. Move sankalp404/axiomfolio to paperwork-labs/axiomfolio. ~30-60 min. GitHub redirects all clone/issue/PR URLs forever; only env-var references and explicit owner/repo strings need updating.
todos:
  - id: pre-flight-inventory
    content: "Pre-flight: Inventory all webhooks, secrets, branch protections, deploy keys, GitHub Actions in current repo. Document for re-application post-move."
    status: pending
  - id: stop-active-deploys
    content: "Pre-move: Pause active Render deploys. Notify any other developers / agents touching the repo."
    status: pending
  - id: do-the-move
    content: "Execute: GitHub UI Settings → Transfer ownership → paperwork-labs. Confirm via second factor."
    status: pending
  - id: verify-redirects
    content: "Post-move verification: clone via old URL works (redirects), gh CLI sees new repo, Render still receives push events, CI runs on new owner."
    status: pending
  - id: update-references
    content: "Post-move references: Brain GITHUB_REPO env var, Cloudflare deploy hooks, any docs hardcoding sankalp404/axiomfolio, .git/config remotes on dev machines."
    status: pending
isProject: false
---

# Repo Move Runbook: sankalp404/axiomfolio → paperwork-labs/axiomfolio

## Context

Phase 0 of agent PR automation Path 2 (see `[/Users/axiomfolio/.cursor/plans/agent-pr-automation_79e8354f.plan.md]`). Done first so all subsequent secrets, GitHub App installs, and Brain's `GITHUB_REPO` env var land in the correct owner from day 1.

## Strategic Framing (not just admin)

This move recognizes a positioning that already exists in `[/Users/axiomfolio/development/paperwork/docs/BRAIN_ARCHITECTURE.md]` line 7:

> "Brain IS the long-term platform. FileFree, LaunchFree, **axiomfolio are skills/capabilities within it**. Products are the hands, Brain is the mind."

Currently AxiomFolio sits at `sankalp404/axiomfolio` — implying a personal-side-project relationship. Moving to `paperwork-labs/axiomfolio` is the act of recognizing what BRAIN_ARCHITECTURE already says: AxiomFolio is one of the Paperwork Labs products, on equal footing with FileFree, LaunchFree, Distill, Trinkets. Once moved:

- Brain's `GITHUB_REPO` env can rotate across `paperwork-labs/*` repos
- One `paperwork-agent` GitHub App installs across the suite (PR automation, decision logging, daily briefing — see Brain plan v2-v4 roadmap)
- AxiomFolio's `docs/TASKS.md` ingests into Brain memory the same way `paperwork/docs/TASKS.md` already does
- Org-level secrets shared with Brain workflows
- Slack channels organize cleanly: `#axf-*`, `#filefree-*`, `#launchfree-*` already match this structure

## What GitHub Redirects (Forever)

GitHub permanently redirects after a transfer:

- `https://github.com/sankalp404/axiomfolio/...` → `https://github.com/paperwork-labs/axiomfolio/...`
- `git clone git@github.com:sankalp404/axiomfolio.git` → resolves to new owner
- `https://api.github.com/repos/sankalp404/axiomfolio/...` → 301 redirect (most clients follow)
- All issue/PR/commit links from external systems
- Stars, watchers, fork references

## What Does NOT Redirect (Manual Updates Required)

- Hardcoded `sankalp404/axiomfolio` strings in YOUR code or env vars
- GitHub Actions secrets at the OLD repo (delete after move; recreate at new repo or org)
- Branch protection rules (re-applied automatically by GitHub for the new owner, but verify)
- Deploy keys (carry over by default, but verify)
- Webhooks added by GitHub Apps (carry over)
- Webhooks added by integrations (carry over)
- Render service-to-repo binding (Render auto-follows the redirect, but a manual deploy after move confirms)

## Pre-Flight Inventory (run BEFORE move)

```bash
# 1. List all webhooks
gh api repos/sankalp404/axiomfolio/hooks > /tmp/hooks-pre-move.json

# 2. List repo-level secrets
gh secret list --repo sankalp404/axiomfolio > /tmp/secrets-pre-move.txt
# Note: secret VALUES not exposed; just names. You'll need to recreate.

# 3. List branch protection on main
gh api repos/sankalp404/axiomfolio/branches/main/protection > /tmp/protection-pre-move.json

# 4. List deploy keys
gh api repos/sankalp404/axiomfolio/keys > /tmp/keys-pre-move.json

# 5. List installed GitHub Apps
gh api repos/sankalp404/axiomfolio/installations 2>/dev/null > /tmp/apps-pre-move.json || true

# 6. List GitHub Actions runners (if self-hosted)
gh api repos/sankalp404/axiomfolio/actions/runners > /tmp/runners-pre-move.json

# 7. List active workflow runs (don't move during one)
gh run list --repo sankalp404/axiomfolio --limit 5 --json status,name | jq '.[] | select(.status == "in_progress")'
```

Save these files. Compare to post-move state.

## Pause Active Systems

1. **Render** — open dashboard, go to axiomfolio services, set "auto-deploy" off (re-enable after move)
2. **Background Agents** — finish or cancel any open Cursor Background Agents on this repo
3. **Cloudflare** — none should be repo-aware (DNS-only), but verify
4. **Other developers** — if any (currently none), notify

## The Move

GitHub UI:

1. Go to `https://github.com/sankalp404/axiomfolio/settings`
2. Scroll to "Danger Zone" → "Transfer ownership"
3. Click "Transfer"
4. New owner: `paperwork-labs`
5. Type repo name to confirm: `axiomfolio`
6. Authorize via 2FA
7. GitHub processes (5-30 sec) → redirects you to new URL

## Post-Move Verification (~15 min)

```bash
# 1. Clone test (use OLD URL to confirm redirect)
cd /tmp
git clone git@github.com:sankalp404/axiomfolio.git test-old-url-clone
cd test-old-url-clone
git remote -v  # should show paperwork-labs/axiomfolio
cd .. && rm -rf test-old-url-clone

# 2. gh CLI sees new repo
gh repo view paperwork-labs/axiomfolio --json name,description,owner

# 3. Webhooks intact
gh api repos/paperwork-labs/axiomfolio/hooks > /tmp/hooks-post-move.json
diff /tmp/hooks-pre-move.json /tmp/hooks-post-move.json
# Expect: identical content (URLs, events, secrets all preserved)

# 4. Branch protection intact
gh api repos/paperwork-labs/axiomfolio/branches/main/protection > /tmp/protection-post-move.json
diff /tmp/protection-pre-move.json /tmp/protection-post-move.json

# 5. Render webhook fires (push a no-op commit)
cd ~/development/axiomfolio
git remote set-url origin git@github.com:paperwork-labs/axiomfolio.git
git remote -v
echo "" >> README.md && git add README.md && git commit -m "chore: verify post-move webhook" && git push
# Watch Render dashboard → should see new deploy triggered

# 6. CI runs on new owner
gh run list --repo paperwork-labs/axiomfolio --limit 3
# Expect: latest run on the new commit, status pending or success

# 7. Open and close a test issue to verify full read/write
gh issue create --repo paperwork-labs/axiomfolio --title "post-move smoke test" --body "delete me"
gh issue close <number> --repo paperwork-labs/axiomfolio
```

## Update External References

### Brain (paperwork repo)

```bash
# In Render dashboard:
# brain-api service → Environment → GITHUB_REPO
# Old: sankalp404/axiomfolio
# New: paperwork-labs/axiomfolio
# Save → triggers redeploy
```

Verify Brain can still read from new repo after redeploy:

```bash
curl -X POST https://brain.paperworklabs.com/api/v1/admin/test-tool \
  -H "Authorization: Bearer $BRAIN_API_SECRET" \
  -d '{"tool": "read_github_file", "args": {"path": "README.md"}}'
```

### AxiomFolio repo internal references

Search and update:

```bash
cd ~/development/axiomfolio
rg -l "sankalp404/axiomfolio"  # find all references
# Update in:
# - docs/*.md
# - .github/workflows/*.yml (if any hardcode owner)
# - README.md badges
```

Likely candidates:
- `[README.md]` — clone URL, badge URLs
- `[docs/ONBOARDING.md]` — clone instructions
- `[docs/PR_AUTOMATION.md]` — gh command examples
- `[.github/workflows/*]` — any `gh` commands hardcoding owner
- `[render.yaml]` — repo URL if present

### Local dev machines

```bash
# On each machine you develop from:
cd ~/development/axiomfolio
git remote set-url origin git@github.com:paperwork-labs/axiomfolio.git
git remote -v  # verify
```

## Repo-Level Secrets Re-Application

GitHub does NOT migrate repo-level secrets across owners. Re-add via gh CLI or UI:

```bash
# List old secrets (names only)
gh secret list --repo sankalp404/axiomfolio
# Manually re-set each one at new repo:
gh secret set RENDER_API_KEY --repo paperwork-labs/axiomfolio
gh secret set CLOUDFLARE_API_TOKEN --repo paperwork-labs/axiomfolio
# ... etc for all ~28 secrets
```

**Better:** move shared secrets to org-level so they apply across paperwork-labs repos:

```bash
gh secret set RENDER_API_KEY --org paperwork-labs --visibility selected --repos axiomfolio
```

For agent-PR-automation specifically:

- `AGENT_APP_ID` → org level (selected repos)
- `AGENT_APP_PRIVATE_KEY` → org level (selected repos)
- `BRAIN_WEBHOOK_URL` → org level (all repos)
- `BRAIN_WEBHOOK_SECRET` → org level (selected repos)

## Risk: GHA Minute Plan

GitHub Actions minute allocation depends on the OWNER account, not the repo:

- `sankalp404` (personal Pro plan): 3,000 min/mo included for private repos; unlimited for public
- `paperwork-labs` (Free org): 2,000 min/mo for private; unlimited for public

**Since axiomfolio is currently public, GHA minutes remain unlimited after move.** No cost change.

If you ever go private, paperwork-labs Free org gets 2,000 min/mo — slightly less than personal Pro's 3,000. Upgrade to Team plan ($4/user/mo) gets 3,000 same as Pro. Decide at that time.

## Acceptance Criteria

- [ ] `gh repo view paperwork-labs/axiomfolio` succeeds; `sankalp404/axiomfolio` redirects
- [ ] All webhooks present at new repo (diff pre/post = empty)
- [ ] Branch protection preserved on `main` (diff = empty)
- [ ] Render webhook fires on push to new owner; deploy triggered
- [ ] CI runs on push to new owner
- [ ] Brain's `GITHUB_REPO` env var updated; Brain can read from new repo via MCP test
- [ ] Local dev `origin` remote updated (this machine; document for other machines)
- [ ] All hardcoded `sankalp404/axiomfolio` references in repo updated
- [ ] D### entry added to `docs/KNOWLEDGE.md` documenting the move date and reason

## Rollback (If Something Breaks)

- **Reversible** within 24h via GitHub support (transfers can be undone)
- **Self-reversible** anytime: paperwork-labs admin can transfer back to sankalp404
- All commits, issues, PRs preserved either way

## Estimated Time

- Pre-flight inventory: 10 min
- Pause systems + actual transfer: 5 min
- Post-move verification: 15 min
- Update Brain env + redeploy: 5 min
- Update internal references + commit: 15 min
- Org-level secrets migration (optional): 30 min

**Total: 30-80 min depending on secrets migration scope.**

---

**Companion plans:**
- `[/Users/axiomfolio/.cursor/plans/agent-pr-automation_79e8354f.plan.md]` — AxiomFolio side of agent automation
- `[/Users/axiomfolio/.cursor/plans/agent-pr-automation-brain.plan.md]` — Paperwork Brain side of agent automation
