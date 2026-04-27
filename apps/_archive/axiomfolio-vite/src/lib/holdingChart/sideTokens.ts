/**
 * `sideTokens` — shared trade-side classification.
 *
 * Several modules need to decide whether a row's `side` field counts as
 * a buy or a sell — `sinceIBoughtRange` (anchors the period selector
 * to the first BUY) and `tradeMarkers` (decides which glyph to paint
 * on a trade day). Before this module they each kept their own private
 * `isBuySide` / `isSellSide` and the two drifted: `sinceIBoughtRange`
 * accepted `BOUGHT` / `SOLD`, the marker pipeline did not. The result
 * was a `BOUGHT`-side row that contributed to "Since I bought" but
 * silently disappeared from the trade-marker overlay — a classic
 * one-of-two-codepaths-was-updated bug.
 *
 * Keep this module the single source of truth. If a future broker emits
 * a new alias (e.g. `PURCHASE`), add it to the appropriate set HERE and
 * every consumer picks it up automatically.
 */

/**
 * All side values that mean "this row is a buy". Compared after
 * `trim().toUpperCase()` so consumers don't have to normalize first.
 */
export const BUY_TOKENS: ReadonlySet<string> = new Set([
  "BUY",
  "B",
  "BOUGHT",
]);

/** All side values that mean "this row is a sell". Same comparison rules. */
export const SELL_TOKENS: ReadonlySet<string> = new Set([
  "SELL",
  "S",
  "SOLD",
]);

export function isBuySide(side: string | undefined | null): boolean {
  if (!side) return false;
  return BUY_TOKENS.has(side.trim().toUpperCase());
}

export function isSellSide(side: string | undefined | null): boolean {
  if (!side) return false;
  return SELL_TOKENS.has(side.trim().toUpperCase());
}
