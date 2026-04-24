import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, screen, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '../../test/render';
import MarketTracked from '../MarketTracked';

vi.mock('../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({
    timezone: 'UTC',
    currency: 'USD',
    tableDensity: 'comfortable',
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

const mockGetSnapshotTable = vi.fn();

vi.mock('../../services/api', () => {
  const mockRows = [
    {
      symbol: 'NVDA',
      current_price: 100,
      perf_1d: 2,
      perf_5d: 4,
      perf_20d: 10,
      sector: 'Technology',
      stage_label: '2A',
      previous_stage_label: '1',
      rs_mansfield_pct: 5,
      range_pos_52w: 75,
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
      stage_label: '2B',
      previous_stage_label: '2A',
      rs_mansfield_pct: 4,
      range_pos_52w: 60,
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
      stage_label: '4',
      previous_stage_label: '3',
      rs_mansfield_pct: -3,
      range_pos_52w: 15,
      sma_50: 90,
      sma_200: 95,
      ema_21: 85,
      ema_8: 84,
      sma_21: 88,
    },
    {
      symbol: 'SPY',
      current_price: 500,
      perf_1d: 0.8,
      perf_5d: 1.2,
      perf_20d: 3.5,
      sector: 'ETF',
      stage_label: '2A',
      previous_stage_label: '2A',
      rs_mansfield_pct: 1,
      range_pos_52w: 85,
      sma_50: 495,
      sma_200: 460,
      ema_21: 497,
      ema_8: 501,
      sma_21: 498,
    },
  ];
  return {
    default: {
      get: vi.fn().mockResolvedValue({ data: {} }),
      patch: vi.fn().mockResolvedValue({ data: {} }),
    },
    marketDataApi: {
      getSnapshotTable: (...args: any[]) => mockGetSnapshotTable(...args),
      getSnapshotAggregates: vi.fn().mockResolvedValue({
        total: 4,
        stage_distribution: [],
        sector_summary: [],
        scan_tier_distribution: [],
        action_distribution: [],
      }),
    },
  };
});

describe('MarketTracked deep-link filters', () => {
  afterEach(() => {
    cleanup();
    mockGetSnapshotTable.mockReset();
  });

  function setupMock(rows = [{ symbol: 'AAA', current_price: 10, stage_label: '2A' }]) {
    mockGetSnapshotTable.mockResolvedValue({ rows, total: rows.length });
  }

  it('applies symbol deep-link via server-side symbols param', async () => {
    setupMock();
    renderWithProviders(<MarketTracked />, { route: '/market/tracked?symbols=NVDA,MSFT' });
    expect(await screen.findByText(/Market Tracked/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(mockGetSnapshotTable).toHaveBeenCalledWith(
        expect.objectContaining({ symbols: 'NVDA,MSFT' }),
      );
    });
  });

  it('applies action_labels deep-link from query params', async () => {
    setupMock();
    renderWithProviders(<MarketTracked />, { route: '/market/tracked?action_labels=BUY' });
    expect(await screen.findByText(/Market Tracked/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(mockGetSnapshotTable).toHaveBeenCalledWith(
        expect.objectContaining({ action_labels: 'BUY' }),
      );
    });
  });

  it('applies preset deep-link for pullback_buy_zone', async () => {
    setupMock();
    renderWithProviders(<MarketTracked />, { route: '/market/tracked?preset=pullback_buy_zone' });
    expect(await screen.findByText(/Market Tracked/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(mockGetSnapshotTable).toHaveBeenCalledWith(
        expect.objectContaining({ preset: 'pullback_buy_zone' }),
      );
    });
  });

  it('applies index_name deep-link for SP500', async () => {
    setupMock();
    renderWithProviders(<MarketTracked />, { route: '/market/tracked?index_name=SP500' });
    expect(await screen.findByText(/Market Tracked/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(mockGetSnapshotTable).toHaveBeenCalledWith(
        expect.objectContaining({ index_name: 'SP500' }),
      );
    });
  });

  it('applies filter_stage deep-link', async () => {
    setupMock();
    renderWithProviders(<MarketTracked />, { route: '/market/tracked?filter_stage=2A' });
    expect(await screen.findByText(/Market Tracked/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(mockGetSnapshotTable).toHaveBeenCalledWith(
        expect.objectContaining({ filter_stage: '2A' }),
      );
    });
  });

  it('applies scan mode with default scan_tiers', async () => {
    setupMock();
    renderWithProviders(<MarketTracked />, { route: '/market/tracked?mode=scan' });
    expect(await screen.findByText(/Market Tracked/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(mockGetSnapshotTable).toHaveBeenCalledWith(
        expect.objectContaining({ scan_tiers: expect.any(String) }),
      );
    });
  });
});
