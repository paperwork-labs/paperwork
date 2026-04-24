# Dependabot automation

Paperwork Labs ships a two-tier Dependabot flow so `pnpm`/`pip`/GitHub Actions
bumps don't consume human attention. Safe bumps auto-approve and auto-merge;
majors go through a cheap Claude Haiku triage before they need human eyes.

## Pipeline

```
dependabot opens PR
  │
  ▼
dependabot-auto-approve.yaml
  ├── patch | minor | grouped-minor  ──►  approve + automerge (squash)
  ├── major                           ──►  label "deps:major" + comment
  └── unknown                         ──►  label "dependencies, needs-human-review"
                                          (fetch-metadata couldn't classify)
                            │
                            ▼
              dependabot-major-triage.yaml
                (triggered by label = deps:major)
                            │
                            ▼
               .github/scripts/dependabot_triage.py
                            │
                            ▼
                 Anthropic Claude Haiku
                            │
                            ▼
       PR comment + label: risk:low | risk:medium | risk:high
```

## Files

| Path | Purpose |
|---|---|
| `.github/workflows/dependabot-auto-approve.yaml` | Classifier + approver + automerger for safe bumps. |
| `.github/workflows/dependabot-major-triage.yaml` | LLM triage for `deps:major` PRs. |
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

To process the existing Dependabot backlog (~40 PRs as of 2026-04-23) without
waiting for Dependabot to push a new commit and re-trigger the workflows, re-run
the auto-approve workflow for each open bot PR:

```bash
# Bulk-approve the currently-open safe dependabot PRs.
for pr in $(gh pr list --author "app/dependabot" --state open --limit 100 --json number,title \
  | jq -r '.[] | select(.title | test("^chore\\(deps.*(patch|minor)|^chore\\(deps.*group")) | .number'); do
  gh pr review "$pr" --approve --body "Drain-backlog approval (patch/minor/group)."
  gh pr merge  "$pr" --auto --squash
done
```

Majors in the backlog get a label + re-trigger of the triage:
```bash
for pr in $(gh pr list --author "app/dependabot" --state open --limit 100 --json number,title \
  | jq -r '.[] | select(.title | test("major|-> ?[0-9]+\\.0\\.0|v2\\.0|v3\\.0")) | .number'); do
  gh pr edit "$pr" --add-label "deps:major,dependencies"
done
```

## Interaction with Brain PR review

The Brain PR reviewer (`.github/workflows/brain-pr-review.yaml`) **skips**
Dependabot PRs — checked in its `if:` guard. Dependency bumps are mechanical
changes; rate-limiting the LLM reviewer on them is wasted spend.

If a major bump needs Brain to weigh in (e.g. Next.js 15 → 16 that requires
real migration code), remove the `dependencies` / `deps:major` labels and the
Brain reviewer will run on the next `synchronize`.
