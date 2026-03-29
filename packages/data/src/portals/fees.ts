/**
 * State Filing Fees
 *
 * Single source of truth for LLC formation filing fees.
 * Verified against official state SOS sources.
 */

export const STATE_FILING_FEES: Record<string, number> = {
  CA: 70,
  TX: 300,
  FL: 125,
  DE: 90,
  WY: 100,
  NY: 200,
  NV: 425,
  IL: 150,
  GA: 100,
  WA: 180,
};

export const STATE_NAMES: Record<string, string> = {
  CA: "California",
  TX: "Texas",
  FL: "Florida",
  DE: "Delaware",
  WY: "Wyoming",
  NY: "New York",
  NV: "Nevada",
  IL: "Illinois",
  GA: "Georgia",
  WA: "Washington",
};
