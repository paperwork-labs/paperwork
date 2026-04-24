/**
 * `useHoldingIndicators` — fetches per-day, calendar-aligned indicator
 * series for a single symbol and processes them into chart-ready
 * `IndicatorPoint[]` plus contiguous `StageSegment[]` runs.
 *
 * Why this lives separate from `useHoldingChartData`:
 *   - Indicator math is driven by an explicit `indicators[]` list. The
 *     consumer toggles overlays on/off and the queryKey must reflect
 *     the exact set requested so the cache stays correct (different
 *     overlay set === different payload).
 *   - The hook is pure: no DOM, no charting library. Everything it does
 *     is testable against fixtures.
 *
 * Decimal-string defense: the backend serializes some indicator
 * columns as `Decimal`, which slips through HTTP as a string. We
 * coerce defensively (`Number(x)`) and drop anything non-finite —
 * the chart can't render holes mid-series and a NaN landing in
 * lightweight-charts produces silent visual artifacts.
 */
import * as React from 'react';
import { useQuery } from '@tanstack/react-query';

import { marketDataApi } from '@/services/api';

import type { BackendPeriod } from './useHoldingChartData';
import type {
  IndicatorKey,
  IndicatorSeriesResponse,
} from '@/types/indicators';

/** A single (date, value) point — already cleaned of nulls / NaN. */
export interface IndicatorPoint {
  /** ISO date `YYYY-MM-DD`. */
  time: string;
  value: number;
}

/** A contiguous run of identical stage labels. */
export interface StageSegment {
  startTime: string;
  endTime: string;
  label: string;
}

export interface UseHoldingIndicatorsOptions {
  symbol: string;
  period: BackendPeriod;
  /**
   * Explicit list of indicator columns to request. Empty array short-
   * circuits the query (we don't ask the backend for nothing).
   */
  indicators: IndicatorKey[];
  enabled?: boolean;
}

export interface UseHoldingIndicatorsResult {
  /** Chart-ready time series, keyed by indicator name. */
  series: Partial<Record<IndicatorKey, IndicatorPoint[]>>;
  /** Contiguous stage runs, present only when `stage_label` was requested. */
  stageSegments: StageSegment[];
  /** Number of calendar-aligned rows reported by the backend. */
  rows: number;
  /** Mirrors backend signal: a backfill job was kicked off for this symbol. */
  backfillRequested: boolean;
  /** Mirrors backend signal: the price feed itself is still warming. */
  pricePending: boolean;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => Promise<void>;
}

const STALE_MS = 60_000;

/**
 * Pull the response payload off the axios envelope. The endpoint can be
 * served wrapped (`{ data: { ... } }`) or flat depending on the path
 * through the request queue, so tolerate both.
 */
function extractResponse(raw: unknown): IndicatorSeriesResponse | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  // axios envelope: { data: { ... } }
  if (r.data && typeof r.data === 'object') {
    const d = r.data as Record<string, unknown>;
    if (typeof d.symbol === 'string' && d.series) {
      return d as unknown as IndicatorSeriesResponse;
    }
  }
  if (typeof r.symbol === 'string' && r.series) {
    return r as unknown as IndicatorSeriesResponse;
  }
  return null;
}

