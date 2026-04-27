/**
 * MetricStripSkeleton — horizontal row of N metric tiles, each with a
 * small label and large `tabular-nums` value placeholder. Use above charts
 * or KPI strips while the underlying values load.
 */
import * as React from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export interface MetricStripSkeletonProps {
  className?: string;
  /** Number of metric tiles to render. Defaults to 4. */
  count?: number;
  label?: string;
}

export function MetricStripSkeleton({
  className,
  count = 4,
  label = "key metrics",
}: MetricStripSkeletonProps) {
  // `Array.from({ length })` throws RangeError for negative or
  // non-finite lengths; coerce defensively so a buggy caller cannot
  // bring the page down. Non-integer values are floored so we never
  // try to allocate a fractional length.
  const safeCount =
    Number.isFinite(count) && count >= 0 ? Math.floor(count) : 0;
  return (
    <div
      role="status"
      aria-busy="true"
      aria-live="polite"
      data-testid="metric-strip-skeleton"
      className={cn(
        "flex w-full flex-wrap items-stretch gap-3 sm:flex-nowrap",
        className,
      )}
    >
      <span className="sr-only">Loading {label}</span>
      {Array.from({ length: safeCount }).map((_, i) => (
        <div
          key={i}
          className="flex min-w-0 flex-1 flex-col gap-2 rounded-lg border border-border/40 bg-card/40 p-3"
          aria-hidden="true"
        >
          <Skeleton className="h-3 w-[55%]" />
          <Skeleton className="h-6 w-[75%] tabular-nums" />
        </div>
      ))}
    </div>
  );
}
