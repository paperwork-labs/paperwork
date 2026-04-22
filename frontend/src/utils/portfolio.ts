/**
 * Shared portfolio utilities used across Overview, Holdings, Options, Transactions.
 * Single source for account building, stage/sector aggregation, and date/format helpers.
 */

import type { AccountData } from '../types/portfolio';
import type { EnrichedPosition } from '../types/portfolio';
import { formatRelativeTime } from './format';

export interface BrokerAccountLike {
  id: number;
  account_number: string;
  broker: string;
  account_name?: string;
  account_type?: string;
  last_successful_sync?: string;
}

/** Loose API / broker payload before normalization. */
export interface RawBrokerAccountInput {
  id?: number;
  account_number?: string;
  broker?: string;
  account_name?: string;
  account_type?: string;
  last_successful_sync?: string | null;
}

/**
 * Keep only rows with a finite numeric id (required for balance joins and stable identity).
 * Normalizes account_number so we never emit the literal string "undefined".
 */
export function normalizeBrokerAccountsForPositions(
  raw: ReadonlyArray<RawBrokerAccountInput>,
): BrokerAccountLike[] {
  return raw
    .filter((a) => Number.isFinite(a.id))
    .map((a) => {
      const id = a.id as number;
      const account_number =
        typeof a.account_number === 'string' && a.account_number.length > 0
          ? a.account_number
          : String(id);
      return {
        id,
        account_number,
        broker: a.broker ?? 'Unknown',
        account_name: a.account_name,
        account_type: a.account_type,
        last_successful_sync: a.last_successful_sync ?? undefined,
      };
    });
}

/** Match key for account filter selection (account_number, else string id). Empty if unusable. */
export function brokerAccountRowKey(a: { id?: number; account_number?: string }): string {
  if (typeof a.account_number === 'string' && a.account_number.length > 0) {
    return a.account_number;
  }
  if (Number.isFinite(a.id)) {
    return String(a.id as number);
  }
  return '';
}

/** React list key for a normalized broker row. */
export function brokerAccountStableReactKey(broker: string, accountNumber: string, id: number): string {
  return `${broker.toLowerCase()}-${accountNumber}-${id}`;
}

/** Build AccountData[] from broker accounts list + positions aggregate. */
export function buildAccountsFromPositions(
  brokerAccounts: BrokerAccountLike[],
  positions: EnrichedPosition[]
): AccountData[] {
  if (!brokerAccounts?.length) return [];
  const byAccount = new Map<string, { value: number; pnl: number; count: number }>();
  for (const p of positions) {
    const key = p.account_number ?? String((p as { account_id?: string })?.account_id ?? '');
    if (!key) continue;
    const cur = byAccount.get(key) ?? { value: 0, pnl: 0, count: 0 };
    cur.value += Number(p.market_value ?? 0);
    cur.pnl += Number(p.unrealized_pnl ?? 0);
    cur.count += 1;
    byAccount.set(key, cur);
  }
  const total = positions.reduce((s, p) => s + Number(p.market_value ?? 0), 0);
  return brokerAccounts.map((acc) => {
    const agg = byAccount.get(acc.account_number) ?? { value: 0, pnl: 0, count: 0 };
    return {
      account_id: acc.account_number,
      account_name: acc.account_name ?? acc.account_number,
      account_type: acc.account_type ?? 'Unknown',
      broker: acc.broker,
      total_value: agg.value,
      unrealized_pnl: agg.pnl,
      unrealized_pnl_pct: agg.value ? (agg.pnl / agg.value) * 100 : 0,
      positions_count: agg.count,
      allocation_pct: total ? (agg.value / total) * 100 : 0,
    };
  });
}

