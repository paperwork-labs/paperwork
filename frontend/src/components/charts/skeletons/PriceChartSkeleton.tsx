/**
 * PriceChartSkeleton — chart-shaped placeholder for line / candlestick price
 * charts. Renders the same outer dimensions as the real chart so the
 * surrounding layout never reflows when data arrives.
 *
 * The shimmer comes from the existing `Skeleton` primitive; the only
 * additional motion is a single SVG ghost line that gently traces itself
 * to communicate "data is loading", which is suppressed under
 * `prefers-reduced-motion`.
 */
import * as React from "react";
import { motion, useReducedMotion } from "framer-motion";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export interface PriceChartSkeletonProps {
  className?: string;
  /** Container height in pixels. Defaults to 380, matching our standard
   *  price-chart card height. */
  height?: number;
  /** Used in the screen-reader announcement. Defaults to "price chart". */
  label?: string;
}

const Y_AXIS_TICKS = 4;
const X_AXIS_TICKS = 5;
// Each entry positions a horizontal grid divider. The final entry uses
// `bottom: 0` instead of `top: 100%` so the bottom-most line renders
// flush with the chart's lower edge rather than one pixel beneath it.
const GRID_LINES: ReadonlyArray<{ key: string; style: React.CSSProperties }> = [
  { key: "g0", style: { top: "0%" } },
  { key: "g1", style: { top: "25%" } },
  { key: "g2", style: { top: "50%" } },
  { key: "g3", style: { top: "75%" } },
  { key: "g4", style: { bottom: 0 } },
];

// Smooth pseudo-price path traced over a 100×40 viewBox.
const GHOST_PATH =
  "M0,28 C12,22 20,30 30,24 S52,12 64,18 78,30 90,16 100,20";

export function PriceChartSkeleton({
  className,
  height = 380,
  label = "price chart",
}: PriceChartSkeletonProps) {
  const reduced = useReducedMotion();
  return (
    <div
      role="status"
      aria-busy="true"
      aria-live="polite"
      data-testid="price-chart-skeleton"
      className={cn(
        "relative w-full overflow-hidden rounded-lg border border-border/40 bg-card/40",
        className,
      )}
      style={{ height }}
    >
      <span className="sr-only">Loading {label}</span>
      <div className="absolute inset-0 grid grid-cols-[60px_1fr]">
        <div className="flex flex-col justify-between px-3 py-4">
          {Array.from({ length: Y_AXIS_TICKS }).map((_, i) => (
            <Skeleton
              key={i}
              className="h-2.5 w-10 tabular-nums"
              aria-hidden="true"
            />
          ))}
        </div>
        <div className="relative">
          {GRID_LINES.map((line) => (
            <div
              key={line.key}
              data-testid={`price-chart-skeleton-grid-${line.key}`}
              className="absolute left-0 right-0 border-t border-border/40"
              style={line.style}
              aria-hidden="true"
            />
          ))}
          <svg
            className="absolute inset-0 h-full w-full text-muted-foreground/40"
            viewBox="0 0 100 40"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <motion.path
              d={GHOST_PATH}
              fill="none"
              stroke="currentColor"
              strokeWidth={0.6}
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
              initial={
                reduced
                  ? { pathLength: 1, opacity: 0.6 }
                  : { pathLength: 0, opacity: 0 }
              }
              animate={
                reduced
                  ? { pathLength: 1, opacity: 0.6 }
                  : { pathLength: [0, 1, 1], opacity: [0, 0.7, 0.7] }
              }
              transition={
                reduced
                  ? { duration: 0 }
                  : {
                      duration: 1.6,
                      ease: "easeInOut",
                      repeat: Infinity,
                      repeatType: "loop",
                    }
              }
            />
          </svg>
          <div className="absolute bottom-2 left-2 right-2 flex justify-between">
            {Array.from({ length: X_AXIS_TICKS }).map((_, i) => (
              <Skeleton
                key={i}
                className="h-2 w-8 tabular-nums"
                aria-hidden="true"
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