/** Coerce a wire cell to a finite number, or `null` if unusable. */
function toFinite(value: number | string | null | undefined): number | null {
  if (value == null) return null;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function buildSeries(
  dates: Array<string | null>,
  cells: Array<number | string | null> | undefined,
): IndicatorPoint[] {
  if (!cells || cells.length === 0) return [];
  const out: IndicatorPoint[] = [];
  // Walk both arrays in lockstep; the wire contract is "calendar-aligned"
  // so length parity matters. Defensive: if the backend returned a
  // shorter `cells` array (column dropped late), stop at min length.
  const len = Math.min(dates.length, cells.length);
  for (let i = 0; i < len; i += 1) {
    const date = dates[i];
    if (typeof date !== 'string' || date.length === 0) continue;
    const value = toFinite(cells[i]);
    if (value === null) continue;
    out.push({ time: date, value });
  }
  return out;
}

/**
 * Walk the stage_label series and emit one `StageSegment` per contiguous
 * run of identical labels. Null / empty labels break a run (the chart
 * shows a gap at warm-up boundaries instead of fabricating a stage).
 */
function buildStageSegments(
  dates: Array<string | null>,
  labels: Array<number | string | null> | undefined,
): StageSegment[] {
  if (!labels || labels.length === 0) return [];
  const segments: StageSegment[] = [];
  const len = Math.min(dates.length, labels.length);

  let runStart: string | null = null;
  let runEnd: string | null = null;
  let runLabel: string | null = null;

  const flush = () => {
    if (runStart && runEnd && runLabel) {
      segments.push({ startTime: runStart, endTime: runEnd, label: runLabel });
    }
    runStart = null;
    runEnd = null;
    runLabel = null;
  };

  for (let i = 0; i < len; i += 1) {
    const date = dates[i];
    const cell = labels[i];
    const label =
      typeof cell === 'string' && cell.length > 0
        ? cell
        : typeof cell === 'number' && Number.isFinite(cell)
          ? String(cell)
          : null;

    if (typeof date !== 'string' || date.length === 0 || label === null) {
      flush();
      continue;
    }

    if (runLabel === null) {
      runStart = date;
      runEnd = date;
      runLabel = label;
    } else if (label === runLabel) {
      runEnd = date;
    } else {
      flush();
      runStart = date;
      runEnd = date;
      runLabel = label;
    }
  }
  flush();
  return segments;
}

export function useHoldingIndicators(
  opts: UseHoldingIndicatorsOptions,
): UseHoldingIndicatorsResult {
  const { symbol, period, indicators, enabled = true } = opts;

  // Sort + dedupe so the queryKey is identity-stable regardless of the
  // order the consumer passed columns. Toggling [a, b] → [b, a] should
  // hit the cache, not refetch.
  const normalized = React.useMemo(() => {
    const set = new Set<IndicatorKey>(indicators);
    return Array.from(set).sort();
  }, [indicators]);

  const wantsAnything = normalized.length > 0;
  const queryEnabled = enabled && Boolean(symbol) && wantsAnything;

  const query = useQuery({
    queryKey: [
      'holdingChart',
      'indicators',
      symbol,
      period,
      normalized.join(','),
    ],
    queryFn: () =>
      marketDataApi.getIndicatorSeries(symbol, {
        period,
        indicators: normalized,
      }),
    enabled: queryEnabled,
    staleTime: STALE_MS,
  });

  const payload = React.useMemo(
    () => extractResponse(query.data),
    [query.data],
  );

  const series = React.useMemo<Partial<Record<IndicatorKey, IndicatorPoint[]>>>(() => {
    if (!payload) return {};
    const dates = Array.isArray(payload.series?.dates)
      ? payload.series.dates
      : [];
    const out: Partial<Record<IndicatorKey, IndicatorPoint[]>> = {};
    for (const key of normalized) {
      if (key === 'stage_label') continue;
      const cells = payload.series?.[key];
      out[key] = buildSeries(dates, cells);
    }
    return out;
  }, [payload, normalized]);

  const stageSegments = React.useMemo<StageSegment[]>(() => {
    if (!payload) return [];
    if (!normalized.includes('stage_label')) return [];
    const dates = Array.isArray(payload.series?.dates)
      ? payload.series.dates
      : [];
    const cells = payload.series?.stage_label;
    return buildStageSegments(dates, cells);
  }, [payload, normalized]);

  const refetch = React.useCallback(async () => {
    await query.refetch();
  }, [query]);

  return {
    series,
    stageSegments,
    rows: payload?.rows ?? 0,
    backfillRequested: payload?.backfill_requested ?? false,
    pricePending: payload?.price_data_pending ?? false,
    isLoading: queryEnabled && query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch,
  };
}

// Exposed for tests — the pure transforms have no React dependency.
export const __test = { extractResponse, buildSeries, buildStageSegments };
