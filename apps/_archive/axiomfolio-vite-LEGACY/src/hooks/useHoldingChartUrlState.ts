/**
 * `useHoldingChartUrlState` — durable URL state for the flagship holding
 * chart so a screenshot, link, or share-card encodes exactly what the
 * viewer sees.
 *
 * URL contract (kept terse on purpose so tweet-length links survive
 * Slack / X mangling):
 *
 *   /holding/AAPL?period=1y&overlays=sma50,bb,sma200&stageBands=1&benchmark=SPY
 *
 * - `period`     — one of `1mo|3mo|6mo|ytd|1y|5y|max|since`
 * - `overlays`   — comma-separated, deduped overlay ids; `bb` is short
 *                  for `bollinger` so the canonical link stays compact
 * - `stageBands` — `1` (on) or `0` (off); absent === off
 * - `benchmark`  — explicit benchmark symbol override, uppercase, or
 *                  absent for "use the auto-resolved sector ETF"
 *
 * Validation strategy: anything we don't recognize is dropped silently.
 * A malformed `period` falls back to the supplied default; an unknown
 * overlay id is filtered out. The hook NEVER throws on bad input — a
 * shared link should always render *something* useful.
 */
import * as React from 'react';
import { useSearchParams } from 'react-router-dom';

import type { HoldingChartPeriod } from '@/lib/holdingChart/useHoldingChartData';

/**
 * The user-facing overlay id space. These map onto one or more
 * `IndicatorKey`s when we issue the indicator request — the chart
 * component owns that translation so a story can render the same
 * overlays without going near the network.
 */
export type OverlayId =
  | 'sma50'
  | 'sma100'
  | 'sma150'
  | 'sma200'
  | 'ema21'
  | 'ema200'
  | 'bollinger';

const ALL_PERIODS: ReadonlyArray<HoldingChartPeriod> = [
  '1mo',
  '3mo',
  '6mo',
  'ytd',
  '1y',
  '5y',
  'max',
  'since',
];

const ALL_OVERLAYS: ReadonlyArray<OverlayId> = [
  'sma50',
  'sma100',
  'sma150',
  'sma200',
  'ema21',
  'ema200',
  'bollinger',
];

/**
 * Wire shorthand for compactness. Bollinger gets `bb` so the canonical
 * "everything on" link stays under the X title-tag truncation point.
 * Round-trip: `OVERLAY_TO_WIRE[id]` → wire token, `WIRE_TO_OVERLAY[wire]`
 * → id. Anything not in the map is treated as unknown and dropped.
 */
const OVERLAY_TO_WIRE: Record<OverlayId, string> = {
  sma50: 'sma50',
  sma100: 'sma100',
  sma150: 'sma150',
  sma200: 'sma200',
  ema21: 'ema21',
  ema200: 'ema200',
  bollinger: 'bb',
};

const WIRE_TO_OVERLAY: Record<string, OverlayId> = Object.fromEntries(
  (Object.entries(OVERLAY_TO_WIRE) as Array<[OverlayId, string]>).map(
    ([id, wire]) => [wire, id],
  ),
);

export interface HoldingChartUrlState {
  period: HoldingChartPeriod;
  overlays: OverlayId[];
  stageBands: boolean;
  /** Uppercase symbol or null when the consumer wants the auto benchmark. */
  benchmark: string | null;
}

export interface UseHoldingChartUrlStateOptions {
  defaultPeriod?: HoldingChartPeriod;
  defaultOverlays?: OverlayId[];
  defaultStageBands?: boolean;
  defaultBenchmark?: string | null;
}

export interface UseHoldingChartUrlStateReturn extends HoldingChartUrlState {
  setPeriod: (next: HoldingChartPeriod) => void;
  setOverlays: (next: OverlayId[]) => void;
  setStageBands: (next: boolean) => void;
  setBenchmark: (next: string | null) => void;
  /** Atomic update for batched changes (e.g. a single "reset" button). */
  setAll: (next: Partial<HoldingChartUrlState>) => void;
}

const SYMBOL_RE = /^[A-Z][A-Z0-9.\-]{0,9}$/;

function parsePeriod(
  raw: string | null,
  fallback: HoldingChartPeriod,
): HoldingChartPeriod {
  if (!raw) return fallback;
  return (ALL_PERIODS as readonly string[]).includes(raw)
    ? (raw as HoldingChartPeriod)
    : fallback;
}

function parseOverlays(raw: string | null): OverlayId[] {
  if (!raw) return [];
  const out = new Set<OverlayId>();
  for (const token of raw.split(',')) {
    const trimmed = token.trim().toLowerCase();
    if (!trimmed) continue;
    const id = WIRE_TO_OVERLAY[trimmed];
    if (id) out.add(id);
  }
  // Stable order = the canonical declaration order in `ALL_OVERLAYS`,
  // so `?overlays=bb,sma50` and `?overlays=sma50,bb` produce the same
  // round-tripped URL. Critical for cache identity downstream.
  return ALL_OVERLAYS.filter((o) => out.has(o));
}

