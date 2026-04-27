/**
 * `ChartCrosshair` — chart-library-agnostic crosshair overlay.
 *
 * Pure rendering: the consumer measures their container (e.g. via
 * `ResizeObserver`) and tracks pointer position with `useCrosshairTracking`,
 * then passes `width / height / x / y` here. We render an absolutely-
 * positioned SVG with `pointer-events: none` so chart interactions still
 * land on the underlying canvas/SVG.
 *
 * The companion hook `useCrosshairTracking` returns ergonomic handlers for
 * the common case where a single container element owns the chart.
 *
 * Color resolution:
 *   - If the consumer passes `color`, use it.
 *   - Else read `--chart-axis` from `:root` at mount, then re-resolve when
 *     either the color palette changes (event `axiomfolio:color-palette-
 *     change` from `useUserPreferences`) or the `.dark` class on
 *     `<html>` toggles (theme switch).
 *   - The token is space-separated R G B / A, so we wrap with `rgb(...)`.
 *   - Fall back to slate-400 (#94a3b8) if the token is unset.
 */
import * as React from "react";
import { motion, useReducedMotion } from "framer-motion";

import { DURATION } from "@/lib/motion";
import { cn } from "@/lib/utils";

const FALLBACK_AXIS_COLOR = "#94a3b8";
const AXIS_TOKEN = "--chart-axis";
const PALETTE_CHANGE_EVENT = "axiomfolio:color-palette-change";

export interface ChartCrosshairProps {
  /** Container width in px. */
  width: number;
  /** Container height in px. */
  height: number;
  /** Pointer x in container-relative px, or `null` to hide. */
  x: number | null;
  /** Pointer y in container-relative px, or `null` to hide. */
  y: number | null;
  /** Stroke color. Defaults to `rgb(var(--chart-axis))` resolved at runtime. */
  color?: string;
  /** Defaults to a 3px-on, 3px-off dash. */
  strokeDasharray?: string;
  /** Render the horizontal line. Default `true`. */
  showHorizontal?: boolean;
  /** Render the vertical line. Default `true`. */
  showVertical?: boolean;
  /** Visually-hidden text announced to screen readers. */
  announceText?: string;
  className?: string;
}

function resolveAxisColor(): string {
  if (typeof window === "undefined") return FALLBACK_AXIS_COLOR;
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue(AXIS_TOKEN)
    .trim();
  if (raw.length === 0) return FALLBACK_AXIS_COLOR;
  // Token is stored as space-separated `R G B / A`, e.g. "15 23 42 / 0.35".
  // Wrap with rgb() so it's a valid CSS color anywhere we plug it in.
  return raw.startsWith("rgb") || raw.startsWith("#") || raw.startsWith("hsl")
    ? raw
    : `rgb(${raw})`;
}

function useAxisColor(explicit?: string): string {
  const [color, setColor] = React.useState<string>(
    () => explicit ?? FALLBACK_AXIS_COLOR,
  );
  React.useEffect(() => {
    if (explicit) {
      setColor(explicit);
      return;
    }
    const refresh = () => setColor(resolveAxisColor());
    refresh();

    // The palette toggle dispatches a custom event (see `useUserPreferences`).
    window.addEventListener(PALETTE_CHANGE_EVENT, refresh);

    // The light/dark theme toggles the `.dark` class on <html>; observe so
    // the crosshair re-resolves the now-different `--chart-axis` value.
    const root = document.documentElement;
    const observer = new MutationObserver(refresh);
    observer.observe(root, { attributes: true, attributeFilter: ["class", "data-palette"] });

    return () => {
      window.removeEventListener(PALETTE_CHANGE_EVENT, refresh);
      observer.disconnect();
    };
  }, [explicit]);
  return color;
}

export function ChartCrosshair({
  width,
  height,
  x,
  y,
  color,
  strokeDasharray = "3 3",
  showHorizontal = true,
  showVertical = true,
  announceText,
  className,
}: ChartCrosshairProps) {
  const reducedMotion = useReducedMotion();
  const stroke = useAxisColor(color);

  if (x === null && y === null) return null;
  if (width <= 0 || height <= 0) return null;

  const hasX = x !== null && Number.isFinite(x);
  const hasY = y !== null && Number.isFinite(y);

  return (
    <>
      <motion.svg
        role="presentation"
        aria-hidden
        className={cn("pointer-events-none absolute left-0 top-0", className)}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        initial={reducedMotion ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={
          reducedMotion ? { duration: 0 } : { duration: DURATION.fast }
        }
      >
        {showVertical && hasX && (
          <line
            x1={x as number}
            x2={x as number}
            y1={0}
            y2={height}
            stroke={stroke}
            strokeWidth={1}
            strokeDasharray={strokeDasharray}
            shapeRendering="crispEdges"
          />
        )}
        {showHorizontal && hasY && (
          <line
            x1={0}
            x2={width}
            y1={y as number}
            y2={y as number}
            stroke={stroke}
            strokeWidth={1}
            strokeDasharray={strokeDasharray}
            shapeRendering="crispEdges"
          />
        )}
      </motion.svg>
      {/*
        Live region rendered as a SIBLING of the SVG, not inside it.
        - The SVG is `aria-hidden` (it's purely decorative); a live region
          INSIDE an aria-hidden subtree is not announced by AT.
        - `<foreignObject>` is also fragile / inconsistently supported by
          screen readers, so we render an HTML element directly.
        - `ChartAnnouncer` is the canonical primitive for chart-wide
          announcements; this fallback exists so a stand-alone crosshair
          (e.g. in a story) can still announce hover state without
          forcing the consumer to wire a separate announcer.
      */}
      {announceText ? (
        <span
          className="sr-only-live"
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          {announceText}
        </span>
      ) : null}
    </>
  );
}

export interface UseCrosshairTrackingReturn {
  x: number | null;
  y: number | null;
  onMouseMove: (e: React.MouseEvent<HTMLElement>) => void;
  onMouseLeave: (e: React.MouseEvent<HTMLElement>) => void;
}

/**
 * Track pointer position relative to a container element. Use the returned
 * `x` / `y` (in container-relative px) directly with `<ChartCrosshair />`.
 * The consumer wires `onMouseMove` and `onMouseLeave` on the same element
 * that owns the chart.
 */
export function useCrosshairTracking(): UseCrosshairTrackingReturn {
  const [coords, setCoords] = React.useState<{
    x: number | null;
    y: number | null;
  }>({ x: null, y: null });

  const onMouseMove = React.useCallback(
    (e: React.MouseEvent<HTMLElement>) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const nx = e.clientX - rect.left;
      const ny = e.clientY - rect.top;
      // Bail if pointer is outside the bounds (can happen on capture).
      if (
        nx < 0 ||
        ny < 0 ||
        nx > rect.width ||
        ny > rect.height
      ) {
        setCoords({ x: null, y: null });
        return;
      }
      setCoords({ x: nx, y: ny });
    },
    [],
  );

  const onMouseLeave = React.useCallback((_e: React.MouseEvent<HTMLElement>) => {
    setCoords({ x: null, y: null });
  }, []);

  return { x: coords.x, y: coords.y, onMouseMove, onMouseLeave };
}

export default ChartCrosshair;
