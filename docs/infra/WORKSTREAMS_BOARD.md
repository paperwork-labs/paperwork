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

## Future queue

- Optimistic UI reorder with debounced PR creation
- Per-workstream subagent dispatch log inline in the row
- "Unblock me" action that posts a comment on the blocking workstream
- Auto-promote `pending → in_progress` when first PR matches the `brief_tag`
- Auto-detect new SSO Q2 plan tracks and seed pending entries
