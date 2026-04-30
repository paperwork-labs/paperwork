import { Skeleton } from "@paperwork-labs/ui";

/**
 * Route-level Suspense fallback for admin (F-007) — visually distinct from empty states.
 */
export function AdminRouteFallback() {
  return (
    <div
      data-testid="admin-route-fallback"
      className="space-y-4 rounded-xl border border-zinc-800/80 bg-zinc-950/40 px-4 py-6"
      aria-busy="true"
      aria-label="Loading page"
    >
      <Skeleton className="h-9 w-64 max-w-full rounded-md" />
      <Skeleton className="h-4 w-full max-w-2xl rounded-md" />
      <div className="grid gap-3 pt-2 md:grid-cols-2">
        <Skeleton className="h-32 w-full rounded-xl" />
        <Skeleton className="h-32 w-full rounded-xl" />
      </div>
      <Skeleton className="h-48 w-full rounded-xl" />
    </div>
  );
}
