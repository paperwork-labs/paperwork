# Dependabot — auto-merge and LLM triage

Paperwork uses Dependabot for weekly dependency bumps. To keep the PR
queue healthy without tying up human review on trivial bumps, we run
**two** GitHub Actions workflows on top of the baseline config in
`.github/dependabot.yml`.

## The two workflows

### 1. `dependabot-auto-approve.yaml` — rules-based

Triggers on `pull_request_target` (open/sync) for any PR authored by
`dependabot[bot]`. Uses `dependabot/fetch-metadata@v2` to classify the
update. Outcome:

| bump class | action |
|---|---|
| Patch | auto-approve → `gh pr merge --auto --squash` |
| Minor | auto-approve → `gh pr merge --auto --squash` |
| Grouped minor-and-patch (`dependency-group` non-empty) | auto-approve → `gh pr merge --auto --squash` |
| `github_actions` ecosystem | auto-approve → `gh pr merge --auto --squash` |
| Major | label `deps:major` + hand off to triage workflow |

Safe bumps merge automatically **only once all required CI checks pass**
— `--auto` tells GitHub to wait. If CI fails, the PR sits and a human
can intervene.

### 2. `dependabot-major-triage.yaml` — LLM-assisted

Triggers when the `deps:major` label is added to a dependabot PR. Pulls:

- Dependabot metadata (package names, prev/new versions, ecosystem)
- Truncated PR diff (first 200 lines)
- Rough import-site counts for each bumped package via `grep`

Feeds all that to **Claude Haiku 4.5** via the Anthropic API (see
`.github/scripts/dependabot_triage.py`). The model returns a JSON object:

```json
{
  "risk": "low | medium | high",
  "summary": "one-line plain-English summary of breaking changes",
  "breaking_changes": ["…"],
  "affected_paths": ["…"],
  "recommendation": "merge | review | hold",
  "confidence": "low | medium | high"
}
```

The workflow posts that as a PR comment and adds a `risk:low|medium|high`
label. **It never auto-merges majors** — a human still clicks merge.

Cost: ~$0.001 per PR (Haiku 4.5, ~2k input + <500 output tokens).

## Setup

One-time repo secret required for the LLM triage:

```bash
gh secret set ANTHROPIC_API_KEY --repo paperwork-labs/paperwork
```

If the secret isn't set, the triage workflow still runs but posts a
"secret not configured" comment instead of a real assessment (won't
block merges).

Labels created by `scripts/setup-dependabot-labels.sh` (or manually the
first time):

- `deps:major`
- `risk:low` / `risk:medium` / `risk:high`

## Draining a backlog

If the auto-approve workflow is added when a large queue already exists,
it only fires on new pushes. To drain existing safe PRs without waiting
for the next sync, run:

```bash
.github/scripts/drain-dependabot-backlog.sh
```

This iterates all open dependabot PRs, classifies them with the same
rules as the workflow, and enables `--auto --squash` on the safe ones.
Major bumps get the `deps:major` label, which will then trigger the
triage workflow.

## Manual overrides

- **Block a PR from auto-merging:** add the `do-not-merge` label or
  request changes in a review — GitHub's branch protection (once
  enabled) will honor that.
- **Force triage on a non-major PR:** apply the `deps:major` label
  manually; the triage workflow will run.
- **Re-run triage:** remove and re-add the `deps:major` label.

## Security notes

- Both workflows use `pull_request_target`, which runs against the base
  branch's workflow definition — immune to tampering via PR edits.
- Neither workflow checks out the PR's head; the triage workflow
  checkouts the **base branch** for usage greps.
- Actor guard: `github.actor == 'dependabot[bot]'` on both workflows
  prevents humans from tricking the automation.
- The LLM receives truncated diffs and usage counts, not the full repo.
