/**
 * Oliver Kell pattern badges (EBC / KRC / PPB) — marker payloads + static
 * rationale copy for Pro+ tooltips (wired in `SymbolChartWithMarkers` crosshair).
 */
import * as React from 'react';
import type { SeriesMarker, UTCTimestamp } from 'lightweight-charts';

import type { KellPatternItem } from '@/types/indicators';
import type { ChartColors } from '@/hooks/useChartColors';

import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

const toDaySec = (iso: string): UTCTimestamp => {
  const d = new Date(iso);
  return Math.floor(
    Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) / 1000,
  ) as UTCTimestamp;
};

const asUTC = (t: number) => t as UTCTimestamp;

function patternBadgeClass(p: 'EBC' | 'KRC' | 'PPB'): string {
  if (p === 'EBC') return 'border-orange-500/50 text-orange-800 dark:text-orange-200';
  if (p === 'KRC') return 'border-emerald-500/50 text-emerald-800 dark:text-emerald-200';
  return 'border-teal-500/50 text-teal-800 dark:text-teal-200';
}

export const KELL_RATIONALE: Record<
  'EBC' | 'KRC' | 'PPB',
  { title: string; context: string; trigger: string; stop: string }
> = {
  EBC: {
    title: 'Exhaustion break & reclaim (EBC)',
    context: 'A climactic down-thrust (often on expanded range/volume) that fails on follow-through.',
    trigger: 'Enter on reclaim back through the mid-point of the exhaustion bar, with volume drying up on the test.',
    stop: 'Invalid if price accepts back below the exhaustion low or the pattern becomes a new leg down on volume.',
  },
  KRC: {
    title: 'Kicker / gap continuation (KRC)',
    context: 'A gap up through a prior bar’s high after a basing/turn structure, with participation.',
    trigger: 'Trade in line with the gap day’s direction; treat the gap zone as a momentum pocket.',
    stop: 'Invalid on full gap fill the next session (gap completely erased) without immediate recovery.',
  },
  PPB: {
    title: 'Perfect pullback (PPB)',
    context: 'In Stage 2, a controlled pullback to a rising moving average (e.g. 10/20) in low volume.',
    trigger: 'Enter on a bullish response from the support zone; demand signs of deceleration on the sell-off.',
    stop: 'Invalid on a high-volume break of the rising support or loss of a higher low structure.',
  },
};

export function buildKellPatternMarkers(
  items: ReadonlyArray<KellPatternItem>,
  colors: ChartColors,
): SeriesMarker<UTCTimestamp>[] {
  const cMap: Record<'EBC' | 'KRC' | 'PPB', string> = {
    EBC: colors.warning,
    KRC: colors.success,
    PPB: colors.brand500,
  };
  const out: SeriesMarker<UTCTimestamp>[] = [];
  for (const k of items) {
    if (k.pattern !== 'EBC' && k.pattern !== 'KRC' && k.pattern !== 'PPB') continue;
    const t = toDaySec(k.date) as number;
    if (t <= 0) continue;
    out.push({
      time: asUTC(t),
      position: 'aboveBar',
      shape: 'square',
      color: cMap[k.pattern],
      text: k.pattern,
      size: 0.6,
    });
  }
  return out.sort((a, b) => (a.time as number) - (b.time as number));
}

export function lookupKellRationale(
  daySec: number,
  byDay: Map<number, KellPatternItem>,
): KellPatternItem | null {
  return byDay.get(daySec) ?? null;
}

export function buildKellByDayMap(
  items: ReadonlyArray<KellPatternItem>,
): Map<number, KellPatternItem> {
  const m = new Map<number, KellPatternItem>();
  for (const k of items) {
    m.set(toDaySec(k.date) as number, k);
  }
  return m;
}

/** Legend row for the chart chrome — not painted on the canvas. */
export function OliverKellLegend({ className }: { className?: string }): React.ReactElement {
  return (
    <div className={cn('flex flex-wrap items-center gap-1.5', className)} aria-label="Oliver Kell patterns">
      {(['EBC', 'KRC', 'PPB'] as const).map((p) => (
        <Badge key={p} variant="outline" className={cn('h-5 px-1.5 text-[10px] font-medium', patternBadgeClass(p))}>
          {p}
        </Badge>
      ))}
    </div>
  );
}

export function OliverKellRationaleCard({
  pattern,
  confidence,
  proPlusRationale,
}: {
  pattern: 'EBC' | 'KRC' | 'PPB';
  confidence: number;
  proPlusRationale: boolean;
}): React.ReactElement {
  const r = KELL_RATIONALE[pattern];
  const inner = proPlusRationale ? (
    <div className="space-y-1.5 text-left text-xs">
      <p className="font-medium text-foreground">{r.title}</p>
      <p className="text-muted-foreground">
        <span className="font-medium text-foreground/90">Context: </span>
        {r.context}
      </p>
      <p className="text-muted-foreground">
        <span className="font-medium text-foreground/90">Trigger: </span>
        {r.trigger}
      </p>
      <p className="text-muted-foreground">
        <span className="font-medium text-foreground/90">Stop: </span>
        {r.stop}
      </p>
      <p className="text-[10px] text-muted-foreground/90">Model confidence: {(confidence * 100).toFixed(0)}%</p>
    </div>
  ) : null;

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn('cursor-default rounded border border-border px-1.5 py-0.5 text-[10px] font-semibold', patternBadgeClass(pattern))}
          >
            {pattern}
          </span>
        </TooltipTrigger>
        {proPlusRationale ? (
          <TooltipContent className="max-w-xs border-border p-3" side="top" align="start">
            {inner}
          </TooltipContent>
        ) : null}
      </Tooltip>
    </TooltipProvider>
  );
}

const OliverKellBadges: React.FC<Record<string, never>> = () => null;
export default OliverKellBadges;
