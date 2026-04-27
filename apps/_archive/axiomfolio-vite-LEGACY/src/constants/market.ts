/**
 * Market data defaults — mirrors backend config.py HISTORY_TARGET_YEARS.
 *
 * If the backend value changes, update this constant to match.
 */
export const HISTORY_TARGET_YEARS = 10;

export function defaultHistoryStart(): string {
  const year = new Date().getFullYear() - HISTORY_TARGET_YEARS;
  return `${year}-01-01`;
}
