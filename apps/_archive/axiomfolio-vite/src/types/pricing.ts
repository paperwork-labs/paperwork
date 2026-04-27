/**
 * Pricing catalog wire types — mirrors `backend/api/routes/pricing.py`.
 *
 * Prices are intentionally typed as 'string' (not 'number') so the wire
 * format preserves Decimal precision end-to-end. UI components must use
 * the BigInt-cents helpers in components/pricing/format.ts to format
 * these values without converting to JS Number.
 */

import type { SubscriptionTier } from './entitlement';

export interface PricingFeature {
  key: string;
  title: string;
  description: string;
  category:
    | 'data'
    | 'picks'
    | 'brain'
    | 'execution'
    | 'research'
    | 'ops'
    | 'mcp'
    | 'strategy';
  /** The minimum tier that includes this feature. */
  min_tier: SubscriptionTier;
}

export interface PricingTier {
  /** Canonical tier slug (e.g. `"pro_plus"`). */
  tier: SubscriptionTier;
  /** Display name (e.g. `"Pro+"`). */
  name: string;
  tagline: string;
  /** Decimal-precision string. `null` only for Enterprise. */
  monthly_price_usd: string | null;
  /** Annual total as a Decimal-precision string. `null` when no annual SKU. */
  annual_price_usd: string | null;
  /** Transparency microcopy: "Your subscription covers X". */
  covers_copy: string;
  cta_label: string;
  /** Free public route to navigate to (e.g. `"/register"`); `null` for paid tiers. */
  cta_route: string | null;
  /** True for tiers that go through sales (Enterprise) instead of self-serve. */
  is_contact_sales: boolean;
  /** Cumulative features included at this tier (everything from this and lower tiers). */
  features: PricingFeature[];
  /** Features that *first* unlock at this tier (the diff vs the tier below). */
  new_features: PricingFeature[];
}

export interface PricingCatalogResponse {
  tiers: PricingTier[];
  /** ISO 4217 currency code (currently always `"USD"`). */
  currency: string;
}
