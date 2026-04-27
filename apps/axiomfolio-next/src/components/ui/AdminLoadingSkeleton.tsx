import { Skeleton } from "@/components/ui/skeleton";

/**
 * Route-level loading placeholder for lazy-loaded admin / operator client trees.
 * Keep dependency-free of heavy charts so the shell stays in the main chunk.
 */
export function AdminLoadingSkeleton() {
  return (
    <div
      className="space-y-4 p-4"
      aria-busy="true"
      aria-label="Loading"
    >
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-40 w-full" />
      <div className="grid gap-3 md:grid-cols-2">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
      </div>
    </div>
  );
}
