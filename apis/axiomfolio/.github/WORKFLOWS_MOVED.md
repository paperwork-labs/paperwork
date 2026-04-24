# Workflows moved to repo root

As of **2026-04-23**, AxiomFolio was absorbed into the paperwork monorepo
at `apis/axiomfolio/`. GitHub Actions only reads workflows from
`.github/workflows/` at the **repo root** — so every `.yml` in
`apis/axiomfolio/.github/workflows/` is now **inert**.

## Where did they go?

| Old path (inert) | New path (live) |
|---|---|
| `apis/axiomfolio/.github/workflows/ci.yml` | `.github/workflows/axiomfolio-ci.yml` |
| `apis/axiomfolio/.github/workflows/agent-auto-pr.yml` | _not ported yet — review & port_ |
| `apis/axiomfolio/.github/workflows/agent-merge-after-ci.yml` | _not ported yet — review & port_ |
| `apis/axiomfolio/.github/workflows/agent-update-branch.yml` | _not ported yet — review & port_ |
| `apis/axiomfolio/.github/workflows/dependabot-automerge.yml` | _not ported yet — may be redundant with paperwork's root auto-merge_ |
| `apis/axiomfolio/.github/workflows/pre-merge-deploy-gate.yml` | _not ported yet — review & port_ |
| `apis/axiomfolio/.github/workflows/request-copilot-review.yml` | _not ported yet — review & port_ |

## Why leave the inert files in-tree?

Git history. Deleting them fragments `git log --follow` for the ported
versions. They cost nothing and are clearly labeled here.

## Ports

The live root workflow is path-filtered to `apis/axiomfolio/**` and
runs with `working-directory: apis/axiomfolio` so relative Makefile /
docker compose paths resolve unchanged.

## Follow-ups

- Port the agent coordination workflows once we decide whether they
  should run per-app or repo-wide. Most likely they need a repo-wide
  rewrite rather than an axiomfolio-prefixed duplicate.
- Reconcile `dependabot-automerge.yml` with paperwork's
  `.github/workflows/auto-merge.yaml` (likely delete axiomfolio's copy).
