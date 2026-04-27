/**
 * `StageOverlay` — translucent stage-color band painted behind the
 * primary price series.
 *
 * The overlay is purely visual and decorative for SR users (`aria-hidden`,
 * `pointer-events-none`, `z-0`). The chart's accessible name and the
 * `ChartAnnouncer` already convey the same information textually.
 *
 * Color resolution follows the same theme/palette reactivity contract
 * as `ChartCrosshair`: pick light/dark hex from `STAGE_HEX[label]` based
 * on the current `<html class="dark">` and re-resolve on:
 *   - palette toggle (`axiomfolio:color-palette-change`)
 *   - dark mode toggle (`<html>` class mutation)
 */
import * as React from 'react';

import { STAGE_HEX } from '@/constants/chart';
import { withAlpha } from '@/lib/holdingChart/themeColors';
import { cn } from '@/lib/utils';
import type { StageSegment } from '@/lib/holdingChart/useHoldingIndicators';

const PALETTE_CHANGE_EVENT = 'axiomfolio:color-palette-change';

const FALLBACK_HEX: [string, string] = STAGE_HEX['1A'];

export interface StageOverlayProps {
  /** Contiguous stage runs sourced from `useHoldingIndicators`. */
  segments: ReadonlyArray<StageSegment>;
  /**
   * Maps a date string (`YYYY-MM-DD` or matching `bucket.startTime`) to a
   * container-relative x in px. The chart owns the actual time→pixel math
   * via `lightweight-charts`' `timeScale().timeToCoordinate`; we stay
   * library-agnostic by accepting it as a function.
   * Return `null` when the time falls off-screen so we can drop the band.
   */
  timeToX: (time: string) => number | null;
  /** Container width (used to clamp the trailing band to the visible area). */
  width: number;
  /** Container height. */
  height: number;
  /** Alpha for the band fill. Defaults to 0.10 (subtle). */
  alpha?: number;
  className?: string;
}

interface ResolvedBand {
  key: string;
  left: number;
  width: number;
  color: string;
}

/**
 * Read whether the document is currently in dark mode. Returns false in
 * SSR — the chart never renders in SSR, but defensive check keeps the
 * helper trivially testable.
 */
function readIsDark(): boolean {
  if (typeof document === 'undefined') return false;
  return document.documentElement.classList.contains('dark');
}

function pickStageColor(label: string, isDark: boolean): string {
  const tuple = STAGE_HEX[label] ?? FALLBACK_HEX;
  return isDark ? tuple[1] : tuple[0];
}

export function StageOverlay({
  segments,
  timeToX,
  width,
  height,
  alpha = 0.1,
  className,
}: StageOverlayProps) {
  // Tracks dark/palette changes so the band colors stay in lock-step with
  // the rest of the chart. Bumping `themeTick` invalidates the bands memo.
  const [themeTick, setThemeTick] = React.useState(0);
  React.useEffect(() => {
    if (typeof window === 'undefined') return;
    const bump = () => setThemeTick((t) => t + 1);
    window.addEventListener(PALETTE_CHANGE_EVENT, bump);
    const observer = new MutationObserver(bump);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class', 'data-palette'],
    });
    return () => {
      window.removeEventListener(PALETTE_CHANGE_EVENT, bump);
      observer.disconnect();
    };
  }, []);

  const bands = React.useMemo<ResolvedBand[]>(() => {
    // Reference themeTick so the memo invalidates on theme/palette change.
    void themeTick;
    if (width <= 0 || segments.length === 0) return [];
    const isDark = readIsDark();
    const out: ResolvedBand[] = [];
    for (let i = 0; i < segments.length; i += 1) {
      const seg = segments[i];
      const startX = timeToX(seg.startTime);
      // For the trailing edge, prefer the next segment's start (so bands
      // touch with no gap) and fall back to the segment's own end + 1
      // calendar day, then to the right edge of the container.
      const next = segments[i + 1];
      let endX: number | null = null;
      if (next) {
        endX = timeToX(next.startTime);
      }
      if (endX === null) {
        endX = timeToX(seg.endTime);
        if (endX === null) endX = width;
      }
      if (startX === null) continue;
      const left = Math.max(0, Math.min(width, startX));
      const right = Math.max(0, Math.min(width, endX));
      if (right <= left) continue;
      out.push({
        key: `${seg.startTime}-${seg.label}-${i}`,
        left,
        width: right - left,
        color: withAlpha(pickStageColor(seg.label, isDark), alpha),
      });
    }
    return out;
  }, [segments, timeToX, width, alpha, themeTick]);

  if (bands.length === 0) return null;

  return (
    <div
      aria-hidden
      data-testid="stage-overlay"
      className={cn(
        'pointer-events-none absolute inset-0 z-0 overflow-hidden',
        className,
      )}
      style={{ height }}
    >
      {bands.map((band) => (
        <div
          key={band.key}
          className="absolute top-0 bottom-0"
          style={{
            left: band.left,
            width: band.width,
            backgroundColor: band.color,
          }}
        />
      ))}
    </div>
  );
}

export default StageOverlay;
