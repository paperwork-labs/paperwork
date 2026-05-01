---
last_reviewed: 2026-05-01
---

# Brain Self-Prioritization

**TL;DR:** How Brain proposes workstream candidates from objectives, POS, and other signals before they become tracker entries. Read when you promote or reject a candidate via the admin API.

Brain self-prioritization is the Phase G2 loop that proposes workstreams before
they become real tracker entries. It writes proposals to
`apis/brain/data/workstream_candidates.json`; the founder reviews them before
promotion to `apps/studio/src/data/workstreams.json`.

## Signal Gathering

`apis/brain/app/services/self_prioritization.py` gathers candidate signals from:

- `docs/strategy/OBJECTIVES.yaml`: objectives with `progress < 50` or stale
  review state older than 30 days.
- `apis/brain/data/operating_score.json`: measured POS pillars where
  `current.pillars.<pillar>.score < 70`.
- `apis/brain/data/procedural_memory.yaml`: orchestrator rules whose placeholder
  weekly use count is above five.
- `docs/STACK_AUDIT_2026-Q2.md`: rows with a `REPLACE` verdict.
- `apis/brain/data/pr_outcomes.json`: merged PRs whose 24-hour outcome has
  `regressed=true`.

Missing source files are treated as no signal from that source. Malformed
candidate persistence raises instead of falling back to an empty list.

## Scoring

Each signal receives a 0-100 composite score:

- Impact weight: `critical=40`, `high=25`, `medium=15`, `low=5`.
- Urgency: `0-30` points from signal age or review staleness.
- Effort discount: `-10` points for each estimated effort day above five.
- Objective alignment: `+20` when directly traceable to an objective.

The service deduplicates by `source_signal + source_ref` and records the top
five by default. The daily APScheduler job runs at `08:00 UTC`.

## Promote A Candidate

Use the admin endpoint:

```bash
curl -X POST \
  -H "X-Brain-Secret: $BRAIN_API_SECRET" \
  "$BRAIN_API_URL/api/v1/admin/workstream-candidates/C-2026-04-29-001/promote"
```

Promotion requires `status="proposed"`. Brain appends a new pending workstream
with `proposed_by_brain: true`, then marks the candidate
`approved_to_workstream` with `promoted_workstream_id`.

## Reject A Candidate

Use the admin endpoint with a founder reason:

```bash
curl -X POST \
  -H "X-Brain-Secret: $BRAIN_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"founder_reason":"Not aligned with this week\u0027s priorities."}' \
  "$BRAIN_API_URL/api/v1/admin/workstream-candidates/C-2026-04-29-001/reject"
```

Rejection requires `status="proposed"` and stores the reason on the candidate
record for auditability.
