# Dependabot automation

Paperwork Labs ships a Brain-owned Dependabot flow: GitHub webhook → Brain
classifier → approve/merge or LLM triage. All logic lives in the Brain service;
the old three GitHub Actions workflows (`dependabot-auto-approve.yaml`,
`dependabot-major-triage.yaml`, `auto-merge-sweep.yaml`) and the companion
`dependabot_triage.py` script were deleted in Track B, Week 1 of the Infra &
Automation Hardening Sprint.

## Pipeline

```
dependabot opens/updates PR
  │
  ▼
GitHub webhook  POST https://brain.paperworklabs.com/api/v1/webhooks/github
  │
  ▼  app/routers/webhooks.py: _handle_pull_request_event
  │
  ▼  app/services/dependabot_classifier.py
  ├── patch / minor (or semver-patch/minor metadata)   ──►  approve + label `deps:safe`
  ├── major (or semver-major metadata)                 ──►  label `deps:major` + `needs-human-review`
  │                                                          + Brain review (Claude Haiku → risk tier comment)
  └── unknown                                          ──►  label `needs-human-review`
  │
  ▼
app/schedulers/pr_sweep.py   (AsyncIOScheduler every 30 min)
  │  Calls:
  │   1. sweep_open_prs (review new heads)
  │   2. merge_ready_prs (squash-merge approved + green + mergeable)
  │
  ▼
squash-merge when APPROVED + all CI green + no deps:major/needs-human-review/do-not-merge labels
```

**Why one place.** Brain is already the authority for PR reviews, memory, and
model routing. Duplicating that decision tree in GitHub Actions meant two
sources of truth with no shared context. The webhook path gives Brain the same
episode history it uses for human PRs.

**Why still a scheduled sweep.** The webhook path fires on PR events. A 30-min
APScheduler tick catches:
- PRs that flipped from red to green between webhook fires (race between
  review approval and CI completion),
- historical backlog (after a migration or a day the webhook endpoint was down),
- and anything Brain missed on first open.

## Code

| Path | Purpose |
|---|---|
| `apis/brain/app/routers/webhooks.py` | `POST /webhooks/github` — HMAC-verified entry point. |
| `apis/brain/app/services/dependabot_classifier.py` | Pure classifier. Patch/minor → safe, major → major, else unknown. |
| `apis/brain/app/services/pr_review.py` | `review_pr` + `sweep_open_prs` — Brain's reviewer. |
| `apis/brain/app/services/pr_merge_sweep.py` | `merge_ready_prs` — squash-merge approved + green + mergeable PRs. |
| `apis/brain/app/schedulers/pr_sweep.py` | AsyncIOScheduler running review + merge every 30 min. |
| `apis/brain/app/services/slack_outbound.py` | Posts Brain review summaries to `#engineering`. |

## Secrets required

All set on the `brain-api` Render service:

| Secret | Used by |
|---|---|
| `GITHUB_TOKEN` | `github` tool — auth for approve / label / merge REST calls. |
| `GITHUB_WEBHOOK_SECRET` | `_verify_github_webhook` — HMAC-SHA256 of request body. |
| `ANTHROPIC_API_KEY` | `pr_review._call_anthropic` — Claude Haiku / Sonnet. |
| `SLACK_BOT_TOKEN` | `slack_outbound` — optional; review posts to #engineering. |
| `SLACK_ENGINEERING_CHANNEL_ID` | Target channel for review posts. |

If `ANTHROPIC_API_KEY` is absent, `review_pr` returns
`{"posted": false, "error": "llm_empty"}` and the sweep logs a warning —
nothing crashes.

## Risk tiering (from the LLM prompt)

| Tier | Definition |
|---|---|
| `low` | Type-safe upgrade, deprecated APIs we don't call, no runtime behavior change. |
| `medium` | Semantic changes in APIs this repo uses; needs a smoke test or quick manual sweep. |
| `high` | Breaks an API used widely, requires cross-file code changes, OR is in a security-critical path (auth, crypto, broker SDK, billing). |

## Costs

Claude Haiku 4.5, ~8k input + ~500 output per review:
- **~$0.002 per PR**.
- At Paperwork's cadence (~5 dep majors / week, ~15 human PRs / week) that's
  **~$0.04 / week**.

## Manual overrides

| What you want | How to do it |
|---|---|
| Force a review for a PR | `curl -X POST $BRAIN_URL/api/v1/admin/pr-review -H "X-Brain-Secret: $BRAIN_API_SECRET" -d '{"pr_number": N}'` |
| Kick the sweep by hand | `curl -X POST $BRAIN_URL/api/v1/admin/pr-sweep -H "X-Brain-Secret: $BRAIN_API_SECRET"` |
| Kick the merge sweep by hand | `curl -X POST $BRAIN_URL/api/v1/admin/pr-merge-sweep -H "X-Brain-Secret: $BRAIN_API_SECRET"` |
| Skip auto-approve for a safe bump | Add label `needs-human-review` to the PR. Classifier short-circuits to `unknown`. |
| Skip Brain review on a human PR | Add label `skip-brain-review`. `sweep_open_prs` honours it. |
| Disable the scheduler | `BRAIN_SCHEDULER_ENABLED=false` on `brain-api`. Webhook path still works. |

## Labels used

Already present in the repo (verified via `gh label list`):

- `deps:safe` — green. Applied by Brain webhook on patch/minor bumps.
- `deps:major` — red. Applied by Brain webhook on major bumps.
- `risk:low` / `risk:medium` / `risk:high` — green / yellow / red. Applied by
  Brain's review in the LLM body (text, not label — tied to the PR comment).
- `needs-human-review` — yellow. Applied on `unknown` classifications and all
  majors.
- `skip-brain-review` — neutral. Opt-out for `sweep_open_prs`.

## Backlog drain

```bash
curl -X POST "$BRAIN_URL/api/v1/admin/pr-sweep" \
  -H "X-Brain-Secret: $BRAIN_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"limit": 50, "force": true}'
```

This scans every open PR and re-reviews at the current head SHA. `force:true`
ignores the "already reviewed at this SHA" memory check.

## Interaction with Brain PR review

This document *is* the Brain PR review path for dependency bumps. Human-authored
PRs go through the same codepath, minus the classifier branch — their first
webhook calls `review_pr` directly. See
[`BRAIN_PR_REVIEW.md`](./BRAIN_PR_REVIEW.md) for the reviewer internals.

## Migration note (2026-04-24)

Track B, Week 1 of the Infra & Automation Hardening Sprint deleted:
- `.github/workflows/dependabot-auto-approve.yaml`
- `.github/workflows/dependabot-major-triage.yaml`
- `.github/workflows/auto-merge-sweep.yaml`
- `.github/scripts/dependabot_triage.py`

Behaviour is byte-for-byte compatible with the old workflows. Unit tests in
`apis/brain/tests/test_dependabot_classifier.py` lock that down.
