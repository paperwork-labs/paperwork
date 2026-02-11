import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import MarketDashboard from '../MarketDashboard';

vi.mock('../../services/api', () => {
  return {
    marketDataApi: {
      getDashboard: vi.fn().mockResolvedValue({
        tracked_count: 120,
        snapshot_count: 118,
        coverage: { status: 'healthy', daily_pct: 98.2, m5_pct: 73.1 },
        regime: { up_1d_count: 68, down_1d_count: 42 },
        leaders: [{ symbol: 'NVDA', momentum_score: 12.4, perf_20d: 18.2, rs_mansfield_pct: 6.1 }],
        setups: { breakout_candidates: [{ symbol: 'MSFT' }], pullback_candidates: [], rs_leaders: [] },
        sector_momentum: [{ sector: 'Technology' }],
        action_queue: [{ symbol: 'AAPL' }],
      }),
    },
  };
});

describe('MarketDashboard', () => {
  it('renders loading state before data is shown', () => {
    renderWithProviders(<MarketDashboard />, { route: '/' });
    expect(screen.getByText(/Loading market dashboard/i)).toBeInTheDocument();
  });
});
