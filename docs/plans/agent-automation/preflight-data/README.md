# Repo Move Pre-Flight Raw Snapshots

Captured 2026-04-23 against `sankalp404/axiomfolio` ahead of the planned
transfer to `paperwork-labs/axiomfolio`. See
`../00-repo-move-preflight-snapshot.md` for the human-readable summary
and `../00-repo-move.md` for the full runbook.

| File | Source command | What "good" looks like post-move |
|---|---|---|
| `hooks-pre-move.json` | `gh api repos/sankalp404/axiomfolio/hooks` | `[]` (and post-move identical) |
| `keys-pre-move.json` | `gh api repos/sankalp404/axiomfolio/keys` | `[]` (and post-move identical) |
| `runners-pre-move.json` | `gh api repos/sankalp404/axiomfolio/actions/runners` | `total_count: 0` |
| `rulesets-pre-move.json` | `gh api repos/sankalp404/axiomfolio/rulesets` | 2 entries (PR Merge Rule, PR Review Rule) — preserved by transfer |
| `ruleset-merge-pre-move.json` | `gh api repos/sankalp404/axiomfolio/rulesets/11622822` | Same `rules` array post-move |
| `ruleset-review-pre-move.json` | `gh api repos/sankalp404/axiomfolio/rulesets/11709753` | Same `rules` array post-move |
| `secrets-pre-move.txt` | `gh secret list --repo sankalp404/axiomfolio` | 3 names; **values do NOT migrate**, must be re-set at new repo or org |

Use `diff <(jq -S . <pre>) <(jq -S . <post>)` for clean, formatting-
independent comparison.

These files are intentionally checked in (not gitignored) so the
post-move PR can produce a verifiable, reviewable diff against them.
