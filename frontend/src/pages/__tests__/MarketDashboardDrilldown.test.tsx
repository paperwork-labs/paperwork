import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { ChakraProvider } from '@chakra-ui/react';
import { MemoryRouter } from 'react-router-dom';

import { system } from '../../theme/system';
import MarketDashboard from '../MarketDashboard';

vi.mock('../../services/api', () => {
  return {
    marketDataApi: {
      getDashboard: vi.fn().mockResolvedValue({
        tracked_count: 120,
        snapshot_count: 118,
        entry_proximity_top: [
          { symbol: 'NVDA', entry_price: 100, distance_pct: 1.2, distance_atr: 0.6 },
          { symbol: 'MSFT', entry_price: 420, distance_pct: 1.9, distance_atr: 1.1 },
        ],
        exit_proximity_top: [{ symbol: 'AAPL', exit_price: 250, distance_pct: 3.2, distance_atr: 1.5 }],
        sector_etf_table: [{ symbol: 'XLK', sector_name: 'Technology', change_1d: 0.9, stage_label: '2A', days_in_stage: 3 }],
        entering_stage_2a: [{ symbol: 'META', previous_stage_label: '1' }],
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

const renderPage = () =>
  render(
    <ChakraProvider value={system}>
      <MemoryRouter initialEntries={['/']}>
        <MarketDashboard />
      </MemoryRouter>
    </ChakraProvider>,
  );

describe('MarketDashboard rebuilt sections', () => {
  afterEach(() => cleanup());

  it('renders entry and exit proximity tables', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText(/Top 10 Closest to Entry/i)).toBeInTheDocument());
    expect(screen.getByText(/Top 10 Closest to Exit/i)).toBeInTheDocument();
    expect(screen.getAllByText(/NVDA/).length).toBeGreaterThan(0);
  });

  it('renders top and bottom metric matrices', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText(/Top 10 Matrix/i)).toBeInTheDocument());
    expect(screen.getByText(/Bottom 10 Matrix/i)).toBeInTheDocument();
  });
});