/** Build AccountData[] from raw broker account list (no position values). */
export function buildAccountsFromBroker(rawAccounts: ReadonlyArray<RawBrokerAccountInput>): AccountData[] {
  const rows = normalizeBrokerAccountsForPositions(rawAccounts);
  if (!rows.length) return [];
  return rows.map((a) => ({
    account_id: a.account_number,
    account_name: a.account_name ?? a.account_number ?? '',
    account_type: a.account_type ?? 'Unknown',
    broker: a.broker ?? 'Unknown',
    total_value: 0,
    unrealized_pnl: 0,
    positions_count: 0,
    allocation_pct: 0,
  }));
}

/** Stage counts from enriched positions. */
export function stageCountsFromPositions(positions: EnrichedPosition[]): {
  counts: Record<string, number>;
  total: number;
} {
  const counts: Record<string, number> = { '1': 0, '2A': 0, '2B': 0, '2C': 0, '3': 0, '4': 0, '?': 0 };
  for (const p of positions) {
    const stage = (p.stage_label ?? '').trim() || '?';
    if (counts[stage] !== undefined) counts[stage]++;
    else counts['?'] = (counts['?'] ?? 0) + 1;
  }
  return { counts, total: positions.length };
}

/** Allocation by sector for donut (from positions with sector). Merges slices < 3% into "Other". */
export function sectorAllocationFromPositions(
  positions: EnrichedPosition[]
): Array<{ name: string; value: number }> {
  const bySector = new Map<string, number>();
  for (const p of positions) {
    const sector = (p.sector as string)?.trim() || 'Other';
    bySector.set(sector, (bySector.get(sector) ?? 0) + Number(p.market_value ?? 0));
  }
  const sorted = Array.from(bySector.entries())
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);
  const total = sorted.reduce((s, x) => s + x.value, 0);
  if (total <= 0) return sorted;
  const threshold = total * 0.03;
  const major: Array<{ name: string; value: number }> = [];
  let otherValue = 0;
  for (const s of sorted) {
    if (s.value >= threshold && s.name !== 'Other') {
      major.push(s);
    } else {
      otherValue += s.value;
    }
  }
  if (otherValue > 0) major.push({ name: 'Other', value: otherValue });
  return major;
}

/** Top 5 contributors / detractors by unrealized P&L. */
export function topMoversFromPositions(positions: EnrichedPosition[]): {
  contributors: EnrichedPosition[];
  detractors: EnrichedPosition[];
} {
  const sorted = [...positions].sort(
    (a, b) => Number(b.unrealized_pnl ?? 0) - Number(a.unrealized_pnl ?? 0)
  );
  return {
    contributors: sorted.filter((p) => Number(p.unrealized_pnl ?? 0) > 0).slice(0, 5),
    detractors: sorted.filter((p) => Number(p.unrealized_pnl ?? 0) < 0).slice(-5).reverse(),
  };
}

/** Date range key -> { start, end } ISO date strings. */
export function toStartEnd(range: string): { start?: string; end?: string } {
  const end = new Date();
  const endStr = end.toISOString().slice(0, 10);
  let start: Date;
  switch (range) {
    case '7d':
      start = new Date(end);
      start.setDate(start.getDate() - 7);
      return { start: start.toISOString().slice(0, 10), end: endStr };
    case '30d':
      start = new Date(end);
      start.setDate(start.getDate() - 30);
      return { start: start.toISOString().slice(0, 10), end: endStr };
    case '90d':
      start = new Date(end);
      start.setDate(start.getDate() - 90);
      return { start: start.toISOString().slice(0, 10), end: endStr };
    case 'ytd':
      start = new Date(end.getFullYear(), 0, 1);
      return { start: start.toISOString().slice(0, 10), end: endStr };
    case '1y':
      start = new Date(end);
      start.setFullYear(start.getFullYear() - 1);
      return { start: start.toISOString().slice(0, 10), end: endStr };
    default:
      return {};
  }
}

/** Human-readable time ago from ISO string. Delegates to formatRelativeTime. */
export function timeAgo(iso: string | null | undefined): string {
  const result = formatRelativeTime(iso);
  return result || '—';
}
