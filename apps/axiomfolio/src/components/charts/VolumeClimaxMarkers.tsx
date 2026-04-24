/**
 * Volume climax & dry-up markers — returns lightweight-charts marker
 * objects to merge with other series markers in `SymbolChartWithMarkers`.
 */
import * as React from 'react';
import type { SeriesMarker, UTCTimestamp } from 'lightweight-charts';

import { SIGNAL_HEX } from '@/constants/chart';
import type { VolumeEventItem } from '@/types/indicators';

const toDaySec = (iso: string): UTCTimestamp => {
  const d = new Date(iso);
  return Math.floor(
    Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) / 1000,
  ) as UTCTimestamp;
};

const asUTC = (t: number) => t as UTCTimestamp;

const climaxHex = (isDark: boolean) => SIGNAL_HEX.warning[isDark ? 1 : 0];
const dryHex = (isDark: boolean) => SIGNAL_HEX.neutral[isDark ? 1 : 0];

export function buildVolumeClimaxMarkers(
  events: ReadonlyArray<VolumeEventItem>,
  isDark: boolean,
): SeriesMarker<UTCTimestamp>[] {
  const out: SeriesMarker<UTCTimestamp>[] = [];
  for (const e of events) {
    const t = toDaySec(e.date) as number;
    if (t <= 0) continue;
    if (e.type === 'climax') {
      out.push({
        time: asUTC(t),
        position: 'aboveBar',
        shape: 'arrowDown',
        color: climaxHex(isDark),
        text: 'Climax',
        size: 1,
      });
    } else if (e.type === 'dry_up') {
      out.push({
        time: asUTC(t),
        position: 'belowBar',
        shape: 'circle',
        color: dryHex(isDark),
        text: 'Dry',
        size: 0.5,
      });
    }
  }
  return out.sort((a, b) => (a.time as number) - (b.time as number));
}

const VolumeClimaxMarkers: React.FC<Record<string, never>> = () => null;
export default VolumeClimaxMarkers;
