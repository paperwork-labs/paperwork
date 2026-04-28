# Workstreams board (Track Z)

Single drag-reorderable list of every active workstream. The Brain dispatcher reads the order on a cadence and pushes cheap subagents at the top-N. `percent_done` is computed ambiently from merged-PR `brief_tag` matches.

## Files

| File | Role |
| --- | --- |
| [`apps/studio/src/data/workstreams.json`](../../apps/studio/src/data/workstreams.json) | Canonical data — versioned in git, edited via PR |
| [`apps/studio/src/lib/workstreams/schema.ts`](../../apps/studio/src/lib/workstreams/schema.ts) | Zod schema, types, dispatch helper, KPI helper |
| [`apps/studio/src/lib/workstreams/__tests__/schema.test.ts`](../../apps/studio/src/lib/workstreams/__tests__/schema.test.ts) | Vitest suite — fails CI if `workstreams.json` ever drifts from the schema |
| `apps/studio/src/app/admin/workstreams/page.tsx` | (TBD — subagent PR) Server component, loads JSON |
| `apps/studio/src/app/admin/workstreams/workstreams-client.tsx` | (TBD — subagent PR) Client, drag-reorder via `@dnd-kit/core` + `@dnd-kit/sortable` |
| `apps/studio/src/app/api/admin/workstreams/reorder/route.ts` | (TBD — subagent PR) POSTs new order to Brain (which opens a PR) |
| `apis/brain/app/routers/workstreams.py` | (TBD — subagent PR) `POST /api/v1/workstreams/reorder` — opens PR updating `workstreams.json` |
| `apis/brain/app/schedulers/workstream_dispatcher.py` | (TBD — subagent PR) APScheduler job, 30 min cadence |
| `apis/brain/app/services/workstream_progress.py` | (TBD — subagent PR) Hourly job, recomputes `percent_done` |

## Schema overview

```ts
type Workstream = {
  id: string;                    // WS-NN-kebab-slug, unique, stable
  title: string;                 // <= 100 chars
  track: string;                 // SSO-Q2 track letter (A, B1, F3, K, M, ...)
  priority: number;              // unique, 0 = highest; reordered via DnD
  status: "pending" | "in_progress" | "blocked" | "completed";
  percent_done: number;          // 0–100, computed by workstream_progress.py
  owner: "brain" | "founder" | "opus";
  brief_tag: string;             // `track:<slug>` — appears in PR body, drives % done
  blockers: string[];            // free-form (or "WS-NN-…" cross-refs)
  last_pr: number | null;        // last PR number against this workstream
  last_activity: string;         // ISO datetime
  last_dispatched_at: string | null;  // ISO datetime — Brain cooldown source
  notes: string;                 // <= 500 chars
  estimated_pr_count: number | null;
  github_actions_workflow: string | null;  // workflow_dispatch target
  related_plan: string | null;   // ~/.cursor/plans slug for context
};
```

## Owner taxonomy

| Owner | Means | Dispatchable |
| --- | --- | --- |
| `brain` | Mechanical or well-bounded — cheap subagent (composer-2-fast) executes via `agent-sprint-runner` workflow | **YES** — top of dispatch queue when criteria met |
| `founder` | Human action only (DNS, secret rotation, Vercel project create, brand iteration) | NO — surfaces in board with action link |
| `opus` | Requires Opus judgment in chat (architecture, schema design, integration glue) | NO — surfaces in board for Opus to claim |

## Status taxonomy

| Status | Meaning |
| --- | --- |
| `pending` | Not started; eligible for dispatch |
| `in_progress` | At least one PR open or merged against the `brief_tag`; still dispatchable when below 100 |
| `blocked` | Explicit blocker; never dispatched. Schema enforces `blockers.length > 0`. |
| `completed` | Done. Schema enforces `percent_done === 100`. Read-only in UI. |

## Brain dispatch contract

`apis/brain/app/schedulers/workstream_dispatcher.py` (TBD — to be authored by subagent) runs every 30 min:

```text
load workstreams.json
filter to (owner=brain) AND (status in {pending, in_progress}) AND (blockers empty)
filter to (last_dispatched_at is null OR last_dispatched_at < now - 4h)
sort ascending by priority
take first 3
for each:
  POST GitHub Actions workflow_dispatch:
    workflow: workstream.github_actions_workflow (default 'agent-sprint-runner')
    inputs:
      brief_tag: workstream.brief_tag
      title: workstream.title
      notes: workstream.notes
      related_plan: workstream.related_plan
  patch workstream.last_dispatched_at = now()
  append { workstream_id, dispatched_at, run_id } to dispatch_log
```

The TypeScript `dispatchableWorkstreams()` helper in `schema.ts` is the **canonical reference implementation**. The Python dispatcher must produce the same selection for the same input.

## Progress contract

