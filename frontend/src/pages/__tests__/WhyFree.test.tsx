import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cleanup, screen, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '../../test/render';
import WhyFree from '../WhyFree';

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
  });

  it('renders without auth and shows key sections and stats strip', async () => {
    renderWithProviders(<WhyFree />, { route: '/why-free' });

    expect(
      screen.getByRole('heading', { name: /AxiomFolio is free because we want it to be/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /What's free, forever/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Why we use CSV instead of Plaid/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /When we'll charge/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /What we'll never do/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Built by a solo founder/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId('public-stats-strip')).toBeInTheDocument();
    });
  });

  it('links to sign in', () => {
    renderWithProviders(<WhyFree />, { route: '/why-free' });
    expect(screen.getByRole('link', { name: /^sign in$/i })).toHaveAttribute('href', '/login');
  });
});
