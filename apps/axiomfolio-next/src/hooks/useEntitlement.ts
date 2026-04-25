/**
 * useEntitlement — single source of truth for tier-gated UI.
 *
 * Loads the current user's tier and per-feature access map once on mount,
 * caches it for 5 minutes, and exposes:
 *
 *   - `tier` / `status` / `isActive` — raw subscription state
 *   - `can(featureKey)` — boolean check
 *   - `requireTier(featureKey)` — returns the minimum tier for the feature
 *
 * Components should never inline tier comparisons — use `can()` so the
 * source of truth stays in `feature_catalog.py`.
 */

import { useQuery } from '@tanstack/react-query';

import { useAuthOptional } from '../context/AuthContext';
import api from '../services/api';
import type {
  MeResponse,
  SubscriptionTier,
  EntitlementStatus,
} from '../types/entitlement';

interface UseEntitlementResult {
  /** Effective tier (FREE if no active subscription / on grace failure). */
  tier: SubscriptionTier;
  /** Raw subscription status from Stripe / manual override. */
  status: EntitlementStatus;
  /** True when the subscription currently grants tier access. */
  isActive: boolean;
  /** Period end (ISO string) — surfaced to render renewal hints. */
  currentPeriodEnd: string | null;
  /** True while the entitlement is loading; gates feature-flag UI render. */
  isLoading: boolean;
  isError: boolean;
  /** Predicate: can the current user use `featureKey`? */
  can: (featureKey: string) => boolean;
  /** Minimum tier required for `featureKey`, or null if the key is unknown. */
  requireTier: (featureKey: string) => SubscriptionTier | null;
  /** Raw response — escape hatch for components that need the full payload. */
  raw: MeResponse | null;
}

/**
 * Fetch + cache the current user's entitlement. Cached for 5 minutes to
 * avoid hammering the endpoint on every component mount; consumers can
 * call `queryClient.invalidateQueries({ queryKey: ['entitlement', 'me'] })`
 * after a successful upgrade to refresh immediately.
 */
export function useEntitlement(): UseEntitlementResult {
  const auth = useAuthOptional();
  const tokenPresent = Boolean(auth?.token);

  const { data, isLoading, isError } = useQuery<MeResponse | null>({
    queryKey: ['entitlement', 'me'],
    queryFn: async () => {
      const res = await api.get<MeResponse>('/entitlements/me');
      return res?.data ?? null;
    },
    enabled: tokenPresent,
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
    retry: 2,
  });

  const can = (featureKey: string): boolean => {
    if (!data) return false;
    const f = data.features.find((row) => row.key === featureKey);
    // Unknown feature key → fail closed. We never grant access for a typo.
    return f?.allowed === true;
  };

  const requireTier = (featureKey: string): SubscriptionTier | null => {
    if (!data) return null;
    const f = data.features.find((row) => row.key === featureKey);
    return f?.min_tier ?? null;
  };

  return {
    tier: data?.tier ?? 'free',
    status: data?.status ?? 'active',
    isActive: data?.is_active ?? false,
    currentPeriodEnd: data?.current_period_end ?? null,
    isLoading,
    isError,
    can,
    requireTier,
    raw: data ?? null,
  };
}

export default useEntitlement;
