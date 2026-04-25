---
owner: agent-ops
last_reviewed: 2026-04-24
doc_kind: reference
domain: docs
status: active
---
# Runbook template

Drop a copy of this file into `docs/<product>/runbooks/<slug>.md` (or
`docs/runbooks/<slug>.md` for company-wide ops) when documenting a
recurring failure mode. Every runbook in the repo should follow this
shape so an on-call human or persona can resolve an incident without
context-switching.

If a section truly does not apply, write `_n/a — <reason>_` instead of
deleting it. The CI check `scripts/check_runbook_template.py` enforces
section presence (warn-only at first, escalating to a hard fail per
sprint plan).

## Anatomy

1. **Frontmatter** — `doc_kind: runbook`, owner persona, last_reviewed,
   severity, and any related runbooks.
2. **One-line summary** under the H1 — what failure this resolves.
3. **When this runbook fires** — concrete tile names, log lines, alert
   names, dashboard URLs. No vague wording.
4. **Severity ladder** — when it's YELLOW vs RED, who pages whom.
5. **Prerequisites** — tokens, dashboard access, repo access, kubectl
   contexts. Anything that would block a fresh on-call.
6. **Triage (≤5 min)** — one or two copy-pasteable commands that
   classify the incident.
7. **Resolution paths** — one numbered procedure per root cause. Stop
   the runbook from becoming a choose-your-own-adventure: branches
   should appear as separate `## Path: …` sections.
8. **Verification** — how you prove the fix worked. Always automated
   when possible (curl `/health`, dashboard tile, log query).
9. **Rollback** — what to do if a step in §7 made things worse.
10. **Escalation** — explicit human contact / Slack channel + when to
    invoke. "On-call" is not enough; name the channel.
11. **Post-incident** — what to log, where (KNOWLEDGE.md, handoff,
    Linear, sprint log).
12. **Appendix** — SQL queries, env var reference, related dashboards.

## Skeleton

```markdown
---
owner: <persona>
last_reviewed: YYYY-MM-DD
doc_kind: runbook
domain: <axiomfolio | filefree | infra | brain | tax | …>
status: active
severity_default: yellow   # yellow | red
related_runbooks:
  - docs/runbooks/<other>.md
---
# Runbook: <Failure Mode in Title Case>

> One-line summary: what's broken, who notices, how long this should take to fix.

## When this fires

Concrete signals. Examples:

- Studio `/admin/infrastructure` shows `Render` red for ≥ 5 min
- `app.tasks.deploys.poll_deploy_health` writes `is_poll_error=True` rows
- Brain logs `RateLimitError` ≥ 5 in 1 min for `persona=cpa`

## Severity ladder

| Level | Trigger | Action |
|---|---|---|
| YELLOW | <signal> | <action> — DM on-call, no merge halt |
| RED | <signal> | <action> — `#incidents` page, halt merges |

## Prerequisites

- Access to `<dashboard>` (link)
- `<TOKEN_NAME>` env var locally; export from `infra/env.dev`
- `gh auth status` clean

## Triage (≤5 min)

```bash
# Classify in one shot.
<command>
```

If `<output X>` → §"Path: code regression".
If `<output Y>` → §"Path: vendor outage".
If timed out → §"Path: telemetry outage".

## Path: <root cause A>

1. <action>
2. <action>
3. Verify: <command>

## Path: <root cause B>

1. …

## Verification

- `curl https://<svc>/health` returns `200 {"status":"ok"}`.
- `<dashboard tile>` returns to GREEN within one Beat cycle (5 min).
- No new error rows in the last 5 minutes:

```sql
SELECT count(*) FROM <table> WHERE created_at > now() - interval '5 minutes' AND status='error';
```

## Rollback

- `git revert <sha>` if §"code regression" path was taken and didn't work.
- Restore previous deploy via Render dashboard → Service → Deploys → previous → "Redeploy".
- If a config change was the fix, `vercel env rm <NAME>` and redeploy.

## Escalation

- Primary: `#ops` Slack channel — DM `@<owner>`.
- Vendor outage: file ticket at `<vendor support URL>`, link the ticket in `#ops`.
- Page-out (RED only): trigger PagerDuty `incident-commander` schedule.

## Post-incident

- Add a row to `docs/KNOWLEDGE.md` under "Recent incidents" with the
  pattern and the runbook section that handled it.
- If a new guardrail emerged, file a `.cursor/rules/*.mdc` update PR.
- If the runbook itself was wrong/stale, update it before closing the
  ticket. Bump `last_reviewed`.

## Appendix

### Useful dashboards

- Studio: `/admin/infrastructure`
- Render: <https://dashboard.render.com>
- Vercel: <https://vercel.com/paperwork-labs>

### Required env vars

- `<NAME>` — purpose, where stored, rotation cadence

### Related queries

```sql
-- <description>
SELECT …;
```
```

## What NOT to do in a runbook

- Don't paste a full architecture explanation. Link to the architecture
  doc instead.
- Don't include passwords, tokens, or unredacted PII. Use placeholders.
- Don't write "this should never happen". Every runbook in the repo
  exists because it did happen.
- Don't make every step manual when a one-liner works. Prefer
  `make <target>` shortcuts and add them to `Makefile` so the next
  on-call can paste-execute.

## Linting

`scripts/check_runbook_template.py` enforces section presence on all
files with `doc_kind: runbook`. Warn-only initially; will harden once
the existing runbooks are migrated.
