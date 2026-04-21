import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cleanup, screen, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '../../test/render';
import WhyFree from '../WhyFree';
import api from '@/services/api';

vi.mock('@/services/api', () => ({
  __esModule: true,
  default: {
    get: vi.fn(),
  },
}));

vi.mock('@/components/transparency/PublicStatsStrip', () => ({
  __esModule: true,
  default: function MockPublicStatsStrip() {
    return (
      <div data-testid="public-stats-strip">
        <span>Portfolios tracked</span>
      </div>
    );
  },
}));

describe('WhyFree', () => {
  beforeEach(() => {
    cleanup();
    vi.mocked(api.get).mockResolvedValue({
      data: {
        currency: 'USD',
        features: [],
        tiers: [
          {
            tier: 'free',
            name: 'Free',
            tagline: 'Free',
            monthly_price_usd: '0',
            annual_price_usd: '0',
            covers_copy: 'No ads',
            cta_label: 'Get started',
            cta_route: '/register',
            is_contact_sales: false,
            features: [
              {
                key: 'data.cached_indicators',
                title: 'Cached indicators',
                description: 'Daily indicators',
                category: 'data',
                min_tier: 'free',
              },
            ],
            new_features: [],
          },
        ],
      },
    } as never);
  });

  it('renders catalog-driven free feature list and stats strip', async () => {
    renderWithProviders(<WhyFree />, { route: '/why-free' });

    expect(
      screen.getByRole('heading', { name: /AxiomFolio is free because we want it to be/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /What's free, forever/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Why we use CSV instead of Plaid/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /What we'll never do/i })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /Built by a solo founder/i })).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('Cached indicators')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByTestId('public-stats-strip')).toBeInTheDocument();
    });
  });

  it('links to sign in', () => {
    renderWithProviders(<WhyFree />, { route: '/why-free' });
    expect(screen.getByRole('link', { name: /^sign in$/i })).toHaveAttribute('href', '/login');
  });
});
