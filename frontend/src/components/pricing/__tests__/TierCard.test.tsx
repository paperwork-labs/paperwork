import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import { TierCard } from '@/components/pricing/TierCard';
import type { PricingTier } from '@/types/pricing';

const baseTier: PricingTier = {
  tier: 'pro',
  name: 'Pro',
  tagline: 'Signals and BYOK',
  monthly_price_usd: '29',
  annual_price_usd: '290',
  covers_copy: 'Covers core compute',
  cta_label: 'Upgrade',
  cta_route: null,
  is_contact_sales: false,
  features: [
    {
      key: 'mcp.read_signals',
      title: 'Signals',
      description: 'Read signals',
      category: 'mcp',
      min_tier: 'pro',
    },
  ],
  new_features: [
    {
      key: 'mcp.read_signals',
      title: 'Signals',
      description: 'Read signals',
      category: 'mcp',
      min_tier: 'pro',
    },
  ],
};

describe('TierCard variants', () => {
  it('renders featured variant', () => {
    render(<TierCard tier={baseTier} variant="featured" currency="USD" />);
    expect(screen.getByText('Most popular')).toBeInTheDocument();
    expect(screen.getByText('Pro')).toBeInTheDocument();
  });

  it('renders compact variant', () => {
    render(<TierCard tier={baseTier} variant="compact" currency="USD" />);
    expect(screen.getByText('Signals')).toBeInTheDocument();
  });

  it('renders enterprise variant as custom', () => {
    render(
      <TierCard
        tier={{ ...baseTier, tier: 'enterprise', name: 'Enterprise', monthly_price_usd: null }}
        variant="enterprise"
        currency="USD"
      />,
    );
    expect(screen.getByText('Custom')).toBeInTheDocument();
  });
});
