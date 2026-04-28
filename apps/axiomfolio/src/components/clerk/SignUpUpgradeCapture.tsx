"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";

import { TIER_LABEL, type SubscriptionTier } from "@/types/entitlement";

const PENDING_UPGRADE_KEY = "pending_upgrade_tier";

const tierKeys = Object.keys(TIER_LABEL) as SubscriptionTier[];
const SUBSCRIPTION_TIER_SET = new Set<SubscriptionTier>(tierKeys);

/**
 * When pricing sends users to `/sign-up?upgrade=<tier>`, persist the tier for
 * post-signup checkout handoff (same behavior as the legacy `/register` page).
 */
export function SignUpUpgradeCapture() {
  const searchParams = useSearchParams();

  React.useEffect(() => {
    const raw = searchParams.get("upgrade");
    if (!raw) return;
    const key = raw.trim().toLowerCase() as SubscriptionTier;
    if (!SUBSCRIPTION_TIER_SET.has(key)) return;
    try {
      localStorage.setItem(PENDING_UPGRADE_KEY, key);
    } catch {
      /* ignore */
    }
  }, [searchParams]);

  return null;
}
