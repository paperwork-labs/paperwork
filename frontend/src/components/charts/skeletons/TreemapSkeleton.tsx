/**
 * TreemapSkeleton — 4×3 grid of variable-size rectangles that mimic the
 * shape of a real treemap (e.g. holdings allocation, sector heatmap).
 *
 * Sizes are deterministic (a fixed weight matrix, no `Math.random`) so
 * server-side renders and snapshot tests stay stable.
 */
import * as React from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export interface TreemapSkeletonProps {
  className?: string;
  /** Container height in pixels. Defaults to 360. */
  height?: number;
  label?: string;
}

// Row weights (one per row) and per-row column weights. All within-row
// column weights sum to ~1.0 so flex-basis maps cleanly. Hand-tuned to
// look "treemap-natural" rather than uniform.
const ROW_WEIGHTS = [0.42, 0.33, 0.25] as const;
const COL_WEIGHTS: ReadonlyArray<ReadonlyArray<number>> = [
  [0.5, 0.28, 0.22],
  [0.22, 0.42, 0.22, 0.14],
  [0.34, 0.34, 0.22, 0.1],
];

export function TreemapSkeleton({
  className,
  height = 360,
  label = "treemap",
}: TreemapSkeletonProps) {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-live="polite"
      data-testid="treemap-skeleton"
      className={cn(
        "relative w-full overflow-hidden rounded-lg border border-border/40 bg-card/40 p-1",
        className,
      )}
      style={{ height }}
    >
      <span className="sr-only">Loading {label}</span>
      <div className="flex h-full w-full flex-col gap-1">
        {ROW_WEIGHTS.map((rowWeight, rowIdx) => (
          <div
            key={rowIdx}
            className="flex w-full gap-1"
            style={{ flexBasis: `${rowWeight * 100}%` }}
            aria-hidden="true"
          >
            {COL_WEIGHTS[rowIdx].map((colWeight, colIdx) => (
              <Skeleton
                key={colIdx}
                className="h-full rounded-md"
                style={{ flexBasis: `${colWeight * 100}%` }}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
