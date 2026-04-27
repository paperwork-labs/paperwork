/**
 * `useHomeAttention` — up to 5 "attention items" derived purely client-side
 * from the data we already fetch for the Home page.
 *
 * The derivation is split into a pure `deriveAttentionItems()` function so it
 * can be unit-tested without React / TanStack Query. The hook itself only
 * orchestrates the existing TanStack Query hooks and hands their results to
 * the pure function.
 *
 * Sources (prioritized):
 *   - Positions in Stage 4 (cut-loss candidates) ................. crit
 *   - Positions with deep drawdown (<= −15%) .................... crit
 *   - Positions approaching stop (−15% < pnl <= −7%) ............ warn
 *   - Upcoming ex-dividend within 7 days ........................ warn
 *   - Runners up ≥ 20% (1R proxy in the absence of plan data) ... ok
 *   - Non-zero realized P&L for the period ...................... ok
 *
 * Note: a dedicated `useStops` hook does not yet exist in the frontend, so
 * stop-armed / stop-moved items are derived heuristically from
 * `unrealized_pnl_pct` and `stage_label`. When a real stops feed ships, swap
 * the heuristic for a direct read in `deriveAttentionItems` — no call-site
 * changes needed.
 */
import { useMemo } from 'react';

import {
  useDividendSummary,
  usePnlSummary,
  usePositions,
} from '@/hooks/usePortfolio';
import type { EnrichedPosition } from '@/types/portfolio';

export type AttentionTone = 'ok' | 'warn' | 'crit';

export type AttentionKind =
  | 'stage-4'
  | 'drawdown'
  | 'approaching-stop'
  | 'ex-div'
  | 'runner'
  | 'realized';

export interface AttentionItem {
  id: string;
  kind: AttentionKind;
  title: string;
  subtitle: string;
  href: string;
  tone: AttentionTone;
}

export interface AttentionInputs {
  positions: readonly EnrichedPosition[] | undefined;
  dividendSummary:
    | {
        upcoming_ex_dates?: Array<{ symbol?: string | null; est_ex_date?: string | null }> | null;
      }
    | null
    | undefined;
  realizedPnl: number | null | undefined;
  now?: Date;
  limit?: number;
}

export interface UseHomeAttentionResult {
  items: AttentionItem[];
  isLoading: boolean;
  isError: boolean;
  isEmpty: boolean;
  refetch: () => void;
}

const TONE_RANK: Record<AttentionTone, number> = { crit: 0, warn: 1, ok: 2 };

function holdingHref(symbol: string): string {
  return `/holding/${encodeURIComponent(symbol)}`;
}

function daysUntil(dateStr: string | null | undefined, now: Date): number | null {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return null;
  const midnightNow = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const midnightTarget = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  return Math.round((midnightTarget - midnightNow) / 86_400_000);
}

