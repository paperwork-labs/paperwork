import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@/test/testing-library';
import { renderWithProviders } from '../../test/render';
import MarketTracked from '../MarketTracked';

const apiGet = vi.fn().mockResolvedValue({ data: { rows: [] } });
const mockGetSnapshotTable = vi.fn().mockResolvedValue({ rows: [], total: 0 });

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

vi.mock('../../hooks/usePortfolioSymbols', () => ({
  usePortfolioSymbols: () => ({ data: {}, isLoading: false }),
}));

vi.mock('../../services/api', () => {
  return {
    default: {
      get: (...args: any[]) => apiGet(...args),
    },
    marketDataApi: {
      getSnapshotTable: (...args: any[]) => mockGetSnapshotTable(...args),
      getSnapshotAggregates: vi.fn().mockResolvedValue({
        total: 0,
        stage_distribution: [],
        sector_summary: [],
        scan_tier_distribution: [],
        action_distribution: [],
      }),
    },
  };
});

describe('MarketTracked snapshot table', () => {
  beforeEach(() => {
    apiGet.mockClear();
    mockGetSnapshotTable.mockClear();
  });

  it('loads and renders default overview-profile columns', async () => {
    mockGetSnapshotTable.mockResolvedValueOnce({
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
      total: 1,
    });

    renderWithProviders(<MarketTracked />, { route: '/market/tracked' });

    expect(await screen.findByText(/Market Tracked/i)).toBeTruthy();
    expect(await screen.findByText('AAA')).toBeTruthy();

    // Columns visible in the default "Overview" profile:
    // symbol, name, current_price, stage_label, current_stage_days,
    // perf_1d, rs_mansfield_pct, sector, scan_tier, action_label
    expect((await screen.findAllByText('Stage')).length).toBeGreaterThanOrEqual(1);
    expect(await screen.findByText('Time in Stage')).toBeTruthy();
    expect(await screen.findByText('RS (Mansfield)')).toBeTruthy();
  });
});
