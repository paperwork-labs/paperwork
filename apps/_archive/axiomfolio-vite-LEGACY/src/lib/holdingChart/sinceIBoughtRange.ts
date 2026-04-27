/**
 * `sinceIBoughtRange` — derive the "Since I bought" date range from
 * activity rows.
 *
 * The flagship chart's killer feature is being able to anchor the period
 * selector to "the day I first opened this position". This module turns a
 * raw activity feed into the earliest BUY date and a backend-friendly
 * `period` string that covers it.
 *
 * Lazy-tolerant of mixed shapes:
 *   - Some endpoints expose `transaction_date`, others expose `date`.
 *   - Sides come through as 'BUY' / 'SELL' / 'B' / 'S' / 'BOUGHT' /
 *     'SOLD' (case-insensitive — see `sideTokens.ts` for the full
 *     accepted set; that module is the single source of truth shared
 *     with the marker pipeline).
 *   - Future-dated rows (rare, mostly bad data) are ignored so we never
 *     pick a buy date AFTER today.
 */
import { isBuySide } from "./sideTokens";

export interface ActivityRowLite {
  /** ISO 8601 timestamp from the unified activity endpoint. */
  transaction_date?: string;
  /** Some legacy endpoints emit `date` instead. */
  date?: string;
  /** 'BUY' | 'SELL' | 'B' | 'S' | 'BOUGHT' | 'SOLD' (case-insensitive). */
  side?: string;
}

/**
 * Pulls a date string off either canonical column. Returns null if neither
 * is present so the caller can ignore the row entirely.
 */
function rowDate(row: ActivityRowLite): string | null {
  const raw = row.transaction_date ?? row.date;
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return trimmed.length > 0 ? trimmed : null;
}

/**
 * Convert an ISO date string to a UTC `YYYY-MM-DD`. Returns null if the
 * input doesn't parse as a real date — invalid rows are silently skipped
 * (the chart should never crash because one row was malformed).
 */
function toIsoDay(raw: string): string | null {
  const ms = Date.parse(raw);
  if (!Number.isFinite(ms)) return null;
  const d = new Date(ms);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function todayUtcMs(today?: Date): number {
  const t = today ?? new Date();
  return Date.UTC(t.getUTCFullYear(), t.getUTCMonth(), t.getUTCDate(), 23, 59, 59);
}

/**
 * Returns the earliest BUY date for the given activity rows as ISO
 * `YYYY-MM-DD`. Returns null if no buys are present.
 *
 * - Filters out non-buy sides (SELL / S / unspecified).
 * - Skips rows missing a parseable date.
 * - Ignores rows whose date is in the future (data-quality guard).
 */
export function earliestBuyDate(
  rows: ReadonlyArray<ActivityRowLite>,
  today?: Date,
): string | null {
  if (!Array.isArray(rows) || rows.length === 0) return null;
  const cutoff = todayUtcMs(today);

  let earliestMs: number | null = null;
  for (const row of rows) {
    if (!isBuySide(row.side)) continue;
    const raw = rowDate(row);
    if (!raw) continue;
    const ms = Date.parse(raw);
    if (!Number.isFinite(ms)) continue;
    if (ms > cutoff) continue;
    if (earliestMs === null || ms < earliestMs) {
      earliestMs = ms;
    }
  }

  if (earliestMs === null) return null;
  return toIsoDay(new Date(earliestMs).toISOString());
}

const PERIOD_DAYS: ReadonlyArray<readonly [period: "1mo" | "3mo" | "6mo" | "1y" | "5y" | "max", days: number]> =
  [
    ["1mo", 31],
    ["3mo", 93],
    ["6mo", 186],
    ["1y", 372],
    ["5y", 1860],
    ["max", Number.POSITIVE_INFINITY],
  ];

/**
 * Returns the smallest `period` string the backend accepts that fully
 * covers `earliestIso` to `today`. Used to choose the upstream fetch
 * window — the visual range is still client-side trimmed to the actual
 * buy date for the "Since I bought" axis.
 *
 * If `earliestIso` doesn't parse, defaults to `'1y'` (the friendly
 * "context-rich" fallback for a brand-new holding).
 */
export function periodCoveringDate(
  earliestIso: string,
  today?: Date,
): "1mo" | "3mo" | "6mo" | "1y" | "5y" | "max" {
  const ms = Date.parse(earliestIso);
  if (!Number.isFinite(ms)) return "1y";
  const now = (today ?? new Date()).getTime();
  const diffDays = Math.max(0, (now - ms) / 86_400_000);
  for (const [period, days] of PERIOD_DAYS) {
    if (diffDays <= days) return period;
  }
  return "max";
}
