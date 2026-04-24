# Dependabot automation

Paperwork Labs ships a two-tier Dependabot flow so `pnpm`/`pip`/GitHub Actions
bumps don't consume human attention. Safe bumps auto-approve and auto-merge;
majors go through a cheap Claude Haiku triage before they need human eyes.

## Pipeline

```
dependabot opens PR
  │
  ▼
dependabot-auto-approve.yaml                           dependabot-major-triage.yaml
  ├── patch | minor | grouped-minor  ──►  approve                  ▲
  ├── major                          ──►  label `deps:major` ─────┘
  └── unknown                        ──►  label `needs-human-review`
                                          (fetch-metadata couldn't classify)
  │                                           │
  │                                           ▼
  │                              .github/scripts/dependabot_triage.py
  │                                           │
  │                                           ▼
  │                                 Anthropic Claude Haiku
  │                                           │
  │                                           ▼
  │              PR comment + label: risk:low | risk:medium | risk:high
  │
  ▼
auto-merge.yaml   (event-driven: on review + on check_suite completed)
  │
  ▼
auto-merge-sweep.yaml   (scheduled every 10 min — catches races)
  │
  ▼
squash-merge when APPROVED + all CI green + no deps:major / needs-human-review / do-not-merge labels
```

**Why two merge workflows?** GitHub Free + private repo doesn't support the
native auto-merge feature (`allow_auto_merge: false` is enforced by the plan).
The event-driven `auto-merge.yaml` merges on approval when CI is already green;
the scheduled `auto-merge-sweep.yaml` catches the race where a PR gets approved
first and CI finishes later.

**Why the event-driven workflow defers bot PRs to the sweep.** Dependabot-authored
PRs run workflows with a read-only `GITHUB_TOKEN` — `pull_request_review` and
`check_suite` events inherit that reduced permission set, so `github.rest.pulls.merge`
403s. The scheduled sweep (a first-party `schedule` event) runs with full repo
permissions, which is why it's the source of truth for Dependabot merges.
Human-authored PRs still merge instantly via the event-driven path.

## Files

| Path | Purpose |
|---|---|
| `.github/workflows/dependabot-auto-approve.yaml` | Classifier + approver for safe bumps. Labels majors `deps:major`. |
| `.github/workflows/dependabot-major-triage.yaml` | LLM triage for `deps:major` PRs. |
| `.github/workflows/auto-merge.yaml` | Merges approved + green PRs on review or check_suite events. |
| `.github/workflows/auto-merge-sweep.yaml` | Scheduled poll (10m) — catches approval-before-CI-done races. |
| `.github/scripts/dependabot_triage.py` | Python script: calls Claude Haiku, renders markdown comment. |

## Risk tiering (from the LLM prompt)

| Tier | Definition |
|---|---|
| `low` | Type-safe upgrade, deprecated APIs we don't call, no runtime behavior change. |
| `medium` | Semantic changes in APIs this repo uses; needs a smoke test or quick manual sweep. |
| `high` | Breaks an API used widely, requires cross-file code changes, OR is in a security-critical path (auth, crypto, broker SDK, billing). |

## Secrets required

All set at the **repo** level (`paperwork-labs/paperwork`):

| Secret | Used by |
|---|---|
| `GITHUB_TOKEN` | auto-approve workflow — standard Actions token (injected). |
| `ANTHROPIC_API_KEY` | major-triage workflow — calls Claude Haiku. |

If `ANTHROPIC_API_KEY` is absent the triage gracefully degrades: it labels the
PR `risk:medium` with a "human review required" comment instead of failing.

## Costs

Claude Haiku 4.5, ~8k input + ~500 output per major:
- **~$0.002 per major triage**.
- At Paperwork's cadence (1–5 majors/week) that's **cents per month**.

## Manual overrides

| What you want | How to do it |
|---|---|
| Force triage for a specific PR | `gh workflow run dependabot-major-triage.yaml -F pr_number=<N>` |
| Skip auto-approve for a safe bump | Add label `needs-human-review` to the PR (workflow already handles it) |
| Skip the entire Brain PR review (separate system, see [BRAIN_PR_REVIEW.md](./BRAIN_PR_REVIEW.md)) | Add label `skip-brain-review` |
| Disable the full pipeline | Delete or disable the workflow files (automerge will stall, flow is safe) |

## Labels used

Already present in the repo (verified via `gh label list`):

- `deps:major` — red. Applied by auto-approve when bump is a major.
- `dependencies` — black. Applied alongside `deps:major`.
- `risk:low` / `risk:medium` / `risk:high` — green/yellow/red. Applied by triage.
- `needs-human-review` — if not present, create with `gh label create needs-human-review --color fbca04 --description "Bot classifier unsure; human should look"`.

## Backlog drain

To process an existing Dependabot backlog without waiting for Dependabot to push a
new commit and re-trigger the workflows, use `scripts/dependabot/drain-backlog.sh`
— it classifies open bot PRs (patch/minor/group vs. major), approves safe ones,
and labels majors to trigger the Haiku triage workflow.

```bash
./scripts/dependabot/drain-backlog.sh
```

After draining, re-run Haiku triage for every major (in case the first pass ran
without `ANTHROPIC_API_KEY` set and fell back to `risk:medium`):

```bash
gh pr list --author "app/dependabot" --label "deps:major" --state open --limit 50 \
  --json number --jq '.[].number' | while IFS= read -r n; do
  gh workflow run dependabot-major-triage.yaml -F pr_number=$n
  sleep 2
done
```

## Interaction with Brain PR review

The Brain PR reviewer (`.github/workflows/brain-pr-review.yaml`) **skips**
Dependabot PRs — checked in its `if:` guard. Dependency bumps are mechanical
changes; rate-limiting the LLM reviewer on them is wasted spend.

If a major bump needs Brain to weigh in (e.g. Next.js 15 → 16 that requires
real migration code), remove the `dependencies` / `deps:major` labels and the
Brain reviewer will run on the next `synchronize`.
