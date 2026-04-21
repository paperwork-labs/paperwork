/**
 * Entitlement / subscription tier types.
 *
 * Mirrors the wire format produced by `backend/api/routes/entitlements.py`.
 * These types are intentionally string-literal unions rather than enums so
 * that:
 *   - The runtime payload can be compared directly against these strings.
 *   - Adding a new tier on the backend yields a TS type error rather than a
 *     silent miss.
 */

export type SubscriptionTier =
  | 'free'
  | 'pro'
  | 'pro_plus'
  | 'quant_desk'
  | 'enterprise';

export type EntitlementStatus =
  | 'active'
  | 'trialing'
  | 'past_due'
  | 'canceled'
  | 'incomplete'
  | 'incomplete_expired'
  | 'unpaid'
  | 'manual';

export interface CatalogFeature {
  key: string;
  title: string;
  description: string;
  category: 'data' | 'picks' | 'brain' | 'execution' | 'research' | 'ops';
  min_tier: SubscriptionTier;
}

export interface CatalogResponse {
  features: CatalogFeature[];
}

export interface FeatureAccess {
  key: string;
  allowed: boolean;
  min_tier: SubscriptionTier;
}

export interface MeResponse {
  tier: SubscriptionTier;
  status: EntitlementStatus;
  is_active: boolean;
  cancel_at_period_end: boolean;
  current_period_end: string | null;
  trial_ends_at: string | null;
  features: FeatureAccess[];
}

export interface CheckResponse {
  allowed: boolean;
  feature: string;
  current_tier: SubscriptionTier;
  required_tier: SubscriptionTier;
  reason: string;
}

/**
 * Numeric rank for tier comparisons. Mirrors `SubscriptionTier.rank()` in
 * `backend/models/entitlement.py`. Rank values are spaced (10, 20, ...) so
 * future tiers can slot in without renumbering.
 *
 * Use `tierRank(t)` rather than direct string equality for any "is this
 * user at least Pro?" check.
 */
const TIER_RANK: Record<SubscriptionTier, number> = {
  free: 0,
  pro: 20,
  pro_plus: 30,
  quant_desk: 40,
  enterprise: 50,
};

export function tierRank(tier: SubscriptionTier | null | undefined): number {
  if (!tier) return 0;
  return TIER_RANK[tier] ?? 0;
}

export function tierAtLeast(
  current: SubscriptionTier | null | undefined,
  required: SubscriptionTier,
): boolean {
  return tierRank(current) >= tierRank(required);
}

/** Display label for a tier. Used by upgrade prompts and the pricing table. */
export const TIER_LABEL: Record<SubscriptionTier, string> = {
  free: 'Free',
  pro: 'Pro',
  pro_plus: 'Pro+',
  quant_desk: 'Quant Desk',
  enterprise: 'Enterprise',
};