function parseStageBands(raw: string | null): boolean {
  if (raw == null) return false;
  return raw === '1' || raw === 'true';
}

function parseBenchmark(raw: string | null): string | null {
  if (!raw) return null;
  const upper = raw.trim().toUpperCase();
  return SYMBOL_RE.test(upper) ? upper : null;
}

function encodeOverlays(overlays: ReadonlyArray<OverlayId>): string | null {
  if (overlays.length === 0) return null;
  // Re-sort by canonical order so the URL stays stable regardless of
  // the order the consumer hands us.
  const canonical = ALL_OVERLAYS.filter((o) => overlays.includes(o));
  return canonical.map((id) => OVERLAY_TO_WIRE[id]).join(',');
}

export function useHoldingChartUrlState(
  options: UseHoldingChartUrlStateOptions = {},
): UseHoldingChartUrlStateReturn {
  const {
    defaultPeriod = '1y',
    defaultOverlays = [],
    defaultStageBands = false,
    defaultBenchmark = null,
  } = options;

  const [searchParams, setSearchParams] = useSearchParams();

  const state = React.useMemo<HoldingChartUrlState>(() => {
    return {
      period: parsePeriod(searchParams.get('period'), defaultPeriod),
      overlays: parseOverlays(searchParams.get('overlays')),
      stageBands: parseStageBands(searchParams.get('stageBands')),
      benchmark: parseBenchmark(searchParams.get('benchmark')),
    };
  }, [searchParams, defaultPeriod]);

  // The defaults are deliberately NOT applied to the parsed state object
  // for overlays/stageBands/benchmark — those are "absent === off /
  // none" for clean URLs. The defaults flow through the initial values
  // when the URL is empty by being the consumer's notion of "starting
  // state"; we only auto-apply `defaultPeriod` because the period
  // selector requires a value at all times.
  const finalState = React.useMemo<HoldingChartUrlState>(() => {
    const overlays =
      searchParams.get('overlays') == null && defaultOverlays.length > 0
        ? ALL_OVERLAYS.filter((o) => defaultOverlays.includes(o))
        : state.overlays;
    const stageBands =
      searchParams.get('stageBands') == null
        ? defaultStageBands
        : state.stageBands;
    const benchmark =
      searchParams.get('benchmark') == null
        ? defaultBenchmark
        : state.benchmark;
    return { period: state.period, overlays, stageBands, benchmark };
  }, [
    state,
    searchParams,
    defaultOverlays,
    defaultStageBands,
    defaultBenchmark,
  ]);

  const writeState = React.useCallback(
    (next: HoldingChartUrlState) => {
      setSearchParams(
        (prev) => {
          const params = new URLSearchParams(prev);
          // Period is always present so the radiogroup can render. We
          // omit it when it equals the default to keep clean URLs.
          if (next.period === defaultPeriod) {
            params.delete('period');
          } else {
            params.set('period', next.period);
          }
          const overlaysWire = encodeOverlays(next.overlays);
          if (!overlaysWire) {
            params.delete('overlays');
          } else {
            params.set('overlays', overlaysWire);
          }
          if (next.stageBands) {
            params.set('stageBands', '1');
          } else {
            params.delete('stageBands');
          }
          if (next.benchmark && SYMBOL_RE.test(next.benchmark)) {
            params.set('benchmark', next.benchmark);
          } else {
            params.delete('benchmark');
          }
          return params;
        },
        { replace: true },
      );
    },
    [setSearchParams, defaultPeriod],
  );

  const setPeriod = React.useCallback(
    (next: HoldingChartPeriod) => writeState({ ...finalState, period: next }),
    [finalState, writeState],
  );
  const setOverlays = React.useCallback(
    (next: OverlayId[]) => writeState({ ...finalState, overlays: next }),
    [finalState, writeState],
  );
  const setStageBands = React.useCallback(
    (next: boolean) => writeState({ ...finalState, stageBands: next }),
    [finalState, writeState],
  );
  const setBenchmark = React.useCallback(
    (next: string | null) =>
      writeState({
        ...finalState,
        benchmark: next ? next.trim().toUpperCase() : null,
      }),
    [finalState, writeState],
  );

  const setAll = React.useCallback(
    (partial: Partial<HoldingChartUrlState>) =>
      writeState({ ...finalState, ...partial }),
    [finalState, writeState],
  );

  return {
    ...finalState,
    setPeriod,
    setOverlays,
    setStageBands,
    setBenchmark,
    setAll,
  };
}

// Exposed for tests. The pure encoders/parsers carry the contract; the
// hook is a thin shell that wires them to `react-router-dom`.
export const __test = {
  parsePeriod,
  parseOverlays,
  parseStageBands,
  parseBenchmark,
  encodeOverlays,
  OVERLAY_TO_WIRE,
  WIRE_TO_OVERLAY,
  ALL_OVERLAYS,
};
