/**
 * Client-side fallback when snapshot search is unavailable (offline, errors).
 * TODO: remove or shrink once a dedicated symbol-search endpoint ships.
 */
export const FALLBACK_TICKER_SYMBOLS = [
  'AAPL',
  'MSFT',
  'GOOGL',
  'AMZN',
  'NVDA',
  'META',
  'TSLA',
  'SPY',
  'QQQ',
  'IWM',
  'AMD',
  'NFLX',
  'JPM',
  'XOM',
  'LLY',
] as const;

export function looksLikeTickerQuery(raw: string): boolean {
  const q = raw.trim().toUpperCase();
  if (q.length < 1 || q.length > 5) return false;
  return /^[A-Z]+$/.test(q);
}
