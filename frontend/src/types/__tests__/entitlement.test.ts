import { describe, expect, it } from 'vitest';

import {
  TIER_LABEL,
  tierAtLeast,
  tierRank,
  type SubscriptionTier,
} from '../entitlement';

describe('tierRank', () => {
  it('returns 0 for null/undefined (fail closed)', () => {
    expect(tierRank(null)).toBe(0);
    expect(tierRank(undefined)).toBe(0);
  });

  it('orders tiers strictly ascending', () => {
    const order: SubscriptionTier[] = [
      'free',
      'lite',
      'pro',
      'pro_plus',
      'quant_desk',
      'enterprise',
    ];
    const ranks = order.map(tierRank);
    expect(ranks).toEqual([...ranks].sort((a, b) => a - b));
    expect(new Set(ranks).size).toBe(ranks.length);
  });

  it('matches the backend rank spacing of 10', () => {
    expect(tierRank('free')).toBe(0);
    expect(tierRank('lite')).toBe(10);
    expect(tierRank('pro')).toBe(20);
    expect(tierRank('pro_plus')).toBe(30);
    expect(tierRank('quant_desk')).toBe(40);
    expect(tierRank('enterprise')).toBe(50);
  });
});

describe('tierAtLeast', () => {
  it('grants access when current tier >= required', () => {
    expect(tierAtLeast('pro_plus', 'pro')).toBe(true);
    expect(tierAtLeast('pro', 'pro')).toBe(true);
    expect(tierAtLeast('enterprise', 'free')).toBe(true);
  });

  it('blocks access when current tier < required', () => {
    expect(tierAtLeast('free', 'pro')).toBe(false);
    expect(tierAtLeast('pro', 'pro_plus')).toBe(false);
    expect(tierAtLeast(null, 'free')).toBe(true);
    expect(tierAtLeast(null, 'pro')).toBe(false);
  });
});

describe('TIER_LABEL', () => {
  it('has a label for every tier', () => {
    const tiers: SubscriptionTier[] = [
      'free',
      'lite',
      'pro',
      'pro_plus',
      'quant_desk',
      'enterprise',
    ];
    for (const t of tiers) {
      expect(TIER_LABEL[t]).toBeTruthy();
    }
  });

  it('renders pro_plus as Pro+ (consumer-facing copy lock)', () => {
    expect(TIER_LABEL.pro_plus).toBe('Pro+');
  });
});
