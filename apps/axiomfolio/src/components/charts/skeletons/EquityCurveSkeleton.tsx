/**
 * EquityCurveSkeleton — equity curve placeholder with a secondary drawdown
 * sub-chart beneath it (1/3 of total height). Mirrors the layout used by
 * the real `EquityCurveChart` so the page does not jump on data load.
 */
import * as React from "react";
import { motion, useReducedMotion } from "framer-motion";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export interface EquityCurveSkeletonProps {
  className?: string;
  /** Combined height of equity + drawdown panels. Default 420 px. */
  height?: number;
  label?: string;
}

const EQUITY_PATH =
  "M0,30 C10,28 18,24 28,22 S46,14 58,12 76,8 86,6 100,4";
const DRAWDOWN_PATH =
  "M0,2 C8,4 14,12 24,10 S42,18 54,14 70,22 82,18 100,16";

// Each grid-line entry positions a divider absolutely. The final entry
// uses `bottom: 0` instead of `top: 100%` so the bottom-most line lands
// flush with the panel edge instead of one pixel below it.
const EQUITY_GRID_LINES: ReadonlyArray<{
  key: string;
  style: React.CSSProperties;
}> = [
  { key: "g0", style: { top: "0%" } },
  { key: "g1", style: { top: "25%" } },
  { key: "g2", style: { top: "50%" } },
  { key: "g3", style: { top: "75%" } },
  { key: "g4", style: { bottom: 0 } },
];

const DRAWDOWN_GRID_LINES: ReadonlyArray<{
  key: string;
  style: React.CSSProperties;
}> = [
  { key: "d0", style: { top: "0%" } },
  { key: "d1", style: { top: "50%" } },
  { key: "d2", style: { bottom: 0 } },
];

function GhostLine({
  d,
  reduced,
  className,
}: {
  d: string;
  reduced: boolean | null;
  className?: string;
}) {
  return (
    <svg
      className={cn("absolute inset-0 h-full w-full", className)}
      viewBox="0 0 100 36"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <motion.path
        d={d}
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
                duration: 1.8,
                ease: "easeInOut",
                repeat: Infinity,
                repeatType: "loop",
              }
        }
      />
    </svg>
  );
}

export function EquityCurveSkeleton({
  className,
  height = 420,
  label = "equity curve",
}: EquityCurveSkeletonProps) {
  const reduced = useReducedMotion();
  const equityHeight = Math.round((height * 2) / 3);
  const drawdownHeight = height - equityHeight;
  return (
    <div
      role="status"
      aria-busy="true"
      aria-live="polite"
      data-testid="equity-curve-skeleton"
      className={cn(
        "relative w-full overflow-hidden rounded-lg border border-border/40 bg-card/40",
        className,
      )}
      style={{ height }}
    >
      <span className="sr-only">Loading {label}</span>
      <div
        className="relative grid grid-cols-[60px_1fr]"
        style={{ height: equityHeight }}
      >
        <div className="flex flex-col justify-between px-3 py-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton
              key={i}
              className="h-2.5 w-10 tabular-nums"
              aria-hidden="true"
            />
          ))}
        </div>
        <div className="relative">
          {EQUITY_GRID_LINES.map((line) => (
            <div
              key={line.key}
              data-testid={`equity-curve-skeleton-grid-${line.key}`}
              className="absolute left-0 right-0 border-t border-border/40"
              style={line.style}
              aria-hidden="true"
            />
          ))}
          <GhostLine
            d={EQUITY_PATH}
            reduced={reduced}
            className="text-muted-foreground/50"
          />
        </div>
      </div>
      <div className="border-t border-border/40" aria-hidden="true" />
      <div
        className="relative grid grid-cols-[60px_1fr]"
        style={{ height: drawdownHeight }}
      >
        <div className="flex flex-col justify-between px-3 py-2">
          <Skeleton className="h-2 w-8 tabular-nums" aria-hidden="true" />
          <Skeleton className="h-2 w-8 tabular-nums" aria-hidden="true" />
        </div>
        <div className="relative">
          {DRAWDOWN_GRID_LINES.map((line) => (
            <div
              key={line.key}
              data-testid={`equity-curve-skeleton-grid-${line.key}`}
              className="absolute left-0 right-0 border-t border-border/30"
              style={line.style}
              aria-hidden="true"
            />
          ))}
          <GhostLine
            d={DRAWDOWN_PATH}
            reduced={reduced}
            className="text-muted-foreground/40"
          />
        </div>
      </div>
    </div>
  );
}
