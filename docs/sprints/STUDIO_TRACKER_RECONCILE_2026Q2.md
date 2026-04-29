# Studio tracker reconcile — WS-69 PR A (2026 Q2)

## Rationale

Overview tiles (`trackers-rail`) filtered plans with `pl.status === "active"` while generated tracker data uses `in_progress`, so active plan counts read **0** despite real in-flight work. Sprint tiles used raw `status === "active"` / `"shipped"` on `tracker-index.json`, diverging from `/admin/sprints`, which already used `sprint-reconcile` pill logic.

This PR centralizes semantics in `apps/studio/src/lib/tracker-reconcile.ts`, keeps `sprint-reconcile.ts` as a one-release re-export shim, and aligns Tasks / Products / Sprints / Overview numbers.

## Files touched

| Area | Path |
|------|------|
| Reconciler | `apps/studio/src/lib/tracker-reconcile.ts` |
| Shim | `apps/studio/src/lib/sprint-reconcile.ts` |
| Tracker helpers | `apps/studio/src/lib/tracker.ts` |
| Overview tiles | `apps/studio/src/app/admin/_components/trackers-rail.tsx` |
| Products roll-up | `apps/studio/src/app/admin/products/page.tsx` |
| Tasks roll-up | `apps/studio/src/app/admin/tasks/page.tsx` |
| Sprints | `apps/studio/src/app/admin/sprints/page.tsx` |
| Workstreams data | `apps/studio/src/data/workstreams.json` (ISO timestamp normalization) |
| Workstreams board marker | `apps/studio/src/app/admin/workstreams/workstreams-client.tsx` |
| IA stubs | `apps/studio/src/app/admin/expenses/page.tsx`, `brain/{personas,conversations,self-improvement}/page.tsx` |
| Tests | `apps/studio/src/lib/__tests__/tracker-reconcile.test.ts`, `apps/studio/e2e/admin-routes.spec.ts` |

## Before / after (representative)

| Metric | Before (Overview tile logic) | After (reconciler) |
|--------|------------------------------|---------------------|
| Active plans | `status === "active"` only → often **0** | `in_progress` **or** legacy `active` |
| Active sprints | raw `status === "active"` | `isSprintActiveForUi` (planned / in progress / legacy active pill) |
| Shipped sprints | raw `status === "shipped"` | `isSprintShippedForUi` (pill `shipped`, incl. `effective_status`) |

Exact counts match `/admin/sprints`, `/admin/products` roll-up line, and Tasks critical-date open count.

## Owner

Brain / Studio platform (WS-69 PR A).
