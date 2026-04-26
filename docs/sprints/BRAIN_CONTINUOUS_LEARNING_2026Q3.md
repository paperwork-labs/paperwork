---
owner: brain
last_reviewed: 2026-04-26
doc_kind: sprint
domain: company
status: active
sprint:
  start: 2026-04-26
  end: 2026-07-01
  duration_weeks: 10
  pr: null
  ships: [brain]
  personas: [engineering, agent-ops]
  budget_usd: 0
  budget_used_usd: 0
---

# Brain continuous learning (ambient signals)

## Goal

Ship three low-noise, idempotent loops so Paperwork Brain gains memory episodes every week from **merged PRs**, **decision records**, and **postmortems** — not only from sprint `## What we learned` bullets and quarterly docs.

## Outcome (loops)

1. **Merged PRs** — `source=merged_pr` (metadata tag). Brain calls the GitHub API for PRs merged in the last 7 days (up to 50), summarizes title + truncated body, labels, top-level path buckets, author, merge time. **Cadence:** every 6h (APScheduler, configurable via `SCHEDULER_MERGED_PRS_HOURS`). **Idempotency:** `source_ref=pr-<number>` + JSON pin `apis/brain/data/ingested_prs.json`. **Local check:** `python3 scripts/ingest_merged_prs.py --dry-run --limit 5` (requires `BRAIN_API_SECRET`).

2. **Decisions** — `source=decision`. Walks `docs/decisions/**`, `**/DECISIONS.md`, `**/decisions/**`, and any `docs/**` file whose frontmatter includes `doc_kind: decision`. **Cadence:** daily 03:00 UTC. **Idempotency:** SHA-256 of markdown body (excluding frontmatter split for hashing — body only) → `ingested_decisions.json`.

3. **Postmortems** — `source=postmortem`. Ingests abandoned sprints (`status: abandoned`) with `## Postmortem` / `## Post-mortem` / `## What went wrong`, and `docs/runbooks/*.md` blocks under `## Incident` that include a date. **Cadence:** daily 03:30 UTC. **Idempotency:** content hash pin `ingested_postmortems.json` + `source_ref` from hash.

**Admin API (on-demand / CI):** `POST /admin/ingest-merged-prs`, `POST /admin/ingest-decisions`, `POST /admin/ingest-postmortems` (same `X-Brain-Secret` as other admin routes).

## Success metrics (weekly)

| Source | Target episodes / week (initial) | How to measure |
| --- | --- | --- |
| merged_pr | ≥ 3 | Studio `/admin/overview` or `GET /admin/memory/episodes?source_prefix=merged` (filter by `source` column) |
| decision | ≥ 0–2 | Same, `source=decision` |
| postmortem | ≥ 0–1 (spiky) | Same, `source=postmortem` |

Tune targets after 2 weeks of data.

## Rollout

1. Land PR; deploy `brain-api` with `REPO_ROOT` pointing at the monorepo on disk (required for file-based ingesters) and `GITHUB_TOKEN` for merged-PR fetch.
2. Backfill on demand: run the three `scripts/ingest_*.py` once with secrets (optional `--limit`).
3. Watch logs for `merged_prs_ingest`, `ingest_decisions_daily`, `ingest_postmortems_daily` job names.

## Tracks

- **Engineering:** service module `app/services/continuous_learning.py`, schedulers under `app/schedulers/`, thin HTTP scripts under `scripts/`.
- **Agent-ops:** document success metrics; adjust `SCHEDULER_MERGED_PRS_HOURS` if API load is a concern (default 6h is conservative).

## What we learned

- (Append only during the sprint.)

## Follow-ups

- Optional: GitHub org webhook → immediate merged-PR episode for hot PRs (out of scope for this sprint).
