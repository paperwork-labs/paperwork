import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import MarketTracked from '../MarketTracked';

const apiGet = vi.fn().mockResolvedValue({ data: { rows: [] } });

vi.mock('../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({
    currency: 'USD',
    timezone: 'UTC',
    tableDensity: 'comfortable',
    coverageHistogramWindowDays: 50,
  }),
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    user: { role: 'analyst' },
  }),
}));

vi.mock('../../services/api', () => {
  return {
    default: {
      get: (...args: any[]) => apiGet(...args),
    },
  };
});

describe('MarketTracked snapshot table', () => {
  beforeEach(() => apiGet.mockClear());

  it('loads and renders Level 1–4 columns', async () => {
    apiGet.mockResolvedValueOnce({
      data: {
        rows: [
          {
            symbol: 'AAA',
            analysis_timestamp: '2026-01-09T00:00:00Z',
            as_of_timestamp: '2026-01-09T00:00:00Z',
            current_price: 10,
            market_cap: 1_000_000_000,
            stage_label: '2B',
            current_stage_days: 7,
            previous_stage_label: '2A',
            previous_stage_days: 12,
            rs_mansfield_pct: 12.3,
            sma_50: 9.5,
            ema_8: 9.9,
            atr_14: 0.8,
            atrp_14: 8.0,
            atrx_sma_50: 0.7,
            range_pos_52w: 55.2,
          },
        ],
      },
    });

    renderWithProviders(<MarketTracked />, { route: '/market/tracked' });

    expect(await screen.findByText(/Market Tracked/i)).toBeTruthy();
    expect(await screen.findByText('AAA')).toBeTruthy();

    // Spot-check representative Level 1–4 headers
    expect(await screen.findByText('Stage')).toBeTruthy();
    expect(await screen.findByText('Time in Stage')).toBeTruthy();
    expect(await screen.findByText('Previous Stage')).toBeTruthy();
    expect(await screen.findByText('Time in Previous Stage')).toBeTruthy();
    expect(await screen.findByText('RS (Mansfield)')).toBeTruthy();
    expect(await screen.findByText('SMA 50')).toBeTruthy();
    expect(await screen.findByText('EMA 8')).toBeTruthy();
    expect(await screen.findByText('ATR 14')).toBeTruthy();
    expect(await screen.findByText('(P−SMA50)/ATR')).toBeTruthy();
    expect(await screen.findByText('Range 52w%')).toBeTruthy();
  });
});