function formatSignedPct(pct: number): string {
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(1)}%`;
}

function formatSignedMoney(amount: number): string {
  const sign = amount >= 0 ? '+' : '−';
  const abs = Math.abs(amount);
  const formatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(abs);
  return `${sign}${formatted}`;
}

/**
 * Pure derivation: given raw data, return a prioritized list of attention
 * items capped at `limit` (default 5). Sorted crit → warn → ok, then within
 * each tone by magnitude of the underlying signal so the most actionable row
 * is always on top.
 */
export function deriveAttentionItems(input: AttentionInputs): AttentionItem[] {
  const { positions, dividendSummary, realizedPnl, now = new Date(), limit = 5 } = input;
  const raw: Array<AttentionItem & { weight: number }> = [];

  for (const p of positions ?? []) {
    const pnlPct = typeof p.unrealized_pnl_pct === 'number' ? p.unrealized_pnl_pct : null;
    const stage = typeof p.stage_label === 'string' ? p.stage_label : null;

    if (stage && stage.startsWith('4')) {
      raw.push({
        id: `stage-4-${p.symbol}-${p.id}`,
        kind: 'stage-4',
        title: `${p.symbol} · Stage ${stage}`,
        subtitle: 'Trend has broken — review the cut plan.',
        href: holdingHref(p.symbol),
        tone: 'crit',
        weight: Math.abs(pnlPct ?? 0) + 100,
      });
      continue;
    }

    if (pnlPct != null && pnlPct <= -15) {
      raw.push({
        id: `drawdown-${p.symbol}-${p.id}`,
        kind: 'drawdown',
        title: `${p.symbol} · ${formatSignedPct(pnlPct)}`,
        subtitle: 'Deep drawdown — stop is overdue.',
        href: holdingHref(p.symbol),
        tone: 'crit',
        weight: Math.abs(pnlPct),
      });
      continue;
    }

    if (pnlPct != null && pnlPct <= -7) {
      raw.push({
        id: `approaching-stop-${p.symbol}-${p.id}`,
        kind: 'approaching-stop',
        title: `${p.symbol} · ${formatSignedPct(pnlPct)}`,
        subtitle: 'Approaching stop — tighten or trim.',
        href: holdingHref(p.symbol),
        tone: 'warn',
        weight: Math.abs(pnlPct),
      });
      continue;
    }

    if (pnlPct != null && pnlPct >= 20) {
      raw.push({
        id: `runner-${p.symbol}-${p.id}`,
        kind: 'runner',
        title: `${p.symbol} · ${formatSignedPct(pnlPct)}`,
        subtitle: 'Runner — let it work, trail the stop.',
        href: holdingHref(p.symbol),
        tone: 'ok',
        weight: pnlPct,
      });
    }
  }

  const upcoming = dividendSummary?.upcoming_ex_dates ?? [];
  for (const row of upcoming) {
    const symbol = typeof row?.symbol === 'string' ? row.symbol : null;
    const date = typeof row?.est_ex_date === 'string' ? row.est_ex_date : null;
    if (!symbol || !date) continue;
    const delta = daysUntil(date, now);
    if (delta == null || delta < 0 || delta > 7) continue;
    const when =
      delta === 0
        ? 'today'
        : delta === 1
          ? 'tomorrow'
          : `in ${delta} days`;
    raw.push({
      id: `ex-div-${symbol}-${date}`,
      kind: 'ex-div',
      title: `${symbol} · ex-div ${when}`,
      subtitle: 'Dividend is on the calendar — check holdings.',
      href: '/portfolio/income',
      tone: 'warn',
      weight: 7 - delta,
    });
  }

  if (typeof realizedPnl === 'number' && Math.abs(realizedPnl) >= 1) {
    raw.push({
      id: 'realized-period',
      kind: 'realized',
      title: `Realized ${formatSignedMoney(realizedPnl)}`,
      subtitle: 'Closed P&L for the period — review trades.',
      href: '/portfolio/tax',
      tone: 'ok',
      weight: Math.min(Math.abs(realizedPnl) / 100, 1000),
    });
  }

  raw.sort((a, b) => {
    const t = TONE_RANK[a.tone] - TONE_RANK[b.tone];
    if (t !== 0) return t;
    return b.weight - a.weight;
  });

  return raw.slice(0, limit).map(({ weight: _weight, ...item }) => item);
}

/**
 * Bind `deriveAttentionItems` to live TanStack Query state. Returns a stable
 * four-state contract: `isLoading` / `isError` / `isEmpty` / data.
 */
export function useHomeAttention(): UseHomeAttentionResult {
  const positionsQuery = usePositions();
  const dividendQuery = useDividendSummary();
  const pnlQuery = usePnlSummary();

  const isLoading =
    positionsQuery.isPending || dividendQuery.isPending || pnlQuery.isPending;
  const isError = positionsQuery.isError || dividendQuery.isError || pnlQuery.isError;

  const items = useMemo(() => {
    if (isLoading || isError) return [];
    return deriveAttentionItems({
      positions: positionsQuery.data,
      dividendSummary: dividendQuery.data as AttentionInputs['dividendSummary'],
      realizedPnl: pnlQuery.data?.realized_pnl ?? null,
    });
  }, [isLoading, isError, positionsQuery.data, dividendQuery.data, pnlQuery.data]);

  const refetch = () => {
    void positionsQuery.refetch();
    void dividendQuery.refetch();
    void pnlQuery.refetch();
  };

  return {
    items,
    isLoading,
    isError,
    isEmpty: !isLoading && !isError && items.length === 0,
    refetch,
  };
}