`apis/brain/app/services/workstream_progress.py` (TBD — subagent) runs hourly:

```text
load workstreams.json
for each workstream:
  query GitHub for PRs whose body contains workstream.brief_tag
  count merged_prs and open_prs
  percent_done = clamp(0, 100, round(merged_prs / max(estimated_pr_count, merged_prs + open_prs)) * 100)
  if percent_done == 100 AND all open_prs closed:
    set status = completed
  patch percent_done, last_pr, last_activity
```

Subagents authoring PRs against a workstream **must** include the `brief_tag` in the PR body for progress tracking to work.

## Reorder contract

UI drag-reorder posts to `POST /api/admin/workstreams/reorder` (Studio Next.js route). Studio forwards the new ordering to Brain (`POST /api/v1/workstreams/reorder` with internal token), which opens a PR updating `workstreams.json`. Studio prod **never writes to git directly** — every change is a reviewable PR.

## KPIs (top of board)

Computed by `computeKpis()` in `schema.ts`:

- `total` — all workstreams
- `active` — `pending` + `in_progress`
- `blocked` — `status === "blocked"`
- `completed` — `status === "completed"`
- `avg_percent_done` — mean of all `percent_done` values

## Adding a workstream

1. Edit `apps/studio/src/data/workstreams.json` directly in a PR (or open a UI "Add" modal once it exists).
2. Pick the next free `WS-NN` id and a unique `priority` (insert anywhere in the order; renumber later).
3. Set `status: "pending"`, `percent_done: 0`, `owner` per taxonomy.
4. Pick a `brief_tag` of the form `track:<kebab-slug>` that future subagents will include in their PR bodies.
5. CI (`schema.test.ts`) catches malformed entries.

## `agent-sprint-runner.yml` workflow contract

[`.github/workflows/agent-sprint-runner.yml`](../../.github/workflows/agent-sprint-runner.yml) is the `workflow_dispatch` entry point that the Brain dispatcher invokes. v1 behaviour is intentionally conservative: it opens a "task ticket" PR (label `agent-ticket`) whose body is the rendered brief; a human or downstream agent picks the ticket up. v2 will swap the ticket-PR step for a real cheap-subagent invocation (Cursor Cloud Agent, Codex CLI, or similar) without changing the dispatch contract.

### Inputs (mirror the Brain dispatcher payload)

| Input | Required | Source |
| --- | --- | --- |
| `brief_tag` | yes | `workstream.brief_tag` |
| `title` | yes | `workstream.title` |
| `notes` | no | `workstream.notes` |
| `related_plan` | no | `workstream.related_plan` |
| `model` | no | dispatcher passes `composer-2-fast`; choices: `composer-2-fast`, `composer-1.5`, `gpt-5.5-medium` |
| `max_open_tickets_per_workstream` | no | guardrail cap (default `1`) |

### Guardrails enforced inside the workflow

1. `brief_tag` must match `^track:[a-z0-9-]+$`.
2. Workstream must exist in `apps/studio/src/data/workstreams.json`.
3. Workstream `status` must not be `blocked` or `completed`.
4. Workstream `owner` must be `brain`.
5. Open ticket PR count for the `brief_tag` must be `< max_open_tickets_per_workstream` (skipped with a warning if at/above cap).

### Standing rules embedded in every brief

The workflow renders the same standing rules into every ticket body. Update them in one place by editing `agent-sprint-runner.yml`:

- ONE concern per PR, type-prefixed title.
- PR body must literally contain the `brief_tag` (so `workstream_progress.py` counts it).
- No hand-authored SVGs.
- No `BRAIN_OWNS_*` flag gating.
- `pnpm install --frozen-lockfile --ignore-scripts` must pass (`code-quality.lockfile-gate`).
- `apps/*/vercel.json` must satisfy `scripts/verify-vercel-json-canon.mjs`.
- Stories live under `apps/design/src/stories/` only.

### Brain dispatch_log webhook (best-effort)

When `BRAIN_API_URL` and `BRAIN_INTERNAL_TOKEN` repo secrets are set, the workflow POSTs the run + ticket URL to `${BRAIN_API_URL}/api/v1/workstreams/dispatch-log`. Failure is non-fatal — the hourly `workstream_progress.py` job will backfill from the `agent-ticket`-labelled PR list either way. (Endpoint is queued for the next Brain PR; until it lands, the warning is expected.)

## Future queue

- Brain `/api/v1/workstreams/dispatch-log` POST endpoint (companion to the workflow above)
- Replace the v1 ticket-PR step with a real cheap-subagent invocation
- Optimistic UI reorder with debounced PR creation
- Per-workstream subagent dispatch log inline in the row
- "Unblock me" action that posts a comment on the blocking workstream
- Auto-promote `pending → in_progress` when first PR matches the `brief_tag`
- Auto-detect new SSO Q2 plan tracks and seed pending entries
