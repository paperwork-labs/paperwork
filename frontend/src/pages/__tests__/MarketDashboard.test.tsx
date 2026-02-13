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
        entry_proximity_top: [{ symbol: 'NVDA', entry_price: 100, distance_pct: 1.2, distance_atr: 0.6 }],
        exit_proximity_top: [{ symbol: 'MSFT', exit_price: 420, distance_pct: 2.1, distance_atr: 0.9 }],
        sector_etf_table: [{ symbol: 'XLK', sector_name: 'Technology', change_1d: 0.9, stage_label: '2A', days_in_stage: 3 }],
        entering_stage_2a: [{ symbol: 'AAPL', previous_stage_label: '1' }],
        regime: { stage_counts_normalized: { '1': 10, '2A': 5, '2B': 3, '2C': 2, '3': 1, '4': 1 } },
        top10_matrix: {
          perf_1d: [{ symbol: 'NVDA', value: 2.3 }],
          perf_5d: [{ symbol: 'NVDA', value: 4.4 }],
          perf_20d: [{ symbol: 'NVDA', value: 12.1 }],
          atrx_sma_21: [{ symbol: 'NVDA', value: 1.2 }],
          atrx_sma_50: [{ symbol: 'NVDA', value: 2.2 }],
          atrx_sma_200: [{ symbol: 'NVDA', value: 3.1 }],
        },
        bottom10_matrix: {
          perf_1d: [{ symbol: 'XOM', value: -1.3 }],
          perf_5d: [{ symbol: 'XOM', value: -2.4 }],
          perf_20d: [{ symbol: 'XOM', value: -7.1 }],
          atrx_sma_21: [{ symbol: 'XOM', value: -1.2 }],
          atrx_sma_50: [{ symbol: 'XOM', value: -2.2 }],
          atrx_sma_200: [{ symbol: 'XOM', value: -3.1 }],
        },
      }),
    },
  };
});

describe('MarketDashboard', () => {
  it('renders loading state before data is shown', () => {
    renderWithProviders(<MarketDashboard />, { route: '/' });
    expect(screen.getByText(/Loading market dashboard/i)).toBeInTheDocument();
  });

  it('marks repeated symbols across matrix columns', async () => {
    renderWithProviders(<MarketDashboard />, { route: '/' });

    const repeatedTop = await screen.findAllByTestId('repeat-text-top-10-matrix');
    const repeatedBottom = await screen.findAllByTestId('repeat-text-bottom-10-matrix');

    expect(repeatedTop.length).toBeGreaterThan(1);
    expect(repeatedBottom.length).toBeGreaterThan(1);
  });
});
