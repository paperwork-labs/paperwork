import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, screen } from '@testing-library/react';

import { renderWithProviders } from '../../test/render';
import MarketTracked from '../MarketTracked';

vi.mock('../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({
    timezone: 'UTC',
    currency: 'USD',
    tableDensity: 'comfortable',
  }),
}));

vi.mock('../../services/api', () => {
  return {
    default: {
      get: vi.fn().mockResolvedValue({
        data: {
          rows: [
            {
              symbol: 'NVDA',
              current_price: 100,
              perf_1d: 2,
              perf_5d: 4,
              perf_20d: 10,
              sector: 'Technology',
              sma_50: 90,
              sma_200: 80,
              ema_21: 95,
              ema_8: 102,
              sma_21: 96,
            },
            {
              symbol: 'MSFT',
              current_price: 90,
              perf_1d: 1,
              perf_5d: 2,
              perf_20d: 7,
              sector: 'Technology',
              sma_50: 85,
              sma_200: 84,
              ema_21: 86,
              ema_8: 91,
              sma_21: 87,
            },
            {
              symbol: 'XOM',
              current_price: 80,
              perf_1d: -1,
              perf_5d: -2,
              perf_20d: -5,
              sector: 'Energy',
              sma_50: 90,
              sma_200: 95,
              ema_21: 85,
              ema_8: 84,
              sma_21: 88,
            },
          ],
        },
      }),
    },
  };
});

describe('MarketTracked deep-link filters', () => {
  afterEach(() => cleanup());

  it('applies symbol deep-link filters from query params', async () => {
    renderWithProviders(<MarketTracked />, { route: '/market/tracked?symbols=NVDA,MSFT' });
    expect(await screen.findByText(/Market Tracked/i)).toBeInTheDocument();
    // SortableTable filter header shows filtered count.
    expect(await screen.findByText('2 of 3')).toBeInTheDocument();
  });

  it('applies preset deep-link filters from query params', async () => {
    renderWithProviders(<MarketTracked />, { route: '/market/tracked?preset=momentum' });
    expect(await screen.findByText(/Market Tracked/i)).toBeInTheDocument();
    // At least one row should remain under momentum rules in this fixture.
    expect(await screen.findByText('2 of 3')).toBeInTheDocument();
  });
});
